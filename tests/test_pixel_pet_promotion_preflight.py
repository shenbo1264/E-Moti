from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_pack(root: Path, *, boundary: str = "official_candidate") -> Path:
    pack_dir = root / "xingxi_pixel_pet"
    (pack_dir / "preview").mkdir(parents=True)
    (pack_dir / "item_icons").mkdir()
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    Image.new("RGBA", (512, 512), (0, 0, 0, 0)).save(pack_dir / "preview" / "contact-sheet.png")
    Image.new("RGBA", (32, 32), (80, 110, 160, 255)).save(pack_dir / "item_icons" / "snack.png")
    _write_json(
        pack_dir / "character.json",
        {
            "character_id": "xingxi_pixel_pet",
            "name": "Xingxi Pixel Pet",
            "title": "Promotion preflight candidate",
            "description": "A pixel pet promotion preflight candidate.",
            "spritesheet": "spritesheet.png",
            "motion_manifest": "motion_manifest.json",
            "default_mode": "Calm",
            "modes": ["Calm"],
            "mode_descriptions": {"Calm": "Calm response."},
            "motion_labels": {
                "Default": "Idle",
                "TouchHead": "Touch",
                "Play": "Play",
                "SwitchDown": "Down",
                "Sleep": "Sleep",
                "Raised": "Raised",
                "Study": "Study",
            },
            "distribution_boundary": "shareable_after_review",
            "renderer": {"backend": "sprite"},
        },
    )
    _write_json(
        pack_dir / "dialogue_style.json",
        {"tone": "gentle", "fallback_style": "short companion line", "keywords": ["xingxi", "pixel"]},
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
                "TouchHead": {"row": 1, "frame_count": 6, "fps": 4},
                "Play": {"row": 2, "frame_count": 6, "fps": 4},
                "SwitchDown": {"row": 3, "frame_count": 6, "fps": 4},
                "Sleep": {"row": 4, "frame_count": 6, "fps": 4},
                "Raised": {"row": 5, "frame_count": 6, "fps": 4},
                "Study": {"row": 6, "frame_count": 6, "fps": 4},
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
    (pack_dir / "provenance.md").write_text("# Provenance\n\nGenerated candidate.\n", encoding="utf-8")
    _write_json(
        pack_dir / "qa_report.json",
        {
            "status": "candidate",
            "manual_qa_required": True,
            "distribution_boundary": boundary,
            "runtime_manifest_updated": False,
        },
    )
    return pack_dir


def _write_manual_qa(path: Path) -> Path:
    _write_json(
        path,
        {
            "manual_decision": "promotion_gate_candidate_clean_edge",
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


def test_pixel_pet_promotion_preflight_reports_manual_qa_pending(tmp_path: Path) -> None:
    from tools.pixel_pet_promotion_preflight import inspect_pixel_pet_promotion_preflight

    pack_dir = _write_pack(tmp_path)

    report = inspect_pixel_pet_promotion_preflight(pack_dir)
    payload = report.to_dict()

    assert payload["ok"] is False
    assert payload["deterministic_ok"] is True
    assert payload["status"] == "needs_manual_qa"
    assert payload["manual_qa_status"] == "missing"
    assert "manual QA decision is required before bundled promotion" in payload["next_actions"]


def test_pixel_pet_promotion_preflight_accepts_ready_manual_qa(tmp_path: Path) -> None:
    from tools.pixel_pet_promotion_preflight import inspect_pixel_pet_promotion_preflight

    pack_dir = _write_pack(tmp_path)
    manual_qa = _write_manual_qa(tmp_path / "manual_qa.json")

    report = inspect_pixel_pet_promotion_preflight(pack_dir, manual_qa_path=manual_qa)
    payload = report.to_dict()

    assert payload["ok"] is True
    assert payload["status"] == "ready_for_promotion_gate"
    assert payload["manual_qa_status"] == "ready"
    assert payload["errors"] == []


def test_pixel_pet_promotion_preflight_cli_writes_report(tmp_path: Path) -> None:
    pack_dir = _write_pack(tmp_path)
    report_path = tmp_path / "preflight.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/pixel_pet_promotion_preflight.py",
            str(pack_dir),
            "--report",
            str(report_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "needs_manual_qa"
