from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from tools.art.validate_companion_atlas import validate_atlas


def write_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "sheet_columns": 8,
                "sheet_rows": 9,
                "frame_width": 192,
                "frame_height": 208,
                "motions": {
                    "Default": {"row": 0, "frame_count": 6, "fps": 4},
                    "TouchHead": {"row": 3, "frame_count": 4, "fps": 6},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_validate_atlas_accepts_valid_8x9_rgba_sheet(tmp_path: Path):
    atlas = tmp_path / "spritesheet.webp"
    manifest = tmp_path / "motion_manifest.json"
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(atlas)
    write_manifest(manifest)

    report = validate_atlas(atlas, manifest)

    assert report.ok is True
    assert report.errors == []
    assert report.width == 1536
    assert report.height == 1872


def test_validate_atlas_reports_wrong_size(tmp_path: Path):
    atlas = tmp_path / "spritesheet.webp"
    manifest = tmp_path / "motion_manifest.json"
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(atlas)
    write_manifest(manifest)

    report = validate_atlas(atlas, manifest)

    assert report.ok is False
    assert "atlas size must be 1536x1872, got 100x100" in report.errors


def test_validate_atlas_reports_invalid_json_manifest(tmp_path: Path):
    atlas = tmp_path / "spritesheet.webp"
    manifest = tmp_path / "motion_manifest.json"
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(atlas)
    manifest.write_text("{not json", encoding="utf-8")

    report = validate_atlas(atlas, manifest)

    assert report.ok is False
    assert any("manifest json is invalid" in error for error in report.errors)


def test_validate_atlas_reports_missing_motions(tmp_path: Path):
    atlas = tmp_path / "spritesheet.webp"
    manifest = tmp_path / "motion_manifest.json"
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(atlas)
    manifest.write_text(
        json.dumps(
            {
                "sheet_columns": 8,
                "sheet_rows": 9,
                "frame_width": 192,
                "frame_height": 208,
            }
        ),
        encoding="utf-8",
    )

    report = validate_atlas(atlas, manifest)

    assert report.ok is False
    assert "motions must be an object" in report.errors


def test_validate_atlas_reports_invalid_motion_row_and_frame_count(tmp_path: Path):
    atlas = tmp_path / "spritesheet.webp"
    manifest = tmp_path / "motion_manifest.json"
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(atlas)
    manifest.write_text(
        json.dumps(
            {
                "sheet_columns": 8,
                "sheet_rows": 9,
                "frame_width": 192,
                "frame_height": 208,
                "motions": {
                    "BadRow": {"row": 9, "frame_count": 1, "fps": 4},
                    "BadFrameCount": {"row": 0, "frame_count": 0, "fps": 4},
                },
            }
        ),
        encoding="utf-8",
    )

    report = validate_atlas(atlas, manifest)

    assert report.ok is False
    assert "BadRow.row must be between 0 and 8, got 9" in report.errors
    assert "BadFrameCount.frame_count must be between 1 and 8, got 0" in report.errors


def test_validate_atlas_reports_non_object_motion(tmp_path: Path):
    atlas = tmp_path / "spritesheet.webp"
    manifest = tmp_path / "motion_manifest.json"
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(atlas)
    manifest.write_text(
        json.dumps(
            {
                "sheet_columns": 8,
                "sheet_rows": 9,
                "frame_width": 192,
                "frame_height": 208,
                "motions": {"Default": "not an object"},
            }
        ),
        encoding="utf-8",
    )

    report = validate_atlas(atlas, manifest)

    assert report.ok is False
    assert "Default must be an object" in report.errors


def test_validate_atlas_reports_unreadable_image(tmp_path: Path):
    atlas = tmp_path / "spritesheet.webp"
    manifest = tmp_path / "motion_manifest.json"
    atlas.write_text("not an image", encoding="utf-8")
    write_manifest(manifest)

    report = validate_atlas(atlas, manifest)

    assert report.ok is False
    assert any("atlas image is invalid" in error for error in report.errors)
