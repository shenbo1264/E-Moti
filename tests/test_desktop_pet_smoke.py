from pathlib import Path
import os
import subprocess
import sys


def test_desktop_pet_smoke_validator_accepts_current_window(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController
    from tools.desktop_pet_smoke import validate_desktop_pet_window

    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "smoke-save.json"
    window = CompanionWindow(
        controller=CompanionController(save_path=save_path, auto_load=False),
        desktop_mode=True,
    )
    window.show()
    app.processEvents()

    errors = validate_desktop_pet_window(app, window)

    assert errors == []
    assert save_path.exists()
    assert Path("data/companion_save.json").resolve() != save_path.resolve()

    window.close()
    app.processEvents()


def test_desktop_pet_smoke_validator_accepts_dialogue_controls(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController
    from tools.desktop_pet_smoke import validate_desktop_pet_window

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(
        controller=CompanionController(save_path=tmp_path / "smoke-save.json", auto_load=False),
        desktop_mode=True,
    )
    window.show()
    app.processEvents()

    assert window.dialogue_input.isVisibleTo(window)
    assert window.dialogue_send_button.isVisibleTo(window)
    assert window.dialogue_asr_button.text() in {"Mic", "🎙"}
    assert window.dialogue_asr_button.isEnabled() is False
    assert validate_desktop_pet_window(app, window) == []

    window.close()
    app.processEvents()


def test_desktop_pet_smoke_validator_accepts_dialogue_history_menu(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController
    from tools.desktop_pet_smoke import EXPECTED_MENU_LABELS, validate_desktop_pet_window

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(
        controller=CompanionController(save_path=tmp_path / "smoke-save.json", auto_load=False),
        desktop_mode=True,
    )
    window.show()
    app.processEvents()

    assert EXPECTED_MENU_LABELS == (
        "状态面板",
        "对话历史",
        "清屏",
        "复制对话",
        "回放上一句",
        "回溯上一轮",
        "返回控制面板",
        "退出",
    )
    assert validate_desktop_pet_window(app, window) == []

    window.close()
    app.processEvents()


def test_desktop_pet_smoke_validator_reports_window_escape(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController
    from tools.desktop_pet_smoke import validate_desktop_pet_window

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(
        controller=CompanionController(save_path=tmp_path / "smoke-save.json", auto_load=False),
        desktop_mode=True,
    )
    window.desktop_shell.available_geometry_provider = lambda: QRect(0, 0, 100, 100)
    window.move(120, 120)
    window.show()
    app.processEvents()

    errors = validate_desktop_pet_window(app, window)

    assert "window is outside available screen bounds" in errors

    window.close()
    app.processEvents()


def test_desktop_pet_smoke_pumps_events_between_validation_intervals():
    from tools.desktop_pet_smoke import _pump_events_for

    class FakeApp:
        def __init__(self):
            self.process_events_calls = 0

        def processEvents(self):
            self.process_events_calls += 1

    current_time = 0.0

    def monotonic():
        return current_time

    def sleep(seconds):
        nonlocal current_time
        current_time += seconds

    app = FakeApp()

    _pump_events_for(app, seconds=0.2, step=0.05, monotonic=monotonic, sleep=sleep)

    assert app.process_events_calls >= 4


def test_desktop_pet_smoke_cli_runs_from_repo_root_without_pythonpath(monkeypatch):
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [
            sys.executable,
            "tools/desktop_pet_smoke.py",
            "--seconds",
            "0.1",
            "--interval",
            "0.05",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "desktop pet smoke ok:" in result.stdout
