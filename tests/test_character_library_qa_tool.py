from __future__ import annotations

import json
import os
import shutil
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


def test_character_library_qa_accepts_local_character_root(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from tools.character_library_qa import run_character_library_qa

    character_root = tmp_path / "character_packs"
    pack_dir = _copy_bundled_pack_as(character_root, "qa_local_only")
    report_path = tmp_path / "character-library-qa.json"
    screenshot_dir = tmp_path / "screenshots"

    report = run_character_library_qa(
        character_id="qa_local_only",
        report_path=report_path,
        screenshot_dir=screenshot_dir,
        character_root=character_root,
        pet_seconds=0.1,
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert report.ok is True
    assert payload["ok"] is True
    assert payload["selected_character_id"] == "qa_local_only"
    assert payload["after_switch_character_id"] == "qa_local_only"
    assert payload["candidate_source"] == "user"
    assert Path(payload["candidate_pack_path"]).is_relative_to(character_root)
    assert payload["candidate_backend"] == "sprite"
    assert payload["desktop_backend"] == "sprite"
    assert "qa_local_only" in payload["available_character_ids"]
    assert Path(payload["character_library_screenshot"]).is_file()
    assert Path(payload["desktop_pet_screenshot"]).is_file()


def test_character_library_qa_accepts_private_fanwork_boundary(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from tools.character_library_qa import run_character_library_qa

    character_root = tmp_path / "character_packs"
    _copy_bundled_pack_as(
        character_root,
        "private_fanwork_local",
        distribution_boundary="private_local_fanwork",
    )
    report_path = tmp_path / "character-library-qa.json"
    screenshot_dir = tmp_path / "screenshots"

    report = run_character_library_qa(
        character_id="private_fanwork_local",
        report_path=report_path,
        screenshot_dir=screenshot_dir,
        character_root=character_root,
        pet_seconds=0.1,
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert report.ok is True
    assert payload["ok"] is True
    assert payload["candidate_source"] == "user"
    assert payload["after_switch_character_id"] == "private_fanwork_local"
    assert payload["errors"] == []


def test_character_library_qa_cli_accepts_local_character_root(tmp_path):
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("PYTHONPATH", None)
    character_root = tmp_path / "character_packs"
    _copy_bundled_pack_as(character_root, "qa_local_only")
    report_path = tmp_path / "character-library-qa.json"
    screenshot_dir = tmp_path / "screenshots"

    result = subprocess.run(
        [
            sys.executable,
            "tools/character_library_qa.py",
            "--character-id",
            "qa_local_only",
            "--character-root",
            str(character_root),
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
    assert payload["after_switch_character_id"] == "qa_local_only"
    assert payload["candidate_source"] == "user"
    assert Path(payload["candidate_pack_path"]).is_relative_to(character_root)
    assert "character library QA ok" in result.stdout


def test_character_library_qa_character_root_takes_priority_over_bundled_duplicate(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from tools.character_library_qa import run_character_library_qa

    character_root = tmp_path / "character_packs"
    _copy_bundled_pack_as(character_root, "xingxi_pixel_pet")
    report_path = tmp_path / "character-library-qa.json"
    screenshot_dir = tmp_path / "screenshots"

    report = run_character_library_qa(
        character_id="xingxi_pixel_pet",
        report_path=report_path,
        screenshot_dir=screenshot_dir,
        character_root=character_root,
        pet_seconds=0.1,
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert report.ok is True
    assert payload["candidate_source"] == "user"
    assert Path(payload["candidate_pack_path"]).is_relative_to(character_root)
    assert payload["after_switch_character_id"] == "xingxi_pixel_pet"


def _copy_bundled_pack_as(
    character_root: Path,
    character_id: str,
    *,
    distribution_boundary: str = "shareable_after_review",
) -> Path:
    source = REPO_ROOT / "assets" / "companion" / "xingxi_pixel_pet"
    target = character_root / character_id
    shutil.copytree(source, target)
    character_path = target / "character.json"
    payload = json.loads(character_path.read_text(encoding="utf-8-sig"))
    payload["character_id"] = character_id
    payload["name"] = "QA Local"
    payload["title"] = "Local user-pack candidate"
    payload["distribution_boundary"] = distribution_boundary
    character_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
