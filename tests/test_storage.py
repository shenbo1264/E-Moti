from pathlib import Path

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
