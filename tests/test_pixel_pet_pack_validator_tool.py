from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

from tools.validate_pixel_pet_pack import validate_pixel_pet_pack_dir


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "validate_pixel_pet_pack.py"


def write_valid_pixel_pet_pack(
    root: Path,
    *,
    character_id: str = "xingxi_pixel_pet",
    distribution_boundary: str = "official_candidate",
) -> None:
    root.mkdir(parents=True)
    (root / "preview").mkdir()
    Image.new("RGBA", (8 * 192, 9 * 208), (0, 0, 0, 0)).save(root / "spritesheet.png")
    Image.new("RGBA", (512, 512), (0, 0, 0, 0)).save(root / "preview" / "contact-sheet.png")
    (root / "motion_manifest.json").write_text(
        json.dumps(
            {
                "sheet_columns": 8,
                "sheet_rows": 9,
                "frame_width": 192,
                "frame_height": 208,
                "motions": {
                    "Default": {"row": 0, "frame_count": 6, "fps": 6},
                    "TouchHead": {"row": 3, "frame_count": 4, "fps": 8},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "character.json").write_text(
        json.dumps(
            {
                "character_id": character_id,
                "name": "Xingxi Pixel Pet",
                "title": "Pixel companion candidate",
                "description": "A local pixel-pet sequence candidate.",
                "spritesheet": "spritesheet.png",
                "motion_manifest": "motion_manifest.json",
                "renderer": {"backend": "sprite"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "dialogue_style.json").write_text(
        json.dumps(
            {
                "tone": "gentle",
                "fallback_style": "short companion line",
                "keywords": ["companion", "pixel"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "provenance.md").write_text(
        "# Provenance\n\nLocal generated pixel-pet candidate for QA.\n",
        encoding="utf-8",
    )
    (root / "qa_report.json").write_text(
        json.dumps(
            {
                "status": "candidate",
                "manual_qa_required": True,
                "distribution_boundary": distribution_boundary,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_validate_pixel_pet_pack_accepts_candidate_contract(tmp_path: Path) -> None:
    pack = tmp_path / "xingxi_pixel_pet"
    write_valid_pixel_pet_pack(pack)

    report = validate_pixel_pet_pack_dir(pack)

    assert report.ok is True
    assert report.character_id == "xingxi_pixel_pet"
    assert report.distribution_boundary == "official_candidate"
    assert report.errors == ()


def test_validate_pixel_pet_pack_rejects_missing_qa_and_provenance(tmp_path: Path) -> None:
    pack = tmp_path / "xingxi_pixel_pet"
    write_valid_pixel_pet_pack(pack)
    (pack / "qa_report.json").unlink()
    (pack / "provenance.md").write_text("", encoding="utf-8")

    report = validate_pixel_pet_pack_dir(pack)

    assert report.ok is False
    assert "qa_report.json is required" in report.errors
    assert "provenance.md must be non-empty" in report.errors


def test_validate_pixel_pet_pack_rejects_unsafe_runtime_paths(tmp_path: Path) -> None:
    pack = tmp_path / "xingxi_pixel_pet"
    write_valid_pixel_pet_pack(pack)
    payload = json.loads((pack / "character.json").read_text(encoding="utf-8"))
    payload["spritesheet"] = "../spritesheet.png"
    payload["motion_manifest"] = "nested/motion_manifest.json"
    (pack / "character.json").write_text(json.dumps(payload), encoding="utf-8")

    report = validate_pixel_pet_pack_dir(pack)

    assert report.ok is False
    assert "character.json.spritesheet must be exactly spritesheet.png" in report.errors
    assert "character.json.motion_manifest must be exactly motion_manifest.json" in report.errors


def test_validate_pixel_pet_pack_requires_local_boundary_for_ugc(tmp_path: Path) -> None:
    pack = tmp_path / "nairong_ugc_pixel_pet"
    write_valid_pixel_pet_pack(
        pack,
        character_id="nairong_ugc_pixel_pet",
        distribution_boundary="official_candidate",
    )

    report = validate_pixel_pet_pack_dir(pack)

    assert report.ok is False
    assert "UGC pixel-pet packs must use local_ugc_only distribution_boundary" in report.errors


def test_validate_pixel_pet_pack_tool_outputs_json(tmp_path: Path) -> None:
    pack = tmp_path / "xingxi_pixel_pet"
    write_valid_pixel_pet_pack(pack)

    result = subprocess.run(
        [sys.executable, str(TOOL), str(pack)],
        check=False,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["character_id"] == "xingxi_pixel_pet"
