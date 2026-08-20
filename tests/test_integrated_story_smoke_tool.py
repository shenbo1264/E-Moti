from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = Path("/mnt/data/E-Moti-submission.zip")


def test_integrated_story_smoke_accepts_explicit_paths(tmp_path: Path) -> None:
    if not SUBMISSION.is_file():
        return
    output = tmp_path / "smoke"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "run_integrated_story_smoke.py"),
            "--output-dir",
            str(output),
            "--submission-zip",
            str(SUBMISSION),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    report = json.loads((output / "integration_smoke_report.json").read_text(encoding="utf-8"))
    assert report["memory_flow"]["first_milk_memory_count"] == 1
    assert report["memory_flow"]["repeat_milk_memory_count"] == 0
    findings = report["security"]["submission_config_findings"]
    assert len(findings) == len({(row["path"], row["field"]) for row in findings})
