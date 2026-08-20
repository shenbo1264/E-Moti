from __future__ import annotations

from guanghe_companion.focus_companion import (
    ActivityKind,
    ActivitySample,
    ApplicationClassifier,
    FocusBreakPolicy,
    FocusCompanionSettings,
    FocusSessionTracker,
    LocalBreakTimer,
)


def test_classifier_keeps_only_coarse_activity_category() -> None:
    kind, label, confidence = ApplicationClassifier().classify(r"C:\Program Files\Microsoft VS Code\Code.exe")

    assert kind == ActivityKind.CODING
    assert label == "写代码"
    assert confidence >= 0.9


def test_tracker_accumulates_deep_work_across_coding_and_writing_apps() -> None:
    tracker = FocusSessionTracker(FocusCompanionSettings(session_gap_grace_seconds=60))
    first = tracker.update(ActivitySample(100.0, ActivityKind.CODING, "Code", idle_seconds=0))
    second = tracker.update(ActivitySample(160.0, ActivityKind.WRITING, "Obsidian", idle_seconds=0))

    assert first.continuous_seconds == 0
    assert second.continuous_seconds == 60
    assert second.kind == ActivityKind.WRITING


def test_tracker_resets_after_user_idle() -> None:
    tracker = FocusSessionTracker(FocusCompanionSettings(idle_reset_seconds=120))
    tracker.update(ActivitySample(100.0, ActivityKind.CODING, "Code", idle_seconds=0))
    observation = tracker.update(ActivitySample(240.0, ActivityKind.CODING, "Code", idle_seconds=130))

    assert observation.kind == ActivityKind.IDLE
    assert observation.continuous_seconds == 0


def test_policy_offers_break_after_threshold_but_never_executes_it() -> None:
    settings = FocusCompanionSettings(enabled=True, threshold_minutes=50, break_minutes=5)
    tracker = FocusSessionTracker(settings)
    observation = tracker.inject_demo_observation(focused_minutes=52, observed_at=10_000)

    decision = FocusBreakPolicy().evaluate(
        observation,
        now=10_000,
        settings=settings,
        pet_stability=78,
        pet_mode="Calm",
    )

    assert decision.allowed is True
    assert decision.offer is not None
    assert decision.offer.kind == "focus_break_offer"
    assert decision.offer.primary_action_id == "start_focus_break"
    assert "52 分钟" in decision.offer.speech
    assert "5 分钟" in decision.offer.speech
    assert "陪我" in decision.offer.speech


def test_policy_respects_pet_state_session_guard_and_cooldown() -> None:
    settings = FocusCompanionSettings(enabled=True, threshold_minutes=50, cooldown_minutes=30)
    tracker = FocusSessionTracker(settings)
    observation = tracker.inject_demo_observation(focused_minutes=52, observed_at=10_000)
    policy = FocusBreakPolicy()

    assert policy.evaluate(
        observation,
        now=10_000,
        settings=settings,
        pet_stability=20,
        pet_mode="Overload",
    ).reason == "pet_state_blocks_offer"

    assert policy.evaluate(
        observation,
        now=10_000,
        settings=settings,
        pet_stability=78,
        pet_mode="Calm",
        offer_emitted_for_session=True,
    ).reason == "already_offered_this_session"

    assert policy.evaluate(
        observation,
        now=10_000,
        settings=settings,
        pet_stability=78,
        pet_mode="Calm",
        last_offer_at=9_000,
    ).reason == "cooldown"


def test_local_break_timer_starts_only_after_explicit_call() -> None:
    timer = LocalBreakTimer()
    assert timer.active is False
    assert timer.remaining_seconds(now=0) == 0

    timer.start(duration_seconds=300, now=100)
    assert timer.active is True
    assert timer.remaining_seconds(now=160) == 240
    assert timer.remaining_seconds(now=400) == 0
    assert timer.active is False
    assert timer.completed_at == 400


def test_runtime_requires_confirmation_before_starting_break() -> None:
    from guanghe_companion.focus_companion import FocusCompanionRuntime, FocusCompanionSettings

    runtime = FocusCompanionRuntime(settings=FocusCompanionSettings(enabled=True))
    offered = runtime.inject_demo_offer(now=10_000, focused_minutes=52)

    assert offered.event_type == "focus_break_offer"
    assert runtime.timer.active is False

    started = runtime.accept_break(now=10_001)
    assert started.event_type == "focus_break_started"
    assert runtime.timer.active is True


def test_runtime_snooze_and_today_mute_are_enforced() -> None:
    from guanghe_companion.focus_companion import FocusCompanionRuntime, FocusCompanionSettings

    runtime = FocusCompanionRuntime(settings=FocusCompanionSettings(enabled=True, cooldown_minutes=30))
    runtime.inject_demo_offer(now=10_000)
    snoozed = runtime.snooze(now=10_001)
    assert snoozed.event_type == "focus_break_snoozed"

    sample = ActivitySample(10_100, ActivityKind.CODING, "Code", idle_seconds=0)
    suppressed = runtime.poll(now=10_100, pet_stability=78, pet_mode="Calm", sample=sample)
    assert suppressed.payload["reason"] == "snoozed"

    runtime.inject_demo_offer(now=100_000)
    muted = runtime.mute_for_today(now=100_001)
    assert muted.event_type == "focus_break_muted"
    suppressed_today = runtime.poll(
        now=100_100,
        pet_stability=78,
        pet_mode="Calm",
        sample=ActivitySample(100_100, ActivityKind.CODING, "Code", idle_seconds=0),
    )
    assert suppressed_today.payload["reason"] == "muted_for_today"


def test_runtime_completion_returns_local_memory_draft_without_growth_mutation() -> None:
    from guanghe_companion.focus_companion import FocusCompanionRuntime, FocusCompanionSettings

    runtime = FocusCompanionRuntime(
        settings=FocusCompanionSettings(enabled=True, break_minutes=1)
    )
    runtime.inject_demo_offer(now=10_000)
    runtime.accept_break(now=10_001)
    completed = runtime.timer_status(now=10_061)

    assert completed.event_type == "focus_break_completed"
    assert completed.payload["growth_state_mutated"] is False
    assert completed.payload["memory_draft"]["kind"] == "主动陪伴"


def test_policy_respects_quiet_hours_and_today_mute() -> None:
    settings = FocusCompanionSettings(enabled=True, threshold_minutes=50)
    observation = FocusSessionTracker(settings).inject_demo_observation(focused_minutes=52, observed_at=10_000)
    policy = FocusBreakPolicy()

    assert policy.evaluate(
        observation,
        now=10_000,
        settings=settings,
        pet_stability=78,
        pet_mode="Calm",
        quiet_hours_active=True,
    ).reason == "quiet_hours"

    assert policy.evaluate(
        observation,
        now=10_000,
        settings=settings,
        pet_stability=78,
        pet_mode="Calm",
        muted_for_today=True,
    ).reason == "muted_for_today"


def test_tracker_keeps_explicit_focus_kind_without_app_label() -> None:
    tracker = FocusSessionTracker(FocusCompanionSettings(session_gap_grace_seconds=60))
    tracker.update(ActivitySample(100.0, ActivityKind.CODING, "", idle_seconds=0))
    observation = tracker.update(ActivitySample(130.0, ActivityKind.CODING, "", idle_seconds=0))

    assert observation.activity_label == "写代码"
    assert observation.confidence >= 0.9
    assert observation.continuous_seconds == 30


def test_policy_respects_configured_quiet_hours() -> None:
    import time

    settings = FocusCompanionSettings(
        enabled=True,
        threshold_minutes=50,
        quiet_hours_enabled=True,
        quiet_start="00:00",
        quiet_end="23:59",
    )
    tracker = FocusSessionTracker(settings)
    now = time.time()
    observation = tracker.inject_demo_observation(focused_minutes=52, observed_at=now)

    decision = FocusBreakPolicy().evaluate(
        observation,
        now=now,
        settings=settings,
        pet_stability=78,
        pet_mode="Calm",
    )

    assert decision.reason == "quiet_hours"
