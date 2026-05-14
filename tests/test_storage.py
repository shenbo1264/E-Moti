from pathlib import Path
import json

from guanghe_companion.controller import CompanionController
from guanghe_companion.storage import load_state, save_state


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
