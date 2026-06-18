from dataclasses import replace

from guanghe_companion.companion_moments import companion_moment_candidates, select_companion_moment
from guanghe_companion.engine import create_initial_state


def test_companion_moment_candidates_cover_daily_and_reaction_moments():
    state = create_initial_state(now=0)
    previous = replace(state)

    state.charge = 24
    low_charge = select_companion_moment(state=state, previous_state=previous, now=900)
    assert low_charge is not None
    assert low_charge.kind == "low_charge"
    assert "能量有点低" in low_charge.summary

    state = create_initial_state(now=8 * 3600)
    morning = select_companion_moment(state=state, previous_state=replace(state), now=8 * 3600)
    assert morning is not None
    assert morning.kind == "morning_greeting"

    state = create_initial_state(now=0)
    previous = replace(state, trust=34)
    state.trust = 35
    high_trust = select_companion_moment(state=state, previous_state=previous, now=120)
    assert high_trust is not None
    assert high_trust.kind == "high_trust"

    state = create_initial_state(now=0)
    state.last_gift_at = 100
    post_gift = select_companion_moment(state=state, previous_state=replace(state), now=130)
    assert post_gift is not None
    assert post_gift.kind == "post_gift"

    state = create_initial_state(now=0)
    state.last_interaction_at = 0
    idle = select_companion_moment(state=state, previous_state=replace(state), now=360)
    assert idle is not None
    assert idle.kind == "return_after_idle"


def test_companion_moment_candidates_prioritize_readonly_context_over_idle_return():
    state = create_initial_state(now=0)
    candidates = companion_moment_candidates(
        state=state,
        previous_state=replace(state),
        now=3600,
        perception_summary="IDE shows a failing pytest summary",
        tool_results=[{"title": "pytest", "summary": "fixture notes"}],
        allow_context_topic=True,
    )

    assert [candidate.kind for candidate in candidates][:2] == ["context_topic", "return_after_idle"]
    assert "pytest" in candidates[0].summary

