from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .capability_settings import ProactiveCompanionSettings
from .companion_moments import companion_moment_candidates
from .emotional_memory_reflection import MemoryRecollection
from .models import CompanionState

GLOBAL_COOLDOWN_KEY = "__global__"
PROACTIVE_REJECTION_COOLDOWN_KEY = "__rejection__"


@dataclass(frozen=True, slots=True)
class ProactiveFeedback:
    kind: str
    speech: str
    summary: str
    memory_source: MemoryRecollection | None = None

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
        updates = {self.feedback.kind: self.now, GLOBAL_COOLDOWN_KEY: self.now}
        if self.feedback.memory_source is not None:
            updates[self.feedback.memory_source.cooldown_key] = self.now
        return updates

    def daily_count_updates(self) -> dict[str, int]:
        if self.feedback is None:
            return {}
        return {daily_count_key(self.now): 1}

    def event_payload(self) -> dict[str, str] | None:
        if self.feedback is None:
            return None
        return {"kind": self.feedback.kind, "summary": self.feedback.summary}

    def memory_drafts(self) -> list[dict[str, object]]:
        if self.feedback is None or self.feedback.memory_source is not None:
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
        forced_kind: str = "",
        memory_candidate: MemoryRecollection | None = None,
        last_dialogue_at: int | None = None,
    ) -> None:
        self.state = state
        self.previous_state = previous_state
        self.now = now
        self.settings = settings
        self.last_proactive_at = last_proactive_at
        self.daily_counts = daily_counts
        self.perception_summary = perception_summary if isinstance(perception_summary, str) else ""
        self.tool_results = tuple(tool_results or ())
        self.forced_kind = forced_kind if isinstance(forced_kind, str) else ""
        self.memory_candidate = memory_candidate
        self.last_dialogue_at = last_dialogue_at

    def select_feedback(self) -> ProactiveFeedback | None:
        if not self._can_emit_any():
            return None
        candidates = companion_moment_candidates(
            state=self.state,
            previous_state=self.previous_state,
            now=self.now,
            perception_summary=self.perception_summary,
            tool_results=self.tool_results,
            allow_context_topic=self.settings.allow_context_topic,
        )
        for candidate in candidates:
            if candidate.kind in {"context_topic", "return_after_idle"}:
                remembered = self._memory_feedback()
                if remembered is not None:
                    return remembered
            if self.forced_kind and candidate.kind != self.forced_kind:
                continue
            if self._can_emit_kind(candidate.kind):
                return ProactiveFeedback(
                    kind=candidate.kind,
                    speech=candidate.speech,
                    summary=candidate.summary,
                )
        return self._memory_feedback()

    def _memory_feedback(self) -> ProactiveFeedback | None:
        candidate = self.memory_candidate
        if (candidate is None or candidate.character_id != self.state.character_id
                or (candidate.valid_until and self.now >= candidate.valid_until)
                or self.now - self.state.last_interaction_at < 300
                or (self.last_dialogue_at is not None and self.now - self.last_dialogue_at < 300)
                or (self.forced_kind and self.forced_kind != "memory_recollection")
                or not self._can_emit_kind("memory_recollection")):
            return None
        last_at = self.last_proactive_at.get(candidate.cooldown_key)
        if last_at is not None and self.now - last_at < 86400:
            return None
        speech = (f"你之前提过喜欢{candidate.interest_topic}，最近有新的发现吗？" if candidate.interest_topic
                  else f"我刚想起一件小事：{candidate.summary}")
        return ProactiveFeedback("memory_recollection", speech,
                                 candidate.summary, candidate)

    def select_decision(self, motion: str) -> ProactiveCompanionDecision:
        return ProactiveCompanionDecision(
            feedback=self.select_feedback(),
            now=self.now,
            motion=motion,
        )

    def _can_emit_any(self) -> bool:
        if not self.settings.enabled:
            return False
        if (self.last_dialogue_at is not None
                and self.now - self.last_dialogue_at < self.settings.global_cooldown_seconds):
            return False
        if self.settings.quiet_hours_enabled and _is_quiet_time(
            self.now,
            self.settings.quiet_start,
            self.settings.quiet_end,
        ):
            return False
        if self.daily_counts.get(daily_count_key(self.now), 0) >= self.settings.daily_limit:
            return False
        last_rejection = self.last_proactive_at.get(PROACTIVE_REJECTION_COOLDOWN_KEY)
        if last_rejection is not None and self.now - last_rejection < rejection_cooldown_seconds(self.settings):
            return False
        last_global = self.last_proactive_at.get(GLOBAL_COOLDOWN_KEY)
        if last_global is not None and self.now - last_global < self.settings.global_cooldown_seconds:
            return False
        return True

    def _can_emit_kind(self, kind: str) -> bool:
        last_at = self.last_proactive_at.get(kind)
        return last_at is None or self.now - last_at >= self.settings.interval_seconds

def daily_count_key(now: int) -> str:
    return str(max(0, int(now)) // 86_400)


def proactive_rejection_cooldown_updates(*, kind: str, now: int) -> dict[str, int]:
    timestamp = max(0, int(now))
    updates = {GLOBAL_COOLDOWN_KEY: timestamp, PROACTIVE_REJECTION_COOLDOWN_KEY: timestamp}
    if kind:
        updates[kind] = timestamp
    return updates


def rejection_cooldown_seconds(settings: ProactiveCompanionSettings) -> int:
    return min(86_400, max(settings.interval_seconds, settings.global_cooldown_seconds * 2))


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
