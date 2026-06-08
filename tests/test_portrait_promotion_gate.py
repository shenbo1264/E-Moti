from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


REQUIRED_EXPRESSIONS = ("neutral", "smile", "thinking", "surprised", "sad", "sleepy")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_portrait(path: Path, color: tuple[int, int, int, int], *, eye_line: int = 0) -> None:
    image = Image.new("RGBA", (256, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((72, 28, 184, 490), radius=28, fill=color)
    if eye_line:
        draw.line((100, eye_line, 156, eye_line), fill=(12, 18, 32, 255), width=4)
    image.save(path)


def _write_promotion_pack(root: Path, *, approved: bool = True, duplicate_expressions: bool = False) -> Path:
    pack_dir = root / "xingxi_vn_promotion_candidate"
    portraits_dir = pack_dir / "portraits"
    item_icons_dir = pack_dir / "item_icons"
    preview_dir = pack_dir / "preview"
    portraits_dir.mkdir(parents=True)
    item_icons_dir.mkdir()
    preview_dir.mkdir()

    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    Image.new("RGBA", (32, 32), (40, 80, 120, 255)).save(item_icons_dir / "stardrop.png")
    Image.new("RGBA", (512, 512), (255, 255, 255, 255)).save(preview_dir / "contact-sheet.png")

    expression_colors = {
        "smile": (70, 140, 170, 255),
        "thinking": (90, 100, 170, 255),
        "surprised": (170, 110, 90, 255),
        "sad": (80, 100, 130, 255),
        "sleepy": (120, 95, 150, 255),
    }
    _write_portrait(portraits_dir / "neutral_open.png", (80, 120, 180, 255), eye_line=138)
    _write_portrait(portraits_dir / "neutral_half.png", (80, 120, 180, 255), eye_line=142)
    _write_portrait(portraits_dir / "neutral_closed.png", (80, 120, 180, 255), eye_line=146)
    for expression, color in expression_colors.items():
        target_color = (70, 140, 170, 255) if duplicate_expressions else color
        _write_portrait(portraits_dir / f"{expression}.png", target_color, eye_line=138)

    _write_json(
        pack_dir / "character.json",
        {
            "character_id": "xingxi_vn_promotion_candidate",
            "name": "星汐 VN Promotion Candidate",
            "title": "Promotion gate fixture",
            "description": "Fixture pack for strict portrait promotion validation.",
            "spritesheet": "spritesheet.png",
            "motion_manifest": "motion_manifest.json",
            "default_mode": "Calm",
            "modes": ["Calm"],
            "mode_descriptions": {"Calm": "Calm response."},
            "motion_labels": {"Default": "Idle"},
            "renderer": {
                "backend": "portrait",
                "portrait_manifest": "portrait_manifest.json",
                "expression_map": {
                    "calm": "neutral",
                    "joy": "smile",
                    "excited": "smile",
                    "focused": "thinking",
                    "surprised": "surprised",
                    "sadness": "sad",
                    "sleepy": "sleepy",
                },
            },
        },
    )
    _write_json(
        pack_dir / "motion_manifest.json",
        {
            "sheet_columns": 8,
            "sheet_rows": 9,
            "frame_width": 192,
            "frame_height": 208,
            "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
        },
    )
    _write_json(pack_dir / "dialogue_style.json", {"tone": "calm", "keywords": ["星汐"], "fallback_style": "short"})
    _write_json(
        pack_dir / "shop_items.json",
        [
            {
                "item_id": "stardrop",
                "name": "Stardrop",
                "category": "gift",
                "icon": "item_icons/stardrop.png",
                "price": 1,
                "effects": {"mood": 1},
            }
        ],
    )
    _write_json(
        pack_dir / "portrait_manifest.json",
        {
            "version": 1,
            "fallback_expression": "neutral",
            "anchor": "bottom_center",
            "default_scale": 1.0,
            "expressions": {
                "neutral": {
                    "open": "portraits/neutral_open.png",
                    "blink_half": "portraits/neutral_half.png",
                    "blink_closed": "portraits/neutral_closed.png",
                },
                **{expression: f"portraits/{expression}.png" for expression in expression_colors},
            },
            "animation": {
                "blink": {"enabled": True, "min_interval_ms": 3000, "max_interval_ms": 7000}
            },
        },
    )
    _write_json(
        pack_dir / "portrait_candidate.json",
        {
            "status": "approved" if approved else "candidate",
            "approval_required": not approved,
            "runtime_manifest_safe": approved,
            "expressions": {
                "neutral": {
                    "open": "portraits/neutral_open.png",
                    "blink_half": "portraits/neutral_half.png",
                    "blink_closed": "portraits/neutral_closed.png",
                },
                **{expression: f"portraits/{expression}.png" for expression in expression_colors},
            },
        },
    )
    (pack_dir / "portrait_assets_provenance.md").write_text(
        "# Portrait provenance\n\nHuman QA accepted this promotion fixture.\n",
        encoding="utf-8",
    )
    return pack_dir


def _overwrite_light_halo_portrait(path: Path) -> None:
    image = Image.new("RGBA", (256, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((70, 26, 186, 492), radius=30, fill=(248, 248, 248, 128))
    draw.rounded_rectangle((78, 34, 178, 484), radius=24, fill=(80, 120, 180, 255))
    draw.line((100, 138, 156, 138), fill=(12, 18, 32, 255), width=4)
    image.save(path)


def test_portrait_promotion_gate_accepts_approved_distinct_vn_pack(tmp_path: Path):
    from tools.portrait_promotion_gate import validate_portrait_promotion_candidate

    pack_dir = _write_promotion_pack(tmp_path)

    report = validate_portrait_promotion_candidate(pack_dir)

    assert report.ok is True
    assert report.character_id == "xingxi_vn_promotion_candidate"
    assert report.errors == ()
    assert report.warnings == ()
    assert report.image_count == 8


def test_portrait_promotion_gate_reports_visual_qa_warnings_without_blocking(tmp_path: Path):
    from tools.portrait_promotion_gate import validate_portrait_promotion_candidate

    pack_dir = _write_promotion_pack(tmp_path)
    _overwrite_light_halo_portrait(pack_dir / "portraits" / "neutral_open.png")

    report = validate_portrait_promotion_candidate(pack_dir)

    assert report.ok is True
    assert report.errors == ()
    assert "portrait visual qa warning: neutral.open: light_edge_halo_risk" in report.warnings


def test_portrait_promotion_gate_requires_human_approval_flags(tmp_path: Path):
    from tools.portrait_promotion_gate import validate_portrait_promotion_candidate

    pack_dir = _write_promotion_pack(tmp_path, approved=False)

    report = validate_portrait_promotion_candidate(pack_dir)

    assert report.ok is False
    assert "portrait_candidate.status must be approved before promotion" in report.errors
    assert "portrait_candidate.approval_required must be false before promotion" in report.errors
    assert "portrait_candidate.runtime_manifest_safe must be true before promotion" in report.errors


def test_portrait_promotion_gate_rejects_duplicate_expression_images(tmp_path: Path):
    from tools.portrait_promotion_gate import validate_portrait_promotion_candidate

    pack_dir = _write_promotion_pack(tmp_path, duplicate_expressions=True)

    report = validate_portrait_promotion_candidate(pack_dir)

    assert report.ok is False
    assert any(error.startswith("portrait expression images must be visually distinct:") for error in report.errors)


def test_portrait_promotion_gate_cli_writes_report_from_repo_root(tmp_path: Path):
    pack_dir = _write_promotion_pack(tmp_path)
    report_path = tmp_path / "promotion-report.json"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [
            sys.executable,
            "tools/portrait_promotion_gate.py",
            str(pack_dir),
            "--report",
            str(report_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert report_path.is_file()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["image_count"] == 8
    assert payload["warnings"] == []
