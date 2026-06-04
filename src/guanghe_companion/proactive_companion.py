from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .capability_settings import ProactiveCompanionSettings
from .models import CompanionState

GLOBAL_COOLDOWN_KEY = "__global__"
MAX_CONTEXT_TOPIC_LENGTH = 80


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


@dataclass(frozen=True, slots=True)
class ProactiveCompanionDecision:
    feedback: ProactiveFeedback | None
    now: int
    motion: str

    @property
    def effect(self) -> str:
        return "ATTENTION" if self.feedback else ""

    def to_legacy_feedback(self) -> dict[str, str] | None:
        return self.feedback.to_legacy_dict() if self.feedback else None

    def cooldown_updates(self) -> dict[str, int]:
        if self.feedback is None:
            return {}
        return {self.feedback.kind: self.now, GLOBAL_COOLDOWN_KEY: self.now}

    def daily_count_updates(self) -> dict[str, int]:
        if self.feedback is None:
            return {}
        return {daily_count_key(self.now): 1}

    def event_payload(self) -> dict[str, str] | None:
        if self.feedback is None:
            return None
        return {"kind": self.feedback.kind, "summary": self.feedback.summary}

    def memory_drafts(self) -> list[dict[str, object]]:
        if self.feedback is None:
            return []
        return [
            {
                "kind": "主动陪伴",
                "summary": self.feedback.summary,
                "motion": self.motion,
            }
        ]


class ProactiveCompanionService:
    def __init__(
        self,
        *,
        state: CompanionState,
        previous_state: CompanionState,
        now: int,
        settings: ProactiveCompanionSettings,
        last_proactive_at: Mapping[str, int],
        daily_counts: Mapping[str, int],
        perception_summary: str = "",
        tool_results: Sequence[Mapping[str, object]] | None = None,
    ) -> None:
        self.state = state
        self.previous_state = previous_state
        self.now = now
        self.settings = settings
        self.last_proactive_at = last_proactive_at
        self.daily_counts = daily_counts
        self.perception_summary = perception_summary if isinstance(perception_summary, str) else ""
        self.tool_results = tuple(tool_results or ())

    def select_feedback(self) -> ProactiveFeedback | None:
        if not self._can_emit_any():
            return None
        idle_seconds = self.now - self.state.last_interaction_at
        if self.state.charge < 25 and self._can_emit_kind("low_charge"):
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
            and self._can_emit_kind("low_mood")
        ):
            line = self._line("low_mood")
            return ProactiveFeedback(
                kind="low_mood",
                speech=line,
                summary=f"久未互动后主动陪伴：{line}",
            )
        if self.settings.allow_context_topic and self._can_emit_kind("context_topic"):
            topic = self._context_topic()
            if topic:
                line = f"我看到你可能在处理 {topic}。不用马上回应，我只是轻轻陪你确认一下节奏。"
                return ProactiveFeedback(
                    kind="context_topic",
                    speech=line,
                    summary=f"只读上下文主动陪伴：{topic}",
                )
        return None

    def select_decision(self, motion: str) -> ProactiveCompanionDecision:
        return ProactiveCompanionDecision(
            feedback=self.select_feedback(),
            now=self.now,
            motion=motion,
        )

    def _can_emit_any(self) -> bool:
        if not self.settings.enabled:
            return False
        if self.settings.quiet_hours_enabled and _is_quiet_time(
            self.now,
            self.settings.quiet_start,
            self.settings.quiet_end,
        ):
            return False
        if self.daily_counts.get(daily_count_key(self.now), 0) >= self.settings.daily_limit:
            return False
        last_global = self.last_proactive_at.get(GLOBAL_COOLDOWN_KEY)
        if last_global is not None and self.now - last_global < self.settings.global_cooldown_seconds:
            return False
        return True

    def _can_emit_kind(self, kind: str) -> bool:
        last_at = self.last_proactive_at.get(kind)
        return last_at is None or self.now - last_at >= self.settings.interval_seconds

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

    def _context_topic(self) -> str:
        parts: list[str] = []
        if self.perception_summary.strip():
            parts.append(self.perception_summary)
        for item in self.tool_results:
            title = item.get("title")
            summary = item.get("summary")
            if isinstance(title, str) and title.strip():
                parts.append(title)
            if isinstance(summary, str) and summary.strip():
                parts.append(summary)
            if parts:
                break
        return _sanitize_topic(" / ".join(parts))


def daily_count_key(now: int) -> str:
    return str(max(0, int(now)) // 86_400)


def _is_quiet_time(now: int, quiet_start: str, quiet_end: str) -> bool:
    current = max(0, int(now)) % 86_400
    start = _time_to_seconds(quiet_start)
    end = _time_to_seconds(quiet_end)
    if start == end:
        return False
    if start < end:
        return start <= current < end
    return current >= start or current < end


def _time_to_seconds(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 3600 + int(minute) * 60


def _sanitize_topic(value: str) -> str:
    cleaned = " ".join(value.replace("\n", " ").replace("\r", " ").split())
    return cleaned[:MAX_CONTEXT_TOPIC_LENGTH]
