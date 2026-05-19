from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from .character_pack import CharacterPack

ExpressionContextProvider = Callable[[], dict[str, object]]
MAX_MOCK_SEARCH_RESULTS = 3


@dataclass(frozen=True, slots=True)
class ExpressionContextChain:
    providers: Iterable[ExpressionContextProvider]

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
            if isinstance(perception_summary, str) and perception_summary.strip():
                perception_summaries.append(perception_summary.strip())
            context_tool_results = context.get("tool_results")
            if isinstance(context_tool_results, list):
                tool_results.extend(entry for entry in context_tool_results if isinstance(entry, dict))

        merged: dict[str, object] = {}
        if perception_summaries:
            merged["perception_summary"] = "\n".join(perception_summaries)
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
class MockSearchExpressionContextProvider:
    query: str
    results: Iterable[Mapping[str, object]]

    def __call__(self) -> dict[str, object]:
        query = self.query.strip()
        if not query:
            return {}

        tool_results: list[dict[str, str]] = []
        for result in self.results:
            title = result.get("title")
            summary = result.get("summary")
            timestamp = result.get("timestamp")
            if not isinstance(title, str) or not isinstance(summary, str) or not isinstance(timestamp, str):
                continue
            title = title.strip()
            summary = summary.strip()
            timestamp = timestamp.strip()
            if not title or not summary or not timestamp:
                continue
            tool_results.append(
                {
                    "source": "mock_search",
                    "title": f"{query}: {title}",
                    "summary": summary,
                    "timestamp": timestamp,
                }
            )
            if len(tool_results) >= MAX_MOCK_SEARCH_RESULTS:
                break

        return {"tool_results": tool_results} if tool_results else {}
