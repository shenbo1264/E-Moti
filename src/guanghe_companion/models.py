from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ItemDefinition:
    item_id: str
    name: str
    category: str
    price: int
    effects: dict[str, float]
    icon: str = ""
    unlock_level: int = 1
    unlock_trust: float = 0


@dataclass(slots=True)
class CompanionState:
    character_id: str
    character_name: str
    focus: float
    charge: float
    stability: float
    mood: float
    trust: float
    exp: int
    level: int
    coins: int
    mode: str
    resting: bool
    inventory: dict[str, int]
    unlocks: list[str]
    current_goal_id: str
    last_interaction_at: int
    last_tick_at: int
    last_gift_item_id: str | None = None
    last_gift_at: int | None = None
    same_gift_chain: int = 0
    study_bonus_exp: int = 0
    memory_log: list[dict[str, object]] = field(default_factory=list)
    schema_version: int = 1


@dataclass(slots=True)
class ActionResult:
    state: CompanionState
    motion: str
    allowed: bool
    delta: dict[str, float]
    feedback: dict[str, str]
