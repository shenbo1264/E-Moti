from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from guanghe_companion.plugin_manifest import load_plugin_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_apply_and_verify_tool_supports_non_destructive_verify_only_mode() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "apply_and_verify_emoti_overlay.py"),
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "--verify-only" in completed.stdout


def test_scaffold_tool_creates_valid_plugin(tmp_path: Path) -> None:
    target = tmp_path / "my-plugin"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "scaffold_emoti_plugin.py"),
            "--target",
            str(target),
            "--id",
            "emoti.community.hello",
            "--name",
            "Hello Plugin",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    manifest = load_plugin_manifest(target / "emoti-plugin.json")
    assert manifest.plugin_id == "emoti.community.hello"
    assert (target / "README.md").exists()
    assert (target / "plugin.py").exists()


def test_validate_tool_emits_machine_readable_report(tmp_path: Path) -> None:
    target = tmp_path / "plugin"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "scaffold_emoti_plugin.py"),
            "--target",
            str(target),
            "--id",
            "emoti.community.valid",
            "--name",
            "Valid Plugin",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    report_path = tmp_path / "report.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "validate_emoti_plugin.py"),
            str(target),
            "--report",
            str(report_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["plugin_id"] == "emoti.community.valid"


def test_validate_tool_activates_required_sibling_dependencies(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    base = plugins / "base"
    child = plugins / "child"
    base.mkdir(parents=True)
    child.mkdir(parents=True)
    (base / "emoti-plugin.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "emoti.test.base",
                "name": "Base",
                "version": "0.1.0",
                "api_version": "1",
                "entrypoint": "plugin.py:activate",
                "default_enabled": False,
                "permissions": [],
            }
        ),
        encoding="utf-8",
    )
    (base / "plugin.py").write_text("def activate(ctx):\n    return None\n", encoding="utf-8")
    (child / "emoti-plugin.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "emoti.test.child",
                "name": "Child",
                "version": "0.1.0",
                "api_version": "1",
                "entrypoint": "plugin.py:activate",
                "default_enabled": False,
                "permissions": [],
                "dependencies": [{"id": "emoti.test.base"}],
            }
        ),
        encoding="utf-8",
    )
    (child / "plugin.py").write_text("def activate(ctx):\n    return None\n", encoding="utf-8")
    report_path = tmp_path / "dependency-report.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "validate_emoti_plugin.py"),
            str(child),
            "--activate",
            "--report",
            str(report_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["load_order"] == ["emoti.test.base", "emoti.test.child"]
