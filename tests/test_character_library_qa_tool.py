from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_character_library_qa_reports_bundled_xingxi_pixel_candidate(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from tools.character_library_qa import run_character_library_qa

    report_path = tmp_path / "character-library-qa.json"
    screenshot_dir = tmp_path / "screenshots"

    report = run_character_library_qa(
        character_id="xingxi_pixel_pet",
        report_path=report_path,
        screenshot_dir=screenshot_dir,
        pet_seconds=0.1,
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert report.ok is True
    assert payload["ok"] is True
    assert payload["default_character_id"] == "original_oc"
    assert payload["selected_character_id"] == "xingxi_pixel_pet"
    assert payload["after_switch_character_id"] == "xingxi_pixel_pet"
    assert payload["candidate_backend"] == "sprite"
    assert payload["desktop_backend"] == "sprite"
    assert set(payload["available_character_ids"]) >= {"original_oc", "xingxi_pixel_pet"}
    assert payload["errors"] == []
    assert Path(payload["character_library_screenshot"]).is_file()
    assert Path(payload["desktop_pet_screenshot"]).is_file()


def test_character_library_qa_cli_runs_from_repo_root(tmp_path):
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("PYTHONPATH", None)
    report_path = tmp_path / "character-library-qa.json"
    screenshot_dir = tmp_path / "screenshots"

    result = subprocess.run(
        [
            sys.executable,
            "tools/character_library_qa.py",
            "--character-id",
            "xingxi_pixel_pet",
            "--report",
            str(report_path),
            "--screenshot-dir",
            str(screenshot_dir),
            "--pet-seconds",
            "0.1",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert "character library QA ok" in result.stdout
