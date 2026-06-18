from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from .character_pack import CharacterPack
from .models import CompanionState
from .relationship import RelationshipService

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
            merged["perception_summary"] = _sanitize_context_string(
                " ".join(perception_summaries),
                MAX_PERCEPTION_SUMMARY_LENGTH,
            )
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
        summary = _sanitize_perception_summary(self.summary)
        return {"perception_summary": summary[:MAX_PERCEPTION_SUMMARY_LENGTH]} if summary else {}


@dataclass(frozen=True, slots=True)
class RuntimeExpressionContextService:
    state: CompanionState
    relationship_decorations: Iterable[Mapping[str, str]] | None = None
    external_provider: ExpressionContextProvider | None = None
    perception_summary: str = ""
    tool_results: Iterable[Mapping[str, object]] | None = None

    def __call__(self) -> dict[str, object]:
        if self.external_provider is not None:
            try:
                external_context = self.external_provider()
            except Exception:
                external_context = {}
        else:
            external_context = {}

        context: dict[str, object] = {}
        if isinstance(external_context, dict):
            for key in ("perception_summary", "tool_results"):
                if key in external_context:
                    context[key] = external_context[key]

        runtime_context = ExpressionContextChain([self._runtime_context])()
        if runtime_context:
            context.update(runtime_context)
        relationship_result = self._relationship_presentation_tool_result()
        if relationship_result is None:
            return context

        existing_tool_results = context.get("tool_results")
        tool_results = existing_tool_results if isinstance(existing_tool_results, list) else []
        return {**context, "tool_results": [*tool_results, relationship_result]}

    def _runtime_context(self) -> dict[str, object]:
        context: dict[str, object] = {}
        if self.perception_summary:
            context["perception_summary"] = self.perception_summary
        if self.tool_results:
            context["tool_results"] = list(self.tool_results)
        return context

    def _relationship_presentation_tool_result(self) -> dict[str, str] | None:
        presentation = RelationshipService(self.state).presentation(self.relationship_decorations)
        if (
            not getattr(self.state, "player_alias", "")
            and not presentation.unlocked_decorations
            and self.state.trust < 20
        ):
            return None
        badges = " / ".join(badge["label"] for badge in presentation.unlocked_decorations) or "none"
        return {
            "source": "local_relationship_presentation",
            "title": "relationship presentation",
            "summary": (
                f"{presentation.address_line}；语气：{presentation.tone_label}；"
                f"小动作：{presentation.micro_motion}；装饰：{badges}"
            ),
        }


def _sanitize_perception_summary(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return _replace_control_characters(value.strip())[:MAX_PERCEPTION_SUMMARY_LENGTH]


def _sanitize_tool_result(entry: object) -> dict[str, str] | None:
    if not isinstance(entry, dict):
        return None
    source = entry.get("source")
    title = entry.get("title")
    summary = entry.get("summary")
    if not isinstance(source, str) or not isinstance(title, str) or not isinstance(summary, str):
        return None
    result = {
        "source": _sanitize_context_string(source, MAX_TOOL_SOURCE_LENGTH),
        "title": _sanitize_context_string(title, MAX_TOOL_TITLE_LENGTH),
        "summary": _sanitize_context_string(summary, MAX_TOOL_SUMMARY_LENGTH),
    }
    if not result["source"] or not result["title"] or not result["summary"]:
        return None
    timestamp = entry.get("timestamp")
    if isinstance(timestamp, str) and timestamp.strip():
        result["timestamp"] = _sanitize_context_string(timestamp, MAX_TOOL_TIMESTAMP_LENGTH)
    return result


def _sanitize_context_string(value: str, max_length: int) -> str:
    return _replace_control_characters(value.strip())[:max_length]


def _replace_control_characters(value: str) -> str:
    return "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value)


@dataclass(frozen=True, slots=True)
class MockSearchExpressionContextProvider:
    query: str
    results: Iterable[Mapping[str, object]]

    def __call__(self) -> dict[str, object]:
        if not isinstance(self.query, str):
            return {}
        query = _sanitize_context_string(self.query, MAX_SEARCH_QUERY_LENGTH)
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
            title = _sanitize_context_string(title, MAX_TOOL_TITLE_LENGTH)
            summary = _sanitize_context_string(summary, MAX_TOOL_SUMMARY_LENGTH)
            timestamp = _sanitize_context_string(timestamp, MAX_TOOL_TIMESTAMP_LENGTH)
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
