from dataclasses import replace

from guanghe_companion.engine import create_initial_state
from guanghe_companion.relationship import (
    ProactiveCompanionDecision,
    ProactiveCompanionService,
    ProactiveFeedback,
    RelationshipPresentation,
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


def test_relationship_service_sets_local_player_alias_and_derives_presentation():
    state = create_initial_state(now=0)
    service = RelationshipService(state)

    alias = service.set_player_alias("  小沈\n同学  ")
    presentation = service.presentation(
        [
            {
                "unlock_id": "unlock_first_nickname",
                "item_id": "star_hairpin",
                "label": "星形发夹",
                "icon": "item_icons/star_hairpin.png",
            }
        ]
    )

    assert alias == "小沈 同学"
    assert state.player_alias == "小沈 同学"
    assert isinstance(presentation, RelationshipPresentation)
    assert presentation.address_line == "星汐记得你：小沈 同学"
    assert presentation.tone_label == "轻声试探"
    assert presentation.micro_motion == "轻轻眨眼"
    assert presentation.unlocked_decorations == []

    state.trust = 20
    state.unlocks = ["unlock_first_nickname"]
    advanced = service.presentation(
        [
            {
                "unlock_id": "unlock_first_nickname",
                "item_id": "star_hairpin",
                "label": "星形发夹",
                "icon": "item_icons/star_hairpin.png",
            }
        ]
    )

    assert advanced.address_line == "星汐会这样称呼你：小沈 同学"
    assert advanced.tone_label == "熟悉陪伴"
    assert advanced.micro_motion == "靠近一点"
    assert advanced.unlocked_decorations == [
        {
            "item_id": "star_hairpin",
            "label": "星形发夹",
            "icon": "item_icons/star_hairpin.png",
        }
    ]


def test_relationship_service_builds_unlock_event_payloads_for_typed_events():
    state = create_initial_state(now=0)
    state.trust = 20
    state.unlocks = ["unlock_first_nickname", "unknown_unlock"]
    service = RelationshipService(state)

    payloads = service.unlock_event_payloads(["unlock_first_nickname", "unknown_unlock"])

    assert payloads == [
        {
            "stage": "熟悉的陪伴",
            "unlock_id": "unlock_first_nickname",
            "message": "第一次主动称呼解锁了。她开始用更亲近的方式回应你。",
        }
    ]


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


def test_proactive_service_builds_decision_for_controller_consumption():
    state = create_initial_state(now=0)
    state.charge = 24
    previous_state = replace(state)

    decision = ProactiveCompanionService(
        state=state,
        previous_state=previous_state,
        now=75,
        last_proactive_at={},
    ).select_decision(motion="Tick")

    assert isinstance(decision, ProactiveCompanionDecision)
    assert decision.feedback is not None
    assert decision.effect == "ATTENTION"
    assert decision.to_legacy_feedback() == decision.feedback.to_legacy_dict()
    assert decision.cooldown_updates() == {"low_charge": 75}
    assert decision.event_payload() == {
        "kind": "low_charge",
        "summary": decision.feedback.summary,
    }
    assert decision.memory_drafts() == [
        {
            "kind": "主动陪伴",
            "summary": decision.feedback.summary,
            "motion": "Tick",
        }
    ]


def test_proactive_service_returns_empty_decision_when_suppressed():
    state = create_initial_state(now=0)
    state.charge = 24
    previous_state = replace(state)

    decision = ProactiveCompanionService(
        state=state,
        previous_state=previous_state,
        now=75,
        last_proactive_at={"low_charge": 10},
    ).select_decision(motion="Tick")

    assert isinstance(decision, ProactiveCompanionDecision)
    assert decision.feedback is None
    assert decision.effect == ""
    assert decision.to_legacy_feedback() is None
    assert decision.cooldown_updates() == {}
    assert decision.event_payload() is None
    assert decision.memory_drafts() == []


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
