from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_character_pack(root: Path) -> None:
    (root / "item_icons").mkdir(parents=True)
    (root / "portraits").mkdir()
    (root / "preview").mkdir()
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(root / "spritesheet.png")
    Image.new("RGBA", (32, 32), (40, 80, 120, 255)).save(root / "item_icons" / "stardrop.png")
    Image.new("RGBA", (64, 64), (255, 255, 255, 255)).save(root / "preview" / "contact-sheet.png")
    for expression, color in {
        "neutral": (40, 80, 120, 255),
        "smile": (50, 130, 90, 255),
        "thinking": (90, 90, 150, 255),
        "surprised": (160, 100, 80, 255),
        "sad": (70, 90, 120, 255),
        "sleepy": (110, 80, 130, 255),
    }.items():
        Image.new("RGBA", (256, 512), color).save(root / "portraits" / f"{expression}.png")
    _write_json(
        root / "character.json",
        {
            "character_id": "original_oc",
            "name": "Xingxi",
            "title": "Desktop companion",
            "description": "Frozen build validation fixture.",
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
        root / "motion_manifest.json",
        {
            "sheet_columns": 8,
            "sheet_rows": 9,
            "frame_width": 192,
            "frame_height": 208,
            "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
        },
    )
    _write_json(root / "dialogue_style.json", {"tone": "calm", "keywords": ["desktop"], "fallback_style": "short"})
    _write_json(
        root / "shop_items.json",
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
        root / "portrait_manifest.json",
        {
            "version": 1,
            "fallback_expression": "neutral",
            "anchor": "bottom_center",
            "default_scale": 1.0,
            "expressions": {expression: f"portraits/{expression}.png" for expression in (
                "neutral",
                "smile",
                "thinking",
                "surprised",
                "sad",
                "sleepy",
            )},
        },
    )
    (root / "portrait_assets_provenance.md").write_text("fixture provenance\n", encoding="utf-8")
    (root / "LICENSE.md").write_text("fixture character pack license\n", encoding="utf-8")


def _write_sprite_character_pack(root: Path) -> None:
    (root / "item_icons").mkdir(parents=True)
    (root / "preview").mkdir()
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(root / "spritesheet.png")
    Image.new("RGBA", (32, 32), (40, 80, 120, 255)).save(root / "item_icons" / "stardrop.png")
    Image.new("RGBA", (64, 64), (255, 255, 255, 255)).save(root / "preview" / "contact-sheet.png")
    _write_json(
        root / "character.json",
        {
            "character_id": "xingxi_pixel_pet",
            "name": "Xingxi Pixel Pet",
            "title": "Sprite companion",
            "description": "Frozen sprite build validation fixture.",
            "spritesheet": "spritesheet.png",
            "motion_manifest": "motion_manifest.json",
            "default_mode": "Calm",
            "modes": ["Calm"],
            "mode_descriptions": {"Calm": "Calm response."},
            "motion_labels": {"Default": "Idle"},
            "renderer": {
                "backend": "sprite",
                "expression_map": {"goofy": "Default"},
            },
        },
    )
    _write_json(
        root / "motion_manifest.json",
        {
            "sheet_columns": 8,
            "sheet_rows": 9,
            "frame_width": 192,
            "frame_height": 208,
            "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
        },
    )
    _write_json(root / "dialogue_style.json", {"tone": "calm", "keywords": ["desktop"], "fallback_style": "short"})
    _write_json(
        root / "shop_items.json",
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
    (root / "provenance.md").write_text("fixture sprite provenance\n", encoding="utf-8")
    (root / "LICENSE.md").write_text("fixture character pack license\n", encoding="utf-8")


def _write_windows_build(root: Path, *, include_portraits: bool = True, include_installer: bool = True) -> tuple[Path, Path]:
    app_dir = root / "dist" / "E-Moti"
    character_dir = app_dir / "_internal" / "assets" / "companion" / "original_oc"
    character_dir.mkdir(parents=True)
    (app_dir / "E-Moti.exe").write_bytes(b"MZ" + (b"0" * 128))
    _write_character_pack(character_dir)
    if not include_portraits:
        for path in (character_dir / "portraits").glob("*.png"):
            path.unlink()
    installer = root / "dist" / "installer" / "E-Moti_Setup_0.1.0.exe"
    if include_installer:
        installer.parent.mkdir(parents=True)
        installer.write_bytes(b"MZ" + (b"1" * 128))
    return app_dir, installer


def _write_windows_build_with_sprite_pack(root: Path) -> tuple[Path, Path]:
    app_dir, installer = _write_windows_build(root)
    sprite_dir = app_dir / "_internal" / "assets" / "companion" / "xingxi_pixel_pet"
    sprite_dir.mkdir(parents=True)
    _write_sprite_character_pack(sprite_dir)
    return app_dir, installer


def test_validate_windows_build_accepts_complete_frozen_app_and_installer(tmp_path: Path):
    from tools.validate_windows_build import validate_windows_build

    app_dir, installer = _write_windows_build(tmp_path)

    report = validate_windows_build(app_dir=app_dir, installer_path=installer)

    assert report.ok is True
    assert report.errors == ()
    assert report.app_exe == str(app_dir / "E-Moti.exe")
    assert report.character_id == "original_oc"
    assert report.installer_path == str(installer)


def test_validate_windows_build_accepts_complete_frozen_sprite_pack(tmp_path: Path):
    from tools.validate_windows_build import validate_windows_build

    app_dir, installer = _write_windows_build_with_sprite_pack(tmp_path)

    report = validate_windows_build(
        app_dir=app_dir,
        installer_path=installer,
        character_id="xingxi_pixel_pet",
    )

    assert report.ok is True
    assert report.errors == ()
    assert report.character_id == "xingxi_pixel_pet"


def test_validate_windows_build_rejects_missing_portrait_assets(tmp_path: Path):
    from tools.validate_windows_build import validate_windows_build

    app_dir, installer = _write_windows_build(tmp_path, include_portraits=False)

    report = validate_windows_build(app_dir=app_dir, installer_path=installer)

    assert report.ok is False
    assert any("portrait image not found" in error for error in report.errors)


def test_validate_windows_build_rejects_missing_character_pack_license(tmp_path: Path):
    from tools.validate_windows_build import validate_windows_build

    app_dir, installer = _write_windows_build(tmp_path)
    license_path = app_dir / "_internal" / "assets" / "companion" / "original_oc" / "LICENSE.md"
    license_path.unlink()

    report = validate_windows_build(app_dir=app_dir, installer_path=installer)

    assert report.ok is False
    assert "frozen character pack missing required bundled asset: LICENSE.md" in report.errors


def test_validate_windows_build_cli_writes_report_from_repo_root(tmp_path: Path):
    app_dir, installer = _write_windows_build(tmp_path)
    report_path = tmp_path / "windows-build-report.json"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [
            sys.executable,
            "tools/validate_windows_build.py",
            "--app-dir",
            str(app_dir),
            "--installer",
            str(installer),
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
    assert json.loads(report_path.read_text(encoding="utf-8"))["ok"] is True
