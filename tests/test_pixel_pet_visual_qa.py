from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "art" / "pixel_pet_visual_qa.py"
FRAME_WIDTH = 192
FRAME_HEIGHT = 208
ROWS = 9


def write_manifest(path: Path, *, columns: int = 2) -> None:
    path.write_text(
        json.dumps(
            {
                "sheet_columns": columns,
                "sheet_rows": ROWS,
                "frame_width": FRAME_WIDTH,
                "frame_height": FRAME_HEIGHT,
                "motions": {
                    "Default": {"row": 0, "frame_count": columns, "fps": 6},
                    "Play": {"row": 4, "frame_count": 1, "fps": 8},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def write_clean_spritesheet(path: Path, *, columns: int = 2) -> None:
    image = Image.new("RGBA", (columns * FRAME_WIDTH, ROWS * FRAME_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for row in range(ROWS):
        for column in range(columns):
            left = column * FRAME_WIDTH + 70
            top = row * FRAME_HEIGHT + 58
            draw.rounded_rectangle((left, top, left + 52, top + 88), radius=8, fill=(42, 46, 52, 255))
    image.save(path)


def write_purple_halo_spritesheet(path: Path, *, columns: int = 2) -> None:
    image = Image.new("RGBA", (columns * FRAME_WIDTH, ROWS * FRAME_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for row in range(ROWS):
        for column in range(columns):
            left = column * FRAME_WIDTH + 66
            top = row * FRAME_HEIGHT + 54
            draw.rounded_rectangle((left, top, left + 60, top + 96), radius=10, fill=(186, 30, 232, 255))
            draw.rounded_rectangle((left + 5, top + 5, left + 55, top + 91), radius=8, fill=(44, 50, 58, 255))
    image.save(path)


def test_pixel_pet_visual_qa_accepts_clean_spritesheet(tmp_path: Path) -> None:
    from tools.art.pixel_pet_visual_qa import inspect_pixel_pet_visual_qa

    spritesheet = tmp_path / "spritesheet.png"
    manifest = tmp_path / "motion_manifest.json"
    write_clean_spritesheet(spritesheet)
    write_manifest(manifest)

    report = inspect_pixel_pet_visual_qa(spritesheet, manifest)

    assert report.ok is True
    assert report.status == "ready"
    assert report.suspicious_edge_halo_pixel_count == 0
    assert report.warnings == ()
    assert report.errors == ()


def test_pixel_pet_visual_qa_flags_suspicious_purple_edge_halo(tmp_path: Path) -> None:
    from tools.art.pixel_pet_visual_qa import inspect_pixel_pet_visual_qa

    spritesheet = tmp_path / "spritesheet.png"
    manifest = tmp_path / "motion_manifest.json"
    write_purple_halo_spritesheet(spritesheet)
    write_manifest(manifest)

    report = inspect_pixel_pet_visual_qa(spritesheet, manifest)

    assert report.ok is True
    assert report.status == "ready_with_warnings"
    assert report.edge_pixel_count > 0
    assert report.suspicious_edge_halo_pixel_count > 0
    assert report.suspicious_edge_halo_ratio > 0
    assert "suspicious_edge_halo_risk" in report.warnings


def test_pixel_pet_visual_qa_cli_writes_report_and_can_fail_on_warnings(tmp_path: Path) -> None:
    spritesheet = tmp_path / "spritesheet.png"
    manifest = tmp_path / "motion_manifest.json"
    report_path = tmp_path / "pixel-pet-visual-qa.json"
    preview_path = tmp_path / "pixel-pet-visual-qa-preview.png"
    write_purple_halo_spritesheet(spritesheet)
    write_manifest(manifest)

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            str(spritesheet),
            "--motion-manifest",
            str(manifest),
            "--report",
            str(report_path),
            "--preview",
            str(preview_path),
            "--fail-on-warnings",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    payload = json.loads(result.stdout)
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert result.returncode == 1
    assert payload["status"] == "ready_with_warnings"
    assert payload["preview_path"] == str(preview_path)
    assert saved["warnings"] == ["suspicious_edge_halo_risk"]
    assert preview_path.is_file()
    with Image.open(preview_path) as preview:
        assert preview.mode == "RGBA"
        assert preview.width > 0
        assert preview.height > 0
