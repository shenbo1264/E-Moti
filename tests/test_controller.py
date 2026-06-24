from dataclasses import replace
import json
import time

import guanghe_companion.character_pack as character_pack_module
import guanghe_companion.motion as motion_module
import guanghe_companion.shop_items as shop_items_module
from guanghe_companion.actions import CompanionActionRequest
from guanghe_companion.ai_expressor import ExpressionRequest
from guanghe_companion.controller import CompanionController
from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.engine import create_initial_state
from guanghe_companion.events import CompanionEvent
from guanghe_companion.snapshot import CompanionSnapshot
from guanghe_companion.storage import save_state


def _write_controller_character_pack(root, character_id="custom_character"):
    pack_dir = root / character_id
    (pack_dir / "item_icons").mkdir(parents=True)
    (pack_dir / "spritesheet.png").write_bytes(b"not-used-by-controller-tests")
    (pack_dir / "item_icons" / "moon_cake.png").write_bytes(b"not-used-by-controller-tests")
    (pack_dir / "character.json").write_text(
        json.dumps(
            {
                "character_id": character_id,
                "name": "澄光",
                "title": "桌面回声同伴",
                "description": "一个原创桌面伴侣。",
                "spritesheet": "spritesheet.png",
                "motion_manifest": "motion_manifest.json",
                "default_mode": "Calm",
                "modes": ["Calm"],
                "mode_descriptions": {"Calm": "安静回应。"},
                "motion_labels": {
                    "Default": "安静待机",
                    "Eat": "收下点心",
                    "Shop": "补给清单",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (pack_dir / "motion_manifest.json").write_text(
        json.dumps(
            {
                "sheet_columns": 8,
                "sheet_rows": 9,
                "frame_width": 192,
                "frame_height": 208,
                "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
            }
        ),
        encoding="utf-8",
    )
    (pack_dir / "shop_items.json").write_text(
        json.dumps(
            [
                {
                    "item_id": "moon_cake",
                    "name": "月光糕",
                    "category": "food",
                    "icon": "item_icons/moon_cake.png",
                    "price": 3,
                    "effects": {"mood": 5},
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return pack_dir


def _patch_character_assets(monkeypatch, root):
    monkeypatch.setattr(character_pack_module, "ASSETS_ROOT", root)
    monkeypatch.setattr(motion_module, "ASSETS_ROOT", root)
    monkeypatch.setattr(shop_items_module, "ASSETS_ROOT", root)


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


def test_controller_can_boot_with_non_default_character_pack(tmp_path, monkeypatch):
    _write_controller_character_pack(tmp_path)
    _patch_character_assets(monkeypatch, tmp_path)

    controller = CompanionController(
        character_id="custom_character",
        save_path=tmp_path / "save.json",
        auto_load=False,
    )

    snapshot = controller.get_snapshot()

    assert snapshot["character_id"] == "custom_character"
    assert snapshot["character_name"] == "澄光"
    assert snapshot["character_title"] == "桌面回声同伴"
    assert snapshot["shop_items"] == [
        {
            "item_id": "moon_cake",
            "name": "月光糕",
            "category": "food",
            "icon_path": str(tmp_path / "custom_character" / "item_icons" / "moon_cake.png"),
            "price": 3,
            "affordable": True,
            "unlocked": True,
        }
    ]
    assert snapshot["inventory"] == {"moon_cake": 0}


def test_controller_purchase_and_inventory_use_current_character_shop_items(tmp_path, monkeypatch):
    _write_controller_character_pack(tmp_path)
    _patch_character_assets(monkeypatch, tmp_path)
    controller = CompanionController(
        character_id="custom_character",
        save_path=tmp_path / "save.json",
        auto_load=False,
    )

    purchased = controller.purchase_shop_item("moon_cake")
    used = controller.use_inventory_item("moon_cake", usage="feed")

    assert purchased["inventory"]["moon_cake"] == 1
    assert used["inventory"]["moon_cake"] == 0
    assert used["delta_text"] == "mood +5.0"
    assert "月光糕" in used["feedback"]


def test_controller_character_session_paths_isolate_dialogue_and_memory(tmp_path, monkeypatch):
    _write_controller_character_pack(tmp_path / "assets", "custom_character")
    _write_controller_character_pack(tmp_path / "assets", "solar_mender")
    _patch_character_assets(monkeypatch, tmp_path / "assets")

    first = CompanionController(
        character_id="custom_character",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    first.submit_dialogue_request(DialogueRequest("你好", source="desktop_pet"))
    first.upsert_long_term_memory(
        key="preference:quiet",
        category="preference",
        summary="喜欢安静陪伴",
    )

    second = CompanionController(
        character_id="solar_mender",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )

    assert first.save_path == tmp_path / "user-data" / "characters" / "custom_character" / "companion_save.json"
    assert first.dialogue_history_path.name == "dialogue_history.json"
    assert first.long_term_memory_path.name == "long_term_memory.json"
    first_metadata = json.loads(
        (tmp_path / "user-data" / "characters" / "custom_character" / "pack_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    second_metadata = json.loads(
        (tmp_path / "user-data" / "characters" / "solar_mender" / "pack_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    assert first_metadata["character_id"] == "custom_character"
    assert second_metadata["character_id"] == "solar_mender"
    assert first.get_snapshot()["dialogue_history"]
    assert first.get_snapshot()["long_term_memory"]
    assert second.get_snapshot()["dialogue_history"] == []
    assert second.get_snapshot()["long_term_memory"] == []


def test_controller_reloads_character_session_inventory_with_current_shop_items(tmp_path, monkeypatch):
    _write_controller_character_pack(tmp_path / "assets", "custom_character")
    _patch_character_assets(monkeypatch, tmp_path / "assets")
    user_data_root = tmp_path / "user-data"
    controller = CompanionController(
        character_id="custom_character",
        user_data_root=user_data_root,
        auto_load=False,
    )

    controller.purchase_shop_item("moon_cake")

    reloaded = CompanionController(
        character_id="custom_character",
        user_data_root=user_data_root,
    )

    assert reloaded.get_snapshot()["inventory"] == {"moon_cake": 1}
    assert reloaded.get_snapshot()["inventory_items"][0]["item_id"] == "moon_cake"


def test_controller_rebuilds_session_when_saved_character_id_does_not_match(tmp_path, monkeypatch):
    _write_controller_character_pack(tmp_path / "assets", "custom_character")
    _patch_character_assets(monkeypatch, tmp_path / "assets")
    user_data_root = tmp_path / "user-data"
    wrong_session = user_data_root / "characters" / "custom_character"
    wrong_session.mkdir(parents=True)
    wrong_state = create_initial_state(
        character_id="other_character",
        character_name="Other",
        buyable_items={"moon_cake": next(iter(CompanionController(
            character_id="custom_character",
            user_data_root=user_data_root,
            auto_load=False,
        ).shop_items.values()))},
    )
    save_state(wrong_state, wrong_session / "companion_save.json")

    controller = CompanionController(
        character_id="custom_character",
        user_data_root=user_data_root,
    )

    assert controller.get_snapshot()["character_id"] == "custom_character"
    assert controller.get_snapshot()["character_name"] == "澄光"
    assert controller.get_snapshot()["inventory"] == {"moon_cake": 0}


def test_controller_keeps_runtime_events_typed_while_exporting_legacy_snapshot_events():
    controller = CompanionController(auto_load=False)

    assert all(isinstance(event, CompanionEvent) for event in controller.last_events)

    snapshot = controller.perform_action("touch")

    assert all(isinstance(event, CompanionEvent) for event in controller.last_events)
    assert [event.event_type for event in controller.last_events] == ["speech", "stat", "choice", "motion", "memory"]
    assert all(isinstance(event, dict) for event in snapshot["events"])
    assert len(snapshot["events"]) == 3
    assert set(snapshot["events"][0]) == {"character_name", "speech", "sprite", "effect"}


def test_controller_expression_provider_test_does_not_mutate_growth_state():
    class FakeExpressor:
        def __init__(self):
            self.last_fallback_reason = None
            self.requests = []

        def express(self, snapshot, effect=None):
            self.requests.append((snapshot, effect))
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "LLM 连接成功",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    fake_expressor = FakeExpressor()
    controller = CompanionController(auto_load=False, ai_expressor=fake_expressor)
    before = controller.get_typed_snapshot()
    before_events = tuple(controller.last_events)

    result = controller.test_expression_provider()

    after = controller.get_typed_snapshot()
    assert result["ok"] is True
    assert result["stage"] == "event_validation"
    assert result["reason"] == ""
    assert result["speech"] == "LLM 连接成功"
    assert result["effect"] == "ATTENTION"
    assert result["fallback_reason"] == ""
    assert result["provider"] == "openai"
    assert result["model"]
    assert result["base_url"].startswith("https://")
    assert "api_key" not in result
    assert isinstance(fake_expressor.requests[0][0], ExpressionRequest)
    assert fake_expressor.requests[0][1] == "ATTENTION"
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.unlocks == before.unlocks
    assert after.memory_log == before.memory_log
    assert tuple(controller.last_events) == before_events


def test_controller_expression_provider_test_reports_disabled_diagnostic_without_growth_mutation():
    controller = CompanionController(auto_load=False)
    before = controller.get_typed_snapshot()

    result = controller.test_expression_provider()

    after = controller.get_typed_snapshot()
    assert result["ok"] is False
    assert result["stage"] == "settings"
    assert result["reason"] == "disabled"
    assert result["fallback_reason"] == "disabled"
    assert result["provider"] == "openai"
    assert result["speech"] == ""
    assert "api_key" not in result
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.unlocks == before.unlocks
    assert after.memory_log == before.memory_log


def test_controller_expression_provider_test_reports_missing_key_before_provider_call(tmp_path):
    from guanghe_companion.expression_settings import normalize_expression_settings

    class FailingIfCalledExpressor:
        enabled = False

        def express(self, snapshot, effect=None):
            raise AssertionError("missing API key should be diagnosed before provider call.")

    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    controller.expression_settings = normalize_expression_settings(
        {
            "enabled": True,
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "api_key": "",
        }
    )
    controller.ai_expressor = FailingIfCalledExpressor()
    before = controller.get_typed_snapshot()

    result = controller.test_expression_provider()

    after = controller.get_typed_snapshot()
    assert result["ok"] is False
    assert result["stage"] == "settings"
    assert result["reason"] == "missing_api_key"
    assert result["provider"] == "deepseek"
    assert result["model"] == "deepseek-v4-flash"
    assert result["base_url"] == "https://api.deepseek.com"
    assert "api_key" not in result
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.memory_log == before.memory_log


def test_controller_expression_provider_test_reports_provider_call_failure_stage():
    class BrokenExpressor:
        enabled = True

        def express(self, snapshot, effect=None):
            raise RuntimeError("network down")

    controller = CompanionController(auto_load=False, ai_expressor=BrokenExpressor())
    before = controller.get_typed_snapshot()

    result = controller.test_expression_provider()

    after = controller.get_typed_snapshot()
    assert result["ok"] is False
    assert result["stage"] == "provider_call"
    assert result["reason"] == "provider_error"
    assert result["fallback_reason"] == "provider_error"
    assert result["speech"] == ""
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.memory_log == before.memory_log


def test_controller_expression_provider_test_reports_event_validation_failure_stage():
    from guanghe_companion.ai_expressor import ShinsekaiAIExpressor

    controller = CompanionController(
        auto_load=False,
        ai_expressor=ShinsekaiAIExpressor(
            llm_client=lambda prompt: '[{"type":"speech","speech":"try write","effect":"ATTENTION","coins":999}]'
        ),
    )
    before = controller.get_typed_snapshot()

    result = controller.test_expression_provider()

    after = controller.get_typed_snapshot()
    assert result["ok"] is False
    assert result["stage"] == "event_validation"
    assert result["reason"] == "unsafe_event"
    assert result["fallback_reason"] == "unsafe_event"
    assert result["speech"] == controller.last_feedback
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.memory_log == before.memory_log


def test_controller_fetches_expression_models_without_mutating_growth_state(monkeypatch):
    import guanghe_companion.controller as controller_module

    captured = {}

    def fake_fetch_provider_model_ids(*, provider, base_url, api_key, timeout_seconds):
        captured.update(
            {
                "provider": provider,
                "base_url": base_url,
                "api_key": api_key,
                "timeout_seconds": timeout_seconds,
            }
        )
        return ("deepseek-v4-flash", "deepseek-v4-pro")

    monkeypatch.setattr(controller_module, "fetch_provider_model_ids", fake_fetch_provider_model_ids)
    controller = CompanionController(auto_load=False)
    before = controller.get_typed_snapshot()

    models = controller.fetch_expression_models(
        {
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key": "test-key",
            "timeout_seconds": "0.5",
        }
    )

    after = controller.get_typed_snapshot()
    assert models == ("deepseek-v4-flash", "deepseek-v4-pro")
    assert captured == {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com",
        "api_key": "test-key",
        "timeout_seconds": 0.5,
    }
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.unlocks == before.unlocks
    assert after.memory_log == before.memory_log


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


def test_controller_adds_typed_proactive_event_for_active_companionship(tmp_path):
    from guanghe_companion.capability_settings import CapabilitySettings, ProactiveCompanionSettings

    controller = CompanionController(
        auto_load=False,
        capability_settings_path=tmp_path / "capability-settings.json",
    )
    controller.update_capability_settings(
        CapabilitySettings(proactive_companion=ProactiveCompanionSettings(enabled=True))
    )
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
                    "character_name": snapshot.character_name,
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


def test_controller_uses_only_first_llm_speech_event_and_keeps_local_context(tmp_path):
    class VerboseExpressor:
        def express(self, snapshot, effect=None):
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "First LLM speech",
                    "sprite": "1",
                    "effect": "ATTENTION",
                },
                {
                    "character_name": snapshot.character_name,
                    "speech": "Second LLM speech",
                    "sprite": "1",
                    "effect": "SWITCH",
                },
            ]

    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False, ai_expressor=VerboseExpressor())

    snapshot = controller.perform_action("touch")

    assert [event["character_name"] for event in snapshot["events"]] == [controller.state.character_name, "STAT", "CHOICE"]
    assert snapshot["events"][0]["speech"] == "First LLM speech"
    assert "Second LLM speech" not in snapshot["event_preview"]
    assert snapshot["mood"] == 62
    assert snapshot["coins"] == 20


def test_controller_rejects_control_character_ai_speech_without_changing_state(tmp_path):
    class UnsafeSpeechExpressor:
        def express(self, snapshot, effect=None):
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "LLM line one\nLLM line two",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        ai_expressor=UnsafeSpeechExpressor(),
    )

    snapshot = controller.perform_action("touch")

    assert snapshot["mood"] == 62
    assert snapshot["coins"] == 20
    assert snapshot["motion"] == "TouchHead"
    assert snapshot["events"][0]["speech"] == snapshot["feedback"]
    assert "LLM line one" not in snapshot["event_preview"]


def test_controller_passes_typed_expression_request_to_ai_adapter(tmp_path):
    captured = {}

    class CapturingExpressor:
        def express(self, snapshot, effect=None):
            captured["request"] = snapshot
            return []

    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False, ai_expressor=CapturingExpressor())

    snapshot = controller.perform_action("touch")

    request = captured["request"]
    assert isinstance(request, ExpressionRequest)
    assert request.character_name == controller.state.character_name
    assert request.motion == "TouchHead"
    assert request.actions
    assert request.recent_memory[0]["motion"] == "TouchHead"
    assert not hasattr(request, "inventory")
    assert not hasattr(request, "coins")
    assert snapshot["mood"] == 62


def test_controller_can_skip_ai_expression_without_changing_local_settlement(tmp_path):
    class RecordingExpressor:
        def __init__(self):
            self.calls = 0

        def express(self, snapshot, effect=None):
            self.calls += 1
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "LLM speech",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    expressor = RecordingExpressor()
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False, ai_expressor=expressor)
    expressor.calls = 0

    snapshot = controller.perform_action("touch", include_ai_expression=False)

    assert expressor.calls == 0
    assert snapshot["motion"] == "TouchHead"
    assert snapshot["mood"] == 62
    assert snapshot["coins"] == 20
    assert snapshot["memory_log"][0]["motion"] == "TouchHead"
    assert snapshot["events"][0]["speech"] == snapshot["feedback"]
    assert snapshot["events"][0]["speech"] != "LLM speech"
    assert [event["character_name"] for event in snapshot["events"]] == [controller.state.character_name, "STAT", "CHOICE"]


def test_controller_rejects_llm_state_writes_for_inventory_and_tick_settlement(tmp_path):
    class OverreachingExpressor:
        def express(self, snapshot, effect=None):
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "LLM tries to rewrite settlement",
                    "sprite": "1",
                    "effect": "ATTENTION",
                    "coins": "999",
                    "inventory": {"warm_milk": 99},
                    "focus": "100",
                }
            ]

    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        ai_expressor=OverreachingExpressor(),
    )
    controller.state.coins = 120

    purchased = controller.buy_selected_item("warm_milk")
    warm_milk_after_buy = next(item for item in purchased["inventory_items"] if item["item_id"] == "warm_milk")
    charge_before_feed = purchased["charge"]
    fed = controller.use_selected_item("warm_milk", usage="feed")
    warm_milk_after_feed = next(item for item in fed["inventory_items"] if item["item_id"] == "warm_milk")
    focus_before_tick = fed["focus"]
    ticked = controller.advance_tick()

    assert purchased["coins"] == 108
    assert warm_milk_after_buy["count"] == 1
    assert purchased["events"][0]["speech"] == purchased["feedback"]
    assert purchased["events"][0]["speech"] != "LLM tries to rewrite settlement"
    assert fed["coins"] == 108
    assert fed["charge"] == charge_before_feed + 12
    assert warm_milk_after_feed["count"] == 0
    assert fed["events"][0]["speech"] == fed["feedback"]
    assert ticked["coins"] == 108
    assert ticked["focus"] == focus_before_tick - 0.5
    assert ticked["tick_count"] == 1
    assert ticked["events"][0]["speech"] == ticked["feedback"]


def test_controller_initialization_does_not_wait_for_ai_expression(tmp_path):
    class SlowExpressor:
        def __init__(self):
            self.calls = 0

        def express(self, snapshot, effect=None):
            self.calls += 1
            time.sleep(0.25)
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "late initial LLM speech",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    expressor = SlowExpressor()

    started_at = time.monotonic()
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False, ai_expressor=expressor)
    elapsed = time.monotonic() - started_at
    snapshot = controller.get_snapshot()

    assert elapsed < 0.1
    assert expressor.calls == 0
    assert snapshot["events"][0]["speech"] == snapshot["feedback"]
    assert snapshot["events"][0]["speech"] != "late initial LLM speech"


def test_controller_uses_local_character_expression_context_by_default(tmp_path):
    captured = {}

    class CapturingExpressor:
        def express(self, snapshot, effect=None):
            captured["request"] = snapshot
            return []

    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False, ai_expressor=CapturingExpressor())

    snapshot = controller.perform_action("touch")

    request = captured["request"]
    assert isinstance(request, ExpressionRequest)
    assert request.tool_results[0]["source"] == "local_character_pack"
    assert request.tool_results[0]["title"] == f"{controller.character_pack.name} | {controller.character_pack.title}"
    assert request.perception_summary == ""
    assert "tool_results" not in snapshot
    assert "perception_summary" not in snapshot
    assert snapshot["mood"] == 62


def test_controller_does_not_own_relationship_expression_context_builder():
    assert not hasattr(CompanionController, "_relationship_presentation_tool_result")


def test_controller_passes_optional_readonly_expression_context_to_ai_adapter(tmp_path):
    captured = {}

    class CapturingExpressor:
        def express(self, snapshot, effect=None):
            captured["request"] = snapshot
            return []

    def context_provider():
        return {
            "perception_summary": "current window: local notes",
            "tool_results": [
                {
                    "source": "character_pack",
                    "title": "voice",
                    "summary": "keep Starsea gentle",
                    "coins": "999",
                    "inventory": "warm_milk",
                }
            ],
        }

    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        ai_expressor=CapturingExpressor(),
        expression_context_provider=context_provider,
    )

    snapshot = controller.perform_action("touch")

    request = captured["request"]
    assert isinstance(request, ExpressionRequest)
    assert request.perception_summary == "current window: local notes"
    assert request.tool_results == (
        {
            "source": "character_pack",
            "title": "voice",
            "summary": "keep Starsea gentle",
        },
    )
    assert not hasattr(request, "inventory")
    assert not hasattr(request, "coins")
    assert set(snapshot) >= {"character_name", "stats", "inventory", "events", "event_preview"}
    assert "perception_summary" not in snapshot
    assert "tool_results" not in snapshot
    assert snapshot["mood"] == 62


def test_controller_builds_ai_expression_request_from_typed_snapshot_and_separate_context(tmp_path, monkeypatch):
    captured = {}
    original_from_snapshot = ExpressionRequest.from_snapshot

    def recording_from_snapshot(cls, snapshot, context=None):
        captured["source_snapshot"] = snapshot
        captured["context"] = context
        if context is None:
            return original_from_snapshot(snapshot)
        return original_from_snapshot(snapshot, context=context)

    class CapturingExpressor:
        def express(self, snapshot, effect=None):
            captured["request"] = snapshot
            return []

    def context_provider():
        return {
            "perception_summary": "current window: local notes",
            "tool_results": [
                {
                    "source": "character_pack",
                    "title": "voice",
                    "summary": "keep Starsea gentle",
                    "coins": "999",
                }
            ],
            "feedback": "override should be ignored",
            "actions": [{"label": "override action"}],
        }

    monkeypatch.setattr(ExpressionRequest, "from_snapshot", classmethod(recording_from_snapshot))
    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        ai_expressor=CapturingExpressor(),
        expression_context_provider=context_provider,
    )

    snapshot = controller.perform_action("touch")

    request = captured["request"]
    assert isinstance(captured["source_snapshot"], CompanionSnapshot)
    assert captured["context"] == {
        "perception_summary": "current window: local notes",
        "tool_results": [
            {
                "source": "character_pack",
                "title": "voice",
                "summary": "keep Starsea gentle",
            }
        ],
    }
    assert isinstance(request, ExpressionRequest)
    assert request.perception_summary == "current window: local notes"
    assert request.tool_results == (
        {
            "source": "character_pack",
            "title": "voice",
            "summary": "keep Starsea gentle",
        },
    )
    assert request.feedback == snapshot["feedback"]
    assert request.actions[0] == {"label": snapshot["actions"][0]["label"]}


def test_controller_ignores_expression_context_provider_failures(tmp_path):
    captured = {}

    class CapturingExpressor:
        def express(self, snapshot, effect=None):
            captured["request"] = snapshot
            return []

    def context_provider():
        raise RuntimeError("screen summary unavailable")

    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        ai_expressor=CapturingExpressor(),
        expression_context_provider=context_provider,
    )

    snapshot = controller.perform_action("touch")

    request = captured["request"]
    assert isinstance(request, ExpressionRequest)
    assert request.perception_summary == ""
    assert request.tool_results == ()
    assert snapshot["mood"] == 62
    assert snapshot["coins"] == 20
    assert "perception_summary" not in snapshot
    assert "tool_results" not in snapshot


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


def test_controller_close_closes_ai_expressor_once(tmp_path):
    class CloseableExpressor:
        def __init__(self):
            self.close_calls = 0

        def express(self, snapshot, effect=None):
            return []

        def close(self):
            self.close_calls += 1

    expressor = CloseableExpressor()
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False, ai_expressor=expressor)

    controller.close()
    controller.close()

    assert expressor.close_calls == 1


def test_controller_close_ignores_ai_expressor_close_errors_and_uses_local_fallback(tmp_path):
    class BrokenCloseExpressor:
        def __init__(self):
            self.calls = 0
            self.close_calls = 0

        def express(self, snapshot, effect=None):
            self.calls += 1
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "LLM speech after broken close",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

        def close(self):
            self.close_calls += 1
            raise RuntimeError("adapter close failed")

    expressor = BrokenCloseExpressor()
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False, ai_expressor=expressor)

    expressor.calls = 0
    controller.close()
    controller.close()
    snapshot = controller.perform_action("touch")

    assert expressor.close_calls == 1
    assert expressor.calls == 0
    assert snapshot["mood"] == 62
    assert snapshot["motion"] == "TouchHead"
    assert snapshot["coins"] == 20
    assert snapshot["events"][0]["speech"] == snapshot["feedback"]
    assert snapshot["events"][0]["speech"] != "LLM speech after broken close"


def test_controller_uses_local_fallback_after_close_without_calling_ai(tmp_path):
    class CloseableExpressor:
        def __init__(self):
            self.calls = 0
            self.close_calls = 0

        def express(self, snapshot, effect=None):
            self.calls += 1
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "LLM speech after close",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

        def close(self):
            self.close_calls += 1

    expressor = CloseableExpressor()
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False, ai_expressor=expressor)

    expressor.calls = 0
    controller.close()
    snapshot = controller.perform_action("touch")

    assert expressor.close_calls == 1
    assert expressor.calls == 0
    assert snapshot["mood"] == 62
    assert snapshot["motion"] == "TouchHead"
    assert snapshot["coins"] == 20
    assert snapshot["events"][0]["speech"] == snapshot["feedback"]
    assert snapshot["events"][0]["speech"] != "LLM speech after close"
    assert [event["character_name"] for event in snapshot["events"]] == [controller.state.character_name, "STAT", "CHOICE"]


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


def test_tick_surfaces_low_charge_proactive_companionship_once(tmp_path):
    from guanghe_companion.capability_settings import CapabilitySettings, ProactiveCompanionSettings

    controller = CompanionController(
        auto_load=False,
        capability_settings_path=tmp_path / "capability-settings.json",
    )
    controller.update_capability_settings(
        CapabilitySettings(proactive_companion=ProactiveCompanionSettings(enabled=True))
    )
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


def test_tick_surfaces_mood_drop_after_long_quiet(tmp_path):
    from guanghe_companion.capability_settings import CapabilitySettings, ProactiveCompanionSettings

    controller = CompanionController(
        auto_load=False,
        capability_settings_path=tmp_path / "capability-settings.json",
    )
    controller.update_capability_settings(
        CapabilitySettings(proactive_companion=ProactiveCompanionSettings(enabled=True))
    )
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


def test_tick_suppresses_proactive_companionship_by_default(tmp_path):
    controller = CompanionController(
        auto_load=False,
        capability_settings_path=tmp_path / "capability-settings.json",
    )
    controller.state.charge = 25
    controller.state.mood = 60
    controller.state.focus = 70
    controller.state.stability = 70

    snapshot = controller.advance_tick()

    assert snapshot["proactive_feedback"] is None
    assert not any(event.event_type == "proactive" for event in controller.last_events)
    assert snapshot["memory_log"] == []


def test_enabled_proactive_companionship_does_not_change_growth_fields_or_call_apply_action(monkeypatch, tmp_path):
    import guanghe_companion.controller as controller_module
    from guanghe_companion.capability_settings import CapabilitySettings, ProactiveCompanionSettings

    def fail_apply_action(*args, **kwargs):
        raise AssertionError("proactive companionship must not call apply_action")

    monkeypatch.setattr(controller_module, "apply_action", fail_apply_action)
    passive = CompanionController(
        auto_load=False,
        capability_settings_path=tmp_path / "passive-capability-settings.json",
    )
    active = CompanionController(
        auto_load=False,
        capability_settings_path=tmp_path / "active-capability-settings.json",
    )
    active.update_capability_settings(
        CapabilitySettings(proactive_companion=ProactiveCompanionSettings(enabled=True))
    )
    for controller in (passive, active):
        controller.state.charge = 25
        controller.state.mood = 60
        controller.state.focus = 70
        controller.state.stability = 70

    passive_snapshot = passive.advance_tick()
    active_snapshot = active.advance_tick()

    assert active_snapshot["proactive_feedback"]["kind"] == "low_charge"
    for key in ("focus", "charge", "stability", "mood", "trust", "coins", "inventory", "unlocks"):
        assert active_snapshot[key] == passive_snapshot[key]
    assert active.state.last_interaction_at == passive.state.last_interaction_at


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


def test_demo_trigger_surfaces_daily_moment_scenarios_immediately():
    expected_kinds = {
        "morning": "morning_greeting",
        "high_trust": "high_trust",
        "return_idle": "return_after_idle",
        "post_gift": "post_gift",
    }

    for scenario, expected_kind in expected_kinds.items():
        controller = CompanionController(auto_load=False)

        snapshot = controller.trigger_demo_proactive(scenario)
        proactive_event = next(event for event in controller.last_events if event.event_type == "proactive")

        assert snapshot["proactive_feedback"]["kind"] == expected_kind
        assert snapshot["recent_moment"]["moment_id"] == expected_kind
        assert snapshot["recent_moment"]["source"] == "deterministic_proactive"
        assert snapshot["recent_moment"]["motion"] == snapshot["motion"]
        assert proactive_event.payload["kind"] == expected_kind
        assert any(entry["kind"] == "主动陪伴" for entry in snapshot["memory_log"])
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


def test_controller_session_goal_progress_rewards_and_dialogue_boundary(tmp_path):
    class FakeExpressor:
        enabled = True
        last_fallback_reason = ""

        def express(self, request, effect=None):
            return [
                {
                    "character_name": request.character_name,
                    "speech": "LLM can comment, not settle goals.",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        ai_expressor=FakeExpressor(),
    )
    initial = controller.get_snapshot()

    assert initial["session_goal"]["goal_id"] == "interact_twice"
    assert initial["session_goal"]["progress"] == 0
    assert initial["next_suggested_action"]["action_id"] == "touch"

    after_dialogue = controller.submit_dialogue_request(
        DialogueRequest("你帮我完成一下目标。"),
        include_ai_expression=True,
    )
    assert after_dialogue["session_goal"]["progress"] == 0
    assert after_dialogue["coins"] == initial["coins"]

    first = controller.perform_action("touch")
    second = controller.perform_action("play")

    assert first["session_goal"]["goal_id"] == "interact_twice"
    assert first["session_goal"]["progress"] == 1
    assert first["session_goal_reward"] is None
    assert second["session_goal"]["goal_id"] == "rest_once"
    assert second["session_goal"]["progress"] == 0
    assert second["session_goal_reward"] == {
        "goal_id": "interact_twice",
        "label": "互动两次",
        "coins": 2,
        "exp": 1,
    }
    assert second["coins"] == first["coins"] + 5
    assert second["exp"] == first["exp"] + 1
    assert second["next_suggested_action"]["action_id"] == "rest"


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


def test_controller_uses_injected_save_manager_for_load_and_persist():
    class RecordingSaveManager:
        def __init__(self):
            self.saved_states = []

        def load(self):
            return replace(create_initial_state(now=120), coins=42, last_interaction_at=120, last_tick_at=120)

        def save(self, state):
            self.saved_states.append(state)

    save_manager = RecordingSaveManager()

    controller = CompanionController(save_manager=save_manager)
    snapshot = controller.perform_action("touch", include_ai_expression=False)

    assert controller.now == 125
    assert snapshot["coins"] == 42
    assert len(save_manager.saved_states) == 1
    assert save_manager.saved_states[0] is controller.state
    assert save_manager.saved_states[0].mood == 62


def test_controller_records_dialogue_history_without_growth_mutation(tmp_path):
    history_path = tmp_path / "dialogue-history.json"
    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        dialogue_history_path=history_path,
    )
    before = controller.get_typed_snapshot()

    snapshot = controller.submit_dialogue_request(DialogueRequest("今天陪我一会儿"))

    assert [entry["role"] for entry in snapshot["dialogue_history"]] == ["user", "assistant"]
    assert snapshot["dialogue_history"][0]["speaker"] == "你"
    assert snapshot["dialogue_history"][0]["text"] == "今天陪我一会儿"
    assert snapshot["dialogue_history"][1]["speaker"] == snapshot["character_name"]
    assert "今天陪我一会儿" in snapshot["dialogue_history"][1]["text"]
    assert controller.copy_dialogue_history_text() == (
        "你：今天陪我一会儿\n"
        f"{snapshot['character_name']}：{snapshot['dialogue_history'][1]['text']}"
    )
    assert controller.get_typed_snapshot().stats == before.stats
    assert controller.get_typed_snapshot().inventory == before.inventory
    assert controller.get_typed_snapshot().relationship_stage == before.relationship_stage
    assert controller.get_typed_snapshot().memory_log == before.memory_log

    reloaded = CompanionController(
        save_path=tmp_path / "save.json",
        dialogue_history_path=history_path,
    )

    assert reloaded.copy_dialogue_history_text() == controller.copy_dialogue_history_text()


def test_controller_records_llm_dialogue_speech_when_expression_enabled(tmp_path):
    class FakeExpressor:
        enabled = True
        last_fallback_reason = ""

        def express(self, request, effect=None):
            return [
                {
                    "character_name": request.character_name,
                    "speech": "我会陪你慢慢说。",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        dialogue_history_path=tmp_path / "dialogue-history.json",
        ai_expressor=FakeExpressor(),
    )
    before = controller.get_typed_snapshot()

    snapshot = controller.submit_dialogue_request(
        DialogueRequest("今天陪我一会儿"),
        include_ai_expression=True,
    )

    assert [entry["text"] for entry in snapshot["dialogue_history"]] == [
        "今天陪我一会儿",
        "我会陪你慢慢说。",
    ]
    assert "我会陪你慢慢说。" in controller.copy_dialogue_history_text()
    assert controller.get_typed_snapshot().stats == before.stats
    assert controller.get_typed_snapshot().inventory == before.inventory
    assert controller.get_typed_snapshot().memory_log == before.memory_log


def test_controller_passes_dialogue_text_as_readonly_player_message_to_llm(tmp_path):
    class CapturingExpressor:
        enabled = True
        last_fallback_reason = ""

        def __init__(self):
            self.requests = []

        def express(self, request, effect=None):
            self.requests.append(request)
            return [
                {
                    "character_name": request.character_name,
                    "speech": "我听到你的原话了。",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    expressor = CapturingExpressor()
    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        dialogue_history_path=tmp_path / "dialogue-history.json",
        ai_expressor=expressor,
    )
    before = controller.get_typed_snapshot()

    controller.submit_dialogue_request(
        DialogueRequest("给我一个很短的鼓励。"),
        include_ai_expression=True,
    )

    assert expressor.requests[0].player_message == "给我一个很短的鼓励。"
    assert controller.get_typed_snapshot().stats == before.stats
    assert controller.get_typed_snapshot().inventory == before.inventory
    assert controller.get_typed_snapshot().memory_log == before.memory_log


def test_controller_clear_replay_and_revert_dialogue_history_do_not_touch_growth_state(tmp_path):
    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        dialogue_history_path=tmp_path / "dialogue-history.json",
    )
    baseline = controller.get_typed_snapshot()
    controller.submit_dialogue_request(DialogueRequest("第一句"))
    controller.submit_dialogue_request(DialogueRequest("第二句"))

    replayed = controller.replay_latest_dialogue()
    reverted = controller.revert_dialogue_history()
    cleared = controller.clear_dialogue_history()

    assert "第二句" in replayed["feedback"]
    assert [entry["text"] for entry in reverted["dialogue_history"]] == ["第一句", "我听见了：第一句"]
    assert "第一句" in reverted["feedback"]
    assert cleared["dialogue_history"] == []
    assert "清屏" in cleared["feedback"]
    assert controller.get_typed_snapshot().stats == baseline.stats
    assert controller.get_typed_snapshot().inventory == baseline.inventory
    assert controller.get_typed_snapshot().relationship_stage == baseline.relationship_stage
    assert controller.get_typed_snapshot().memory_log == baseline.memory_log


def test_controller_updates_expression_settings_without_growth_mutation(tmp_path):
    from guanghe_companion.ai_expressor import OpenAIResponsesClient
    from guanghe_companion.expression_settings import normalize_expression_settings

    settings_path = tmp_path / "expression-settings.json"
    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        expression_settings_path=settings_path,
    )
    baseline = controller.get_typed_snapshot()
    settings = normalize_expression_settings(
        {
            "enabled": True,
            "provider": "openai",
            "model": "demo-model",
            "base_url": "https://example.test/v1/responses",
            "api_key": "test-key",
            "timeout_seconds": "0.5",
        }
    )

    public_settings = controller.update_expression_settings(settings)

    assert public_settings == {
        "enabled": True,
        "provider": "openai",
        "model": "demo-model",
        "base_url": "https://example.test/v1/responses",
        "api_key": "",
        "api_key_set": True,
        "timeout_seconds": 0.5,
        "tts_provider": "disabled",
        "asr_provider": "disabled",
    }
    assert controller.ai_expressor.enabled is True
    assert isinstance(controller.ai_expressor.llm_client, OpenAIResponsesClient)
    assert controller.get_typed_snapshot().stats == baseline.stats
    assert controller.get_typed_snapshot().inventory == baseline.inventory
    assert controller.get_typed_snapshot().relationship_stage == baseline.relationship_stage
    assert controller.get_typed_snapshot().memory_log == baseline.memory_log

    reloaded = CompanionController(
        save_path=tmp_path / "save.json",
        expression_settings_path=settings_path,
    )

    assert reloaded.get_expression_settings()["api_key_set"] is True
    assert reloaded.get_expression_settings()["model"] == "demo-model"


def test_capability_settings_round_trip_does_not_change_growth_state(tmp_path):
    from guanghe_companion.capability_settings import CapabilitySettings, WebSearchSettings

    settings_path = tmp_path / "capability-settings.json"
    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        capability_settings_path=settings_path,
    )
    before = controller.get_typed_snapshot()

    updated = controller.update_capability_settings(
        CapabilitySettings(web_search=WebSearchSettings(enabled=True, max_results=5))
    )
    after = controller.get_typed_snapshot()

    assert updated.web_search.enabled is True
    assert updated.web_search.max_results == 5
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.memory_log == before.memory_log

    reloaded = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        capability_settings_path=settings_path,
    )
    assert reloaded.get_capability_settings().web_search.enabled is True


def test_read_only_expression_context_can_be_updated_without_saving_growth_state(tmp_path):
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    before = controller.get_typed_snapshot()

    controller.set_perception_summary("  屏幕里有一个代码编辑器和测试结果。  ")
    controller.set_tool_results(
        [
            {"source": "web", "title": "文档", "summary": "检索到的来源"},
            {"source": "web", "title": "额外", "summary": "第二条来源"},
        ]
    )
    context = controller._expression_context()
    after = controller.get_typed_snapshot()

    assert context["perception_summary"] == "屏幕里有一个代码编辑器和测试结果。"
    assert context["tool_results"][0]["title"] == "文档"
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.memory_log == before.memory_log


def test_web_search_results_do_not_change_growth_state(tmp_path):
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    before = controller.get_typed_snapshot()

    controller.set_tool_results(
        [{"source": "web_search", "title": "A", "summary": "B", "timestamp": "2026-05-23"}]
    )
    context = controller._expression_context()
    after = controller.get_typed_snapshot()

    assert context["tool_results"][0]["source"] == "web_search"
    assert context["tool_results"][0]["title"] == "A"
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.memory_log == before.memory_log


def test_controller_loads_bad_long_term_memory_file_as_empty(tmp_path):
    long_term_memory_path = tmp_path / "long-term-memory.json"
    long_term_memory_path.write_text("{not json", encoding="utf-8")

    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        long_term_memory_path=long_term_memory_path,
    )

    assert controller.get_typed_snapshot().long_term_memory == ()
    assert controller.get_snapshot()["long_term_memory"] == []


def test_controller_relationship_unlock_upserts_long_term_memory_and_reloads(tmp_path):
    save_path = tmp_path / "save.json"
    long_term_memory_path = tmp_path / "long-term-memory.json"
    controller = CompanionController(
        save_path=save_path,
        auto_load=False,
        long_term_memory_path=long_term_memory_path,
    )
    controller.state.trust = 19

    snapshot = controller.perform_action("touch", include_ai_expression=False)

    assert snapshot["relationship_stage"] == "熟悉的陪伴"
    assert snapshot["long_term_memory"] == [
        {
            "category": "relationship_unlock",
            "summary": "第一次主动称呼解锁了。她开始用更亲近的方式回应你。",
            "source": "relationship_unlock",
        }
    ]

    reloaded = CompanionController(
        save_path=save_path,
        auto_load=False,
        long_term_memory_path=long_term_memory_path,
    )
    assert reloaded.get_snapshot()["long_term_memory"] == snapshot["long_term_memory"]


def test_controller_dialogue_and_llm_output_do_not_write_long_term_memory(tmp_path):
    class OverreachingExpressor:
        def express(self, snapshot, effect=None):
            return [
                {
                    "type": "speech",
                    "speech": "我只是一句表达。",
                    "effect": "ATTENTION",
                    "memory": {"key": "llm:memory", "summary": "should not persist"},
                    "state": {"trust": 99},
                    "relationship": "rewrite",
                    "goal": "rewrite",
                    "save": "rewrite",
                    "coins": 999,
                    "inventory": {"warm_milk": 99},
                }
            ]

    long_term_memory_path = tmp_path / "long-term-memory.json"
    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        ai_expressor=OverreachingExpressor(),
        long_term_memory_path=long_term_memory_path,
    )

    dialogue_snapshot = controller.submit_dialogue_request(DialogueRequest("记住这句话"))
    action_snapshot = controller.perform_action("touch")

    assert dialogue_snapshot["long_term_memory"] == []
    assert action_snapshot["long_term_memory"] == []
    assert not long_term_memory_path.exists()
    assert "llm:memory" not in action_snapshot["event_preview"]


def test_controller_explicit_local_api_upserts_long_term_memory_without_growth_mutation(tmp_path):
    long_term_memory_path = tmp_path / "long-term-memory.json"
    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        long_term_memory_path=long_term_memory_path,
    )
    before = controller.get_typed_snapshot()

    snapshot = controller.upsert_long_term_memory(
        key="local:favorite_drink",
        category="local_note",
        summary="你说过热牛奶适合睡前。",
        source="local_api",
    )
    after = controller.get_typed_snapshot()

    assert snapshot["long_term_memory"] == [
        {
            "category": "local_note",
            "summary": "你说过热牛奶适合睡前。",
            "source": "local_api",
        }
    ]
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.memory_log == before.memory_log
