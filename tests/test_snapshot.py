from guanghe_companion.controller import CompanionController
from guanghe_companion.events import EventBuilder
from guanghe_companion.events import CompanionEvent
from guanghe_companion.snapshot import (
    CompanionSnapshot,
    SnapshotBuilder,
    SnapshotBuilderInput,
    SnapshotCompatibleSerializer,
    format_delta_text,
    format_event_preview,
    legacy_ui_events,
)


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
    assert typed_snapshot.current_motion == "Default"
    assert typed_snapshot.feedback
    assert all(isinstance(event, CompanionEvent) for event in typed_snapshot.events)
    assert [event.event_type for event in typed_snapshot.events] == ["speech", "stat", "choice"]
    assert typed_snapshot.proactive_feedback is None


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
    assert snapshot.actions == actions
    assert snapshot.shop_items == shop_items
    assert snapshot.inventory_items == inventory_items
    assert [event.event_type for event in snapshot.events] == ["speech", "stat", "choice"]


def test_format_delta_text_keeps_existing_controller_delta_copy():
    assert format_delta_text({}) == "数值无变化"
    assert format_delta_text({"focus": -12, "trust": 4, "coins": 8}) == "focus -12 / trust +4 / coins +8"
