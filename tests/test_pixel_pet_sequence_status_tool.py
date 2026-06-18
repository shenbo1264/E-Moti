from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_pixel_pet_sequence_status_reports_missing_run_dir(tmp_path: Path) -> None:
    report = tmp_path / "status.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/pixel_pet_sequence_status.py",
            "--run-dir",
            str(tmp_path / "missing"),
            "--report",
            str(report),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["status"] == "missing_run_dir"


def test_pixel_pet_sequence_status_reports_candidate_pack_ready(tmp_path: Path) -> None:
    pack_dir = tmp_path / "run" / "character_packs_drafts" / "sample_pet"
    pack_dir.mkdir(parents=True)
    (pack_dir / "character.json").write_text("{}", encoding="utf-8")
    report = tmp_path / "status.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/pixel_pet_sequence_status.py",
            "--run-dir",
            str(tmp_path / "run"),
            "--report",
            str(report),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["status"] == "has_candidate_pack"
    assert payload["candidate_pack_count"] == 1
