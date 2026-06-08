from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from tools.art.validate_portrait_candidates import validate_portrait_candidate


def _write_reference(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (240, 480), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((72, 28, 168, 456), radius=24, fill=(64, 92, 148, 255))
    draw.ellipse((84, 42, 156, 126), fill=(238, 210, 194, 255))
    draw.ellipse((103, 78, 115, 94), fill=(94, 66, 38, 255))
    draw.ellipse((128, 78, 140, 94), fill=(94, 66, 38, 255))
    image.save(path)


def _write_frame(path: Path, *, eye: str, drift: int = 0) -> None:
    image = Image.new("RGB", (240, 480), (245, 247, 250))
    draw = ImageDraw.Draw(image)
    offset = drift
    draw.rounded_rectangle((72 + offset, 28, 168 + offset, 456), radius=24, fill=(64, 92, 148))
    draw.ellipse((84 + offset, 42, 156 + offset, 126), fill=(238, 210, 194))
    if eye == "open":
        draw.ellipse((103 + offset, 78, 115 + offset, 94), fill=(94, 66, 38))
        draw.ellipse((128 + offset, 78, 140 + offset, 94), fill=(94, 66, 38))
    elif eye == "half":
        draw.line((102 + offset, 84, 116 + offset, 88), fill=(68, 50, 48), width=3)
        draw.line((127 + offset, 84, 141 + offset, 88), fill=(68, 50, 48), width=3)
    elif eye == "closed":
        draw.line((102 + offset, 88, 116 + offset, 88), fill=(68, 50, 48), width=4)
        draw.line((127 + offset, 88, 141 + offset, 88), fill=(68, 50, 48), width=4)
    image.save(path)


def _write_frames(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _write_frame(root / "frame_0001.png", eye="open")
    _write_frame(root / "frame_0002.png", eye="half")
    _write_frame(root / "frame_0003.png", eye="closed")
    _write_frame(root / "frame_0004.png", eye="open", drift=22)


def test_extract_portrait_motion_frames_builds_blink_candidate_pack(tmp_path: Path):
    from tools.art.extract_portrait_motion_frames import extract_portrait_motion_frames

    reference = tmp_path / "reference" / "neutral_open.png"
    frames = tmp_path / "frames"
    output = tmp_path / "motion-candidate"
    _write_reference(reference)
    _write_frames(frames)

    report = extract_portrait_motion_frames(
        reference_image_path=reference,
        frames_dir=frames,
        output_dir=output,
        idle_frame_count=3,
    )

    assert report.ok is True
    assert report.selected_open_frame == "reference"
    assert report.selected_blink_half_frame == "frame_0002.png"
    assert report.selected_blink_closed_frame == "frame_0003.png"
    assert report.rejected_frame_count == 1
    assert report.generated_frames == (
        "portraits/neutral_open.png",
        "portraits/neutral_blink_half.png",
        "portraits/neutral_blink_closed.png",
    )
    assert (output / "portrait_candidate.json").is_file()
    assert (output / "candidate-motion-frame-report.json").is_file()
    assert (output / "motion_frames" / "idle_0001.png").is_file()

    payload = json.loads((output / "portrait_candidate.json").read_text(encoding="utf-8"))
    assert payload["status"] == "candidate"
    assert payload["approval_required"] is True
    assert payload["runtime_manifest_safe"] is False
    assert payload["expressions"]["neutral"] == {
        "open": "portraits/neutral_open.png",
        "blink_half": "portraits/neutral_blink_half.png",
        "blink_closed": "portraits/neutral_blink_closed.png",
    }
    assert payload["motion_frames"] == [
        "motion_frames/idle_0001.png",
        "motion_frames/idle_0002.png",
        "motion_frames/idle_0003.png",
    ]
    assert validate_portrait_candidate(output / "portrait_candidate.json").ok is True

    with Image.open(output / "portraits" / "neutral_open.png") as opened:
        open_frame = opened.convert("RGB")
    with Image.open(output / "portraits" / "neutral_blink_closed.png") as closed:
        assert ImageChops.difference(open_frame, closed.convert("RGB")).getbbox() is not None


def test_extract_portrait_motion_frames_cli_runs_from_repo_root(tmp_path: Path):
    reference = tmp_path / "reference" / "neutral_open.png"
    frames = tmp_path / "frames"
    output = tmp_path / "motion-candidate"
    report_path = output / "candidate-motion-frame-report.json"
    _write_reference(reference)
    _write_frames(frames)

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/extract_portrait_motion_frames.py",
            "--reference-image",
            str(reference),
            "--frames-dir",
            str(frames),
            "--output-dir",
            str(output),
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
    assert payload["selected_blink_closed_frame"] == "frame_0003.png"
    assert report_path.is_file()
