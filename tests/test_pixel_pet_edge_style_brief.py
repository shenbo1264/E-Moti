from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "art" / "pixel_pet_edge_style_brief.py"


def write_visual_qa_report(path: Path, *, status: str = "ready_with_warnings") -> Path:
    payload = {
        "ok": True,
        "status": status,
        "spritesheet_path": "assets\\companion\\xingxi_pixel_pet\\spritesheet.png",
        "motion_manifest_path": "assets\\companion\\xingxi_pixel_pet\\motion_manifest.json",
        "width": 1536,
        "height": 1872,
        "mode": "RGBA",
        "visible_pixel_count": 916167,
        "edge_pixel_count": 37202,
        "suspicious_edge_halo_pixel_count": 13883 if status == "ready_with_warnings" else 0,
        "suspicious_edge_halo_ratio": 0.373179 if status == "ready_with_warnings" else 0.0,
        "preview_path": "artifacts\\character-library-qa\\xingxi-pixel-pet-visual-qa-preview.png",
        "warnings": ["suspicious_edge_halo_risk"] if status == "ready_with_warnings" else [],
        "errors": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_pixel_pet_edge_style_brief_blocks_default_promotion_for_halo_warning(tmp_path: Path) -> None:
    from tools.art.pixel_pet_edge_style_brief import (
        build_pixel_pet_edge_style_brief,
        render_pixel_pet_edge_style_markdown,
    )

    report_path = write_visual_qa_report(tmp_path / "visual-qa.json")

    brief = build_pixel_pet_edge_style_brief(
        visual_qa_report_path=report_path,
        character_id="xingxi_pixel_pet",
        character_name="Xingxi",
    )

    assert brief.ok is True
    assert brief.character_id == "xingxi_pixel_pet"
    assert brief.decision_state == "regenerate_or_redraw_edge_style"
    assert brief.default_promotion_allowed is False
    assert brief.suspicious_edge_halo_ratio == 0.373179
    assert "suspicious_edge_halo_risk" in brief.blockers
    assert "Do not run automatic transparent edge erasing on the current bundled spritesheet." in brief.prompt_locks
    assert "Preserve Xingxi's blue-purple hair mass" in brief.regeneration_prompt
    assert "no red or purple outer halo" in brief.regeneration_prompt
    assert "exactly ONE standalone base reference sprite" in brief.regeneration_prompt
    assert "NOT a sprite sheet" in brief.regeneration_prompt
    assert "NOT a row strip" in brief.regeneration_prompt
    assert "NOT an atlas" in brief.regeneration_prompt
    assert "Do not repeat the character" in brief.regeneration_prompt
    assert "sprite sheet, row strip, atlas" in brief.negative_prompt
    assert "red edge halo" in brief.negative_prompt
    assert any("pixel_pet_visual_qa.py" in command for command in brief.suggested_commands)
    assert any("--fail-on-warnings" in command for command in brief.suggested_commands)
    prepare_command = next(command for command in brief.suggested_commands if "prepare_pet_run.py" in command)
    assert "exactly one standalone base reference sprite" in prepare_command
    assert "no sprite sheet" in prepare_command
    assert "no row strip" in prepare_command
    assert "no atlas" in prepare_command
    assert any("tests\\test_app.py" in command for command in brief.acceptance_gates)
    markdown = render_pixel_pet_edge_style_markdown(brief)
    assert "# Pixel Pet Edge Style Decision Brief" in markdown
    assert "- Decision state: `regenerate_or_redraw_edge_style`" in markdown
    assert "## Regeneration Prompt" in markdown
    assert "## Acceptance Gates" in markdown


def test_pixel_pet_edge_style_brief_allows_manual_review_when_visual_qa_is_ready(tmp_path: Path) -> None:
    from tools.art.pixel_pet_edge_style_brief import build_pixel_pet_edge_style_brief

    report_path = write_visual_qa_report(tmp_path / "visual-qa.json", status="ready")

    brief = build_pixel_pet_edge_style_brief(
        visual_qa_report_path=report_path,
        character_id="xingxi_pixel_pet",
        character_name="Xingxi",
    )

    assert brief.ok is True
    assert brief.decision_state == "eligible_for_manual_default_review"
    assert brief.default_promotion_allowed is False
    assert brief.blockers == ()
    assert "run real desktop manual QA before default promotion" in brief.next_actions


def test_pixel_pet_edge_style_brief_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    report_path = write_visual_qa_report(tmp_path / "visual-qa.json")
    output_json = tmp_path / "edge-style-brief.json"
    output_md = tmp_path / "edge-style-brief.md"

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--visual-qa-report",
            str(report_path),
            "--character-id",
            "xingxi_pixel_pet",
            "--character-name",
            "Xingxi",
            "--report",
            str(output_json),
            "--markdown",
            str(output_md),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["decision_state"] == "regenerate_or_redraw_edge_style"
    assert payload["default_promotion_allowed"] is False
    assert output_json.is_file()
    assert output_md.is_file()
    assert "Pixel Pet Edge Style Decision Brief" in output_md.read_text(encoding="utf-8")
