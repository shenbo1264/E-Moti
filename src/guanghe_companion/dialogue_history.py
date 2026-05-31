from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

CURRENT_DIALOGUE_HISTORY_SCHEMA_VERSION = 1
MAX_DIALOGUE_HISTORY_ENTRIES = 80
MAX_DIALOGUE_HISTORY_TEXT_LENGTH = 240
MAX_DIALOGUE_HISTORY_SPEAKER_LENGTH = 24
MAX_DIALOGUE_HISTORY_EFFECT_LENGTH = 20
USER_DIALOGUE_SPEAKER = "你"
ALLOWED_DIALOGUE_HISTORY_ROLES = frozenset({"user", "assistant", "system"})


@dataclass(frozen=True, slots=True)
class DialogueHistoryEntry:
    role: str
    speaker: str
    text: str
    effect: str = ""
    source: str = "desktop_pet"

    def to_dict(self) -> dict[str, str]:
        return {
            "role": self.role,
            "speaker": self.speaker,
            "text": self.text,
            "effect": self.effect,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class DialogueHistoryStore:
    path: Path | str

    def load(self) -> tuple[DialogueHistoryEntry, ...]:
        target = Path(self.path)
        if not target.exists():
            return ()
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return ()
        entries_payload = payload.get("entries") if isinstance(payload, dict) else payload
        if not isinstance(entries_payload, list):
            return ()
        entries: list[DialogueHistoryEntry] = []
        for item in entries_payload:
            entry = _entry_from_payload(item)
            if entry is None:
                return ()
            entries.append(entry)
        return tuple(entries[-MAX_DIALOGUE_HISTORY_ENTRIES:])

    def save(self, entries: Iterable[DialogueHistoryEntry]) -> None:
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        normalized = tuple(entries)[-MAX_DIALOGUE_HISTORY_ENTRIES:]
        payload = {
            "schema_version": CURRENT_DIALOGUE_HISTORY_SCHEMA_VERSION,
            "entries": [entry.to_dict() for entry in normalized],
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear(self) -> None:
        self.save(())


def append_dialogue_exchange(
    entries: Iterable[DialogueHistoryEntry],
    *,
    user_text: str,
    assistant_name: str,
    assistant_text: str,
    effect: str = "",
    source: str = "desktop_pet",
) -> tuple[DialogueHistoryEntry, ...]:
    next_entries = list(entries)
    cleaned_user_text = _clean_append_text(user_text, MAX_DIALOGUE_HISTORY_TEXT_LENGTH)
    cleaned_assistant_text = _clean_append_text(assistant_text, MAX_DIALOGUE_HISTORY_TEXT_LENGTH)
    cleaned_assistant_name = _clean_append_text(assistant_name, MAX_DIALOGUE_HISTORY_SPEAKER_LENGTH) or "星汐"
    cleaned_effect = _clean_append_text(effect, MAX_DIALOGUE_HISTORY_EFFECT_LENGTH)
    cleaned_source = _clean_append_text(source, MAX_DIALOGUE_HISTORY_SPEAKER_LENGTH) or "desktop_pet"
    if cleaned_user_text:
        next_entries.append(
            DialogueHistoryEntry(
                role="user",
                speaker=USER_DIALOGUE_SPEAKER,
                text=cleaned_user_text,
                source=cleaned_source,
            )
        )
    if cleaned_assistant_text:
        next_entries.append(
            DialogueHistoryEntry(
                role="assistant",
                speaker=cleaned_assistant_name,
                text=cleaned_assistant_text,
                effect=cleaned_effect,
                source=cleaned_source,
            )
        )
    return tuple(next_entries[-MAX_DIALOGUE_HISTORY_ENTRIES:])


def format_dialogue_history_text(entries: Iterable[DialogueHistoryEntry]) -> str:
    lines = [f"{entry.speaker}：{entry.text}" for entry in entries if entry.text]
    return "\n".join(lines)


def replay_latest_assistant(entries: Iterable[DialogueHistoryEntry]) -> DialogueHistoryEntry | None:
    for entry in reversed(tuple(entries)):
        if entry.role == "assistant":
            return entry
    return None


def revert_latest_exchange(
    entries: Iterable[DialogueHistoryEntry],
) -> tuple[tuple[DialogueHistoryEntry, ...], DialogueHistoryEntry | None]:
    items = tuple(entries)
    for index in range(len(items) - 1, -1, -1):
        if items[index].role == "user":
            reverted = items[:index]
            return reverted, replay_latest_assistant(reverted)
    return items, replay_latest_assistant(items)


def _entry_from_payload(value: object) -> DialogueHistoryEntry | None:
    if not isinstance(value, dict):
        return None
    role = _clean_loaded_text(value.get("role"), MAX_DIALOGUE_HISTORY_SPEAKER_LENGTH)
    speaker = _clean_loaded_text(value.get("speaker"), MAX_DIALOGUE_HISTORY_SPEAKER_LENGTH)
    text = _clean_loaded_text(value.get("text"), MAX_DIALOGUE_HISTORY_TEXT_LENGTH)
    effect = _clean_loaded_text(value.get("effect", ""), MAX_DIALOGUE_HISTORY_EFFECT_LENGTH)
    source = _clean_loaded_text(value.get("source", "desktop_pet"), MAX_DIALOGUE_HISTORY_SPEAKER_LENGTH)
    if role not in ALLOWED_DIALOGUE_HISTORY_ROLES:
        return None
    if not speaker or not text:
        return None
    return DialogueHistoryEntry(
        role=role,
        speaker=speaker,
        text=text,
        effect=effect,
        source=source or "desktop_pet",
    )


def _clean_loaded_text(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if _has_control_character(text) or len(text) > max_length:
        return ""
    return text


def _clean_append_text(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    normalized = "".join(" " if _is_control_character(char) else char for char in value)
    return normalized.strip()[:max_length]


def _has_control_character(value: str) -> bool:
    return any(_is_control_character(char) for char in value)


def _is_control_character(char: str) -> bool:
    return ord(char) < 32 or ord(char) == 127
