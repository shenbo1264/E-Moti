from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import zipfile

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_private_provider_smoke_is_bounded_and_redacted(tmp_path: Path) -> None:
    submission = tmp_path / "private-submission.zip"
    expression = {
        "enabled": True,
        "provider": "custom",
        "model": "test-model",
        "base_url": "http://127.0.0.1:9/v1",
        "api_key": "sk-" + "test-private-key-should-not-leak",
    }
    capability = {
        "screen_observation": {
            "enabled": True,
            "vision_model": "test-vision",
            "vision_base_url": "http://127.0.0.1:9/v1",
            "vision_api_key": "sk-" + "test-private-vision-key-should-not-leak",
        }
    }
    with zipfile.ZipFile(submission, "w") as archive:
        archive.writestr("user_data/expression_settings.json", json.dumps(expression))
        archive.writestr("user_data/capability_settings.json", json.dumps(capability))
    report = tmp_path / "report.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "run_private_provider_smoke.py"),
            "--submission-zip",
            str(submission),
            "--report",
            str(report),
            "--timeout",
            "1",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = report.read_text(encoding="utf-8")
    assert ("sk-" + "test-private") not in payload
    parsed = json.loads(payload)
    assert parsed["ok"] is True
    assert parsed["online_verified"] is False
    assert parsed["secrets_in_report"] is False
