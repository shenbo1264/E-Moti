import guanghe_companion.relationship as relationship_module
from guanghe_companion.engine import create_initial_state
from guanghe_companion.relationship import RelationshipPresentation, RelationshipService


def test_relationship_module_does_not_export_proactive_policy():
    assert not hasattr(relationship_module, "ProactiveFeedback")
    assert not hasattr(relationship_module, "ProactiveCompanionDecision")
    assert not hasattr(relationship_module, "ProactiveCompanionService")


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
