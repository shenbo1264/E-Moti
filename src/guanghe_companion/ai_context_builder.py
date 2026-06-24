from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .dialogue_history import DialogueHistoryEntry

MAX_AI_CONTEXT_DIALOGUE = 5
MAX_AI_CONTEXT_LONG_TERM_MEMORY = 5
MAX_AI_CONTEXT_TOOL_RESULTS = 3
MAX_AI_CONTEXT_ROLE_LENGTH = 16
MAX_AI_CONTEXT_SPEAKER_LENGTH = 24
MAX_AI_CONTEXT_DIALOGUE_TEXT_LENGTH = 240
MAX_AI_CONTEXT_MEMORY_CATEGORY_LENGTH = 40
MAX_AI_CONTEXT_MEMORY_SUMMARY_LENGTH = 160
MAX_AI_CONTEXT_MEMORY_SOURCE_LENGTH = 40
MAX_AI_CONTEXT_PERCEPTION_LENGTH = 240
MAX_AI_CONTEXT_TOOL_SOURCE_LENGTH = 60
MAX_AI_CONTEXT_TOOL_TITLE_LENGTH = 80
MAX_AI_CONTEXT_TOOL_SUMMARY_LENGTH = 180
MAX_AI_CONTEXT_TOOL_TIMESTAMP_LENGTH = 40
MAX_AI_CONTEXT_OPENING_LINE_LENGTH = 80
ALLOWED_DIALOGUE_ROLES = frozenset({"user", "assistant", "system"})


@dataclass(frozen=True, slots=True)
class AIContextBuilder:
    dialogue_history: Iterable[DialogueHistoryEntry | Mapping[str, object]] = ()
    long_term_memory: Iterable[Mapping[str, object]] = ()
    perception_summary: object = ""
    tool_results: Iterable[Mapping[str, object]] = ()

    def build(self) -> dict[str, object]:
        return build_ai_context_payload(
            dialogue_history=self.dialogue_history,
            long_term_memory=self.long_term_memory,
            perception_summary=self.perception_summary,
            tool_results=self.tool_results,
        )


def build_ai_context_payload(
    *,
    dialogue_history: Iterable[DialogueHistoryEntry | Mapping[str, object]] = (),
    long_term_memory: Iterable[Mapping[str, object]] = (),
    perception_summary: object = "",
    tool_results: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    payload: dict[str, object] = {}
    recent_dialogue = _sanitize_dialogue_history(dialogue_history)
    memory = _sanitize_long_term_memory(long_term_memory)
    perception = _short_text(perception_summary, MAX_AI_CONTEXT_PERCEPTION_LENGTH)
    tools = _sanitize_tool_results(tool_results)
    if recent_dialogue:
        payload["recent_dialogue"] = recent_dialogue
    if memory:
        payload["long_term_memory"] = memory
    if perception:
        payload["perception_summary"] = perception
    if tools:
        payload["tool_results"] = tools
    return payload


def _sanitize_dialogue_history(
    entries: Iterable[DialogueHistoryEntry | Mapping[str, object]],
) -> list[dict[str, str]]:
    sanitized: list[dict[str, str]] = []
    for entry in _safe_iter(entries):
        row = _sanitize_dialogue_entry(entry)
        if row is not None:
            sanitized.append(row)
    return sanitized[-MAX_AI_CONTEXT_DIALOGUE:]


def _sanitize_dialogue_entry(entry: object) -> dict[str, str] | None:
    if isinstance(entry, DialogueHistoryEntry):
        role = entry.role
        speaker = entry.speaker
        text = entry.text
    elif isinstance(entry, Mapping):
        role = entry.get("role")
        speaker = entry.get("speaker")
        text = entry.get("text")
    else:
        return None
    role_text = _short_text(role, MAX_AI_CONTEXT_ROLE_LENGTH)
    speaker_text = _short_text(speaker, MAX_AI_CONTEXT_SPEAKER_LENGTH)
    message_text = _short_text(text, MAX_AI_CONTEXT_DIALOGUE_TEXT_LENGTH)
    if role_text not in ALLOWED_DIALOGUE_ROLES or not speaker_text or not message_text:
        return None
    return {"role": role_text, "speaker": speaker_text, "text": message_text}


def _sanitize_long_term_memory(entries: Iterable[Mapping[str, object]]) -> list[dict[str, str]]:
    memory: list[dict[str, str]] = []
    for entry in _safe_iter(entries):
        if not isinstance(entry, Mapping):
            continue
        category = _short_text(entry.get("category"), MAX_AI_CONTEXT_MEMORY_CATEGORY_LENGTH)
        summary = _short_text(entry.get("summary"), MAX_AI_CONTEXT_MEMORY_SUMMARY_LENGTH)
        source = _short_text(entry.get("source"), MAX_AI_CONTEXT_MEMORY_SOURCE_LENGTH)
        if not category or not summary or not source:
            continue
        memory.append({"category": category, "summary": summary, "source": source})
        if len(memory) >= MAX_AI_CONTEXT_LONG_TERM_MEMORY:
            break
    return memory


def _sanitize_tool_results(entries: Iterable[Mapping[str, object]]) -> list[dict[str, str]]:
    tools: list[dict[str, str]] = []
    for entry in _safe_iter(entries):
        if not isinstance(entry, Mapping):
            continue
        source = _short_text(entry.get("source"), MAX_AI_CONTEXT_TOOL_SOURCE_LENGTH)
        title = _short_text(entry.get("title"), MAX_AI_CONTEXT_TOOL_TITLE_LENGTH)
        summary = _short_text(entry.get("summary"), MAX_AI_CONTEXT_TOOL_SUMMARY_LENGTH)
        if not source or not title or not summary:
            continue
        row = {"source": source, "title": title, "summary": summary}
        timestamp = _short_text(entry.get("timestamp"), MAX_AI_CONTEXT_TOOL_TIMESTAMP_LENGTH)
        if timestamp:
            row["timestamp"] = timestamp
        opening_line = _short_text(entry.get("opening_line"), MAX_AI_CONTEXT_OPENING_LINE_LENGTH)
        if opening_line:
            row["opening_line"] = opening_line
        tools.append(row)
        if len(tools) >= MAX_AI_CONTEXT_TOOL_RESULTS:
            break
    return tools


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
    return _replace_control_characters(value.strip())[:max_length]


def _replace_control_characters(value: str) -> str:
    return "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value)
