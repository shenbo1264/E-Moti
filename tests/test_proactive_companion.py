from dataclasses import replace

from guanghe_companion.capability_settings import ProactiveCompanionSettings
from guanghe_companion.engine import create_initial_state
from guanghe_companion.proactive_companion import (
    ProactiveCompanionDecision,
    ProactiveCompanionService,
    ProactiveFeedback,
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
