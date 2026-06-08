import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "release_readiness_report.py"


def _copy_original_pack(target: Path) -> Path:
    source = REPO_ROOT / "assets" / "companion" / "original_oc"
    destination = target / "original_oc"
    shutil.copytree(source, destination)
    return destination


def _write_frozen_build(root: Path, *, include_license: bool = True) -> tuple[Path, Path]:
    app_dir = root / "dist" / "E-Moti"
    character_dir = app_dir / "_internal" / "assets" / "companion"
    _copy_original_pack(character_dir)
    if not include_license:
        (character_dir / "original_oc" / "LICENSE.md").unlink()
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "E-Moti.exe").write_bytes(b"MZ" + b"0" * 128)
    installer = root / "dist" / "installer" / "E-Moti_Setup_0.1.0.exe"
    installer.parent.mkdir(parents=True)
    installer.write_bytes(b"MZ" + b"1" * 128)
    return app_dir, installer


def _run_tool(character_pack: Path, app_dir: Path, installer: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--character-pack",
            str(character_pack),
            "--app-dir",
            str(app_dir),
            "--installer",
            str(installer),
            "--json",
            str(tmp_path / "readiness.json"),
            "--markdown",
            str(tmp_path / "readiness.md"),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )


def test_release_readiness_report_accepts_ready_source_and_frozen_artifacts(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")

    result = _run_tool(character_pack, app_dir, installer, tmp_path)

    payload = json.loads(result.stdout)
    saved = json.loads((tmp_path / "readiness.json").read_text(encoding="utf-8"))
    assert result.returncode == 0, result.stderr
    assert payload == saved
    assert payload["ok"] is True
    assert payload["status"] == "ready"
    assert [check["id"] for check in payload["checks"]] == ["source_character_pack", "windows_build"]
    assert all(check["ok"] is True for check in payload["checks"])
    assert payload["next_actions"] == []
    assert (tmp_path / "readiness.md").read_text(encoding="utf-8").startswith("# E-Moti Release Readiness")


def test_release_readiness_report_surfaces_source_pack_distribution_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    (character_pack / "LICENSE.md").unlink()
    app_dir, installer = _write_frozen_build(tmp_path / "build")

    result = _run_tool(character_pack, app_dir, installer, tmp_path)

    payload = json.loads(result.stdout)
    source_check = payload["checks"][0]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["status"] == "needs_attention"
    assert source_check["id"] == "source_character_pack"
    assert source_check["ok"] is False
    assert source_check["status"] == "needs_distribution_review"
    assert "add license or usage-rights note before sharing or bundling" in payload["next_actions"]


def test_release_readiness_report_surfaces_frozen_build_license_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build", include_license=False)

    result = _run_tool(character_pack, app_dir, installer, tmp_path)

    payload = json.loads(result.stdout)
    build_check = payload["checks"][1]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert build_check["id"] == "windows_build"
    assert build_check["ok"] is False
    assert "frozen character pack missing required bundled asset: LICENSE.md" in build_check["errors"]
    assert "rebuild Windows app and installer after fixing release artifacts" in payload["next_actions"]
