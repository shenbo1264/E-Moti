from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from .character_pack import CharacterPack

ExpressionContextProvider = Callable[[], dict[str, object]]
MAX_MOCK_SEARCH_RESULTS = 3
MAX_PERCEPTION_SUMMARY_LENGTH = 240
MAX_SEARCH_QUERY_LENGTH = 40
MAX_TOOL_SOURCE_LENGTH = 60
MAX_TOOL_TITLE_LENGTH = 80
MAX_TOOL_SUMMARY_LENGTH = 180
MAX_TOOL_TIMESTAMP_LENGTH = 25


@dataclass(frozen=True, slots=True)
class ExpressionContextChain:
    providers: Iterable[ExpressionContextProvider]

    def __post_init__(self) -> None:
        object.__setattr__(self, "providers", tuple(self.providers))

    def __call__(self) -> dict[str, object]:
        perception_summaries: list[str] = []
        tool_results: list[dict[str, object]] = []
        for provider in self.providers:
            try:
                context = provider()
            except Exception:
                continue
            if not isinstance(context, dict):
                continue
            perception_summary = context.get("perception_summary")
            sanitized_perception = _sanitize_perception_summary(perception_summary)
            if sanitized_perception:
                perception_summaries.append(sanitized_perception)
            context_tool_results = context.get("tool_results")
            if isinstance(context_tool_results, list):
                for entry in context_tool_results:
                    if len(tool_results) >= MAX_MOCK_SEARCH_RESULTS:
                        break
                    sanitized = _sanitize_tool_result(entry)
                    if sanitized is None:
                        continue
                    tool_results.append(sanitized)

        merged: dict[str, object] = {}
        if perception_summaries:
            merged["perception_summary"] = "\n".join(perception_summaries)[:MAX_PERCEPTION_SUMMARY_LENGTH]
        if tool_results:
            merged["tool_results"] = tool_results
        return merged


@dataclass(frozen=True, slots=True)
class CharacterProfileExpressionContextProvider:
    character_pack: CharacterPack

    def __call__(self) -> dict[str, object]:
        return {
            "tool_results": [
                {
                    "source": "local_character_pack",
                    "title": f"{self.character_pack.name} | {self.character_pack.title}",
                    "summary": self.character_pack.description,
                },
                {
                    "source": "local_character_pack",
                    "title": "modes",
                    "summary": self._mode_summary(),
                },
            ]
        }

    def _mode_summary(self) -> str:
        parts = [
            f"{mode}: {self.character_pack.mode_descriptions[mode]}"
            for mode in self.character_pack.modes[:3]
            if mode in self.character_pack.mode_descriptions
        ]
        return " / ".join(parts)


@dataclass(frozen=True, slots=True)
class ManualPerceptionExpressionContextProvider:
    summary: str = ""
    enabled: bool = False

    def __call__(self) -> dict[str, object]:
        if not self.enabled:
            return {}
        if not isinstance(self.summary, str):
            return {}
        summary = self.summary.strip()
        return {"perception_summary": summary[:MAX_PERCEPTION_SUMMARY_LENGTH]} if summary else {}


def _sanitize_perception_summary(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:MAX_PERCEPTION_SUMMARY_LENGTH]


def _sanitize_tool_result(entry: object) -> dict[str, str] | None:
    if not isinstance(entry, dict):
        return None
    source = entry.get("source")
    title = entry.get("title")
    summary = entry.get("summary")
    if not isinstance(source, str) or not isinstance(title, str) or not isinstance(summary, str):
        return None
    result = {
        "source": source.strip()[:MAX_TOOL_SOURCE_LENGTH],
        "title": title.strip()[:MAX_TOOL_TITLE_LENGTH],
        "summary": summary.strip()[:MAX_TOOL_SUMMARY_LENGTH],
    }
    if not result["source"] or not result["title"] or not result["summary"]:
        return None
    timestamp = entry.get("timestamp")
    if isinstance(timestamp, str) and timestamp.strip():
        result["timestamp"] = timestamp.strip()[:MAX_TOOL_TIMESTAMP_LENGTH]
    return result


@dataclass(frozen=True, slots=True)
class MockSearchExpressionContextProvider:
    query: str
    results: Iterable[Mapping[str, object]]

    def __call__(self) -> dict[str, object]:
        if not isinstance(self.query, str):
            return {}
        query = self.query.strip()[:MAX_SEARCH_QUERY_LENGTH]
        if not query:
            return {}
        if not isinstance(self.results, Iterable):
            return {}

        tool_results: list[dict[str, str]] = []
        for result in self.results:
            if not isinstance(result, Mapping):
                continue
            title = result.get("title")
            summary = result.get("summary")
            timestamp = result.get("timestamp")
            if not isinstance(title, str) or not isinstance(summary, str) or not isinstance(timestamp, str):
                continue
            title = title.strip()[:MAX_TOOL_TITLE_LENGTH]
            summary = summary.strip()[:MAX_TOOL_SUMMARY_LENGTH]
            timestamp = timestamp.strip()[:MAX_TOOL_TIMESTAMP_LENGTH]
            if not title or not summary or not timestamp:
                continue
            combined_title = f"{query}: {title}"[:MAX_TOOL_TITLE_LENGTH]
            tool_results.append(
                {
                    "source": "mock_search",
                    "title": combined_title,
                    "summary": summary,
                    "timestamp": timestamp,
                }
            )
            if len(tool_results) >= MAX_MOCK_SEARCH_RESULTS:
                break

        return {"tool_results": tool_results} if tool_results else {}
