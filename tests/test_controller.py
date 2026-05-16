from dataclasses import replace

from guanghe_companion.actions import CompanionActionRequest
from guanghe_companion.controller import CompanionController
from guanghe_companion.engine import create_initial_state
from guanghe_companion.events import CompanionEvent
from guanghe_companion.storage import save_state


def test_snapshot_exposes_status_actions_shop_and_inventory():
    controller = CompanionController(auto_load=False)

    snapshot = controller.get_snapshot()

    assert snapshot["character_name"] == "星汐"
    assert snapshot["mode"] == "Calm"
    assert snapshot["coins"] == 20
    assert len(snapshot["actions"]) == 6
    assert snapshot["actions"][0]["label"] == "轻触"
    assert len(snapshot["shop_items"]) == 8
    assert snapshot["shop_items"][0]["item_id"] == "warm_milk"
    assert snapshot["inventory_items"][0]["count"] == 0
    assert len(snapshot["events"]) == 3
    assert snapshot["events"][0]["character_name"] == "星汐"
    assert snapshot["relationship_stage"] == "初识"
    assert "信任达到 20" in snapshot["next_relationship_unlock"]


def test_controller_keeps_runtime_events_typed_while_exporting_legacy_snapshot_events():
    controller = CompanionController(auto_load=False)

    assert all(isinstance(event, CompanionEvent) for event in controller.last_events)

    snapshot = controller.perform_action("touch")

    assert all(isinstance(event, CompanionEvent) for event in controller.last_events)
    assert [event.event_type for event in controller.last_events] == ["speech", "stat", "choice", "motion", "memory"]
    assert all(isinstance(event, dict) for event in snapshot["events"])
    assert len(snapshot["events"]) == 3
    assert set(snapshot["events"][0]) == {"character_name", "speech", "sprite", "effect"}


def test_controller_adds_typed_inventory_event_without_changing_legacy_events():
    controller = CompanionController(auto_load=False)
    controller.state.coins = 120

    snapshot = controller.buy_selected_item("warm_milk")
    inventory_event = next(event for event in controller.last_events if event.event_type == "inventory")

    assert inventory_event.payload["item_id"] == "warm_milk"
    assert inventory_event.payload["action"] == "purchase"
    assert inventory_event.payload["item_name"] == "热牛奶"
    assert len(snapshot["events"]) == 3
    assert [event["character_name"] for event in snapshot["events"]] == ["星汐", "STAT", "CHOICE"]


def test_controller_adds_typed_relationship_event_for_unlock_feedback():
    controller = CompanionController(auto_load=False)
    controller.state.trust = 19

    snapshot = controller.perform_action("touch")
    relationship_event = next(event for event in controller.last_events if event.event_type == "relationship")

    assert relationship_event.payload["stage"] == "熟悉的陪伴"
    assert relationship_event.payload["unlock_id"] == "unlock_first_nickname"
    assert "第一次主动称呼" in relationship_event.payload["message"]
    assert len(snapshot["events"]) == 3


def test_controller_adds_typed_proactive_event_for_active_companionship():
    controller = CompanionController(auto_load=False)
    controller.state.charge = 25
    controller.state.mood = 60
    controller.state.focus = 70
    controller.state.stability = 70

    snapshot = controller.advance_tick()
    proactive_event = next(event for event in controller.last_events if event.event_type == "proactive")

    assert proactive_event.payload["kind"] == "low_charge"
    assert "能量有点低" in proactive_event.payload["summary"]
    assert len(snapshot["events"]) == 3


def test_controller_syncs_loaded_original_oc_save_to_pack_name(tmp_path):
    save_path = tmp_path / "save.json"
    old_state = replace(create_initial_state(now=0), character_name="光核伴生体")
    save_state(old_state, save_path)

    controller = CompanionController(save_path=save_path)
    snapshot = controller.get_snapshot()

    assert snapshot["character_name"] == "星汐"
    assert snapshot["events"][0]["character_name"] == "星汐"


def test_controller_closes_buy_and_use_loop():
    controller = CompanionController(auto_load=False)

    study = controller.perform_action("study")
    assert study["coins"] == 28
    assert "共同学习" in study["feedback"]

    purchased = controller.buy_selected_item("warm_milk")
    assert purchased["coins"] == 16
    warm_milk = next(item for item in purchased["inventory_items"] if item["item_id"] == "warm_milk")
    assert warm_milk["count"] == 1

    fed = controller.use_selected_item("warm_milk", usage="feed")
    assert fed["charge"] == 72
    assert fed["mood"] == 60
    assert "投喂" in fed["feedback"]


def test_controller_keeps_local_stat_and_choice_events_when_ai_supplies_speech(tmp_path):
    class MockExpressor:
        def express(self, snapshot, effect=None):
            return [
                {
                    "character_name": str(snapshot["character_name"]),
                    "speech": "LLM speech",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False, ai_expressor=MockExpressor())

    snapshot = controller.perform_action("touch")

    assert [event["character_name"] for event in snapshot["events"]] == [controller.state.character_name, "STAT", "CHOICE"]
    assert snapshot["events"][0]["speech"] == "LLM speech"
    assert snapshot["mood"] == 62
    assert snapshot["coins"] == 20
    assert set(snapshot) >= {"character_name", "stats", "inventory", "events", "event_preview"}


def test_controller_falls_back_when_ai_adapter_raises_without_changing_state(tmp_path):
    class ExplodingExpressor:
        def express(self, snapshot, effect=None):
            raise RuntimeError("adapter offline")

    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False, ai_expressor=ExplodingExpressor())

    initial = controller.get_snapshot()
    touched = controller.perform_action("touch")

    assert [event["character_name"] for event in initial["events"]] == [controller.state.character_name, "STAT", "CHOICE"]
    assert [event["character_name"] for event in touched["events"]] == [controller.state.character_name, "STAT", "CHOICE"]
    assert touched["mood"] == 62
    assert touched["coins"] == 20
    assert touched["motion"] == "TouchHead"
    assert touched["memory_log"][0]["motion"] == "TouchHead"
    assert touched["memory_log"][0]["summary"]


def test_controller_accepts_typed_action_request_without_changing_snapshot_shape():
    controller = CompanionController(auto_load=False)

    snapshot = controller.perform_action_request(CompanionActionRequest(action_id="touch", source="desktop_pet"))

    assert snapshot["motion"] == "TouchHead"
    assert snapshot["actions"][0] == {
        "action_id": "touch",
        "label": "轻触",
        "motion": "TouchHead",
        "enabled": True,
    }
    assert snapshot["mood"] == 62


def test_controller_reports_refused_feed_without_consuming_item():
    controller = CompanionController(auto_load=False)
    controller.state.coins = 120
    controller.state.charge = 96
    controller.buy_selected_item("warm_milk")

    snapshot = controller.use_selected_item("warm_milk", usage="feed")
    warm_milk = next(item for item in snapshot["inventory_items"] if item["item_id"] == "warm_milk")

    assert snapshot["allowed"] is False
    assert snapshot["motion"] == "SwitchDown"
    assert "能量已经很满" in snapshot["feedback"]
    assert warm_milk["count"] == 1
    assert snapshot["charge"] == 96


def test_controller_reports_blocked_action_without_crashing():
    controller = CompanionController(auto_load=False)
    controller.state.focus = 10

    snapshot = controller.perform_action("study")

    assert snapshot["allowed"] is False
    assert snapshot["motion"] == "SwitchDown"
    assert "先让我休息一下" in snapshot["feedback"]
    assert snapshot["events"][0]["effect"] == "DISAPPOINTED"


def test_controller_tick_updates_status_and_tick_counter():
    controller = CompanionController(auto_load=False)
    initial_focus = controller.get_snapshot()["focus"]

    snapshot = controller.advance_tick()

    assert snapshot["focus"] == initial_focus - 0.5
    assert snapshot["tick_count"] == 1


def test_tick_surfaces_low_charge_proactive_companionship_once():
    controller = CompanionController(auto_load=False)
    controller.state.charge = 25
    controller.state.mood = 60
    controller.state.focus = 70
    controller.state.stability = 70

    snapshot = controller.advance_tick()

    assert snapshot["proactive_feedback"]["kind"] == "low_charge"
    assert "能量有点低" in snapshot["feedback"]
    assert snapshot["events"][0]["speech"] == snapshot["feedback"]
    assert snapshot["memory_log"][0]["kind"] == "主动陪伴"
    assert "能量有点低" in snapshot["memory_log"][0]["summary"]

    repeated = controller.advance_tick()

    assert repeated["proactive_feedback"] is None
    assert [entry["kind"] for entry in repeated["memory_log"]].count("主动陪伴") == 1


def test_tick_surfaces_mood_drop_after_long_quiet():
    controller = CompanionController(auto_load=False)
    controller.now = 60
    controller.state.last_interaction_at = 0
    controller.state.charge = 80
    controller.state.focus = 80
    controller.state.stability = 80
    controller.state.mood = 35

    snapshot = controller.advance_tick()

    assert snapshot["proactive_feedback"]["kind"] == "low_mood"
    assert "我还在这里" in snapshot["feedback"]
    assert snapshot["memory_log"][0]["kind"] == "主动陪伴"
    assert "久未互动" in snapshot["memory_log"][0]["summary"]


def test_demo_trigger_surfaces_low_charge_proactive_companionship_immediately():
    controller = CompanionController(auto_load=False)

    snapshot = controller.trigger_demo_proactive("low_charge")

    assert snapshot["proactive_feedback"]["kind"] == "low_charge"
    assert "能量有点低" in snapshot["feedback"]
    assert snapshot["memory_log"][0]["kind"] == "主动陪伴"
    assert snapshot["charge"] < 25
    assert snapshot["tick_count"] == 1


def test_demo_trigger_surfaces_quiet_mood_proactive_companionship_immediately():
    controller = CompanionController(auto_load=False)

    snapshot = controller.trigger_demo_proactive("quiet_mood")

    assert snapshot["proactive_feedback"]["kind"] == "low_mood"
    assert "我还在这里" in snapshot["feedback"]
    assert snapshot["memory_log"][0]["kind"] == "主动陪伴"
    assert snapshot["mood"] <= 35
    assert snapshot["tick_count"] == 1


def test_controller_records_recent_relationship_memories_for_actions_and_items():
    controller = CompanionController(auto_load=False)

    initial = controller.get_snapshot()
    assert initial["memory_log"] == []

    touched = controller.perform_action("touch")
    assert touched["memory_log"][0]["kind"] == "互动"
    assert touched["memory_log"][0]["motion"] == "TouchHead"
    assert "轻触" in touched["memory_log"][0]["summary"]

    controller.state.coins = 120
    controller.buy_selected_item("warm_milk")
    fed = controller.use_selected_item("warm_milk", usage="feed")

    assert fed["memory_log"][0]["kind"] == "投喂"
    assert fed["memory_log"][0]["item_id"] == "warm_milk"
    assert "热牛奶" in fed["memory_log"][0]["summary"]
    assert fed["memory_log"][1]["kind"] == "互动"


def test_controller_surfaces_relationship_unlock_feedback():
    controller = CompanionController(auto_load=False)
    controller.state.trust = 19

    snapshot = controller.perform_action("touch")

    assert "unlock_first_nickname" in snapshot["unlocks"]
    assert snapshot["relationship_stage"] == "熟悉的陪伴"
    assert "第一次主动称呼" in snapshot["feedback"]
    assert snapshot["events"][0]["effect"] == "SHOCKED"
    assert snapshot["memory_log"][0]["kind"] == "关系解锁"
    assert "第一次主动称呼" in snapshot["memory_log"][0]["summary"]
    assert "信任达到 35" in snapshot["next_relationship_unlock"]


def test_demo_reset_restores_fixed_clean_seed_after_pollution(tmp_path):
    controller = CompanionController(save_path=tmp_path / "demo-save.json", auto_load=False)
    controller.perform_action("study")
    controller.buy_selected_item("warm_milk")
    controller.perform_action("rest")
    assert controller.get_snapshot()["memory_log"]

    snapshot = controller.reset_demo_state()

    assert snapshot["coins"] == 20
    assert snapshot["trust"] == 5
    assert snapshot["relationship_stage"] == "初识"
    assert snapshot["memory_log"] == []
    assert snapshot["resting"] is False
    assert snapshot["tick_count"] == 0
    assert all(item["count"] == 0 for item in snapshot["inventory_items"])


def test_demo_reset_ignores_existing_polluted_save(tmp_path):
    save_path = tmp_path / "demo-save.json"
    polluted = replace(
        create_initial_state(now=480),
        coins=2,
        trust=36,
        resting=True,
        inventory={"warm_milk": 3},
        unlocks=["unlock_first_nickname", "unlock_shared_ritual"],
        memory_log=[{"at": 480, "kind": "演示污染", "summary": "上一轮排练", "motion": "Tick"}],
    )
    save_state(polluted, save_path)
    controller = CompanionController(save_path=save_path)

    snapshot = controller.reset_demo_state()

    assert snapshot["coins"] == 20
    assert snapshot["trust"] == 5
    assert snapshot["relationship_stage"] == "初识"
    assert snapshot["memory_log"] == []
    assert snapshot["resting"] is False
    assert all(item["count"] == 0 for item in snapshot["inventory_items"])


def test_demo_save_path_keeps_formal_save_unchanged(tmp_path):
    formal_path = tmp_path / "formal-save.json"
    demo_path = tmp_path / "demo-save.json"
    formal_controller = CompanionController(save_path=formal_path, auto_load=False)
    formal_controller.perform_action("touch")
    formal_before = formal_path.read_text(encoding="utf-8")

    demo_controller = CompanionController(save_path=demo_path, auto_load=False)
    demo_controller.reset_demo_state()
    demo_controller.trigger_demo_proactive("low_charge")

    assert formal_path.read_text(encoding="utf-8") == formal_before
    assert demo_path.read_text(encoding="utf-8") != formal_before


def test_controller_resumes_logical_time_from_loaded_save(tmp_path):
    save_path = tmp_path / "save.json"
    state = replace(create_initial_state(now=480), last_interaction_at=480, last_tick_at=480)
    save_state(state, save_path)

    controller = CompanionController(save_path=save_path)

    assert controller.now == 480
    snapshot = controller.advance_tick()
    assert controller.now == 495
    assert controller.state.last_tick_at == 495
    assert snapshot["tick_count"] == 1
