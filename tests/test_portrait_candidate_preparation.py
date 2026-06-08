from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from tools.art.validate_portrait_candidates import validate_portrait_candidate


def _write_rgb_source(path: Path) -> None:
    image = Image.new("RGB", (320, 640), (246, 247, 250))
    draw = ImageDraw.Draw(image)
    draw.ellipse((118, 72, 202, 156), fill=(236, 238, 244), outline=(60, 64, 82), width=3)
    draw.rounded_rectangle((102, 150, 218, 560), radius=24, fill=(42, 84, 148), outline=(36, 42, 64), width=4)
    draw.rectangle((132, 560, 152, 620), fill=(50, 55, 75))
    draw.rectangle((168, 560, 188, 620), fill=(50, 55, 75))
    image.save(path)


def test_prepare_portrait_candidate_builds_valid_alpha_candidate_pack(tmp_path: Path):
    from tools.art.prepare_portrait_candidate import prepare_portrait_candidate

    source = tmp_path / "source.png"
    output = tmp_path / "portrait-candidate-xingxi-vn"
    _write_rgb_source(source)

    report = prepare_portrait_candidate(source, output, report_path=output / "candidate-preparation-report.json")

    manifest = output / "portrait_candidate.json"
    portrait = output / "portraits" / "neutral_open.png"
    contact_sheet = output / "preview" / "portrait-contact-sheet.png"
    report_path = output / "candidate-preparation-report.json"

    assert report.ok is True
    assert report.errors == ()
    assert manifest.is_file()
    assert portrait.is_file()
    assert contact_sheet.is_file()
    assert report_path.is_file()

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["status"] == "candidate"
    assert payload["approval_required"] is True
    assert payload["runtime_manifest_safe"] is False
    assert payload["expressions"] == {"neutral": {"open": "portraits/neutral_open.png"}}

    with Image.open(portrait) as image:
        assert image.mode == "RGBA"
        assert image.size == (320, 640)
        assert image.getpixel((0, 0))[3] == 0
        assert image.getpixel((160, 320))[3] == 255

    validation = validate_portrait_candidate(manifest)
    assert validation.ok is True


def test_prepare_portrait_candidate_rejects_non_image_source(tmp_path: Path):
    from tools.art.prepare_portrait_candidate import prepare_portrait_candidate

    source = tmp_path / "source.png"
    source.write_text("not an image", encoding="utf-8")

    report = prepare_portrait_candidate(source, tmp_path / "candidate")

    assert report.ok is False
    assert any(error.startswith("source image invalid:") for error in report.errors)


def test_prepare_portrait_candidate_cli_runs_from_repo_root(tmp_path: Path):
    source = tmp_path / "source.png"
    output = tmp_path / "portrait-candidate"
    _write_rgb_source(source)

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/prepare_portrait_candidate.py",
            str(source),
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert (output / "portrait_candidate.json").is_file()


def test_build_portrait_candidate_visual_qa_writes_preview_and_metrics(tmp_path: Path):
    from tools.art.portrait_candidate_visual_qa import build_portrait_candidate_visual_qa
    from tools.art.prepare_portrait_candidate import prepare_portrait_candidate

    source = tmp_path / "source.png"
    candidate = tmp_path / "portrait-candidate"
    report_path = tmp_path / "portrait-qa-report.json"
    preview_path = tmp_path / "portrait-qa-preview.png"
    _write_rgb_source(source)
    prepare_portrait_candidate(source, candidate)

    report = build_portrait_candidate_visual_qa(
        candidate / "portrait_candidate.json",
        preview_path=preview_path,
        report_path=report_path,
    )

    assert report.ok is True
    assert report.image_count == 1
    assert report.preview_path == str(preview_path)
    assert report_path.is_file()
    assert preview_path.is_file()
    assert report.images[0]["label"] == "neutral.open"
    assert report.images[0]["path"] == "portraits/neutral_open.png"
    assert report.images[0]["alpha_extrema"] == [0, 255]
    assert report.images[0]["transparent_corner_count"] == 4
    assert report.images[0]["edge_alpha_pixel_count"] > 0
    with Image.open(preview_path) as image:
        assert image.mode == "RGBA"
        assert image.width == 3 * 320
        assert image.height >= 640


def test_portrait_candidate_visual_qa_cli_runs_from_repo_root(tmp_path: Path):
    from tools.art.prepare_portrait_candidate import prepare_portrait_candidate

    source = tmp_path / "source.png"
    candidate = tmp_path / "portrait-candidate"
    report_path = tmp_path / "portrait-qa-report.json"
    preview_path = tmp_path / "portrait-qa-preview.png"
    _write_rgb_source(source)
    prepare_portrait_candidate(source, candidate)

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/portrait_candidate_visual_qa.py",
            str(candidate / "portrait_candidate.json"),
            "--preview",
            str(preview_path),
            "--report",
            str(report_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["preview_path"] == str(preview_path)


def test_portrait_candidate_visual_qa_flags_light_edge_halo_risk(tmp_path: Path):
    from tools.art.portrait_candidate_visual_qa import build_portrait_candidate_visual_qa

    candidate = tmp_path / "portrait-candidate"
    portraits = candidate / "portraits"
    portraits.mkdir(parents=True)
    image = Image.new("RGBA", (128, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((36, 24, 92, 232), radius=18, fill=(248, 248, 248, 128))
    draw.rounded_rectangle((42, 30, 86, 226), radius=14, fill=(40, 68, 120, 255))
    image.save(portraits / "neutral_open.png")
    (candidate / "portrait_candidate.json").write_text(
        json.dumps(
            {
                "status": "candidate",
                "expressions": {"neutral": {"open": "portraits/neutral_open.png"}},
            }
        ),
        encoding="utf-8",
    )

    report = build_portrait_candidate_visual_qa(
        candidate / "portrait_candidate.json",
        preview_path=tmp_path / "preview.png",
    )

    image_report = report.images[0]
    assert image_report["light_edge_alpha_pixel_count"] > 0
    assert image_report["light_edge_alpha_ratio"] > 0
    assert "light_edge_halo_risk" in image_report["warnings"]
