from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from .capability_settings import WebSearchSettings
from .character_session import is_safe_character_id
from .expression_context import _sanitize_context_string
from .web_search import WebSearchService

BriefClient = Callable[[str], str]
MAX_SOURCE_NOTES = 5
MAX_BRIEF_LIST_ITEMS = 8


class FanworkPolicy(StrEnum):
    ORIGINAL_INSPIRATION = "original_inspiration"
    LOCAL_FANWORK = "local_fanwork"


@dataclass(frozen=True, slots=True)
class CharacterInspirationResult:
    ok: bool
    message: str
    policy: FanworkPolicy
    source_notes: tuple[dict[str, str], ...]
    brief: dict[str, object]
    requires_user_authorization: bool = False


class CharacterInspirationService:
    def __init__(
        self,
        *,
        search_service: WebSearchService | None = None,
        settings: WebSearchSettings | None = None,
        brief_client: BriefClient | None = None,
    ) -> None:
        self.search_service = search_service or WebSearchService()
        self.settings = settings or WebSearchSettings(enabled=False)
        self.brief_client = brief_client

    def build_original_inspiration(self, query: str) -> CharacterInspirationResult:
        sanitized_query = _sanitize_context_string(str(query), 80)
        if not sanitized_query:
            return CharacterInspirationResult(
                ok=False,
                message="搜索词为空",
                policy=FanworkPolicy.ORIGINAL_INSPIRATION,
                source_notes=(),
                brief={},
            )
        search_result = self.search_service.search(
            f"{sanitized_query} character personality visual traits",
            self.settings,
        )
        if not search_result.ok:
            return CharacterInspirationResult(
                ok=False,
                message=search_result.message,
                policy=FanworkPolicy.ORIGINAL_INSPIRATION,
                source_notes=(),
                brief={},
            )
        source_notes = tuple(_source_note_from_tool_result(entry) for entry in search_result.tool_results)
        prompt = _build_brief_prompt(sanitized_query, source_notes)
        brief = _fallback_brief(sanitized_query, source_notes)
        if self.brief_client is not None:
            try:
                brief = _parse_brief(self.brief_client(prompt), fallback=brief)
            except Exception:
                brief = _fallback_brief(sanitized_query, source_notes)
        brief = _sanitize_brief(brief, blocked_terms=_blocked_terms(sanitized_query))
        return CharacterInspirationResult(
            ok=True,
            message="已生成原创灵感 brief，来源仅用于抽象特征。",
            policy=FanworkPolicy.ORIGINAL_INSPIRATION,
            source_notes=source_notes,
            brief=brief,
        )

    def describe_local_fanwork_policy(self, source_character: str) -> CharacterInspirationResult:
        sanitized = _sanitize_context_string(str(source_character), 80) or "指定角色"
        return CharacterInspirationResult(
            ok=True,
            message=(
                f"{sanitized} 可作为本地二创包由用户自行导入；开源仓库不内置、"
                "不下载、不分发受版权保护素材或专有设定。"
            ),
            policy=FanworkPolicy.LOCAL_FANWORK,
            source_notes=(),
            brief={},
            requires_user_authorization=True,
        )


def _source_note_from_tool_result(entry: dict[str, str]) -> dict[str, str]:
    note = {
        "title": _sanitize_context_string(entry.get("title", ""), 80),
        "summary": _sanitize_context_string(entry.get("summary", ""), 180),
        "source": _sanitize_context_string(entry.get("source", ""), 60),
    }
    url = _sanitize_context_string(entry.get("url", ""), 240)
    if url:
        note["url"] = url
    timestamp = _sanitize_context_string(entry.get("timestamp", ""), 25)
    if timestamp:
        note["timestamp"] = timestamp
    return note


def _build_brief_prompt(query: str, source_notes: tuple[dict[str, str], ...]) -> str:
    notes = "\n".join(
        f"- {note['title']}: {note['summary']} ({note.get('url', 'no url')})"
        for note in source_notes[:MAX_SOURCE_NOTES]
    )
    return (
        "你在为开源桌面 AI 伴侣生成原创角色 brief。\n"
        f"来源角色/主题：{query}\n"
        "只抽象特征，不要复制角色名、发型、服装、标志物、经典台词、专有背景或受保护设定。\n"
        "输出 JSON object，字段：character_id, name, title, description, "
        "visual_keywords, personality_keywords, boundaries。\n"
        "来源：\n"
        f"{notes}"
    )


def _parse_brief(raw: str, *, fallback: dict[str, object]) -> dict[str, object]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return fallback
    return payload


def _sanitize_brief(brief: dict[str, object], *, blocked_terms: tuple[str, ...]) -> dict[str, object]:
    character_id = _safe_character_id(brief.get("character_id"))
    name = _clean_brief_text(brief.get("name"), 32, blocked_terms=blocked_terms)
    title = _clean_brief_text(brief.get("title"), 40, blocked_terms=blocked_terms)
    description = _clean_brief_text(brief.get("description"), 180, blocked_terms=blocked_terms)
    if not name:
        name = "原创桌面同伴"
    if not title:
        title = "原创桌面同伴"
    if not description:
        description = "一个由抽象灵感生成的原创桌面伴侣。"
    return {
        "character_id": character_id,
        "name": name,
        "title": title,
        "description": description,
        "visual_keywords": _clean_brief_list(brief.get("visual_keywords"), blocked_terms=blocked_terms),
        "personality_keywords": _clean_brief_list(brief.get("personality_keywords"), blocked_terms=blocked_terms),
        "boundaries": _clean_brief_list(brief.get("boundaries"), blocked_terms=()),
    }


def _fallback_brief(query: str, source_notes: tuple[dict[str, str], ...]) -> dict[str, object]:
    words = " ".join(note["summary"] for note in source_notes[:2])
    return {
        "character_id": _safe_character_id(_slug_from_text(query)),
        "name": "原创桌面同伴",
        "title": "抽象灵感同伴",
        "description": "一个由公开来源抽象气质生成的原创桌面伴侣。",
        "visual_keywords": _keyword_candidates(words, limit=4),
        "personality_keywords": ["稳定", "亲近", "低打扰"],
        "boundaries": ["不复制来源角色名、立绘、台词或专有设定"],
    }


def _clean_brief_list(value: object, *, blocked_terms: tuple[str, ...]) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = _clean_brief_text(item, 40, blocked_terms=blocked_terms)
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= MAX_BRIEF_LIST_ITEMS:
            break
    return cleaned


def _clean_brief_text(value: object, max_length: int, *, blocked_terms: tuple[str, ...]) -> str:
    if not isinstance(value, str):
        return ""
    text = _sanitize_context_string(value, max_length)
    for term in blocked_terms:
        if term and term.lower() in text.lower():
            return ""
    return text


def _blocked_terms(query: str) -> tuple[str, ...]:
    terms = [query]
    terms.extend(part for part in re.split(r"\s+", query.strip()) if len(part) >= 3)
    return tuple(dict.fromkeys(terms))


def _safe_character_id(value: object) -> str:
    if isinstance(value, str) and is_safe_character_id(value):
        return value
    return "original_inspiration"


def _slug_from_text(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    return slug or "original_inspiration"


def _keyword_candidates(value: str, *, limit: int) -> list[str]:
    words = [
        word
        for word in re.split(r"[\s,.;:，。；：、]+", value)
        if 2 <= len(word) <= 16
    ]
    return list(dict.fromkeys(words))[:limit]
