from pathlib import Path

import guanghe_companion.controller as controller_module
from guanghe_companion.controller import CompanionController


def test_default_controller_save_path_is_isolated_during_pytest(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    real_save_path = repo_root / "data" / "companion_save.json"
    before = real_save_path.read_bytes() if real_save_path.exists() else None

    controller = CompanionController(auto_load=False)
    controller.perform_action("touch")

    after = real_save_path.read_bytes() if real_save_path.exists() else None
    assert before == after
    assert controller_module.DEFAULT_SAVE_PATH == tmp_path / "companion_save.json"
    assert controller.save_path == tmp_path / "companion_save.json"
    assert controller.save_path.exists()
