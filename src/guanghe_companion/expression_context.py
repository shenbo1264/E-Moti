from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .character_pack import CharacterPack

ExpressionContextProvider = Callable[[], dict[str, object]]


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
