from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "art" / "hatch_pet_imagegen_route_preflight.py"


def write_run(root: Path) -> None:
    (root / "raw").mkdir(parents=True)
    (root / "prompts").mkdir(parents=True)
    (root / "prompts" / "base-pet.md").write_text("base prompt", encoding="utf-8")
    (root / "imagegen-jobs.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "id": "base",
                        "kind": "base-pet",
                        "status": "pending",
                        "prompt_file": "prompts/base-pet.md",
                        "input_images": [],
                        "output_path": "decoded/base.png",
                        "depends_on": [],
                        "generation_skill": "$imagegen",
                        "requires_grounded_generation": False,
                        "allow_prompt_only_generation": True,
                    },
                    {
                        "id": "idle",
                        "kind": "row-strip",
                        "status": "pending",
                        "prompt_file": "prompts/rows/idle.md",
                        "input_images": [{"path": "decoded/base.png", "role": "canonical base"}],
                        "output_path": "decoded/idle.png",
                        "depends_on": ["base"],
                        "generation_skill": "$imagegen",
                        "requires_grounded_generation": True,
                        "allow_prompt_only_generation": False,
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "raw" / "base.response.json").write_text(
        json.dumps(
            {
                "error": {
                    "message": "Incorrect API key provided: SECRET_TOKEN_SHOULD_NOT_LEAK.",
                    "code": "invalid_api_key",
                },
                "status": 401,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_route_preflight_reports_invalid_key_and_codex_access_denied_without_leaking_secret(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from tools.art.hatch_pet_imagegen_route_preflight import inspect_hatch_pet_imagegen_route_preflight

    def fake_run(*args, **kwargs):
        raise PermissionError("Access is denied")

    monkeypatch.setattr(
        "tools.art.hatch_pet_imagegen_route_preflight.subprocess.run",
        fake_run,
    )
    run_dir = tmp_path / "run"
    write_run(run_dir)

    report = inspect_hatch_pet_imagegen_route_preflight(
        run_dir,
        openai_api_key_present=True,
        check_codex_exec=True,
        codex_bin="codex",
    )

    assert report.ok is False
    assert report.status == "blocked_generation_route"
    assert report.secondary_fallback_status == "blocked_invalid_openai_api_key"
    assert report.codex_exec_status == "access_denied"
    assert report.ready_job_ids == ("base",)
    assert report.blocked_job_ids == ("idle",)
    assert "raw response reports invalid OpenAI API key" in report.blockers
    assert "codex exec is not launchable: access denied" in report.blockers
    payload = json.dumps(report.to_dict(), ensure_ascii=False)
    assert "SECRET_TOKEN_SHOULD_NOT_LEAK" not in payload


def test_route_preflight_cli_writes_report_and_markdown(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    write_run(run_dir)
    report_path = tmp_path / "route-preflight.json"
    markdown_path = tmp_path / "route-preflight.md"

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--run-dir",
            str(run_dir),
            "--codex-bin",
            str(tmp_path / "missing-codex.exe"),
            "--check-codex-exec",
            "--report",
            str(report_path),
            "--markdown",
            str(markdown_path),
            "--openai-api-key-present",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    payload = json.loads(result.stdout)
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert result.returncode == 1
    assert payload == saved
    assert payload["status"] == "blocked_generation_route"
    assert payload["codex_exec_status"] == "missing"
    assert "SECRET_TOKEN_SHOULD_NOT_LEAK" not in result.stdout
    assert "# Hatch Pet Imagegen Route Preflight" in markdown
    assert "- Codex exec status: `missing`" in markdown
