from __future__ import annotations

"""Lifecycle coordinator for E-Moti's optional heartbeat companion moment."""

from dataclasses import dataclass, field, replace
import json
from pathlib import Path
import time
from typing import Mapping

from .focus_companion import (
    ActivityKind,
    ActivitySample,
    FocusBreakOffer,
    FocusBreakPolicy,
    FocusCompanionCopy,
    FocusCompanionSettings,
    FocusObservation,
    FocusSessionTracker,
    LocalBreakTimer,
)


@dataclass(frozen=True, slots=True)
class FocusSkillEvent:
    event_type: str
    speech: str
    motion: str
    payload: Mapping[str, object] = field(default_factory=dict)
    memory_draft: Mapping[str, object] | None = None

    def to_public_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "type": self.event_type,
            "speech": self.speech,
            "motion": self.motion,
            "payload": dict(self.payload),
        }
        if self.memory_draft is not None:
            result["memory_draft"] = dict(self.memory_draft)
        return result


@dataclass(frozen=True, slots=True)
class FocusCompanionRuntimeSnapshot:
    observation: FocusObservation
    pending_offer: FocusBreakOffer | None
    timer: Mapping[str, object]
    offers_today: int
    muted_today: bool
    snoozed_until: float | None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "observation": self.observation.to_public_dict(),
            "pending_offer": self.pending_offer.to_public_dict() if self.pending_offer else None,
            "timer": dict(self.timer),
            "offers_today": self.offers_today,
            "muted_today": self.muted_today,
            "snoozed_until": self.snoozed_until,
        }


@dataclass(slots=True)
class FocusCompanionStateStore:
    """Persist only throttling choices; never persist process names or screenshots."""

    path: Path | str | None = None

    def load(self) -> dict[str, object]:
        if self.path is None:
            return {}
        target = Path(self.path)
        if not target.exists():
            return {}
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def save(self, payload: Mapping[str, object]) -> None:
        if self.path is None:
            return
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        safe_payload = {
            "schema_version": 1,
            "day_key": str(payload.get("day_key", "")),
            "offers_today": max(0, int(payload.get("offers_today", 0))),
            "muted_day_key": str(payload.get("muted_day_key", "")),
            "last_offer_at": float(payload["last_offer_at"])
            if payload.get("last_offer_at") is not None
            else None,
            "snoozed_until": float(payload["snoozed_until"])
            if payload.get("snoozed_until") is not None
            else None,
        }
        temporary.write_text(json.dumps(safe_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)


class FocusCompanionCoordinator:
    """Own consent, throttling, and one local break-timer Skill.

    This coordinator does not mutate the pet's growth state. The host translates
    returned events into the existing typed-event/presentation pipeline.
    """

    def __init__(
        self,
        settings: FocusCompanionSettings | None = None,
        *,
        tracker: FocusSessionTracker | None = None,
        policy: FocusBreakPolicy | None = None,
        timer: LocalBreakTimer | None = None,
        copy: FocusCompanionCopy | None = None,
        state_store: FocusCompanionStateStore | None = None,
    ) -> None:
        self.settings = (settings or FocusCompanionSettings()).normalized()
        self.copy = copy or FocusCompanionCopy()
        self.tracker = tracker or FocusSessionTracker(self.settings)
        self.policy = policy or FocusBreakPolicy(self.copy)
        self.timer = timer or LocalBreakTimer()
        self.state_store = state_store or FocusCompanionStateStore()
        self.observation = FocusObservation(
            ActivityKind.UNAVAILABLE,
            "等待授权",
            0,
            0.0,
            "not_started",
        )
        self.pending_offer: FocusBreakOffer | None = None
        restored = self.state_store.load()
        self.last_offer_at = _optional_float(restored.get("last_offer_at"))
        self.snoozed_until = _optional_float(restored.get("snoozed_until"))
        self.offers_today = max(0, _safe_int(restored.get("offers_today")))
        self._day_key = _safe_text(restored.get("day_key")) or None
        self._muted_day_key = _safe_text(restored.get("muted_day_key")) or None
        self._completion_reported_at: float | None = None

    def update_settings(self, settings: FocusCompanionSettings) -> None:
        self.settings = settings.normalized()
        self.tracker.settings = self.settings
        if not self.settings.enabled:
            self.pending_offer = None
            self.snoozed_until = None
            self.tracker.reset()
        self._persist()

    def process_sample(
        self,
        sample: ActivitySample,
        *,
        now: float | None = None,
        pet_stability: float,
        pet_mode: str,
    ) -> tuple[FocusSkillEvent, ...]:
        current = sample.observed_at if now is None else float(now)
        self._rollover_day(current)
        self.observation = self.tracker.update(sample)
        return self._evaluate(current, pet_stability=pet_stability, pet_mode=pet_mode)

    def inject_demo_focus(
        self,
        *,
        focused_minutes: int = 52,
        kind: ActivityKind = ActivityKind.CODING,
        now: float | None = None,
        pet_stability: float = 78.0,
        pet_mode: str = "Calm",
    ) -> tuple[FocusSkillEvent, ...]:
        current = time.time() if now is None else float(now)
        self._rollover_day(current)
        original_settings = self.settings
        demo_settings = replace(original_settings, enabled=True)
        self.settings = demo_settings
        self.tracker.settings = demo_settings
        try:
            self.observation = self.tracker.inject_demo_observation(
                focused_minutes=focused_minutes,
                kind=kind,
                observed_at=current,
            )
            return self._evaluate(current, pet_stability=pet_stability, pet_mode=pet_mode)
        finally:
            self.settings = original_settings
            self.tracker.settings = original_settings

    def confirm_break(
        self,
        *,
        now: float | None = None,
        duration_seconds_override: int | None = None,
    ) -> FocusSkillEvent:
        if self.pending_offer is None:
            raise RuntimeError("no focus break offer is waiting for confirmation")
        current = time.time() if now is None else float(now)
        offer = self.pending_offer
        duration_seconds = (
            int(duration_seconds_override)
            if duration_seconds_override is not None
            else offer.break_minutes * 60
        )
        self.timer.start(duration_seconds=duration_seconds, now=current)
        self.pending_offer = None
        self._completion_reported_at = None
        self._persist()
        return FocusSkillEvent(
            event_type="focus_break_started",
            speech=self.copy.break_started(offer.break_minutes),
            motion="Sleep",
            payload={
                "skill_id": "local_break_timer",
                "duration_seconds": duration_seconds,
                "display_break_minutes": offer.break_minutes,
                "requires_confirmation": True,
                "computer_control": False,
            },
        )

    def snooze(self, *, now: float | None = None) -> FocusSkillEvent:
        if self.pending_offer is None:
            raise RuntimeError("no focus break offer is waiting for a response")
        current = time.time() if now is None else float(now)
        self.pending_offer = None
        self.snoozed_until = current + self.settings.snooze_minutes * 60
        self.tracker.allow_reoffer_after_snooze()
        self._persist()
        return FocusSkillEvent(
            event_type="focus_break_snoozed",
            speech=self.copy.snoozed(),
            motion="Default",
            payload={"snooze_minutes": self.settings.snooze_minutes},
        )

    def mute_today(self, *, now: float | None = None) -> FocusSkillEvent:
        current = time.time() if now is None else float(now)
        self._rollover_day(current)
        self.pending_offer = None
        self.snoozed_until = None
        self._muted_day_key = self._day_key
        self.tracker.mark_offer_emitted()
        self._persist()
        return FocusSkillEvent(
            event_type="focus_break_muted_today",
            speech=self.copy.muted_today(),
            motion="Default",
            payload={"day": self._day_key or ""},
        )

    def tick(self, *, now: float | None = None) -> tuple[FocusSkillEvent, ...]:
        current = time.time() if now is None else float(now)
        was_active = self.timer.active
        remaining = self.timer.remaining_seconds(now=current)
        if not was_active or remaining > 0 or self.timer.completed_at is None:
            return ()
        if self._completion_reported_at == self.timer.completed_at:
            return ()
        self._completion_reported_at = self.timer.completed_at
        completed_minutes = max(1, round(self.timer.duration_seconds / 60))
        self.tracker.reset()
        return (
            FocusSkillEvent(
                event_type="focus_break_completed",
                speech=self.copy.completed(),
                motion="Default",
                payload={
                    "skill_id": "local_break_timer",
                    "duration_seconds": self.timer.duration_seconds,
                    "state_mutation": False,
                    "user_accepted": True,
                    "completed": True,
                    "contains_screen_content": False,
                },
                memory_draft={
                    "kind": "主动陪伴",
                    "summary": self.copy.memory_summary(completed_minutes),
                    "source": "focus_companion_skill",
                },
            ),
        )

    def cancel_break(self, *, now: float | None = None) -> FocusSkillEvent:
        self.timer.cancel(now=now)
        return FocusSkillEvent(
            event_type="focus_break_cancelled",
            speech=self.copy.cancelled(),
            motion="Default",
            payload={"skill_id": "local_break_timer"},
        )

    def snapshot(self, *, now: float | None = None) -> FocusCompanionRuntimeSnapshot:
        current = time.time() if now is None else float(now)
        self._rollover_day(current)
        return FocusCompanionRuntimeSnapshot(
            observation=self.observation,
            pending_offer=self.pending_offer,
            timer=self.timer.to_public_dict(now=current),
            offers_today=self.offers_today,
            muted_today=self._muted_day_key == self._day_key,
            snoozed_until=self.snoozed_until,
        )

    def _evaluate(
        self,
        now: float,
        *,
        pet_stability: float,
        pet_mode: str,
    ) -> tuple[FocusSkillEvent, ...]:
        if self.timer.active or self.pending_offer is not None:
            return ()
        if self._muted_day_key == self._day_key:
            return ()
        if self.snoozed_until is not None:
            if now < self.snoozed_until:
                return ()
            self.snoozed_until = None

        decision = self.policy.evaluate(
            self.observation,
            now=now,
            settings=self.settings,
            pet_stability=pet_stability,
            pet_mode=pet_mode,
            last_offer_at=self.last_offer_at,
            offers_today=self.offers_today,
            offer_emitted_for_session=self.tracker.offer_emitted_for_session,
        )
        if decision.offer is None:
            self._persist()
            return ()

        self.pending_offer = decision.offer
        self.last_offer_at = now
        self.offers_today += 1
        self.tracker.mark_offer_emitted()
        self._persist()
        return (
            FocusSkillEvent(
                event_type="focus_break_offer",
                speech=decision.offer.speech,
                motion="ConfusedShy",
                payload={
                    **decision.offer.to_public_dict(),
                    "requires_confirmation": True,
                    "computer_control": False,
                },
            ),
        )

    def _rollover_day(self, now: float) -> None:
        key = time.strftime("%Y-%m-%d", time.localtime(now))
        if key == self._day_key:
            return
        self._day_key = key
        self.offers_today = 0
        self._muted_day_key = None
        if self.snoozed_until is not None and self.snoozed_until < now:
            self.snoozed_until = None
        self._persist()

    def _persist(self) -> None:
        self.state_store.save(
            {
                "day_key": self._day_key or "",
                "offers_today": self.offers_today,
                "muted_day_key": self._muted_day_key or "",
                "last_offer_at": self.last_offer_at,
                "snoozed_until": self.snoozed_until,
            }
        )


def _safe_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _safe_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _optional_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
