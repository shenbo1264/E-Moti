from dataclasses import replace

from guanghe_companion.capability_settings import ProactiveCompanionSettings
from guanghe_companion.engine import create_initial_state
from guanghe_companion.proactive_companion import (
    PROACTIVE_REJECTION_COOLDOWN_KEY,
    PROACTIVE_REJECTION_STREAK_KEY,
    GLOBAL_COOLDOWN_KEY,
    ProactiveCompanionDecision,
    ProactiveCompanionService,
    ProactiveFeedback,
    proactive_defer_updates,
    proactive_rejection_cooldown_updates,
    rejection_cooldown_seconds,
)


def test_default_settings_suppress_proactive_feedback() -> None:
    state = create_initial_state(now=0)
    state.charge = 24

    decision = ProactiveCompanionService(
        state=state,
        previous_state=replace(state),
        now=900,
        settings=ProactiveCompanionSettings(),
        last_proactive_at={},
        daily_counts={},
    ).select_decision(motion="Tick")

    assert isinstance(decision, ProactiveCompanionDecision)
    assert decision.feedback is None
    assert decision.effect == ""
    assert decision.cooldown_updates() == {}
    assert decision.daily_count_updates() == {}
    assert decision.memory_drafts() == []


def test_enabled_low_charge_feedback_respects_global_cooldown_and_daily_limit() -> None:
    state = create_initial_state(now=0)
    state.charge = 24
    settings = ProactiveCompanionSettings(enabled=True, global_cooldown_seconds=1800, daily_limit=1)

    first = ProactiveCompanionService(
        state=state,
        previous_state=replace(state),
        now=3600,
        settings=settings,
        last_proactive_at={},
        daily_counts={},
    ).select_decision(motion="Tick")

    assert isinstance(first.feedback, ProactiveFeedback)
    assert first.feedback.kind == "low_charge"
    assert first.cooldown_updates() == {"low_charge": 3600, "__global__": 3600}
    assert first.daily_count_updates() == {"0": 1}

    cooled_down_but_capped = ProactiveCompanionService(
        state=state,
        previous_state=replace(state),
        now=7200,
        settings=settings,
        last_proactive_at=first.cooldown_updates(),
        daily_counts=first.daily_count_updates(),
    ).select_feedback()

    assert cooled_down_but_capped is None

    next_day = ProactiveCompanionService(
        state=state,
        previous_state=replace(state),
        now=90_000,
        settings=settings,
        last_proactive_at=first.cooldown_updates(),
        daily_counts=first.daily_count_updates(),
    ).select_feedback()

    assert next_day is not None
    assert next_day.kind == "low_charge"


def test_quiet_hours_suppress_across_midnight() -> None:
    state = create_initial_state(now=0)
    state.charge = 24
    settings = ProactiveCompanionSettings(
        enabled=True,
        quiet_hours_enabled=True,
        quiet_start="23:00",
        quiet_end="08:00",
    )

    suppressed = ProactiveCompanionService(
        state=state,
        previous_state=replace(state),
        now=23 * 3600 + 30 * 60,
        settings=settings,
        last_proactive_at={},
        daily_counts={},
    ).select_feedback()

    allowed = ProactiveCompanionService(
        state=state,
        previous_state=replace(state),
        now=12 * 3600,
        settings=settings,
        last_proactive_at={},
        daily_counts={},
    ).select_feedback()

    assert suppressed is None
    assert allowed is not None


def test_context_topic_uses_readonly_perception_and_tool_results() -> None:
    state = create_initial_state(now=0)
    state.charge = 80
    state.mood = 70
    settings = ProactiveCompanionSettings(enabled=True, allow_context_topic=True)

    feedback = ProactiveCompanionService(
        state=state,
        previous_state=replace(state),
        now=3600,
        settings=settings,
        last_proactive_at={},
        daily_counts={},
        perception_summary="IDE shows a failing pytest summary",
        tool_results=[{"source": "web_search", "title": "pytest", "summary": "fixture troubleshooting notes"}],
    ).select_feedback()

    assert feedback is not None
    assert feedback.kind == "context_topic"
    assert "pytest" in feedback.summary
    assert "failing pytest" in feedback.summary


def test_context_topic_can_be_disabled() -> None:
    state = create_initial_state(now=0)
    state.last_interaction_at = 3550
    settings = ProactiveCompanionSettings(enabled=True, allow_context_topic=False)

    feedback = ProactiveCompanionService(
        state=state,
        previous_state=replace(state),
        now=3600,
        settings=settings,
        last_proactive_at={},
        daily_counts={},
        perception_summary="IDE shows a failing pytest summary",
    ).select_feedback()

    assert feedback is None


def test_rejection_feedback_extends_global_cooldown() -> None:
    state = create_initial_state(now=0)
    state.charge = 24
    settings = ProactiveCompanionSettings(
        enabled=True,
        interval_seconds=60,
        global_cooldown_seconds=60,
    )

    first = ProactiveCompanionService(
        state=state,
        previous_state=replace(state),
        now=100,
        settings=settings,
        last_proactive_at={},
        daily_counts={},
    ).select_decision(motion="Tick")
    assert first.feedback is not None

    rejection_updates = proactive_rejection_cooldown_updates(
        kind=first.feedback.kind,
        now=100,
    )

    assert rejection_updates == {
        "low_charge": 100,
        GLOBAL_COOLDOWN_KEY: 100,
        PROACTIVE_REJECTION_COOLDOWN_KEY: 100,
        PROACTIVE_REJECTION_STREAK_KEY: 1,
    }
    assert (
        ProactiveCompanionService(
            state=state,
            previous_state=replace(state),
            now=219,
            settings=settings,
            last_proactive_at=rejection_updates,
            daily_counts={},
        ).select_feedback()
        is None
    )
    assert (
        ProactiveCompanionService(
            state=state,
            previous_state=replace(state),
            now=221,
            settings=settings,
            last_proactive_at=rejection_updates,
            daily_counts={},
        ).select_feedback()
        is not None
    )


def _service(state, now, **kwargs):
    defaults = dict(settings=ProactiveCompanionSettings(enabled=True), last_proactive_at={}, daily_counts={})
    return ProactiveCompanionService(state=state, previous_state=replace(state), now=now, **{**defaults, **kwargs})


def _low_charge():
    state = create_initial_state(now=0)
    state.charge = 24
    return state


def test_consecutive_rejections_back_off_and_a_reply_resets_them() -> None:
    first = proactive_rejection_cooldown_updates(kind="x", now=1000)
    second = proactive_rejection_cooldown_updates(kind="x", now=9000, history=first)
    third = proactive_rejection_cooldown_updates(kind="x", now=20000, history=second)
    assert [row[PROACTIVE_REJECTION_STREAK_KEY] for row in (first, second, third)] == [1, 2, 3]

    settings = ProactiveCompanionSettings(enabled=True)
    assert rejection_cooldown_seconds(settings, 3) == 4 * rejection_cooldown_seconds(settings, 1)
    assert rejection_cooldown_seconds(settings, 50) == 7 * 86_400

    reset = proactive_rejection_cooldown_updates(kind="x", now=30000, history=third, last_dialogue_at=25000)
    assert reset[PROACTIVE_REJECTION_STREAK_KEY] == 1


def test_streak_extends_the_quiet_period() -> None:
    settings = ProactiveCompanionSettings(enabled=True)
    history = {PROACTIVE_REJECTION_COOLDOWN_KEY: 1000, PROACTIVE_REJECTION_STREAK_KEY: 3}
    now = 1000 + rejection_cooldown_seconds(settings, 1) + 1
    assert _service(_low_charge(), now, last_proactive_at=history).select_feedback() is None


def test_deferred_until_blocks_then_releases() -> None:
    updates = proactive_defer_updates(now=1000, seconds=3600)
    state = _low_charge()
    assert _service(state, 2000, last_proactive_at=updates).select_feedback() is None
    assert _service(state, 4601, last_proactive_at=updates).select_feedback() is not None


def test_focus_silences_every_proactive_kind() -> None:
    assert _service(_low_charge(), 900, focus_active=True).select_feedback() is None


def test_quiet_hours_and_morning_follow_the_real_clock_not_logical_seconds() -> None:
    settings = ProactiveCompanionSettings(enabled=True, quiet_hours_enabled=True,
                                          quiet_start="23:00", quiet_end="08:00")
    state = _low_charge()
    assert _service(state, 12 * 3600, settings=settings, wall_seconds=2 * 3600).select_feedback() is None
    assert _service(state, 2 * 3600, settings=settings, wall_seconds=12 * 3600).select_feedback() is not None

    calm = create_initial_state(now=8 * 3600 - 10)
    assert _service(calm, 8 * 3600, wall_seconds=20 * 3600).select_feedback() is None
    calm = create_initial_state(now=20 * 3600 - 10)
    assert _service(calm, 20 * 3600, wall_seconds=8 * 3600).select_feedback().kind == "morning_greeting"


def test_long_absence_is_a_gentle_return_without_guilt() -> None:
    state = create_initial_state(now=995)
    feedback = _service(state, 1000, wall_seconds=12 * 3600, away_seconds=4 * 86_400).select_feedback()
    assert feedback.kind == "long_absence"
    assert "？" not in feedback.speech


def test_companionship_does_not_depend_on_work_context() -> None:
    feedback = _service(_low_charge(), 900, wall_seconds=12 * 3600).select_feedback()
    assert feedback is not None
    assert all(word not in feedback.speech for word in ("任务", "工作", "进度"))
