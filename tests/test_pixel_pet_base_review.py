from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from tools.art.review_pixel_pet_base import review_pixel_pet_base_candidate


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "art" / "review_pixel_pet_base.py"


def write_base_candidate(path: Path, *, background: tuple[int, int, int] = (255, 0, 255)) -> None:
    image = Image.new("RGB", (512, 512), background)
    draw = ImageDraw.Draw(image)
    draw.rectangle((180, 120, 330, 420), fill=(80, 120, 180))
    draw.rectangle((210, 160, 300, 230), fill=(230, 240, 255))
    draw.rectangle((220, 250, 290, 380), fill=(20, 30, 50))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def write_prompt(path: Path) -> None:
    path.write_text(
        "Create a compact pixel-adjacent digital pet sprite on #FF00FF background.",
        encoding="utf-8",
    )


def write_character_definition(path: Path, *, character_id: str = "xingxi_pixel_pet") -> None:
    path.write_text(
        json.dumps(
            {
                "track": "original",
                "character_id": character_id,
                "display_name": "Xingxi",
                "distribution": "eligible_after_original_asset_QA",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def write_prior_qa(path: Path, *, decision: str = "accepted_for_row_testing") -> None:
    path.write_text(
        json.dumps(
            {
                "status": "first_row_identity_check",
                "character_id": "xingxi_pixel_pet",
                "base_decision": decision,
                "notes": ["base identity is strong"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_review_pixel_pet_base_accepts_candidate_and_writes_outputs(tmp_path: Path) -> None:
    candidate = tmp_path / "base.png"
    prompt = tmp_path / "base-pet.md"
    definition = tmp_path / "character_definition.json"
    prior_qa = tmp_path / "first-row-qa.json"
    report_path = tmp_path / "review" / "base-review.json"
    markdown_path = tmp_path / "review" / "base-review.md"
    preview_path = tmp_path / "review" / "base-review.png"
    write_base_candidate(candidate)
    write_prompt(prompt)
    write_character_definition(definition)
    write_prior_qa(prior_qa)

    report = review_pixel_pet_base_candidate(
        candidate_image=candidate,
        character_id="xingxi_pixel_pet",
        prompt_path=prompt,
        character_definition_path=definition,
        prior_qa_path=prior_qa,
        decision="accepted_for_row_testing",
        report_path=report_path,
        markdown_path=markdown_path,
        preview_path=preview_path,
    )

    assert report.ok is True
    assert report.character_id == "xingxi_pixel_pet"
    assert report.decision == "accepted_for_row_testing"
    assert report.runtime_manifest_updated is False
    assert report.errors == ()
    assert report_path.is_file()
    assert markdown_path.is_file()
    assert preview_path.is_file()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["asset_boundary"] == "ignored_candidate_only"
    assert payload["image"]["mode"] == "RGB"


def test_review_pixel_pet_base_rejects_missing_prompt_and_wrong_background(tmp_path: Path) -> None:
    candidate = tmp_path / "base.png"
    definition = tmp_path / "character_definition.json"
    write_base_candidate(candidate, background=(255, 255, 255))
    write_character_definition(definition)

    report = review_pixel_pet_base_candidate(
        candidate_image=candidate,
        character_id="xingxi_pixel_pet",
        prompt_path=tmp_path / "missing.md",
        character_definition_path=definition,
        decision="accepted_for_row_testing",
    )

    assert report.ok is False
    assert "prompt file not found" in report.errors
    assert "candidate background corners should be flat #FF00FF chroma key" in report.errors


def test_review_pixel_pet_base_accepts_near_magenta_candidate_with_cleanup_warning(tmp_path: Path) -> None:
    candidate = tmp_path / "base.png"
    prompt = tmp_path / "base-pet.md"
    definition = tmp_path / "character_definition.json"
    write_base_candidate(candidate, background=(236, 12, 235))
    with Image.open(candidate) as image:
        image.putpixel((0, 0), (236, 12, 235))
        image.putpixel((image.width - 1, 0), (243, 16, 240))
        image.putpixel((0, image.height - 1), (234, 35, 234))
        image.putpixel((image.width - 1, image.height - 1), (240, 29, 238))
        image.save(candidate)
    write_prompt(prompt)
    write_character_definition(definition)

    report = review_pixel_pet_base_candidate(
        candidate_image=candidate,
        character_id="xingxi_pixel_pet",
        prompt_path=prompt,
        character_definition_path=definition,
        decision="accepted_for_row_testing",
    )

    assert report.ok is True
    assert any("cleanup required before sprite slicing" in warning for warning in report.warnings)


def test_review_pixel_pet_base_warns_when_prior_qa_does_not_accept_base(tmp_path: Path) -> None:
    candidate = tmp_path / "base.png"
    prompt = tmp_path / "base-pet.md"
    definition = tmp_path / "character_definition.json"
    prior_qa = tmp_path / "first-row-qa.json"
    write_base_candidate(candidate)
    write_prompt(prompt)
    write_character_definition(definition)
    write_prior_qa(prior_qa, decision="needs_regeneration")

    report = review_pixel_pet_base_candidate(
        candidate_image=candidate,
        character_id="xingxi_pixel_pet",
        prompt_path=prompt,
        character_definition_path=definition,
        prior_qa_path=prior_qa,
        decision="candidate",
    )

    assert report.ok is True
    assert "prior QA base_decision is needs_regeneration" in report.warnings


def test_review_pixel_pet_base_tool_outputs_json_markdown_and_preview(tmp_path: Path) -> None:
    candidate = tmp_path / "base.png"
    prompt = tmp_path / "base-pet.md"
    definition = tmp_path / "character_definition.json"
    output_dir = tmp_path / "review"
    write_base_candidate(candidate)
    write_prompt(prompt)
    write_character_definition(definition)

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            str(candidate),
            "--character-id",
            "xingxi_pixel_pet",
            "--prompt",
            str(prompt),
            "--character-definition",
            str(definition),
            "--decision",
            "accepted_for_row_testing",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert (output_dir / "base-review.json").is_file()
    assert (output_dir / "base-review.md").is_file()
    assert (output_dir / "base-review.png").is_file()
