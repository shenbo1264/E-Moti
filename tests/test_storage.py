from pathlib import Path
import json

from guanghe_companion.controller import CompanionController
from guanghe_companion.engine import create_initial_state
import guanghe_companion.storage as storage_module
from guanghe_companion.storage import CURRENT_SAVE_SCHEMA_VERSION, load_state, logical_time_from_state, save_state


def test_save_and_load_round_trip(tmp_path: Path):
    controller = CompanionController(save_path=tmp_path / "controller-save.json", auto_load=False)
    controller.perform_action("study")
    controller.buy_selected_item("warm_milk")

    save_path = tmp_path / "save.json"
    save_state(controller.state, save_path)

    loaded = load_state(save_path)

    assert loaded.coins == controller.state.coins
    assert loaded.exp == controller.state.exp
    assert loaded.inventory["warm_milk"] == 1
    assert loaded.current_goal_id == controller.state.current_goal_id


def test_save_state_writes_current_schema_version(tmp_path: Path):
    state = create_initial_state(now=0)
    save_path = tmp_path / "save.json"

    save_state(state, save_path)

    payload = json.loads(save_path.read_text(encoding="utf-8"))
    assert payload.get("schema_version") == 1


def test_load_state_backfills_schema_version_for_older_saves(tmp_path: Path):
    save_path = tmp_path / "old-save.json"
    save_state(create_initial_state(now=0), save_path)
    payload = json.loads(save_path.read_text(encoding="utf-8"))
    payload.pop("schema_version", None)
    save_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_state(save_path)

    assert loaded is not None
    assert getattr(loaded, "schema_version", None) == 1


def test_save_manager_wraps_schema_aware_load_and_save(tmp_path: Path):
    save_path = tmp_path / "managed-save.json"
    manager_type = getattr(storage_module, "SaveManager", None)

    assert manager_type is not None
    manager = manager_type(save_path)
    manager.save(create_initial_state(now=0))
    payload = json.loads(save_path.read_text(encoding="utf-8"))
    loaded = manager.load()

    assert payload.get("schema_version") == 1
    assert loaded is not None
    assert getattr(loaded, "schema_version", None) == 1


def test_load_state_ignores_unknown_top_level_fields_from_future_saves(tmp_path: Path):
    save_path = tmp_path / "future-save.json"
    save_state(create_initial_state(now=0), save_path)
    payload = json.loads(save_path.read_text(encoding="utf-8"))
    payload["future_field"] = {"should": "not crash old demo"}
    save_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_state(save_path)

    assert loaded is not None
    assert not hasattr(loaded, "future_field")
    assert loaded.schema_version == CURRENT_SAVE_SCHEMA_VERSION


def test_load_state_normalizes_invalid_schema_version(tmp_path: Path):
    save_path = tmp_path / "invalid-schema-save.json"
    save_state(create_initial_state(now=0), save_path)
    payload = json.loads(save_path.read_text(encoding="utf-8"))
    payload["schema_version"] = "not-an-int"
    save_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_state(save_path)

    assert loaded is not None
    assert loaded.schema_version == CURRENT_SAVE_SCHEMA_VERSION


def test_load_state_returns_none_for_corrupt_or_non_object_json(tmp_path: Path):
    corrupt = tmp_path / "corrupt-save.json"
    corrupt.write_text("{not json", encoding="utf-8")
    non_object = tmp_path / "non-object-save.json"
    non_object.write_text("[1, 2, 3]", encoding="utf-8")

    assert load_state(corrupt) is None
    assert load_state(non_object) is None


def test_load_state_returns_none_for_missing_file(tmp_path: Path):
    missing = tmp_path / "missing.json"

    loaded = load_state(missing)

    assert loaded is None


def test_load_state_backfills_memory_log_for_older_saves(tmp_path: Path):
    controller = CompanionController(save_path=tmp_path / "controller-save.json", auto_load=False)
    save_path = tmp_path / "old-save.json"
    save_state(controller.state, save_path)
    payload = json.loads(save_path.read_text(encoding="utf-8"))
    payload.pop("memory_log")
    save_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_state(save_path)

    assert loaded is not None
    assert loaded.memory_log == []


def test_load_state_backfills_missing_inventory_items(tmp_path: Path):
    controller = CompanionController(save_path=tmp_path / "controller-save.json", auto_load=False)
    save_path = tmp_path / "old-save.json"
    save_state(controller.state, save_path)
    payload = json.loads(save_path.read_text(encoding="utf-8"))
    payload["inventory"] = {"warm_milk": 1}
    save_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_state(save_path)

    assert loaded is not None
    assert loaded.inventory["warm_milk"] == 1
    assert "energy_candy" in loaded.inventory
    assert loaded.inventory["energy_candy"] == 0


def test_load_state_repairs_invalid_inventory_shape(tmp_path: Path):
    save_path = tmp_path / "bad-inventory-save.json"
    save_state(create_initial_state(now=0), save_path)
    payload = json.loads(save_path.read_text(encoding="utf-8"))
    payload["inventory"] = "not a dict"
    save_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_state(save_path)

    assert loaded is not None
    assert loaded.inventory["warm_milk"] == 0
    assert loaded.inventory["energy_candy"] == 0


def test_load_state_repairs_invalid_inventory_counts_and_drops_unknown_items(tmp_path: Path):
    save_path = tmp_path / "bad-inventory-counts-save.json"
    save_state(create_initial_state(now=0), save_path)
    payload = json.loads(save_path.read_text(encoding="utf-8"))
    payload["inventory"] = {
        "warm_milk": "2",
        "energy_candy": -3,
        "berry_tart": True,
        "unknown_item": 5,
    }
    save_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_state(save_path)

    assert loaded is not None
    assert loaded.inventory["warm_milk"] == 2
    assert loaded.inventory["energy_candy"] == 0
    assert loaded.inventory["berry_tart"] == 0
    assert "unknown_item" not in loaded.inventory


def test_logical_time_from_state_uses_latest_runtime_timestamp():
    state = create_initial_state(now=20)
    state.last_interaction_at = 45
    state.last_tick_at = 30
    state.last_gift_at = 60
    state.memory_log = [{"at": 75, "kind": "互动", "summary": "摸摸头", "motion": "TouchHead"}]

    assert logical_time_from_state(state) == 75
