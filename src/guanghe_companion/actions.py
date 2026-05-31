from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import CompanionState

ActionSource = Literal["control_panel", "desktop_pet", "shortcut", "demo", "test"]


@dataclass(frozen=True, slots=True)
class ActionSpec:
    action_id: str
    label: str
    motion: str


@dataclass(frozen=True, slots=True)
class CompanionAction:
    action_id: str
    label: str
    motion: str
    enabled: bool

    def to_legacy_dict(self) -> dict[str, object]:
        return {
            "action_id": self.action_id,
            "label": self.label,
            "motion": self.motion,
            "enabled": self.enabled,
        }


@dataclass(frozen=True, slots=True)
class CompanionActionRequest:
    action_id: str
    source: ActionSource = "control_panel"


ACTION_SPECS: tuple[ActionSpec, ...] = (
    ActionSpec("touch", "轻触", "TouchHead"),
    ActionSpec("soothe", "安抚", "Comfort"),
    ActionSpec("rest", "休息", "Sleep"),
    ActionSpec("study", "共同学习", "Study"),
    ActionSpec("play", "共同娱乐", "Play"),
    ActionSpec("drag", "拖拽/提起", "Raised"),
)


class CompanionActionLayer:
    def __init__(self, state: CompanionState) -> None:
        self.state = state

    def available_actions(self) -> list[CompanionAction]:
        actions: list[CompanionAction] = []
        for spec in ACTION_SPECS:
            label = "结束休息" if spec.action_id == "rest" and self.state.resting else spec.label
            actions.append(
                CompanionAction(
                    action_id=spec.action_id,
                    label=label,
                    motion=spec.motion,
                    enabled=self.is_action_enabled(spec.action_id),
                )
            )
        return actions

    def is_action_enabled(self, action_id: str) -> bool:
        if self.state.mode == "Overload" and action_id not in {"soothe", "rest"}:
            return False
        if action_id == "study" and self.state.focus < 20:
            return False
        if action_id == "play" and self.state.charge < 10:
            return False
        return True


def action_label(action_id: str) -> str:
    for spec in ACTION_SPECS:
        if spec.action_id == action_id:
            return spec.label
    return action_id
