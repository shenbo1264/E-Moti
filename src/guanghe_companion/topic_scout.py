from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .capability_settings import WebSearchSettings
from .web_search import WebSearchService

MAX_TOPIC_QUERY_LENGTH = 100
MAX_TOPIC_SOURCE_LENGTH = 240
MAX_TOPIC_CARDS = 3
MAX_TOPIC_TITLE_LENGTH = 80
MAX_TOPIC_SUMMARY_LENGTH = 180
MAX_TOPIC_TIMESTAMP_LENGTH = 40
MAX_TOPIC_OPENING_LINE_LENGTH = 120
TOPIC_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+#.-]{1,}")
TOPIC_PHRASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("AI companion", ("ai companion", "ai companions", "ai伴侣", "ai 陪伴", "人工智能伴侣")),
    ("desktop pet", ("desktop pet", "virtual pet", "桌宠", "电子宠物")),
    ("联网搜索", ("web search", "online search", "联网搜索", "网页搜索", "上网搜索", "找信息")),
    ("主动聊天", ("proactive chat", "proactive topic", "proactive web search", "主动聊天", "主动找话题", "主动陪伴", "主动打扰")),
    ("屏幕观察", ("screen observation", "screen-aware", "screen aware", "看屏幕", "屏幕观察", "根据屏幕")),
    ("pixel art", ("pixel pet", "pixel art", "pixel", "像素")),
    ("blink animation", ("blink", "blinking", "眨眼")),
    ("breathing animation", ("breathing", "呼吸感", "呼吸动画")),
    ("TTS", ("tts", "text to speech", "语音合成", "角色语音")),
    ("ASR", ("asr", "speech recognition", "语音识别")),
)
TOPIC_STOP_WORDS = {
    "a",
    "about",
    "ai",
    "and",
    "an",
    "are",
    "browser",
    "chrome",
    "code",
    "companion",
    "companions",
    "desktop",
    "editing",
    "emoti",
    "e-moti",
    "file",
    "frames",
    "for",
    "github",
    "ide",
    "ideas",
    "is",
    "likes",
    "player",
    "powershell",
    "project",
    "researching",
    "search",
    "screen",
    "shows",
    "tab",
    "the",
    "to",
    "user",
    "virtual",
    "vscode",
    "vs",
    "want",
    "window",
    "with",
    "pet",
    "proactive",
    "web",
}


@dataclass(frozen=True, slots=True)
class TopicScoutResult:
    ok: bool
    reason: str
    query: str
    cards: list[dict[str, str]]


class TopicScout:
    def __init__(self, search_service: WebSearchService | object | None = None) -> None:
        self.search_service = search_service or WebSearchService()

    def scout(
        self,
        *,
        context: Mapping[str, object],
        settings: WebSearchSettings,
        interests: Iterable[object] = (),
    ) -> TopicScoutResult:
        query = build_topic_search_query(context=context, interests=interests)
        if not query:
            return TopicScoutResult(False, "empty_query", "", [])
        result = self.search_service.search(query, settings)  # type: ignore[attr-defined]
        if not result.ok:
            return TopicScoutResult(False, "search_failed", query, [])
        cards = _topic_cards_from_tool_results(result.tool_results)
        return TopicScoutResult(bool(cards), "" if cards else "empty_results", query, cards)


def build_topic_search_query(*, context: Mapping[str, object], interests: Iterable[object] = ()) -> str:
    parts: list[str] = []
    for interest in _safe_iter(interests):
        _append_topic_terms(parts, interest)
    _append_topic_terms(parts, context.get("perception_summary"))
    for entry in _safe_iter(context.get("recent_dialogue")):
        if isinstance(entry, Mapping):
            _append_topic_terms(parts, entry.get("text"))
    for entry in _safe_iter(context.get("long_term_memory")):
        if isinstance(entry, Mapping):
            _append_topic_terms(parts, entry.get("summary"))
    return _bounded_join(parts, MAX_TOPIC_QUERY_LENGTH)


def _topic_cards_from_tool_results(tool_results: Iterable[Mapping[str, object]]) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for entry in _safe_iter(tool_results):
        if not isinstance(entry, Mapping):
            continue
        title = _short_text(entry.get("title"), MAX_TOPIC_TITLE_LENGTH)
        summary = _short_text(entry.get("summary"), MAX_TOPIC_SUMMARY_LENGTH)
        if not title or not summary:
            continue
        card = {
            "source": "web_search",
            "title": title,
            "summary": summary,
        }
        timestamp = _short_text(entry.get("timestamp"), MAX_TOPIC_TIMESTAMP_LENGTH)
        if timestamp:
            card["timestamp"] = timestamp
        card["opening_line"] = _short_text(
            f"我刚看到一个关于 {title} 的小话题，要听听吗？",
            MAX_TOPIC_OPENING_LINE_LENGTH,
        )
        cards.append(card)
        if len(cards) >= MAX_TOPIC_CARDS:
            break
    return cards


def _append_topic_terms(parts: list[str], value: object) -> None:
    for term in _topic_terms(value):
        if term.lower() in {part.lower() for part in parts}:
            continue
        parts.append(term)


def _topic_terms(value: object) -> list[str]:
    text = _short_text(value, MAX_TOPIC_SOURCE_LENGTH)
    if not text:
        return []
    lower_text = text.lower()
    terms: list[str] = []
    local_skip_words: set[str] = set()
    for canonical, aliases in TOPIC_PHRASES:
        if any(alias.lower() in lower_text for alias in aliases):
            terms.append(canonical)
            local_skip_words.update(word.lower() for word in canonical.split())

    for match in TOPIC_TOKEN_PATTERN.finditer(text):
        token = match.group(0).strip(".-").lower()
        if not token or token in TOPIC_STOP_WORDS or token in local_skip_words:
            continue
        if len(token) < 3 and token not in {"ai"}:
            continue
        if token not in {term.lower() for term in terms}:
            terms.append(token)
        if len(terms) >= 6:
            break
    return terms


def _bounded_join(parts: Iterable[str], max_length: int) -> str:
    result = ""
    for part in parts:
        candidate = part if not result else f"{result} {part}"
        if len(candidate) > max_length:
            break
        result = candidate
    return result


def _safe_iter(value: object) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)):
        return ()
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError:
        return ()


def _short_text(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value.strip())[:max_length]
