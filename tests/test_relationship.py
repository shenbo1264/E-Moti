from dataclasses import replace

from guanghe_companion.engine import create_initial_state
from guanghe_companion.relationship import (
    ProactiveCompanionService,
    ProactiveFeedback,
    RelationshipService,
)


def test_relationship_service_reports_stage_next_unlock_and_memory_drafts():
    state = create_initial_state(now=0)
    service = RelationshipService(state)

    assert service.stage() == "初识"
    assert "信任达到 20" in service.next_unlock()

    state.trust = 20
    state.unlocks = ["unlock_first_nickname"]
    unlocks = service.new_unlocks(previous_unlocks=set())
    drafts = service.unlock_memory_drafts(unlocks, motion="TouchHead")

    assert service.stage() == "熟悉的陪伴"
    assert "信任达到 35" in service.next_unlock()
    assert unlocks == ["unlock_first_nickname"]
    assert "第一次主动称呼" in service.unlock_feedback(unlocks)
    assert drafts == [
        {
            "kind": "关系解锁",
            "summary": "第一次主动称呼解锁了。她开始用更亲近的方式回应你。",
            "motion": "TouchHead",
        }
    ]


def test_relationship_service_reports_final_stage_after_ritual_unlock():
    state = create_initial_state(now=0)
    state.trust = 35
    state.unlocks = ["unlock_first_nickname", "unlock_shared_ritual"]

    service = RelationshipService(state)

    assert service.stage() == "共同日常"
    assert "继续保持稳定陪伴" in service.next_unlock()


def test_proactive_service_selects_low_charge_feedback_and_respects_cooldown():
    state = create_initial_state(now=0)
    state.charge = 24
    previous_state = replace(state)

    feedback = ProactiveCompanionService(
        state=state,
        previous_state=previous_state,
        now=75,
        last_proactive_at={},
    ).select_feedback()

    assert isinstance(feedback, ProactiveFeedback)
    assert feedback.kind == "low_charge"
    assert "能量有点低" in feedback.speech
    assert "能量有点低时主动陪伴" in feedback.summary
    assert feedback.to_legacy_dict() == {
        "kind": feedback.kind,
        "speech": feedback.speech,
        "summary": feedback.summary,
    }

    suppressed = ProactiveCompanionService(
        state=state,
        previous_state=previous_state,
        now=75,
        last_proactive_at={"low_charge": 10},
    ).select_feedback()

    assert suppressed is None


def test_proactive_service_selects_quiet_mood_drop_feedback():
    previous_state = create_initial_state(now=0)
    previous_state.mood = 36
    state = replace(previous_state)
    state.charge = 80
    state.focus = 80
    state.stability = 80
    state.mood = 35
    state.last_interaction_at = 0

    feedback = ProactiveCompanionService(
        state=state,
        previous_state=previous_state,
        now=76,
        last_proactive_at={},
    ).select_feedback()

    assert feedback is not None
    assert feedback.kind == "low_mood"
    assert "我还在这里" in feedback.speech
    assert "久未互动后主动陪伴" in feedback.summary
