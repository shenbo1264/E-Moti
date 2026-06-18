from dataclasses import replace

from guanghe_companion.controller import CompanionController
from guanghe_companion.events import EventBuilder
from guanghe_companion.events import CompanionEvent
from guanghe_companion.interaction_intents import InteractionIntent
from guanghe_companion.snapshot import (
    CompanionSnapshot,
    SnapshotBuilder,
    SnapshotBuilderInput,
    SnapshotCompatibleSerializer,
    SnapshotContextFactory,
    format_delta_text,
    format_event_preview,
    legacy_ui_events,
)
from guanghe_companion.visual_actions import VisualAction


def test_controller_exposes_typed_snapshot_with_required_stage_one_fields(tmp_path):
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)

    typed_snapshot = controller.get_typed_snapshot()

    assert isinstance(typed_snapshot, CompanionSnapshot)
    assert typed_snapshot.character_id == "original_oc"
    assert typed_snapshot.character_name == "星汐"
    assert typed_snapshot.mode == "Calm"
    assert typed_snapshot.stats.focus == 72
    assert typed_snapshot.inventory["warm_milk"] == 0
    assert typed_snapshot.shop_items[0]["item_id"] == "warm_milk"
    assert typed_snapshot.relationship_stage == "初识"
    assert "信任达到 20" in typed_snapshot.next_relationship_unlock
    assert typed_snapshot.unlocks == []
    assert typed_snapshot.memory_log == []
    assert typed_snapshot.long_term_memory == ()
    assert typed_snapshot.relationship_presentation.address_line == "星汐还在认识你"
    assert typed_snapshot.relationship_presentation.tone_label == "轻声试探"
    assert typed_snapshot.relationship_presentation.micro_motion == "轻轻眨眼"
    assert typed_snapshot.relationship_presentation.unlocked_decorations == []
    assert typed_snapshot.current_motion == "Default"
    assert typed_snapshot.feedback
    assert all(isinstance(event, CompanionEvent) for event in typed_snapshot.events)
    assert [event.event_type for event in typed_snapshot.events] == ["speech", "stat", "choice"]
    assert typed_snapshot.proactive_feedback is None
    assert typed_snapshot.recent_moment is None
    assert typed_snapshot.session_goal["goal_id"] == "interact_twice"
    assert typed_snapshot.next_suggested_action["action_id"] == "touch"
    assert typed_snapshot.session_goal_reward is None


def test_typed_snapshot_exports_controller_compatible_dict_without_ui_shape_changes(tmp_path):
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    controller.perform_action("touch")

    typed_snapshot = controller.get_typed_snapshot()
    snapshot = controller.get_snapshot()
    compatible = typed_snapshot.to_compatible_dict()

    assert compatible["character_id"] == "original_oc"
    assert compatible["stats"] == {
        "focus": snapshot["focus"],
        "charge": snapshot["charge"],
        "stability": snapshot["stability"],
        "mood": snapshot["mood"],
        "trust": snapshot["trust"],
        "exp": snapshot["exp"],
        "level": snapshot["level"],
        "coins": snapshot["coins"],
    }
    assert compatible["inventory"] == controller.state.inventory
    assert compatible["current_motion"] == snapshot["motion"]
    assert [event.event_type for event in typed_snapshot.events] == ["speech", "stat", "choice", "motion", "memory"]
    assert len(compatible["events"]) == 3
    assert compatible["events"] == snapshot["events"]
    assert compatible["event_preview"] == snapshot["event_preview"]
    assert compatible["actions"] == snapshot["actions"]
    assert compatible["long_term_memory"] == snapshot["long_term_memory"]
    assert compatible["relationship_presentation"] == typed_snapshot.relationship_presentation.to_dict()
    assert compatible["recent_moment"] is None
    assert compatible["session_goal"]["goal_id"] == "interact_twice"
    assert compatible["next_suggested_action"]["action_id"] == "touch"
    assert compatible["session_goal_reward"] is None


def test_snapshot_legacy_event_helpers_filter_domain_events_and_format_preview():
    controller = CompanionController(auto_load=False)
    state = controller.state
    builder = EventBuilder(state)
    events = [
        *builder.fallback_events(feedback="信号稳定。", choices=["轻触", "共同学习"], effect="ATTENTION"),
        builder.motion_event(motion="TouchHead", reason="轻触后切换动作"),
        builder.memory_event(kind="互动", summary="轻触：信号稳定。", motion="TouchHead"),
    ]

    legacy_events = legacy_ui_events(events)
    preview = format_event_preview(legacy_events)

    assert [event["character_name"] for event in legacy_events] == ["星汐", "STAT", "CHOICE"]
    assert all("event_type" not in event for event in legacy_events)
    assert "MOTION" not in preview
    assert preview == "\n".join(
        [
            '{"character_name": "星汐", "speech": "信号稳定。", "sprite": "1", "effect": "ATTENTION"}',
            '{"character_name": "STAT", "speech": "专注 72 / 能量 65 / 稳定 78 / 心情 58 / 信任 5", "sprite": "-1", "effect": ""}',
            '{"character_name": "CHOICE", "speech": "轻触 / 共同学习", "sprite": "-1", "effect": ""}',
        ]
    )


def test_snapshot_compatible_serializer_exports_legacy_shape_and_copies_mutables(tmp_path):
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    controller.perform_action("touch")
    typed_snapshot = controller.get_typed_snapshot()

    compatible = SnapshotCompatibleSerializer(typed_snapshot).to_dict()

    assert compatible == typed_snapshot.to_compatible_dict()
    assert compatible["focus"] == typed_snapshot.stats.focus
    assert compatible["motion"] == typed_snapshot.current_motion
    assert compatible["events"] == legacy_ui_events(typed_snapshot.events)
    assert compatible["event_preview"] == format_event_preview(compatible["events"])

    compatible["inventory"]["warm_milk"] = 99
    compatible["actions"][0]["label"] = "被外部篡改"
    compatible["events"][0]["speech"] = "被外部篡改"

    fresh = SnapshotCompatibleSerializer(typed_snapshot).to_dict()
    assert fresh["inventory"]["warm_milk"] == 0
    assert fresh["actions"][0]["label"] == "轻触"
    assert fresh["events"][0]["speech"] != "被外部篡改"


def test_snapshot_serializer_exports_visual_actions_without_legacy_event_leakage(tmp_path):
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    visual_action = VisualAction(
        action_type="motion",
        action_id="Raised",
        ttl_ms=1800,
        priority=60,
        source="llm",
    )
    typed_snapshot = controller.get_typed_snapshot()
    typed_snapshot = replace(
        typed_snapshot,
        events=[
            *typed_snapshot.events,
            CompanionEvent(
                event_type="visual",
                character_name="VISUAL",
                speech="llm visual action",
                payload={"actions": [visual_action.to_dict()]},
            ),
        ],
    )

    compatible = typed_snapshot.to_compatible_dict()

    assert compatible["visual_actions"] == [visual_action.to_dict()]
    assert all(event["character_name"] != "VISUAL" for event in compatible["events"])


def test_snapshot_serializer_exports_interaction_intents_without_legacy_event_leakage(tmp_path):
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    intent = InteractionIntent(intent_id="offer_rest", ttl_ms=5000, priority=50, source="llm")
    typed_snapshot = controller.get_typed_snapshot()
    typed_snapshot = replace(
        typed_snapshot,
        events=[
            *typed_snapshot.events,
            CompanionEvent(
                event_type="intent",
                character_name="INTENT",
                speech="llm interaction intent",
                payload={"intents": [intent.to_dict()]},
            ),
        ],
    )

    compatible = typed_snapshot.to_compatible_dict()

    assert compatible["interaction_intents"] == [intent.to_dict()]
    assert all(event["character_name"] != "INTENT" for event in compatible["events"])


def test_snapshot_builder_accepts_single_typed_input_context(tmp_path):
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    actions = controller._build_actions()
    shop_items = controller._build_shop_items()
    inventory_items = controller._build_inventory_items()
    builder_input = SnapshotBuilderInput(
        state=controller.state,
        character_title=controller.character_pack.title,
        character_description=controller.character_pack.description,
        goal="目标：信任达到 20",
        relationship_stage="初识",
        next_relationship_unlock="信任达到 20：解锁第一次主动称呼",
        current_motion="Default",
        motion_caption="默认待机",
        feedback="信号稳定。",
        delta_text="暂无变化",
        allowed=True,
        tick_count=0,
        events=controller.last_events,
        actions=actions,
        shop_items=shop_items,
        inventory_items=inventory_items,
        item_feedback_icon=None,
        proactive_feedback=None,
    )

    snapshot = SnapshotBuilder(builder_input).build()

    assert snapshot.character_name == "星汐"
    assert snapshot.goal == "目标：信任达到 20"
    assert snapshot.session_goal == {}
    assert snapshot.next_suggested_action is None
    assert snapshot.session_goal_reward is None
    assert snapshot.actions == actions
    assert snapshot.shop_items == shop_items
    assert snapshot.inventory_items == inventory_items
    assert [event.event_type for event in snapshot.events] == ["speech", "stat", "choice"]


def test_snapshot_builder_exports_bounded_long_term_memory_summaries(tmp_path):
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    long_term_memory = tuple(
        {
            "category": "local_note",
            "summary": f"长期记忆 {index}",
            "source": "local_api",
        }
        for index in range(6)
    )
    builder_input = SnapshotBuilderInput(
        state=controller.state,
        character_title=controller.character_pack.title,
        character_description=controller.character_pack.description,
        goal="目标：信任达到 20",
        relationship_stage="初识",
        next_relationship_unlock="信任达到 20：解锁第一次主动称呼",
        current_motion="Default",
        motion_caption="默认待机",
        feedback="信号稳定。",
        delta_text="暂无变化",
        allowed=True,
        tick_count=0,
        events=controller.last_events,
        actions=controller._build_actions(),
        shop_items=controller._build_shop_items(),
        inventory_items=controller._build_inventory_items(),
        item_feedback_icon=None,
        proactive_feedback=None,
        long_term_memory=long_term_memory,
    )

    snapshot = SnapshotBuilder(builder_input).build()
    compatible = snapshot.to_compatible_dict()

    assert snapshot.long_term_memory == long_term_memory[:5]
    assert compatible["long_term_memory"] == list(long_term_memory[:5])


def test_snapshot_exposes_player_alias_and_relationship_badges_as_readonly_presentation(tmp_path):
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    controller.set_player_alias("小沈")
    controller.state.trust = 20
    controller.state.unlocks = ["unlock_first_nickname"]

    typed_snapshot = controller.get_typed_snapshot()
    compatible = typed_snapshot.to_compatible_dict()

    assert typed_snapshot.relationship_presentation.address_line == "星汐会这样称呼你：小沈"
    assert typed_snapshot.relationship_presentation.tone_label == "熟悉陪伴"
    assert typed_snapshot.relationship_presentation.micro_motion == "靠近一点"
    assert typed_snapshot.relationship_presentation.unlocked_decorations == [
        {
            "item_id": "star_hairpin",
            "label": "星形发夹",
            "icon": "item_icons/star_hairpin.png",
        }
    ]
    assert compatible["relationship_presentation"] == typed_snapshot.relationship_presentation.to_dict()
    assert compatible["player_alias"] == "小沈"


def test_snapshot_context_factory_derives_state_owned_snapshot_fields(tmp_path):
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    factory = SnapshotContextFactory(
        state=controller.state,
        character_title=controller.character_pack.title,
        character_description=controller.character_pack.description,
        current_motion="Default",
        motion_caption="默认待机",
        feedback="信号稳定。",
        delta_text="暂无变化",
        allowed=True,
        tick_count=0,
        events=controller.last_events,
        actions=controller._build_actions(),
        shop_items=controller._build_shop_items(),
        inventory_items=controller._build_inventory_items(),
        item_feedback_icon=None,
        proactive_feedback=None,
    )

    builder_input = factory.build_input()

    assert isinstance(builder_input, SnapshotBuilderInput)
    assert builder_input.goal == "目标：让信任达到 20，解锁第一次主动称呼。"
    assert builder_input.session_goal == {}
    assert builder_input.next_suggested_action is None
    assert builder_input.session_goal_reward is None
    assert builder_input.relationship_stage == "初识"
    assert builder_input.next_relationship_unlock == "信任达到 20：解锁第一次主动称呼"


def test_format_delta_text_keeps_existing_controller_delta_copy():
    assert format_delta_text({}) == "数值无变化"
    assert format_delta_text({"focus": -12, "trust": 4, "coins": 8}) == "focus -12 / trust +4 / coins +8"
