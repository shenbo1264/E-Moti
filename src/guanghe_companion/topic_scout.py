from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .capability_settings import WebSearchSettings
from .web_search import WebSearchService

MAX_TOPIC_QUERY_LENGTH = 100
MAX_TOPIC_CARDS = 3
MAX_TOPIC_TITLE_LENGTH = 80
MAX_TOPIC_SUMMARY_LENGTH = 180
MAX_TOPIC_TIMESTAMP_LENGTH = 40
MAX_TOPIC_OPENING_LINE_LENGTH = 120


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
        _append_part(parts, interest)
    _append_part(parts, context.get("perception_summary"))
    for entry in _safe_iter(context.get("recent_dialogue")):
        if isinstance(entry, Mapping):
            _append_part(parts, entry.get("text"))
    for entry in _safe_iter(context.get("long_term_memory")):
        if isinstance(entry, Mapping):
            _append_part(parts, entry.get("summary"))
    return _short_text(" ".join(parts), MAX_TOPIC_QUERY_LENGTH)


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


def _append_part(parts: list[str], value: object) -> None:
    cleaned = _short_text(value, MAX_TOPIC_QUERY_LENGTH)
    if cleaned:
        parts.append(cleaned)


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
