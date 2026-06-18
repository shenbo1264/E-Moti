from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_promotion_pack(
    root: Path,
    *,
    character_id: str = "xingxi_pixel_pet",
    qa_boundary: str = "official_candidate",
    character_boundary: str = "shareable_after_review",
) -> Path:
    pack_dir = root / character_id
    (pack_dir / "item_icons").mkdir(parents=True)
    (pack_dir / "preview").mkdir()
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    Image.new("RGBA", (512, 512), (0, 0, 0, 0)).save(pack_dir / "preview" / "contact-sheet.png")
    Image.new("RGBA", (32, 32), (40, 80, 120, 255)).save(pack_dir / "item_icons" / "snack.png")
    _write_json(
        pack_dir / "character.json",
        {
            "character_id": character_id,
            "name": "Xingxi Pixel Pet",
            "title": "Promotion gate candidate",
            "description": "A pixel-pet promotion gate candidate.",
            "spritesheet": "spritesheet.png",
            "motion_manifest": "motion_manifest.json",
            "default_mode": "Calm",
            "modes": ["Calm"],
            "mode_descriptions": {"Calm": "Calm response."},
            "motion_labels": {"Default": "Idle", "Play": "Jumping", "SwitchDown": "Failed"},
            "distribution_boundary": character_boundary,
            "renderer": {"backend": "sprite"},
        },
    )
    _write_json(
        pack_dir / "dialogue_style.json",
        {
            "tone": "gentle",
            "fallback_style": "short companion line",
            "keywords": ["xingxi", "pixel"],
        },
    )
    _write_json(
        pack_dir / "motion_manifest.json",
        {
            "sheet_columns": 8,
            "sheet_rows": 9,
            "frame_width": 192,
            "frame_height": 208,
            "motions": {
                "Default": {"row": 0, "frame_count": 6, "fps": 4},
                "Play": {"row": 4, "frame_count": 5, "fps": 7},
                "SwitchDown": {"row": 5, "frame_count": 8, "fps": 5},
            },
        },
    )
    _write_json(
        pack_dir / "shop_items.json",
        [
            {
                "item_id": "snack",
                "name": "Snack",
                "category": "food",
                "icon": "item_icons/snack.png",
                "price": 1,
                "effects": {"mood": 1},
            }
        ],
    )
    (pack_dir / "provenance.md").write_text(
        "# Provenance\n\nGenerated pixel-pet candidate with manual QA.\n",
        encoding="utf-8",
    )
    _write_json(
        pack_dir / "qa_report.json",
        {
            "status": "candidate",
            "manual_qa_required": True,
            "distribution_boundary": qa_boundary,
            "runtime_manifest_updated": False,
        },
    )
    return pack_dir


def _write_manual_qa(root: Path, *, decision: str = "promotion_gate_candidate") -> Path:
    path = root / "manual_qa.json"
    _write_json(
        path,
        {
            "character_id": "xingxi_pixel_pet",
            "manual_decision": decision,
            "runtime_manifest_updated": False,
            "deterministic_checks": {
                "final_validation_ok": True,
                "hatch_review_ok": True,
                "pixel_pack_validation_ok": True,
                "runtime_import_smoke_ok": True,
            },
        },
    )
    return path


def test_pixel_pet_promotion_gate_accepts_official_candidate(tmp_path: Path) -> None:
    from tools.pixel_pet_promotion_gate import validate_pixel_pet_promotion_candidate

    pack_dir = _write_promotion_pack(tmp_path)
    manual_qa = _write_manual_qa(tmp_path)

    report = validate_pixel_pet_promotion_candidate(pack_dir, manual_qa_path=manual_qa)

    assert report.ok is True
    assert report.character_id == "xingxi_pixel_pet"
    assert report.distribution_boundary == "official_candidate"
    assert report.manual_decision == "promotion_gate_candidate"
    assert report.errors == ()


def test_pixel_pet_promotion_gate_rejects_ugc_or_private_boundaries(tmp_path: Path) -> None:
    from tools.pixel_pet_promotion_gate import validate_pixel_pet_promotion_candidate

    pack_dir = _write_promotion_pack(
        tmp_path,
        character_id="ikaros_ugc_pixel_pet",
        qa_boundary="private_local_fanwork",
        character_boundary="private_local_fanwork",
    )
    manual_qa = _write_manual_qa(tmp_path)

    report = validate_pixel_pet_promotion_candidate(pack_dir, manual_qa_path=manual_qa)

    assert report.ok is False
    assert "UGC pixel-pet packs cannot pass official promotion gate" in report.errors
    assert "qa_report.distribution_boundary must be official_candidate for promotion gate" in report.errors
    assert "character.json.distribution_boundary must be shareable_after_review for promotion gate" in report.errors


def test_pixel_pet_promotion_gate_requires_manual_qa_decision(tmp_path: Path) -> None:
    from tools.pixel_pet_promotion_gate import validate_pixel_pet_promotion_candidate

    pack_dir = _write_promotion_pack(tmp_path)
    manual_qa = _write_manual_qa(tmp_path, decision="keep_as_local_import_candidate")
    payload = json.loads(manual_qa.read_text(encoding="utf-8"))
    payload["deterministic_checks"]["runtime_import_smoke_ok"] = False
    manual_qa.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = validate_pixel_pet_promotion_candidate(pack_dir, manual_qa_path=manual_qa)

    assert report.ok is False
    assert "manual_qa.manual_decision must start with promotion_gate_candidate" in report.errors
    assert "manual_qa.deterministic_checks.runtime_import_smoke_ok must be true" in report.errors


def test_pixel_pet_promotion_gate_cli_writes_report_from_repo_root(tmp_path: Path) -> None:
    pack_dir = _write_promotion_pack(tmp_path)
    manual_qa = _write_manual_qa(tmp_path)
    report_path = tmp_path / "pixel-promotion-report.json"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [
            sys.executable,
            "tools/pixel_pet_promotion_gate.py",
            str(pack_dir),
            "--manual-qa",
            str(manual_qa),
            "--report",
            str(report_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["character_id"] == "xingxi_pixel_pet"
