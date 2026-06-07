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


def test_validate_atlas_accepts_manifest_declared_wide_sheet(tmp_path: Path):
    atlas = tmp_path / "spritesheet.png"
    manifest = tmp_path / "motion_manifest.json"
    Image.new("RGBA", (2880, 1872), (0, 0, 0, 0)).save(atlas)
    manifest.write_text(
        json.dumps(
            {
                "sheet_columns": 15,
                "sheet_rows": 9,
                "frame_width": 192,
                "frame_height": 208,
                "motions": {
                    "Default": {"row": 0, "frame_count": 15, "fps": 8},
                },
            }
        ),
        encoding="utf-8",
    )

    report = validate_atlas(atlas, manifest)

    assert report.ok is True
    assert report.errors == []
    assert report.width == 2880
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


def test_build_previews_preserves_identical_gif_frames(tmp_path: Path):
    atlas = tmp_path / "spritesheet.png"
    manifest = tmp_path / "motion_manifest.json"
    output = tmp_path / "preview"
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(atlas)
    write_manifest(manifest)

    build_previews(atlas, manifest, output)

    with Image.open(output.joinpath("gifs", "Default.gif")) as image:
        assert image.n_frames == 6


def test_build_previews_preserves_original_oc_manifest_frame_counts(tmp_path: Path):
    root = Path(__file__).resolve().parents[1] / "assets" / "companion" / "original_oc"
    manifest = root / "motion_manifest.json"
    output = tmp_path / "preview"
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    build_previews(root / "spritesheet.png", manifest, output)

    for name, motion in payload["motions"].items():
        with Image.open(output.joinpath("gifs", f"{name}.gif")) as image:
            assert image.n_frames == motion["frame_count"], name


def test_build_smooth_sprite_atlas_inserts_blended_frames_and_updates_manifest(tmp_path: Path):
    from tools.art.build_smooth_sprite_atlas import build_smooth_sprite_atlas

    atlas = tmp_path / "spritesheet.png"
    manifest = tmp_path / "motion_manifest.json"
    output_atlas = tmp_path / "smooth.png"
    output_manifest = tmp_path / "smooth_manifest.json"
    frame_width = 192
    frame_height = 208
    source = Image.new("RGBA", (3 * frame_width, 9 * frame_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(source)
    source_colors = [
        (255, 0, 0, 255),
        (0, 0, 255, 255),
        (0, 255, 0, 255),
    ]
    for index, color in enumerate(source_colors):
        draw.rectangle(
            (index * frame_width, 0, (index + 1) * frame_width - 1, frame_height - 1),
            fill=color,
        )
    source.save(atlas)
    manifest.write_text(
        json.dumps(
            {
                "sheet_columns": 3,
                "sheet_rows": 9,
                "frame_width": frame_width,
                "frame_height": frame_height,
                "motions": {"Default": {"row": 0, "frame_count": 3, "fps": 6}},
            }
        ),
        encoding="utf-8",
    )

    build_smooth_sprite_atlas(atlas, manifest, output_atlas, output_manifest)

    output_payload = json.loads(output_manifest.read_text(encoding="utf-8"))
    assert output_payload["sheet_columns"] == 5
    assert output_payload["motions"]["Default"] == {"row": 0, "frame_count": 5, "fps": 10}
    with Image.open(output_atlas) as image:
        assert image.size == (5 * frame_width, 9 * frame_height)
        pixels = [
            image.getpixel((index * frame_width + 8, 8))
            for index in range(5)
        ]
    assert pixels[0] == source_colors[0]
    assert pixels[2] == source_colors[1]
    assert pixels[4] == source_colors[2]
    assert pixels[1][:3] in {(127, 0, 127), (128, 0, 128)}
    assert pixels[3][:3] in {(0, 127, 127), (0, 128, 128)}
    assert validate_atlas(output_atlas, output_manifest).ok


def test_validate_portrait_candidate_writes_contact_sheet(tmp_path: Path):
    from tools.art.validate_portrait_candidates import validate_portrait_candidate

    candidate = tmp_path / "candidate"
    candidate.mkdir()
    Image.new("RGBA", (256, 512), (20, 40, 80, 255)).save(candidate / "neutral_open.png")
    Image.new("RGBA", (256, 512), (80, 40, 20, 255)).save(candidate / "smile_open.png")
    manifest = candidate / "portrait_candidate.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "candidate",
                "expressions": {
                    "neutral": "neutral_open.png",
                    "smile": {"open": "smile_open.png"},
                },
            }
        ),
        encoding="utf-8",
    )
    contact_sheet = tmp_path / "candidate-contact-sheet.png"

    report = validate_portrait_candidate(manifest, contact_sheet_path=contact_sheet)

    assert report.ok is True
    assert report.status == "candidate"
    assert report.image_count == 2
    assert report.errors == []
    assert contact_sheet.exists()
    with Image.open(contact_sheet) as image:
        assert image.mode == "RGBA"
        assert image.width >= 512
        assert image.height >= 512


def test_validate_portrait_candidate_rejects_invalid_status_and_unsafe_path(tmp_path: Path):
    from tools.art.validate_portrait_candidates import validate_portrait_candidate

    candidate = tmp_path / "candidate"
    candidate.mkdir()
    manifest = candidate / "portrait_candidate.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "final",
                "expressions": {
                    "neutral": "../neutral.png",
                },
            }
        ),
        encoding="utf-8",
    )

    report = validate_portrait_candidate(manifest)

    assert report.ok is False
    assert "status must be one of: approved, candidate, rejected" in report.errors
    assert "expressions.neutral path must stay inside candidate directory" in report.errors


def test_validate_portrait_candidate_rejects_unapproved_runtime_manifest_reference(tmp_path: Path):
    from tools.art.validate_portrait_candidates import validate_portrait_candidate

    candidate = tmp_path / "candidate"
    candidate.mkdir()
    Image.new("RGBA", (256, 512), (20, 40, 80, 255)).save(candidate / "neutral_open.png")
    candidate_manifest = candidate / "portrait_candidate.json"
    candidate_manifest.write_text(
        json.dumps({"status": "candidate", "expressions": {"neutral": "neutral_open.png"}}),
        encoding="utf-8",
    )
    runtime_manifest = tmp_path / "portrait_manifest.json"
    runtime_manifest.write_text(
        json.dumps(
            {
                "fallback_expression": "neutral",
                "expressions": {
                    "neutral": "candidate/neutral_open.png",
                },
            }
        ),
        encoding="utf-8",
    )

    report = validate_portrait_candidate(candidate_manifest, runtime_manifest_path=runtime_manifest)

    assert report.ok is False
    assert "runtime manifest references unapproved candidate image: neutral_open.png" in report.errors

    candidate_manifest.write_text(
        json.dumps({"status": "approved", "expressions": {"neutral": "neutral_open.png"}}),
        encoding="utf-8",
    )

    approved_report = validate_portrait_candidate(candidate_manifest, runtime_manifest_path=runtime_manifest)

    assert approved_report.ok is True
    assert approved_report.status == "approved"


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
