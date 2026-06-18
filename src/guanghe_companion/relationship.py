from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping

from .models import CompanionState


RELATIONSHIP_UNLOCK_LINES: dict[str, str] = {
    "unlock_first_nickname": "第一次主动称呼解锁了。她开始用更亲近的方式回应你。",
    "unlock_shared_ritual": "共同日常仪式解锁了。你们之间有了一段固定的小默契。",
}

MAX_PLAYER_ALIAS_LENGTH = 20
DEFAULT_RELATIONSHIP_DECORATIONS: tuple[dict[str, str], ...] = (
    {
        "unlock_id": "unlock_first_nickname",
        "item_id": "star_hairpin",
        "label": "星形发夹",
        "icon": "item_icons/star_hairpin.png",
    },
    {
        "unlock_id": "unlock_shared_ritual",
        "item_id": "comet_ribbon",
        "label": "彗尾丝带",
        "icon": "item_icons/comet_ribbon.png",
    },
)


@dataclass(frozen=True, slots=True)
class RelationshipPresentation:
    address_line: str
    tone_label: str
    micro_motion: str
    unlocked_decorations: list[dict[str, str]]

    def to_dict(self) -> dict[str, object]:
        return {
            "address_line": self.address_line,
            "tone_label": self.tone_label,
            "micro_motion": self.micro_motion,
            "unlocked_decorations": deepcopy(self.unlocked_decorations),
        }


class RelationshipService:
    def __init__(self, state: CompanionState) -> None:
        self.state = state

    def set_player_alias(self, alias: str) -> str:
        normalized = normalize_player_alias(alias)
        self.state.player_alias = normalized
        return normalized

    def stage(self) -> str:
        if self.state.trust >= 35:
            return "共同日常"
        if self.state.trust >= 20:
            return "熟悉的陪伴"
        return "初识"

    def presentation(
        self,
        decorations: Iterable[Mapping[str, str]] | None = None,
    ) -> RelationshipPresentation:
        stage = self.stage()
        alias = normalize_player_alias(getattr(self.state, "player_alias", ""))
        if alias and "unlock_first_nickname" in self.state.unlocks:
            address_line = f"{self.state.character_name}会这样称呼你：{alias}"
        elif alias:
            address_line = f"{self.state.character_name}记得你：{alias}"
        else:
            address_line = f"{self.state.character_name}还在认识你"
        return RelationshipPresentation(
            address_line=address_line,
            tone_label=_tone_label(stage),
            micro_motion=_micro_motion(stage),
            unlocked_decorations=_unlocked_decoration_badges(
                self.state.unlocks,
                decorations or DEFAULT_RELATIONSHIP_DECORATIONS,
            ),
        )

    def next_unlock(self) -> str:
        if "unlock_first_nickname" not in self.state.unlocks:
            return "信任达到 20：解锁第一次主动称呼"
        if "unlock_shared_ritual" not in self.state.unlocks:
            return "信任达到 35：解锁共同日常仪式"
        return "继续保持稳定陪伴，观察她的主动回应"

    def new_unlocks(self, previous_unlocks: set[str]) -> list[str]:
        return [unlock_id for unlock_id in self.state.unlocks if unlock_id not in previous_unlocks]

    def unlock_feedback(self, unlocks: list[str]) -> str:
        return " ".join(
            RELATIONSHIP_UNLOCK_LINES[unlock_id]
            for unlock_id in unlocks
            if unlock_id in RELATIONSHIP_UNLOCK_LINES
        )

    def unlock_memory_drafts(self, unlocks: list[str], motion: str) -> list[dict[str, object]]:
        return [
            {
                "kind": "关系解锁",
                "summary": RELATIONSHIP_UNLOCK_LINES[unlock_id],
                "motion": motion,
            }
            for unlock_id in unlocks
            if unlock_id in RELATIONSHIP_UNLOCK_LINES
        ]

    def unlock_event_payloads(self, unlocks: list[str]) -> list[dict[str, str]]:
        return [
            {
                "stage": self.stage(),
                "unlock_id": unlock_id,
                "message": RELATIONSHIP_UNLOCK_LINES[unlock_id],
            }
            for unlock_id in unlocks
            if unlock_id in RELATIONSHIP_UNLOCK_LINES
        ]


def normalize_player_alias(value: object) -> str:
    if not isinstance(value, str):
        return ""
    normalized = " ".join(_replace_control_characters(value).strip().split())
    return normalized[:MAX_PLAYER_ALIAS_LENGTH]


def _tone_label(stage: str) -> str:
    if stage == "共同日常":
        return "共同日常"
    if stage == "熟悉的陪伴":
        return "熟悉陪伴"
    return "轻声试探"


def _micro_motion(stage: str) -> str:
    if stage == "共同日常":
        return "贴近点头"
    if stage == "熟悉的陪伴":
        return "靠近一点"
    return "轻轻眨眼"


def _unlocked_decoration_badges(
    unlocks: Iterable[str],
    decorations: Iterable[Mapping[str, str]],
) -> list[dict[str, str]]:
    unlocked = set(unlocks)
    badges: list[dict[str, str]] = []
    for decoration in decorations:
        unlock_id = decoration.get("unlock_id")
        item_id = decoration.get("item_id")
        label = decoration.get("label")
        icon = decoration.get("icon")
        if unlock_id not in unlocked:
            continue
        if not all(isinstance(value, str) and value.strip() for value in (item_id, label, icon)):
            continue
        badges.append(
            {
                "item_id": item_id.strip(),
                "label": _replace_control_characters(label.strip()),
                "icon": icon.strip(),
            }
        )
    return badges


def _replace_control_characters(value: str) -> str:
    return "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value)
