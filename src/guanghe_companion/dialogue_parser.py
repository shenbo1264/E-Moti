from __future__ import annotations

import json
from collections.abc import Iterator
from json import JSONDecodeError

from .events import ALLOWED_EFFECTS, CompanionEvent

ALLOWED_DIALOGUE_FIELDS = frozenset({"type", "speech", "effect", "motion_hint", "intent_hint"})
MAX_DIALOGUE_SPEECH_LENGTH = 80
MAX_DIALOGUE_MOTION_HINT_LENGTH = 40
MAX_DIALOGUE_EFFECT_LENGTH = 20


class DialogueStreamParser:
    def __init__(self, character_name: str) -> None:
        self.character_name = character_name
        self._buffer = ""
        self.accumulated_text = ""
        self.last_error: str | None = None
        self._decoder = json.JSONDecoder()

    def feed(self, chunk: str) -> Iterator[CompanionEvent]:
        if chunk:
            self._buffer += chunk
            self.accumulated_text += chunk
        yield from self._drain()

    def has_pending_text(self) -> bool:
        return bool(self._buffer.strip())

    def _drain(self) -> Iterator[CompanionEvent]:
        while self._buffer.strip():
            text = self._buffer.lstrip()
            if text[0] not in "[{":
                self.last_error = "invalid_json"
                self._buffer = ""
                return
            try:
                payload, end_index = self._decoder.raw_decode(text)
            except JSONDecodeError:
                if not _has_balanced_json_prefix(text):
                    return
                self.last_error = "invalid_json"
                self._buffer = ""
                return
            self._buffer = text[end_index:].strip()
            yield from self._events_from_payload(payload)

    def _events_from_payload(self, payload: object) -> Iterator[CompanionEvent]:
        rows = payload if isinstance(payload, list) else [payload]
        events: list[CompanionEvent] = []
        for row in rows:
            event = self._normalize_row(row)
            if event is None:
                return
            events.append(event)
        yield from events

    def _normalize_row(self, row: object) -> CompanionEvent | None:
        if not isinstance(row, dict):
            self.last_error = "invalid_row"
            return None
        if not set(row).issubset(ALLOWED_DIALOGUE_FIELDS):
            self.last_error = "unsafe_fields"
            return None
        if row.get("type") != "speech":
            self.last_error = "unsupported_type"
            return None
        speech = _bounded_clean_text(row.get("speech"), MAX_DIALOGUE_SPEECH_LENGTH)
        if not speech:
            self.last_error = "empty_speech"
            return None
        effect = _bounded_clean_text(row.get("effect", ""), MAX_DIALOGUE_EFFECT_LENGTH)
        if effect not in ALLOWED_EFFECTS:
            self.last_error = "unsafe_effect"
            return None
        motion_hint = _bounded_clean_text(row.get("motion_hint", ""), MAX_DIALOGUE_MOTION_HINT_LENGTH)
        if row.get("motion_hint", "") and not motion_hint:
            self.last_error = "unsafe_motion_hint"
            return None
        return CompanionEvent(
            event_type="speech",
            character_name=self.character_name,
            speech=speech,
            sprite="1",
            effect=effect,
        )


def _bounded_clean_text(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if _has_control_character(text):
        return ""
    if len(text) > max_length:
        return ""
    return text


def _has_control_character(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


def _has_balanced_json_prefix(text: str) -> bool:
    depth = 0
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
            if depth <= 0:
                return True
    return depth == 0
