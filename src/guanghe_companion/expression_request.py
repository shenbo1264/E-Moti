from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from .memory import MAX_LONG_TERM_MEMORY_SUMMARIES
from .snapshot import CompanionSnapshot

MAX_PERCEPTION_SUMMARY_LENGTH = 240
MAX_TOOL_RESULTS = 3
MAX_ACTION_LABEL_LENGTH = 40
MAX_RECENT_MEMORY = 3
MAX_CHARACTER_NAME_LENGTH = 40
MAX_MODE_LENGTH = 40
MAX_MOTION_LENGTH = 40
MAX_FEEDBACK_LENGTH = 160
MAX_DELTA_TEXT_LENGTH = 80
MAX_GOAL_LENGTH = 160
MAX_MEMORY_KIND_LENGTH = 40
MAX_MEMORY_SUMMARY_LENGTH = 160
MAX_MEMORY_MOTION_LENGTH = 40
MAX_LONG_TERM_MEMORY_CATEGORY_LENGTH = 40
MAX_LONG_TERM_MEMORY_SOURCE_LENGTH = 40
MAX_TOOL_TIMESTAMP_LENGTH = 40


@dataclass(frozen=True, slots=True)
class ExpressionRequest:
    character_name: str
    mode: str
    motion: str
    focus: float
    charge: float
    stability: float
    mood: float
    trust: float
    feedback: str
    delta_text: str
    goal: str
    actions: tuple[dict[str, str], ...]
    recent_memory: tuple[dict[str, str], ...]
    long_term_memory: tuple[dict[str, str], ...] = ()
    perception_summary: str = ""
    tool_results: tuple[dict[str, str], ...] = ()

    @classmethod
    def from_snapshot(
        cls,
        snapshot: dict[str, object] | CompanionSnapshot,
        context: Mapping[str, object] | None = None,
    ) -> "ExpressionRequest":
        source = _expression_payload_from_snapshot(snapshot)
        context_payload = _expression_payload_from_context(context)
        if context_payload:
            source = {**source, **context_payload}
        actions = _sanitize_actions(source.get("actions", []))
        recent_memory = _sanitize_recent_memory(source.get("memory_log", []))
        long_term_memory = _sanitize_long_term_memory(source.get("long_term_memory", []))
        return cls(
            character_name=_short_string(source.get("character_name", ""), MAX_CHARACTER_NAME_LENGTH),
            mode=_short_string(source.get("mode", ""), MAX_MODE_LENGTH),
            motion=_short_string(source.get("motion", source.get("current_motion", "")), MAX_MOTION_LENGTH),
            focus=_finite_float(source["focus"]),
            charge=_finite_float(source["charge"]),
            stability=_finite_float(source["stability"]),
            mood=_finite_float(source["mood"]),
            trust=_finite_float(source["trust"]),
            feedback=_short_string(source.get("feedback", ""), MAX_FEEDBACK_LENGTH),
            delta_text=_short_string(source.get("delta_text", ""), MAX_DELTA_TEXT_LENGTH),
            goal=_short_string(source.get("goal", ""), MAX_GOAL_LENGTH),
            actions=actions,
            recent_memory=recent_memory,
            long_term_memory=long_term_memory,
            perception_summary=_short_string(source.get("perception_summary", ""), MAX_PERCEPTION_SUMMARY_LENGTH),
            tool_results=_sanitize_tool_results(source.get("tool_results", [])),
        )

    def to_prompt_dict(self) -> dict[str, object]:
        return {
            "character_name": self.character_name,
            "mode": self.mode,
            "motion": self.motion,
            "focus": self.focus,
            "charge": self.charge,
            "stability": self.stability,
            "mood": self.mood,
            "trust": self.trust,
            "feedback": self.feedback,
            "delta_text": self.delta_text,
            "goal": self.goal,
            "actions": [dict(action) for action in self.actions],
            "recent_memory": [dict(entry) for entry in self.recent_memory],
            "long_term_memory": [dict(entry) for entry in self.long_term_memory],
            "perception_summary": self.perception_summary,
            "tool_results": [dict(entry) for entry in self.tool_results],
        }


def ensure_expression_request(snapshot: dict[str, object] | CompanionSnapshot | ExpressionRequest) -> ExpressionRequest:
    if isinstance(snapshot, ExpressionRequest):
        return snapshot
    return ExpressionRequest.from_snapshot(snapshot)


def _expression_payload_from_snapshot(snapshot: dict[str, object] | CompanionSnapshot) -> dict[str, object]:
    if isinstance(snapshot, CompanionSnapshot):
        return {
            "character_name": snapshot.character_name,
            "mode": snapshot.mode,
            "motion": snapshot.current_motion,
            "current_motion": snapshot.current_motion,
            "focus": snapshot.stats.focus,
            "charge": snapshot.stats.charge,
            "stability": snapshot.stats.stability,
            "mood": snapshot.stats.mood,
            "trust": snapshot.stats.trust,
            "feedback": snapshot.feedback,
            "delta_text": snapshot.delta_text,
            "goal": snapshot.goal,
            "actions": snapshot.actions,
            "memory_log": snapshot.memory_log,
            "long_term_memory": snapshot.long_term_memory,
        }
    if isinstance(snapshot, dict):
        return snapshot
    raise TypeError("expression snapshot must be a dict or CompanionSnapshot")


def _expression_payload_from_context(context: Mapping[str, object] | None) -> dict[str, object]:
    if not isinstance(context, Mapping):
        return {}
    payload: dict[str, object] = {}
    for key in ("perception_summary", "tool_results"):
        if key in context:
            payload[key] = context[key]
    return payload


def _as_dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _sanitize_tool_results(value: object) -> tuple[dict[str, str], ...]:
    results: list[dict[str, str]] = []
    for entry in _as_dict_list(value):
        source = _short_string(entry.get("source", ""), 60)
        title = _short_string(entry.get("title", ""), 80)
        summary = _short_string(entry.get("summary", ""), 180)
        if not source or not title or not summary:
            continue
        result = {"source": source, "title": title, "summary": summary}
        timestamp = _short_string(entry.get("timestamp", ""), MAX_TOOL_TIMESTAMP_LENGTH)
        if timestamp:
            result["timestamp"] = timestamp
        results.append(result)
        if len(results) >= MAX_TOOL_RESULTS:
            break
    return tuple(results)


def _sanitize_actions(value: object) -> tuple[dict[str, str], ...]:
    actions: list[dict[str, str]] = []
    for action in _as_dict_list(value):
        label = _short_string(action.get("label", ""), MAX_ACTION_LABEL_LENGTH)
        if label:
            actions.append({"label": label})
    return tuple(actions)


def _sanitize_recent_memory(value: object) -> tuple[dict[str, str], ...]:
    memory: list[dict[str, str]] = []
    for entry in _as_dict_list(value):
        kind = _short_string(entry.get("kind", ""), MAX_MEMORY_KIND_LENGTH)
        summary = _short_string(entry.get("summary", ""), MAX_MEMORY_SUMMARY_LENGTH)
        motion = _short_string(entry.get("motion", ""), MAX_MEMORY_MOTION_LENGTH)
        if not kind or not summary or not motion:
            continue
        memory.append({"kind": kind, "summary": summary, "motion": motion})
        if len(memory) >= MAX_RECENT_MEMORY:
            break
    return tuple(memory)


def _sanitize_long_term_memory(value: object) -> tuple[dict[str, str], ...]:
    memory: list[dict[str, str]] = []
    for entry in _as_dict_list(value):
        category = _short_string(entry.get("category", ""), MAX_LONG_TERM_MEMORY_CATEGORY_LENGTH)
        summary = _short_string(entry.get("summary", ""), MAX_MEMORY_SUMMARY_LENGTH)
        source = _short_string(entry.get("source", ""), MAX_LONG_TERM_MEMORY_SOURCE_LENGTH)
        if not category or not summary or not source:
            continue
        memory.append({"category": category, "summary": summary, "source": source})
        if len(memory) >= MAX_LONG_TERM_MEMORY_SUMMARIES:
            break
    return tuple(memory)


def _short_string(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    return _replace_control_characters(value.strip())[:max_length]


def _replace_control_characters(value: str) -> str:
    return "".join(" " if _is_control_character(char) else char for char in value)


def _finite_float(value: object) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite expression stat")
    return parsed


def _is_control_character(char: str) -> bool:
    return ord(char) < 32 or ord(char) == 127
