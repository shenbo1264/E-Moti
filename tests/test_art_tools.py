from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageSequence

from tools.art.build_companion_preview import build_previews, main as preview_main
from tools.art.validate_companion_atlas import main, validate_atlas


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


def write_preview_atlas(path: Path) -> None:
    image = Image.new("RGBA", (1536, 1872), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for row in range(9):
        for column in range(8):
            left = column * 192
            top = row * 208
            color = ((column * 31) % 255, (row * 47) % 255, 160, 255)
            draw.rectangle((left, top, left + 191, top + 207), fill=color)
            draw.text((left + 8, top + 8), f"{row}:{column}", fill=(255, 255, 255, 255))
    image.save(path)


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


def test_build_previews_writes_contact_sheet_and_gifs(tmp_path: Path):
    atlas = tmp_path / "spritesheet.png"
    manifest = tmp_path / "motion_manifest.json"
    output = tmp_path / "preview"
    write_preview_atlas(atlas)
    write_manifest(manifest)

    generated = build_previews(atlas, manifest, output)

    contact_sheet = output.joinpath("contact-sheet.png")
    default_gif = output.joinpath("gifs", "Default.gif")
    touch_head_gif = output.joinpath("gifs", "TouchHead.gif")
    assert contact_sheet.exists()
    assert default_gif.exists()
    assert touch_head_gif.exists()
    assert "contact-sheet.png" in {path.name for path in generated}
    with Image.open(contact_sheet) as image:
        assert image.size == (1536, 1872)
    with Image.open(default_gif) as image:
        assert sum(1 for _ in ImageSequence.Iterator(image)) == 6
    with Image.open(touch_head_gif) as image:
        assert sum(1 for _ in ImageSequence.Iterator(image)) == 4


def test_build_previews_rejects_invalid_manifest_without_output(tmp_path: Path):
    atlas = tmp_path / "spritesheet.png"
    manifest = tmp_path / "motion_manifest.json"
    output = tmp_path / "preview"
    write_preview_atlas(atlas)
    manifest.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="manifest json is invalid"):
        build_previews(atlas, manifest, output)

    assert not output.exists()


def test_build_previews_rejects_invalid_atlas_without_output(tmp_path: Path):
    atlas = tmp_path / "spritesheet.webp"
    manifest = tmp_path / "motion_manifest.json"
    output = tmp_path / "preview"
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(atlas)
    write_manifest(manifest)

    with pytest.raises(ValueError, match="atlas size must be 1536x1872"):
        build_previews(atlas, manifest, output)

    assert not output.exists()


def test_preview_main_returns_one_and_prints_error_for_invalid_input(
    tmp_path: Path, capsys, monkeypatch
):
    atlas = tmp_path / "spritesheet.png"
    manifest = tmp_path / "motion_manifest.json"
    output = tmp_path / "preview"
    write_preview_atlas(atlas)
    manifest.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_companion_preview.py",
            "--atlas",
            str(atlas),
            "--manifest",
            str(manifest),
            "--output",
            str(output),
        ],
    )

    exit_code = preview_main()

    assert exit_code == 1
    assert "ERROR manifest json is invalid" in capsys.readouterr().out
    assert not output.exists()


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


def test_validate_atlas_reports_truncated_image_payload(tmp_path: Path):
    atlas = tmp_path / "spritesheet.png"
    manifest = tmp_path / "motion_manifest.json"
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(atlas)
    atlas.write_bytes(atlas.read_bytes()[:128])
    write_manifest(manifest)

    report = validate_atlas(atlas, manifest)

    assert report.ok is False
    assert any("atlas image is invalid" in error for error in report.errors)


def test_validate_atlas_rejects_boolean_row_and_frame_count(tmp_path: Path):
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
                    "BoolRow": {"row": True, "frame_count": 1, "fps": 4},
                    "BoolFrameCount": {"row": 0, "frame_count": True, "fps": 4},
                },
            }
        ),
        encoding="utf-8",
    )

    report = validate_atlas(atlas, manifest)

    assert report.ok is False
    assert "BoolRow.row must be between 0 and 8, got True" in report.errors
    assert "BoolFrameCount.frame_count must be between 1 and 8, got True" in report.errors


def test_main_returns_one_and_prints_error_for_malformed_manifest(
    tmp_path: Path, capsys, monkeypatch
):
    atlas = tmp_path / "spritesheet.webp"
    manifest = tmp_path / "motion_manifest.json"
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(atlas)
    manifest.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_companion_atlas.py",
            "--atlas",
            str(atlas),
            "--manifest",
            str(manifest),
        ],
    )

    exit_code = main()

    assert exit_code == 1
    assert "ERROR manifest json is invalid" in capsys.readouterr().out
