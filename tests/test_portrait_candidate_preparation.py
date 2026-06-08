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
