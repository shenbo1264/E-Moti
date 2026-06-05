from __future__ import annotations

from typing import Any

from .dialogue_parser import DialogueStreamParser
from .events import ALLOWED_EFFECTS
from .visual_actions import clean_speech_and_visual_actions

MAX_SPEECH_LENGTH = 80
MAX_MOTION_HINT_LENGTH = 40
MAX_EFFECT_LENGTH = 20


class ExpressionPayloadError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def stringify_event(event: dict[Any, Any]) -> dict[str, str]:
    return {str(key): str(value).strip() for key, value in event.items()}


def normalize_expression_event(state, event: dict[Any, Any]) -> dict[str, str] | None:
    if _is_allowed_legacy_expression_event(state, event):
        return stringify_event(event)
    return _normalize_speech_schema_event(state, event)


def parse_shinsekai_object_stream(raw: str, state) -> list[dict[str, str]] | None:
    if not raw.lstrip().startswith("{"):
        return None
    parser = DialogueStreamParser(character_name=state.character_name)
    events = list(parser.feed(raw))
    if parser.has_pending_text():
        raise ExpressionPayloadError("invalid_json")
    if parser.last_error is not None:
        raise ExpressionPayloadError(_dialogue_parser_fallback_reason(parser.last_error))
    if not events:
        raise ExpressionPayloadError("invalid_payload")
    if len(events) > 4:
        raise ExpressionPayloadError("too_many_events")
    return [event.to_legacy_dict() for event in events]


def _dialogue_parser_fallback_reason(reason: str) -> str:
    if reason == "invalid_json":
        return "invalid_json"
    return "unsafe_event"


def _is_allowed_legacy_expression_event(state, event: dict[Any, Any]) -> bool:
    if {str(key) for key in event.keys()} != {"character_name", "speech", "sprite", "effect"}:
        return False
    if not all(isinstance(event.get(key), str) for key in ("character_name", "speech", "sprite", "effect")):
        return False
    normalized = stringify_event(event)
    if not normalized["speech"]:
        return False
    if _has_control_character(normalized["speech"]):
        return False
    if len(normalized["speech"]) > MAX_SPEECH_LENGTH:
        return False
    if not _is_safe_legacy_sprite(normalized["sprite"]):
        return False
    if normalized["effect"] not in ALLOWED_EFFECTS:
        return False
    return normalized["character_name"] == state.character_name


def _is_safe_legacy_sprite(sprite: str) -> bool:
    return sprite == "1"


def _normalize_speech_schema_event(state, event: dict[Any, Any]) -> dict[str, str] | None:
    allowed_keys = {"type", "speech", "effect", "motion_hint"}
    if not set(event.keys()).issubset(allowed_keys):
        return None
    if event.get("type") != "speech":
        return None

    speech = event.get("speech")
    effect = event.get("effect", "")
    motion_hint = event.get("motion_hint", "")
    if not isinstance(speech, str) or not speech.strip():
        return None
    normalized_speech = speech.strip()
    normalized_speech, _ = clean_speech_and_visual_actions(normalized_speech, "")
    if _has_control_character(normalized_speech):
        return None
    if len(normalized_speech) > MAX_SPEECH_LENGTH:
        return None
    if not normalized_speech:
        return None
    if not isinstance(effect, str):
        return None
    normalized_effect = effect.strip()
    if len(normalized_effect) > MAX_EFFECT_LENGTH:
        return None
    if normalized_effect not in ALLOWED_EFFECTS:
        normalized_effect = "ATTENTION"
    if motion_hint != "" and not isinstance(motion_hint, str):
        return None
    if isinstance(motion_hint, str):
        normalized_motion_hint = motion_hint.strip()
        if _has_control_character(normalized_motion_hint):
            return None
        if len(normalized_motion_hint) > MAX_MOTION_HINT_LENGTH:
            return None

    return {
        "character_name": state.character_name,
        "speech": normalized_speech,
        "sprite": "1",
        "effect": normalized_effect,
    }


def _has_control_character(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)
