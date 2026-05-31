from pathlib import Path
import importlib.util


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_entrypoint(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_control_panel_entrypoint_launches_demo_save(monkeypatch):
    import guanghe_companion.app as app_module

    captured = {}

    def fake_launch(argv):
        captured["argv"] = argv
        return 23

    monkeypatch.setattr(app_module, "launch", fake_launch)

    module = load_entrypoint(REPO_ROOT / "packaging" / "launch_control_panel.py")

    assert module.main([]) == 23
    assert captured["argv"] == ["E-Moti", "--demo-save"]


def test_control_panel_entrypoint_keeps_shortcut_arguments(monkeypatch):
    import guanghe_companion.app as app_module

    captured = {}

    def fake_launch(argv):
        captured["argv"] = argv
        return 25

    monkeypatch.setattr(app_module, "launch", fake_launch)

    module = load_entrypoint(REPO_ROOT / "packaging" / "launch_control_panel.py")

    assert module.main(["--pet-mode"]) == 25
    assert captured["argv"] == ["E-Moti", "--pet-mode", "--demo-save"]


def test_pet_mode_entrypoint_launches_pet_demo_save(monkeypatch):
    import guanghe_companion.app as app_module

    captured = {}

    def fake_launch(argv):
        captured["argv"] = argv
        return 24

    monkeypatch.setattr(app_module, "launch", fake_launch)

    module = load_entrypoint(REPO_ROOT / "packaging" / "launch_pet_mode.py")

    assert module.main() == 24
    assert captured["argv"] == ["E-Moti", "--pet-mode", "--demo-save"]
