from __future__ import annotations

import pytest

from guanghe_companion.focus_companion import FocusCompanionSettings
from guanghe_companion.focus_companion_runtime import FocusCompanionCoordinator


def settings() -> FocusCompanionSettings:
    return FocusCompanionSettings(
        enabled=True,
        threshold_minutes=50,
        break_minutes=5,
        cooldown_minutes=30,
        snooze_minutes=30,
        daily_limit=4,
    )


def test_coordinator_builds_one_permissioned_offer_and_waits() -> None:
    coordinator = FocusCompanionCoordinator(settings())

    events = coordinator.inject_demo_focus(now=10_000, focused_minutes=52)

    assert len(events) == 1
    assert events[0].event_type == "focus_break_offer"
    assert events[0].motion == "ConfusedShy"
    assert events[0].payload["requires_confirmation"] is True
    assert events[0].payload["computer_control"] is False
    assert coordinator.timer.active is False
    assert coordinator.inject_demo_focus(now=10_005, focused_minutes=52) == ()


def test_confirmation_is_required_before_local_skill_starts_and_completes() -> None:
    coordinator = FocusCompanionCoordinator(settings())
    coordinator.inject_demo_focus(now=20_000, focused_minutes=52)

    started = coordinator.confirm_break(now=20_010, duration_seconds_override=3)

    assert started.event_type == "focus_break_started"
    assert started.motion == "Sleep"
    assert coordinator.timer.active is True
    assert coordinator.tick(now=20_012) == ()

    completed = coordinator.tick(now=20_014)
    assert len(completed) == 1
    assert completed[0].event_type == "focus_break_completed"
    assert completed[0].memory_draft is not None
    assert completed[0].payload["state_mutation"] is False
    assert coordinator.tick(now=20_015) == ()


def test_confirm_without_pending_offer_is_rejected() -> None:
    coordinator = FocusCompanionCoordinator(settings())

    with pytest.raises(RuntimeError):
        coordinator.confirm_break(now=1)


def test_snooze_blocks_immediate_repeat_but_allows_later_offer() -> None:
    coordinator = FocusCompanionCoordinator(settings())
    coordinator.inject_demo_focus(now=30_000, focused_minutes=52)

    event = coordinator.snooze(now=30_010)
    assert event.event_type == "focus_break_snoozed"
    assert coordinator.inject_demo_focus(now=30_100, focused_minutes=55) == ()

    later = coordinator.inject_demo_focus(now=31_900, focused_minutes=82)
    assert len(later) == 1
    assert later[0].event_type == "focus_break_offer"


def test_mute_today_blocks_more_offers_until_day_rollover() -> None:
    coordinator = FocusCompanionCoordinator(settings())
    coordinator.inject_demo_focus(now=40_000, focused_minutes=52)
    muted = coordinator.mute_today(now=40_010)

    assert muted.event_type == "focus_break_muted_today"
    assert coordinator.snapshot(now=40_020).muted_today is True
    assert coordinator.inject_demo_focus(now=41_000, focused_minutes=65) == ()

    next_day = coordinator.inject_demo_focus(now=100_000, focused_minutes=52)
    assert len(next_day) == 1
    assert coordinator.snapshot(now=100_000).muted_today is False
