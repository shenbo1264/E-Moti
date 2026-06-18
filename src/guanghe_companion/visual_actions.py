from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ActionType = Literal["expression", "motion"]

MAX_VISUAL_ACTIONS = 4
MAX_MOTION_HINT_LENGTH = 40
DEFAULT_EXPRESSION_TTL_MS = 3000
DEFAULT_MOTION_TTL_MS = 1800
LLM_SOURCE = "llm"

SPRITE_MOTION_IDS = frozenset(
    {
        "Default",
        "TouchHead",
        "Play",
        "SwitchDown",
        "Sleep",
        "Raised",
        "Study",
    }
)

TAG_ALIASES: dict[str, tuple[str, str]] = {
    "joy": ("joy", "TouchHead"),
    "happy": ("joy", "TouchHead"),
    "smile": ("joy", "TouchHead"),
    "sad": ("sadness", "SwitchDown"),
    "sadness": ("sadness", "SwitchDown"),
    "sleepy": ("sleepy", "Sleep"),
    "tired": ("sleepy", "Sleep"),
    "excited": ("excited", "Play"),
    "play": ("excited", "Play"),
    "focus": ("focused", "Study"),
    "focused": ("focused", "Study"),
    "study": ("focused", "Study"),
    "surprised": ("surprised", "Raised"),
    "calm": ("calm", "Default"),
    "goofy": ("goofy", "Play"),
    "confused": ("confused", "Study"),
    "blink": ("blink", "Default"),
}

PIXEL_EXPRESSION_MOTION_IDS: dict[str, str] = {
    "joy": "TouchHead",
    "happy": "TouchHead",
    "smile": "TouchHead",
    "sadness": "SwitchDown",
    "sad": "SwitchDown",
    "sleepy": "Sleep",
    "tired": "Sleep",
    "excited": "Play",
    "play": "Play",
    "focused": "Study",
    "focus": "Study",
    "study": "Study",
    "surprised": "Raised",
    "calm": "Default",
    "neutral": "Default",
    "blink": "Default",
    "goofy": "Play",
    "confused": "Study",
}

_TAG_PATTERN = re.compile(r"\[([A-Za-z0-9_-]{1,32})\]")


@dataclass(frozen=True, slots=True)
class VisualAction:
    action_type: ActionType
    action_id: str
    ttl_ms: int
    priority: int
    source: str = LLM_SOURCE

    def to_dict(self) -> dict[str, object]:
        return {
            "type": self.action_type,
            "id": self.action_id,
            "ttl_ms": self.ttl_ms,
            "priority": self.priority,
            "source": self.source,
        }


def clean_speech_and_visual_actions(speech: str, motion_hint: str = "") -> tuple[str, tuple[VisualAction, ...]]:
    actions: list[VisualAction] = []

    def replace_tag(match: re.Match[str]) -> str:
        tag = match.group(1).strip().lower()
        mapped = TAG_ALIASES.get(tag)
        if mapped is None:
            return ""
        expression_id, motion_id = mapped
        actions.append(
            VisualAction(
                action_type="expression",
                action_id=expression_id,
                ttl_ms=DEFAULT_EXPRESSION_TTL_MS,
                priority=70,
                source=LLM_SOURCE,
            )
        )
        actions.append(_motion_action(motion_id))
        return ""

    cleaned_speech = _TAG_PATTERN.sub(replace_tag, speech).strip()
    motion = _clean_motion_hint(motion_hint)
    if motion in SPRITE_MOTION_IDS:
        actions.append(_motion_action(motion))
    return cleaned_speech, _deduplicate_actions(actions)


def visual_actions_from_payload_row(row: object) -> tuple[VisualAction, ...]:
    if not isinstance(row, dict):
        return ()
    if row.get("type") != "speech":
        return ()
    speech = row.get("speech")
    if not isinstance(speech, str):
        return ()
    motion_hint = row.get("motion_hint", "")
    if not isinstance(motion_hint, str):
        motion_hint = ""
    return clean_speech_and_visual_actions(speech, motion_hint)[1]


def visual_actions_from_payload_rows(rows: object) -> tuple[VisualAction, ...]:
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list) or not rows:
        return ()
    return visual_actions_from_payload_row(rows[0])


def visual_actions_from_dicts(raw_actions: object) -> tuple[VisualAction, ...]:
    if not isinstance(raw_actions, list):
        return ()
    actions: list[VisualAction] = []
    for raw in raw_actions[:MAX_VISUAL_ACTIONS]:
        if not isinstance(raw, dict):
            continue
        action_type = raw.get("type")
        action_id = raw.get("id")
        ttl_ms = raw.get("ttl_ms")
        priority = raw.get("priority")
        source = raw.get("source", LLM_SOURCE)
        if action_type not in {"expression", "motion"}:
            continue
        if not isinstance(action_id, str) or not action_id:
            continue
        if action_type == "motion" and action_id not in SPRITE_MOTION_IDS:
            continue
        if isinstance(ttl_ms, bool) or not isinstance(ttl_ms, int) or ttl_ms <= 0:
            continue
        if isinstance(priority, bool) or not isinstance(priority, int):
            continue
        if not isinstance(source, str) or source != LLM_SOURCE:
            continue
        actions.append(
            VisualAction(
                action_type=action_type,
                action_id=action_id,
                ttl_ms=ttl_ms,
                priority=priority,
                source=source,
            )
        )
    return _deduplicate_actions(actions)


def sprite_motion_override(actions: object) -> str | None:
    normalized = actions if isinstance(actions, tuple) else visual_actions_from_dicts(actions)
    for action in normalized:
        if action.action_type == "motion" and action.action_id in SPRITE_MOTION_IDS:
            return action.action_id
    return None


def pixel_motion_override(actions: object) -> str | None:
    normalized = actions if isinstance(actions, tuple) else visual_actions_from_dicts(actions)
    explicit_motion = sprite_motion_override(normalized)
    if explicit_motion:
        return explicit_motion
    for action in normalized:
        if action.action_type != "expression":
            continue
        motion = PIXEL_EXPRESSION_MOTION_IDS.get(action.action_id)
        if motion in SPRITE_MOTION_IDS:
            return motion
    return None


def _motion_action(motion_id: str) -> VisualAction:
    return VisualAction(
        action_type="motion",
        action_id=motion_id,
        ttl_ms=DEFAULT_MOTION_TTL_MS,
        priority=60,
        source=LLM_SOURCE,
    )


def _clean_motion_hint(value: str) -> str:
    text = value.strip()
    if len(text) > MAX_MOTION_HINT_LENGTH or _has_control_character(text):
        return ""
    return text


def _deduplicate_actions(actions: list[VisualAction]) -> tuple[VisualAction, ...]:
    deduped: list[VisualAction] = []
    seen: set[tuple[str, str]] = set()
    for action in actions:
        key = (action.action_type, action.action_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
        if len(deduped) >= MAX_VISUAL_ACTIONS:
            break
    return tuple(deduped)


def _has_control_character(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)
