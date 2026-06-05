from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json

from .dialogue_history import DialogueHistoryEntry, format_dialogue_history_text
from .engine import describe_goal
from .events import CompanionEvent
from .memory import MAX_LONG_TERM_MEMORY_SUMMARIES
from .models import CompanionState
from .relationship import RelationshipPresentation, RelationshipService


def format_delta_text(delta: dict[str, float]) -> str:
    if not delta:
        return "数值无变化"
    parts: list[str] = []
    labels = {
        "focus": "focus",
        "charge": "charge",
        "stability": "stability",
        "mood": "mood",
        "trust": "trust",
        "exp": "exp",
        "coins": "coins",
    }
    for key, value in delta.items():
        sign = "+" if value > 0 else ""
        parts.append(f"{labels.get(key, key)} {sign}{value}")
    return " / ".join(parts)


def legacy_ui_events(events: list[CompanionEvent]) -> list[dict[str, str]]:
    return [
        event.to_legacy_dict()
        for event in events
        if event.event_type in {"speech", "stat", "choice"}
    ]


def visual_actions_from_events(events: list[CompanionEvent]) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for event in events:
        if event.event_type != "visual":
            continue
        raw_actions = event.payload.get("actions")
        if not isinstance(raw_actions, list):
            continue
        actions.extend(dict(action) for action in raw_actions if isinstance(action, dict))
    return actions


def interaction_intents_from_events(events: list[CompanionEvent]) -> list[dict[str, object]]:
    intents: list[dict[str, object]] = []
    for event in events:
        if event.event_type != "intent":
            continue
        raw_intents = event.payload.get("intents")
        if not isinstance(raw_intents, list):
            continue
        intents.extend(dict(intent) for intent in raw_intents if isinstance(intent, dict))
    return intents


def format_event_preview(events: list[dict[str, str]]) -> str:
    return "\n".join(json.dumps(event, ensure_ascii=False) for event in events)


@dataclass(frozen=True, slots=True)
class CompanionStats:
    focus: float
    charge: float
    stability: float
    mood: float
    trust: float
    exp: int
    level: int
    coins: int

    @classmethod
    def from_state(cls, state: CompanionState) -> "CompanionStats":
        return cls(
            focus=state.focus,
            charge=state.charge,
            stability=state.stability,
            mood=state.mood,
            trust=state.trust,
            exp=state.exp,
            level=state.level,
            coins=state.coins,
        )

    def to_dict(self) -> dict[str, float | int]:
        return {
            "focus": self.focus,
            "charge": self.charge,
            "stability": self.stability,
            "mood": self.mood,
            "trust": self.trust,
            "exp": self.exp,
            "level": self.level,
            "coins": self.coins,
        }


@dataclass(frozen=True, slots=True)
class CompanionSnapshot:
    character_id: str
    character_name: str
    player_alias: str
    mode: str
    stats: CompanionStats
    inventory: dict[str, int]
    shop_items: list[dict[str, object]]
    relationship_stage: str
    next_relationship_unlock: str
    relationship_presentation: RelationshipPresentation
    unlocks: list[str]
    memory_log: list[dict[str, object]]
    current_motion: str
    feedback: str
    events: list[CompanionEvent]
    proactive_feedback: dict[str, str] | None
    character_title: str
    character_description: str
    goal: str
    motion_caption: str
    delta_text: str
    allowed: bool
    tick_count: int
    resting: bool
    actions: list[dict[str, object]]
    inventory_items: list[dict[str, object]]
    item_feedback_icon: str | None = None
    dialogue_history: tuple[DialogueHistoryEntry, ...] = ()
    long_term_memory: tuple[dict[str, str], ...] = ()

    def to_compatible_dict(self) -> dict[str, object]:
        return SnapshotCompatibleSerializer(self).to_dict()


@dataclass(frozen=True, slots=True)
class SnapshotCompatibleSerializer:
    snapshot: CompanionSnapshot

    def to_dict(self) -> dict[str, object]:
        stats = self.snapshot.stats.to_dict()
        legacy_events = legacy_ui_events(self.snapshot.events)
        visual_actions = visual_actions_from_events(self.snapshot.events)
        interaction_intents = interaction_intents_from_events(self.snapshot.events)
        return {
            "character_id": self.snapshot.character_id,
            "character_name": self.snapshot.character_name,
            "mode": self.snapshot.mode,
            "stats": stats,
            "inventory": deepcopy(self.snapshot.inventory),
            "character_title": self.snapshot.character_title,
            "character_description": self.snapshot.character_description,
            "focus": stats["focus"],
            "charge": stats["charge"],
            "stability": stats["stability"],
            "mood": stats["mood"],
            "trust": stats["trust"],
            "exp": stats["exp"],
            "level": stats["level"],
            "coins": stats["coins"],
            "goal": self.snapshot.goal,
            "player_alias": self.snapshot.player_alias,
            "relationship_stage": self.snapshot.relationship_stage,
            "next_relationship_unlock": self.snapshot.next_relationship_unlock,
            "relationship_presentation": self.snapshot.relationship_presentation.to_dict(),
            "unlocks": list(self.snapshot.unlocks),
            "feedback": self.snapshot.feedback,
            "current_motion": self.snapshot.current_motion,
            "motion": self.snapshot.current_motion,
            "motion_caption": self.snapshot.motion_caption,
            "delta_text": self.snapshot.delta_text,
            "allowed": self.snapshot.allowed,
            "tick_count": self.snapshot.tick_count,
            "resting": self.snapshot.resting,
            "events": legacy_events,
            "event_preview": format_event_preview(legacy_events),
            "visual_actions": deepcopy(visual_actions),
            "interaction_intents": deepcopy(interaction_intents),
            "item_feedback_icon": self.snapshot.item_feedback_icon,
            "proactive_feedback": deepcopy(self.snapshot.proactive_feedback),
            "memory_log": deepcopy(self.snapshot.memory_log),
            "actions": deepcopy(self.snapshot.actions),
            "shop_items": deepcopy(self.snapshot.shop_items),
            "inventory_items": deepcopy(self.snapshot.inventory_items),
            "dialogue_history": [entry.to_dict() for entry in self.snapshot.dialogue_history],
            "dialogue_history_text": format_dialogue_history_text(self.snapshot.dialogue_history),
            "long_term_memory": [dict(entry) for entry in self.snapshot.long_term_memory],
        }


@dataclass(frozen=True, slots=True)
class SnapshotBuilderInput:
    state: CompanionState
    character_title: str
    character_description: str
    goal: str
    relationship_stage: str
    next_relationship_unlock: str
    current_motion: str
    motion_caption: str
    feedback: str
    delta_text: str
    allowed: bool
    tick_count: int
    events: list[CompanionEvent]
    actions: list[dict[str, object]]
    shop_items: list[dict[str, object]]
    inventory_items: list[dict[str, object]]
    item_feedback_icon: str | None
    proactive_feedback: dict[str, str] | None
    dialogue_history: tuple[DialogueHistoryEntry, ...] = ()
    long_term_memory: tuple[dict[str, str], ...] = ()
    relationship_presentation: RelationshipPresentation | None = None


@dataclass(frozen=True, slots=True)
class SnapshotContextFactory:
    state: CompanionState
    character_title: str
    character_description: str
    current_motion: str
    motion_caption: str
    feedback: str
    delta_text: str
    allowed: bool
    tick_count: int
    events: list[CompanionEvent]
    actions: list[dict[str, object]]
    shop_items: list[dict[str, object]]
    inventory_items: list[dict[str, object]]
    item_feedback_icon: str | None
    proactive_feedback: dict[str, str] | None
    dialogue_history: tuple[DialogueHistoryEntry, ...] = ()
    long_term_memory: tuple[dict[str, str], ...] = ()
    relationship_decorations: tuple[dict[str, str], ...] = ()

    def build_input(self) -> SnapshotBuilderInput:
        relationship = RelationshipService(self.state)
        return SnapshotBuilderInput(
            state=self.state,
            character_title=self.character_title,
            character_description=self.character_description,
            goal=describe_goal(self.state),
            relationship_stage=relationship.stage(),
            next_relationship_unlock=relationship.next_unlock(),
            relationship_presentation=relationship.presentation(self.relationship_decorations),
            current_motion=self.current_motion,
            motion_caption=self.motion_caption,
            feedback=self.feedback,
            delta_text=self.delta_text,
            allowed=self.allowed,
            tick_count=self.tick_count,
            events=self.events,
            actions=self.actions,
            shop_items=self.shop_items,
            inventory_items=self.inventory_items,
            item_feedback_icon=self.item_feedback_icon,
            proactive_feedback=self.proactive_feedback,
            dialogue_history=self.dialogue_history,
            long_term_memory=self.long_term_memory,
        )


@dataclass(frozen=True, slots=True)
class SnapshotBuilder:
    input: SnapshotBuilderInput

    def build(self) -> CompanionSnapshot:
        source = self.input
        relationship_presentation = source.relationship_presentation or RelationshipService(
            source.state
        ).presentation()
        return CompanionSnapshot(
            character_id=source.state.character_id,
            character_name=source.state.character_name,
            player_alias=getattr(source.state, "player_alias", ""),
            mode=source.state.mode,
            stats=CompanionStats.from_state(source.state),
            inventory=deepcopy(source.state.inventory),
            shop_items=deepcopy(source.shop_items),
            relationship_stage=source.relationship_stage,
            next_relationship_unlock=source.next_relationship_unlock,
            relationship_presentation=relationship_presentation,
            unlocks=list(source.state.unlocks),
            memory_log=deepcopy(source.state.memory_log),
            current_motion=source.current_motion,
            feedback=source.feedback,
            events=list(source.events),
            proactive_feedback=deepcopy(source.proactive_feedback),
            character_title=source.character_title,
            character_description=source.character_description,
            goal=source.goal,
            motion_caption=source.motion_caption,
            delta_text=source.delta_text,
            allowed=source.allowed,
            tick_count=source.tick_count,
            resting=source.state.resting,
            actions=deepcopy(source.actions),
            inventory_items=deepcopy(source.inventory_items),
            item_feedback_icon=source.item_feedback_icon,
            dialogue_history=tuple(source.dialogue_history),
            long_term_memory=tuple(dict(entry) for entry in source.long_term_memory[:MAX_LONG_TERM_MEMORY_SUMMARIES]),
        )
