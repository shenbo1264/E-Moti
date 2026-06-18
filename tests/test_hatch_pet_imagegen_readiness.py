from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "art" / "hatch_pet_imagegen_readiness.py"


def write_run(root: Path, *, raw_error_code: str | None = None) -> None:
    (root / "prompts" / "rows").mkdir(parents=True)
    (root / "raw").mkdir(parents=True)
    (root / "prompts" / "base-pet.md").write_text("base prompt", encoding="utf-8")
    (root / "prompts" / "rows" / "idle.md").write_text("idle prompt", encoding="utf-8")
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
                        "input_images": [
                            {"path": "references/canonical-base.png", "role": "canonical identity reference"}
                        ],
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
    if raw_error_code is not None:
        (root / "raw" / "base.response.json").write_text(
            json.dumps(
                {
                    "error": {
                        "message": "Incorrect API key provided: SECRET_TOKEN_SHOULD_NOT_LEAK.",
                        "type": "invalid_request_error",
                        "code": raw_error_code,
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


def test_hatch_pet_imagegen_readiness_blocks_invalid_key_without_leaking_secret(tmp_path: Path) -> None:
    from tools.art.hatch_pet_imagegen_readiness import inspect_hatch_pet_imagegen_readiness

    run_dir = tmp_path / "run"
    write_run(run_dir, raw_error_code="invalid_api_key")

    report = inspect_hatch_pet_imagegen_readiness(run_dir, openai_api_key_present=True)

    assert report.ok is False
    assert report.status == "blocked_invalid_openai_api_key"
    assert report.complete_job_count == 0
    assert report.ready_job_count == 1
    assert report.blocked_job_count == 1
    assert report.ready_job_ids == ("base",)
    assert report.raw_error_codes == ("invalid_api_key",)
    assert "raw response reports invalid OpenAI API key" in report.blockers
    assert all("sk-" not in item for item in report.blockers)
    assert "set a valid OPENAI_API_KEY or use the built-in $imagegen path before retrying base generation" in report.next_actions
    payload = json.dumps(report.to_dict(), ensure_ascii=False)
    assert "SECRET_TOKEN_SHOULD_NOT_LEAK" not in payload


def test_hatch_pet_imagegen_readiness_reports_ready_route_when_no_errors(tmp_path: Path) -> None:
    from tools.art.hatch_pet_imagegen_readiness import inspect_hatch_pet_imagegen_readiness

    run_dir = tmp_path / "run"
    write_run(run_dir)

    report = inspect_hatch_pet_imagegen_readiness(run_dir, openai_api_key_present=True)

    assert report.ok is True
    assert report.status == "ready_for_base_generation"
    assert report.ready_job_ids == ("base",)
    assert report.blockers == ()
    assert "generate only the ready base job first" in report.next_actions


def test_hatch_pet_imagegen_readiness_cli_writes_report_and_markdown(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    write_run(run_dir, raw_error_code="invalid_api_key")
    report_path = tmp_path / "readiness.json"
    markdown_path = tmp_path / "readiness.md"

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--run-dir",
            str(run_dir),
            "--openai-api-key-present",
            "--report",
            str(report_path),
            "--markdown",
            str(markdown_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["status"] == "blocked_invalid_openai_api_key"
    assert "sk-" not in result.stdout
    assert report_path.is_file()
    assert markdown_path.is_file()
    assert "Hatch Pet Imagegen Readiness" in markdown_path.read_text(encoding="utf-8")
