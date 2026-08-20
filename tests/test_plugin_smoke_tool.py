from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_bundled_plugin_smoke_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "plugin-smoke.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "run_plugin_smoke.py"),
            "--report",
            str(report_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert all(report["checks"].values())
    assert report["private_data_in_report"] is False
