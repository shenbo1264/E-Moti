from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "art" / "hatch_pet_base_intake_preflight.py"


def write_run(root: Path, *, depends_on: list[str] | None = None, output_exists: bool = False) -> None:
    (root / "prompts").mkdir(parents=True)
    (root / "decoded").mkdir(parents=True)
    (root / "prompts" / "base-pet.md").write_text(
        "Create a compact pixel-adjacent digital pet sprite on #FF00FF background.",
        encoding="utf-8",
    )
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
                        "depends_on": depends_on or [],
                        "generation_skill": "$imagegen",
                        "requires_grounded_generation": False,
                        "allow_prompt_only_generation": True,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    if output_exists:
        write_base_candidate(root / "decoded" / "base.png")


def write_base_candidate(path: Path, *, background: tuple[int, int, int] = (255, 0, 255)) -> None:
    image = Image.new("RGB", (512, 512), background)
    draw = ImageDraw.Draw(image)
    draw.ellipse((160, 90, 350, 285), fill=(98, 132, 214))
    draw.rectangle((200, 245, 310, 430), fill=(88, 62, 142))
    draw.rectangle((228, 145, 244, 165), fill=(20, 25, 55))
    draw.rectangle((272, 145, 288, 165), fill=(20, 25, 55))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def write_character_definition(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "track": "original",
                "character_id": "xingxi_pixel_pet",
                "display_name": "Xingxi",
                "distribution": "eligible_after_original_asset_QA",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def generated_source(tmp_path: Path) -> tuple[Path, Path]:
    generated_root = tmp_path / "codex-home" / "generated_images"
    source = generated_root / "session-1" / "ig_xingxi_base.png"
    write_base_candidate(source)
    return generated_root, source


def test_base_intake_preflight_accepts_builtin_imagegen_source_without_recording(tmp_path: Path) -> None:
    from tools.art.hatch_pet_base_intake_preflight import inspect_hatch_pet_base_intake_preflight

    run_dir = tmp_path / "run"
    definition = tmp_path / "character_definition.json"
    generated_root, source = generated_source(tmp_path)
    write_run(run_dir)
    write_character_definition(definition)

    report = inspect_hatch_pet_base_intake_preflight(
        run_dir=run_dir,
        job_id="base",
        source=source,
        character_id="xingxi_pixel_pet",
        character_definition_path=definition,
        generated_images_root=generated_root,
    )

    payload = report.to_dict()
    assert report.ok is True
    assert report.status == "ready_to_record"
    assert payload["source_provenance"] == "built-in-imagegen"
    assert payload["job_ready"] is True
    assert payload["output_exists"] is False
    assert payload["base_review"]["ok"] is True
    assert "record_imagegen_result.py" in payload["record_command"]
    assert "--job-id base" in payload["record_command"]
    assert not (run_dir / "decoded" / "base.png").exists()
    manifest = json.loads((run_dir / "imagegen-jobs.json").read_text(encoding="utf-8"))
    assert manifest["jobs"][0]["status"] == "pending"


def test_base_intake_preflight_rejects_non_builtin_source(tmp_path: Path) -> None:
    from tools.art.hatch_pet_base_intake_preflight import inspect_hatch_pet_base_intake_preflight

    run_dir = tmp_path / "run"
    definition = tmp_path / "character_definition.json"
    generated_root = tmp_path / "codex-home" / "generated_images"
    source = tmp_path / "manual" / "base.png"
    write_run(run_dir)
    write_character_definition(definition)
    write_base_candidate(source)

    report = inspect_hatch_pet_base_intake_preflight(
        run_dir=run_dir,
        job_id="base",
        source=source,
        character_id="xingxi_pixel_pet",
        character_definition_path=definition,
        generated_images_root=generated_root,
    )

    assert report.ok is False
    assert report.status == "source_not_built_in_imagegen"
    assert any("$CODEX_HOME/generated_images" in error for error in report.errors)
    assert not (run_dir / "decoded" / "base.png").exists()


def test_base_intake_preflight_rejects_not_ready_job(tmp_path: Path) -> None:
    from tools.art.hatch_pet_base_intake_preflight import inspect_hatch_pet_base_intake_preflight

    run_dir = tmp_path / "run"
    definition = tmp_path / "character_definition.json"
    generated_root, source = generated_source(tmp_path)
    write_run(run_dir, depends_on=["missing-upstream"])
    write_character_definition(definition)

    report = inspect_hatch_pet_base_intake_preflight(
        run_dir=run_dir,
        job_id="base",
        source=source,
        character_id="xingxi_pixel_pet",
        character_definition_path=definition,
        generated_images_root=generated_root,
    )

    assert report.ok is False
    assert report.status == "job_not_ready"
    assert "missing dependency result(s): missing-upstream" in report.errors


def test_base_intake_preflight_blocks_existing_output(tmp_path: Path) -> None:
    from tools.art.hatch_pet_base_intake_preflight import inspect_hatch_pet_base_intake_preflight

    run_dir = tmp_path / "run"
    definition = tmp_path / "character_definition.json"
    generated_root, source = generated_source(tmp_path)
    write_run(run_dir, output_exists=True)
    write_character_definition(definition)

    report = inspect_hatch_pet_base_intake_preflight(
        run_dir=run_dir,
        job_id="base",
        source=source,
        character_id="xingxi_pixel_pet",
        character_definition_path=definition,
        generated_images_root=generated_root,
    )

    assert report.ok is False
    assert report.status == "recording_would_overwrite"
    assert "decoded/base.png already exists; recording would overwrite it" in report.errors


def test_base_intake_preflight_cli_writes_report_and_markdown(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    definition = tmp_path / "character_definition.json"
    generated_root, source = generated_source(tmp_path)
    report_path = tmp_path / "base-intake.json"
    markdown_path = tmp_path / "base-intake.md"
    write_run(run_dir)
    write_character_definition(definition)

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--run-dir",
            str(run_dir),
            "--job-id",
            "base",
            "--source",
            str(source),
            "--character-id",
            "xingxi_pixel_pet",
            "--character-definition",
            str(definition),
            "--generated-images-root",
            str(generated_root),
            "--report",
            str(report_path),
            "--markdown",
            str(markdown_path),
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
    assert result.returncode == 0
    assert payload == saved
    assert payload["status"] == "ready_to_record"
    assert "# Hatch Pet Base Intake Preflight" in markdown
    assert "ready_to_record" in markdown
