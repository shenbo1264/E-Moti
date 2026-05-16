from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Literal

from .models import CompanionState

ALLOWED_EFFECTS = {"", "ATTENTION", "DISAPPOINTED", "SHOCKED", "SWITCH", "OVERLOAD"}
ALLOWED_META_NAMES = {"STAT", "CHOICE", "NARR"}
ACTION_EFFECTS = {
    "touch": "ATTENTION",
    "soothe": "SWITCH",
    "rest": "SWITCH",
    "study": "ATTENTION",
    "play": "ATTENTION",
    "drag": "SWITCH",
}
EventType = Literal[
    "speech",
    "stat",
    "choice",
    "motion",
    "memory",
    "relationship",
    "inventory",
    "proactive",
    "system",
]
EVENT_PAYLOAD_FIELDS: dict[EventType, frozenset[str]] = {
    "speech": frozenset(),
    "stat": frozenset({"stats"}),
    "choice": frozenset({"choices"}),
    "motion": frozenset({"motion", "reason"}),
    "memory": frozenset({"kind", "summary", "motion"}),
    "relationship": frozenset({"stage", "unlock_id", "message"}),
    "inventory": frozenset({"item_id", "action", "item_name", "icon_path"}),
    "proactive": frozenset({"kind", "summary"}),
    "system": frozenset({"code", "message"}),
}


def action_event_effect(action_id: str, allowed: bool, mode: str) -> str:
    if not allowed:
        return "OVERLOAD" if mode == "Overload" else "DISAPPOINTED"
    return ACTION_EFFECTS.get(action_id, "")


@dataclass(frozen=True, slots=True)
class EventContext:
    state: CompanionState
    motion: str
    feedback: str
    delta_text: str
    goal: str
    actions: list[dict[str, object]]
    memory_log: list[dict[str, object]] = field(default_factory=list)

    def to_expressor_dict(self) -> dict[str, object]:
        return {
            "character_name": self.state.character_name,
            "mode": self.state.mode,
            "motion": self.motion,
            "focus": self.state.focus,
            "charge": self.state.charge,
            "stability": self.state.stability,
            "mood": self.state.mood,
            "trust": self.state.trust,
            "feedback": self.feedback,
            "delta_text": self.delta_text,
            "goal": self.goal,
            "actions": self.actions,
            "memory_log": self.memory_log,
        }


@dataclass(frozen=True, slots=True)
class CompanionEvent:
    event_type: EventType
    character_name: str
    speech: str
    sprite: str = "-1"
    effect: str = ""
    payload: dict[str, object] = field(default_factory=dict)

    def to_legacy_dict(self) -> dict[str, str]:
        return {
            "character_name": self.character_name,
            "speech": self.speech,
            "sprite": self.sprite,
            "effect": self.effect,
        }

    @classmethod
    def from_legacy_dict(cls, state: CompanionState, event: dict[str, str]) -> "CompanionEvent":
        character_name = event["character_name"]
        event_type: EventType
        if character_name == state.character_name:
            event_type = "speech"
        elif character_name == "STAT":
            event_type = "stat"
        elif character_name == "CHOICE":
            event_type = "choice"
        else:
            event_type = "system"
        return cls(
            event_type=event_type,
            character_name=character_name,
            speech=event["speech"],
            sprite=event["sprite"],
            effect=event["effect"],
        )


class EventBuilder:
    def __init__(self, state: CompanionState) -> None:
        self.state = state

    def fallback_events(self, feedback: str, choices: list[str], effect: str = "") -> list[CompanionEvent]:
        choice_text = " / ".join(choices[:6])
        stats = {
            "focus": int(self.state.focus),
            "charge": int(self.state.charge),
            "stability": int(self.state.stability),
            "mood": int(self.state.mood),
            "trust": int(self.state.trust),
        }
        stat_text = (
            f"专注 {stats['focus']} / 能量 {stats['charge']} / 稳定 {stats['stability']} / "
            f"心情 {stats['mood']} / 信任 {stats['trust']}"
        )
        return [
            CompanionEvent(
                event_type="speech",
                character_name=self.state.character_name,
                speech=feedback,
                sprite="1",
                effect=effect if effect in ALLOWED_EFFECTS else "",
            ),
            CompanionEvent(event_type="stat", character_name="STAT", speech=stat_text, payload={"stats": stats}),
            CompanionEvent(event_type="choice", character_name="CHOICE", speech=choice_text, payload={"choices": choices[:6]}),
        ]

    def motion_event(self, motion: str, reason: str, effect: str = "SWITCH") -> CompanionEvent:
        return CompanionEvent(
            event_type="motion",
            character_name="MOTION",
            speech=reason,
            effect=effect if effect in ALLOWED_EFFECTS else "",
            payload={"motion": motion, "reason": reason},
        )

    def memory_event(self, kind: str, summary: str, motion: str) -> CompanionEvent:
        return CompanionEvent(
            event_type="memory",
            character_name="MEMORY",
            speech=summary,
            payload={"kind": kind, "summary": summary, "motion": motion},
        )

    def relationship_event(self, stage: str, unlock_id: str, message: str) -> CompanionEvent:
        return CompanionEvent(
            event_type="relationship",
            character_name="RELATIONSHIP",
            speech=message,
            effect="SHOCKED" if unlock_id else "",
            payload={"stage": stage, "unlock_id": unlock_id, "message": message},
        )

    def inventory_event(self, item_id: str, action: str, item_name: str, icon_path: str) -> CompanionEvent:
        speech = f"{action}: {item_name}"
        return CompanionEvent(
            event_type="inventory",
            character_name="INVENTORY",
            speech=speech,
            effect="ATTENTION",
            payload={"item_id": item_id, "action": action, "item_name": item_name, "icon_path": icon_path},
        )

    def proactive_event(self, kind: str, summary: str) -> CompanionEvent:
        return CompanionEvent(
            event_type="proactive",
            character_name="PROACTIVE",
            speech=summary,
            effect="ATTENTION",
            payload={"kind": kind, "summary": summary},
        )

    def system_event(self, code: str, message: str) -> CompanionEvent:
        return CompanionEvent(
            event_type="system",
            character_name="SYSTEM",
            speech=message,
            payload={"code": code, "message": message},
        )

    def action_domain_events(
        self,
        motion: str,
        feedback: str,
        effect: str,
        memory_kind: str | None = None,
        memory_summary: str | None = None,
        relationship_unlocks: list[dict[str, str]] | None = None,
    ) -> list[CompanionEvent]:
        events = [self.motion_event(motion=motion, reason=feedback, effect=effect)]
        if memory_kind and memory_summary:
            events.append(self.memory_event(kind=memory_kind, summary=memory_summary, motion=motion))
        events.extend(self._relationship_events(relationship_unlocks or []))
        return events

    def inventory_domain_events(
        self,
        motion: str,
        feedback: str,
        effect: str,
        item_id: str,
        action: str,
        item_name: str,
        icon_path: str,
        memory_kind: str | None = None,
        memory_summary: str | None = None,
        relationship_unlocks: list[dict[str, str]] | None = None,
    ) -> list[CompanionEvent]:
        events = [
            self.motion_event(motion=motion, reason=feedback, effect=effect),
            self.inventory_event(
                item_id=item_id,
                action=action,
                item_name=item_name,
                icon_path=icon_path,
            ),
        ]
        if memory_kind and memory_summary:
            events.append(self.memory_event(kind=memory_kind, summary=memory_summary, motion=motion))
        events.extend(self._relationship_events(relationship_unlocks or []))
        return events

    def proactive_domain_events(
        self,
        motion: str,
        feedback: str,
        effect: str,
        proactive_kind: str | None = None,
        proactive_summary: str | None = None,
        relationship_unlocks: list[dict[str, str]] | None = None,
    ) -> list[CompanionEvent]:
        events = [self.motion_event(motion=motion, reason=feedback, effect=effect)]
        if proactive_kind and proactive_summary:
            events.extend(
                [
                    self.proactive_event(kind=proactive_kind, summary=proactive_summary),
                    self.memory_event(kind="主动陪伴", summary=proactive_summary, motion=motion),
                ]
            )
        events.extend(self._relationship_events(relationship_unlocks or []))
        return events

    def _relationship_events(self, relationship_unlocks: list[dict[str, str]]) -> list[CompanionEvent]:
        return [
            self.relationship_event(
                stage=unlock["stage"],
                unlock_id=unlock["unlock_id"],
                message=unlock["message"],
            )
            for unlock in relationship_unlocks
        ]


class EventValidator:
    def __init__(self, state: CompanionState) -> None:
        self.state = state

    def validate(
        self,
        events: list[dict[str, str]],
        fallback_feedback: str,
        choices: list[str],
    ) -> list[CompanionEvent]:
        if not events or len(events) > 4:
            return EventBuilder(self.state).fallback_events(fallback_feedback, choices, effect="DISAPPOINTED")

        validated: list[CompanionEvent] = []
        for event in events:
            if not _is_valid_event(self.state, event):
                return EventBuilder(self.state).fallback_events(fallback_feedback, choices, effect="DISAPPOINTED")
            validated.append(CompanionEvent.from_legacy_dict(self.state, deepcopy(event)))
        return validated

    def validate_typed(
        self,
        events: list[CompanionEvent],
        fallback_feedback: str,
        choices: list[str],
    ) -> list[CompanionEvent]:
        if not events or len(events) > 4:
            return EventBuilder(self.state).fallback_events(fallback_feedback, choices, effect="DISAPPOINTED")

        for event in events:
            if not _is_valid_typed_event(event):
                return EventBuilder(self.state).fallback_events(fallback_feedback, choices, effect="DISAPPOINTED")
        return list(events)


def build_fallback_events(
    state: CompanionState,
    feedback: str,
    choices: list[str],
    effect: str = "",
) -> list[dict[str, str]]:
    return [event.to_legacy_dict() for event in build_typed_fallback_events(state, feedback, choices, effect)]


def build_typed_fallback_events(
    state: CompanionState,
    feedback: str,
    choices: list[str],
    effect: str = "",
) -> list[CompanionEvent]:
    return EventBuilder(state).fallback_events(feedback, choices, effect)


def validate_events(
    state: CompanionState,
    events: list[dict[str, str]],
    fallback_feedback: str,
    choices: list[str],
) -> list[dict[str, str]]:
    return [
        event.to_legacy_dict()
        for event in EventValidator(state).validate(
            events=events,
            fallback_feedback=fallback_feedback,
            choices=choices,
        )
    ]


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


def _is_valid_typed_event(event: CompanionEvent) -> bool:
    if event.event_type not in EVENT_PAYLOAD_FIELDS:
        return False

    required_payload_fields = EVENT_PAYLOAD_FIELDS[event.event_type]
    if not required_payload_fields.issubset(event.payload.keys()):
        return False

    if not event.character_name:
        return False

    if not isinstance(event.speech, str) or not event.speech or len(event.speech) > 120:
        return False

    if event.sprite != "-1" and not event.sprite.isdigit():
        return False

    if event.effect not in ALLOWED_EFFECTS:
        return False

    return True
