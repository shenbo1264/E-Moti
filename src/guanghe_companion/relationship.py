from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .models import CompanionState


RELATIONSHIP_UNLOCK_LINES: dict[str, str] = {
    "unlock_first_nickname": "第一次主动称呼解锁了。她开始用更亲近的方式回应你。",
    "unlock_shared_ritual": "共同日常仪式解锁了。你们之间有了一段固定的小默契。",
}

PROACTIVE_COOLDOWN_SECONDS = 120


@dataclass(frozen=True, slots=True)
class ProactiveFeedback:
    kind: str
    speech: str
    summary: str

    def to_legacy_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "speech": self.speech,
            "summary": self.summary,
        }


class RelationshipService:
    def __init__(self, state: CompanionState) -> None:
        self.state = state

    def stage(self) -> str:
        if self.state.trust >= 35:
            return "共同日常"
        if self.state.trust >= 20:
            return "熟悉的陪伴"
        return "初识"

    def next_unlock(self) -> str:
        if "unlock_first_nickname" not in self.state.unlocks:
            return "信任达到 20：解锁第一次主动称呼"
        if "unlock_shared_ritual" not in self.state.unlocks:
            return "信任达到 35：解锁共同日常仪式"
        return "继续保持稳定陪伴，观察她的主动回应"

    def new_unlocks(self, previous_unlocks: set[str]) -> list[str]:
        return [unlock_id for unlock_id in self.state.unlocks if unlock_id not in previous_unlocks]

    def unlock_feedback(self, unlocks: list[str]) -> str:
        return " ".join(RELATIONSHIP_UNLOCK_LINES[unlock_id] for unlock_id in unlocks if unlock_id in RELATIONSHIP_UNLOCK_LINES)

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


class ProactiveCompanionService:
    def __init__(
        self,
        state: CompanionState,
        previous_state: CompanionState,
        now: int,
        last_proactive_at: Mapping[str, int],
    ) -> None:
        self.state = state
        self.previous_state = previous_state
        self.now = now
        self.last_proactive_at = last_proactive_at

    def select_feedback(self) -> ProactiveFeedback | None:
        idle_seconds = self.now - self.state.last_interaction_at
        if self.state.charge < 25 and self._can_emit("low_charge"):
            line = self._line("low_charge")
            return ProactiveFeedback(
                kind="low_charge",
                speech=line,
                summary=f"能量有点低时主动陪伴：{line}",
            )
        if (
            idle_seconds > 60
            and self.state.mood <= 35
            and self.state.mood < self.previous_state.mood
            and self._can_emit("low_mood")
        ):
            line = self._line("low_mood")
            return ProactiveFeedback(
                kind="low_mood",
                speech=line,
                summary=f"久未互动后主动陪伴：{line}",
            )
        return None

    def _can_emit(self, kind: str) -> bool:
        last_at = self.last_proactive_at.get(kind)
        return last_at is None or self.now - last_at >= PROACTIVE_COOLDOWN_SECONDS

    def _line(self, kind: str) -> str:
        has_ritual = "unlock_shared_ritual" in self.state.unlocks
        has_nickname = "unlock_first_nickname" in self.state.unlocks
        if kind == "low_charge":
            if has_ritual:
                return "像我们的日常小仪式一样，先把节奏放轻一点吧。我的能量有点低，陪你安静待一会儿也很好。"
            if has_nickname:
                return "现在可以更亲近一点叫你了。能量有点低，我想挨着你慢慢缓一会儿。"
            return "能量有点低了。我会把亮度放轻一点；你想休息或给我一点小点心都可以。"
        if has_ritual:
            return "刚才安静得有点久，我还在这里。按我们的小默契，我先轻轻靠近你。"
        if has_nickname:
            return "刚才安静得有点久，我还在这里。现在我可以更自然地靠近你一点。"
        return "刚才安静得有点久，我还在这里。你不用立刻回应，我只是想靠近一点。"
