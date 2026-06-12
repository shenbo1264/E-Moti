from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "pixel_pet_emote_mapping_check.py"


def write_motion_manifest(path: Path, motions: set[str]) -> Path:
    payload = {
        "sheet_columns": 8,
        "sheet_rows": 9,
        "frame_width": 192,
        "frame_height": 208,
        "background": "transparent",
        "motions": {
            motion_id: {
                "row": index,
                "frame_count": 4,
                "fps": 5,
            }
            for index, motion_id in enumerate(sorted(motions))
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_pixel_pet_emote_mapping_accepts_current_xingxi_pack() -> None:
    from tools.pixel_pet_emote_mapping_check import inspect_pixel_pet_emote_mapping

    report = inspect_pixel_pet_emote_mapping(REPO_ROOT / "assets" / "companion" / "xingxi_pixel_pet")

    assert report.ok is True
    assert report.status == "ready"
    assert report.character_pack_path.endswith("assets\\companion\\xingxi_pixel_pet") or report.character_pack_path.endswith(
        "assets/companion/xingxi_pixel_pet"
    )
    assert report.missing_motion_ids == ()
    assert report.unsupported_expression_ids == ()
    assert "goofy" in report.supported_expression_ids
    assert "confused" in report.supported_expression_ids
    assert "focused" in report.supported_expression_ids


def test_pixel_pet_emote_mapping_reports_missing_motion_families(tmp_path: Path) -> None:
    from tools.pixel_pet_emote_mapping_check import inspect_pixel_pet_emote_mapping

    pack = tmp_path / "pack"
    write_motion_manifest(pack / "motion_manifest.json", {"Default", "TouchHead", "Sleep", "SwitchDown"})

    report = inspect_pixel_pet_emote_mapping(pack)

    assert report.ok is False
    assert report.status == "missing_motion_families"
    assert report.missing_motion_ids == ("Play", "Raised", "Study")
    assert "goofy" in report.unsupported_expression_ids
    assert "confused" in report.unsupported_expression_ids
    assert "surprised" in report.unsupported_expression_ids
    assert "add motion_manifest entries for: Play, Raised, Study" in report.next_actions


def test_pixel_pet_emote_mapping_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    write_motion_manifest(pack / "motion_manifest.json", {"Default", "TouchHead", "Sleep", "SwitchDown"})
    report_path = tmp_path / "emote-mapping.json"
    markdown_path = tmp_path / "emote-mapping.md"

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            str(pack),
            "--json",
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
    assert result.returncode == 1
    assert payload == saved
    assert payload["status"] == "missing_motion_families"
    assert "# Pixel Pet Emote Mapping Check" in markdown
    assert "- Missing motions: `Play, Raised, Study`" in markdown
