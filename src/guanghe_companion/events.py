from __future__ import annotations

from copy import deepcopy

from .models import CompanionState

ALLOWED_EFFECTS = {"", "ATTENTION", "DISAPPOINTED", "SHOCKED", "SWITCH", "OVERLOAD"}
ALLOWED_META_NAMES = {"STAT", "CHOICE", "NARR"}


def build_fallback_events(
    state: CompanionState,
    feedback: str,
    choices: list[str],
    effect: str = "",
) -> list[dict[str, str]]:
    choice_text = " / ".join(choices[:6])
    stat_text = (
        f"专注 {int(state.focus)} / 能量 {int(state.charge)} / 稳定 {int(state.stability)} / "
        f"心情 {int(state.mood)} / 信任 {int(state.trust)}"
    )
    return [
        {
            "character_name": state.character_name,
            "speech": feedback,
            "sprite": "1",
            "effect": effect if effect in ALLOWED_EFFECTS else "",
        },
        {
            "character_name": "STAT",
            "speech": stat_text,
            "sprite": "-1",
            "effect": "",
        },
        {
            "character_name": "CHOICE",
            "speech": choice_text,
            "sprite": "-1",
            "effect": "",
        },
    ]


def validate_events(
    state: CompanionState,
    events: list[dict[str, str]],
    fallback_feedback: str,
    choices: list[str],
) -> list[dict[str, str]]:
    if not events or len(events) > 4:
        return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")

    validated: list[dict[str, str]] = []
    for event in events:
        if not _is_valid_event(state, event):
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")
        validated.append(deepcopy(event))
    return validated


def _is_valid_event(state: CompanionState, event: dict[str, str]) -> bool:
    required = {"character_name", "speech", "sprite", "effect"}
    if set(event.keys()) != required:
        return False

    character_name = event["character_name"]
    if character_name != state.character_name and character_name not in ALLOWED_META_NAMES:
        return False

    speech = event["speech"]
    max_length = 120 if character_name == "STAT" else 80
    if not isinstance(speech, str) or not speech or len(speech) > max_length:
        return False

    sprite = event["sprite"]
    if sprite != "-1" and not sprite.isdigit():
        return False

    effect = event["effect"]
    if effect not in ALLOWED_EFFECTS:
        return False

    return True
