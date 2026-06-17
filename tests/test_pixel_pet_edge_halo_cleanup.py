from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "art" / "clean_pixel_pet_edge_halo.py"
FRAME_WIDTH = 192
FRAME_HEIGHT = 208
ROWS = 9


def _write_pixel_pet_pack_with_halo(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "preview").mkdir()
    _write_halo_spritesheet(root / "spritesheet.png")
    Image.new("RGBA", (512, 512), (0, 0, 0, 0)).save(root / "preview" / "contact-sheet.png")
    (root / "motion_manifest.json").write_text(
        json.dumps(
            {
                "sheet_columns": 2,
                "sheet_rows": ROWS,
                "frame_width": FRAME_WIDTH,
                "frame_height": FRAME_HEIGHT,
                "motions": {
                    "Default": {"row": 0, "frame_count": 2, "fps": 6},
                    "Play": {"row": 4, "frame_count": 1, "fps": 8},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "character.json").write_text(
        json.dumps(
            {
                "character_id": root.name,
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
            {"tone": "gentle", "fallback_style": "short companion line", "keywords": ["companion"]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "provenance.md").write_text("# Provenance\n\nGenerated pixel-pet candidate.\n", encoding="utf-8")
    (root / "qa_report.json").write_text(
        json.dumps(
            {
                "status": "candidate",
                "manual_qa_required": True,
                "distribution_boundary": "official_candidate",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_halo_spritesheet(path: Path) -> None:
    image = Image.new("RGBA", (2 * FRAME_WIDTH, ROWS * FRAME_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for row in range(ROWS):
        for column in range(2):
            left = column * FRAME_WIDTH + 66
            top = row * FRAME_HEIGHT + 54
            draw.rounded_rectangle((left, top, left + 60, top + 96), radius=10, fill=(186, 30, 232, 255))
            draw.rounded_rectangle((left + 3, top + 3, left + 57, top + 93), radius=9, fill=(35, 2, 35, 255))
            draw.rounded_rectangle((left + 7, top + 7, left + 53, top + 89), radius=8, fill=(44, 50, 58, 255))
            draw.rounded_rectangle((left + 72, top + 6, left + 92, top + 30), radius=4, fill=(35, 2, 35, 255))
            draw.rounded_rectangle((left + 76, top + 10, left + 88, top + 26), radius=3, fill=(44, 50, 58, 255))
    image.save(path)


def test_clean_pixel_pet_edge_halo_clones_pack_and_clears_visual_warning(tmp_path: Path) -> None:
    from tools.art.clean_pixel_pet_edge_halo import clean_pixel_pet_edge_halo
    from tools.art.pixel_pet_visual_qa import inspect_pixel_pet_visual_qa

    source_pack = tmp_path / "xingxi_pixel_pet"
    _write_pixel_pet_pack_with_halo(source_pack)
    before = inspect_pixel_pet_visual_qa(source_pack / "spritesheet.png", source_pack / "motion_manifest.json")
    before_dark_purple_edges = _count_dark_purple_edge_pixels(source_pack / "spritesheet.png")

    output_pack = tmp_path / "xingxi_pixel_pet_cleaned"
    report = clean_pixel_pet_edge_halo(source_pack, output_pack, report_path=output_pack / "edge-cleanup-report.json")

    after = inspect_pixel_pet_visual_qa(output_pack / "spritesheet.png", output_pack / "motion_manifest.json")
    after_dark_purple_edges = _count_dark_purple_edge_pixels(output_pack / "spritesheet.png")
    after_transparent_suspicious_rgb = _count_near_transparent_suspicious_rgb(output_pack / "spritesheet.png")
    qa_payload = json.loads((output_pack / "qa_report.json").read_text(encoding="utf-8"))

    assert before.status == "ready_with_warnings"
    assert report.ok is True
    assert report.changed_pixel_count > 0
    assert report.visual_qa_before["warnings"] == ["suspicious_edge_halo_risk"]
    assert report.visual_qa_after["status"] == "ready"
    assert after.status == "ready"
    assert after.suspicious_edge_halo_pixel_count < before.suspicious_edge_halo_pixel_count
    assert before_dark_purple_edges > 0
    assert after_dark_purple_edges == 0
    assert after_transparent_suspicious_rgb == 0
    assert (output_pack / "character.json").is_file()
    assert (output_pack / "edge-cleanup-report.json").is_file()
    assert qa_payload["edge_halo_cleanup"]["changed_pixel_count"] == report.changed_pixel_count

    original_pixels = Image.open(source_pack / "spritesheet.png").convert("RGBA").tobytes()
    cleaned_pixels = Image.open(output_pack / "spritesheet.png").convert("RGBA").tobytes()
    assert original_pixels != cleaned_pixels


def _count_dark_purple_edge_pixels(path: Path) -> int:
    from tools.art.pixel_pet_visual_qa import (
        VISIBLE_ALPHA_THRESHOLD,
        _touches_transparent_neighbor,
    )

    with Image.open(path) as image:
        rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    count = 0
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if alpha < VISIBLE_ALPHA_THRESHOLD:
                continue
            if not _touches_transparent_neighbor(pixels, x, y, width, height):
                continue
            if green <= 16 and red >= 16 and blue >= 16 and abs(red - blue) <= 48:
                count += 1
    return count


def _count_near_transparent_suspicious_rgb(path: Path) -> int:
    from tools.art.pixel_pet_visual_qa import VISIBLE_ALPHA_THRESHOLD, _is_suspicious_halo_color

    with Image.open(path) as image:
        rgba = image.convert("RGBA")
    payload = rgba.tobytes()
    count = 0
    for index in range(0, len(payload), 4):
        red, green, blue, alpha = payload[index : index + 4]
        if alpha < VISIBLE_ALPHA_THRESHOLD and _is_suspicious_halo_color(red, green, blue):
            count += 1
    return count


def test_clean_pixel_pet_edge_halo_rejects_existing_output(tmp_path: Path) -> None:
    from tools.art.clean_pixel_pet_edge_halo import clean_pixel_pet_edge_halo

    source_pack = tmp_path / "xingxi_pixel_pet"
    output_pack = tmp_path / "xingxi_pixel_pet_cleaned"
    _write_pixel_pet_pack_with_halo(source_pack)
    output_pack.mkdir()

    report = clean_pixel_pet_edge_halo(source_pack, output_pack)

    assert report.ok is False
    assert "output_dir already exists" in report.errors


def test_clean_pixel_pet_edge_halo_cli_runs_from_repo_root(tmp_path: Path) -> None:
    source_pack = tmp_path / "xingxi_pixel_pet"
    output_pack = tmp_path / "xingxi_pixel_pet_cleaned"
    report_path = output_pack / "edge-cleanup-report.json"
    _write_pixel_pet_pack_with_halo(source_pack)

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            str(source_pack),
            "--output",
            str(output_pack),
            "--report",
            str(report_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert payload["changed_pixel_count"] > 0
    assert payload["visual_qa_after"]["status"] == "ready"
    assert report_path.is_file()
