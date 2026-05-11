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
