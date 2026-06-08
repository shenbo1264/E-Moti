from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


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


def _write_source_pack(tmp_path: Path) -> Path:
    from tools.art.create_portrait_video_source_pack import create_portrait_video_source_pack

    source = tmp_path / "source" / "neutral_open.png"
    _write_reference(source)
    report = create_portrait_video_source_pack(
        source_image_path=source,
        output_root=tmp_path / "portrait-video-source",
        set_id="xingxi-vn-neutral-20260608",
        character_name="Xingxi",
        source_label="VN neutral candidate",
    )
    return Path(report.output_dir)


def test_process_portrait_video_source_pack_extracts_candidate_from_frames(tmp_path: Path):
    from tools.art.process_portrait_video_source_pack import process_portrait_video_source_pack

    source_pack = _write_source_pack(tmp_path)
    _write_frames(source_pack / "frames")
    output_dir = tmp_path / "motion-candidate"

    report = process_portrait_video_source_pack(source_pack_dir=source_pack, output_dir=output_dir)

    assert report.ok is True
    assert report.set_id == "xingxi-vn-neutral-20260608"
    assert Path(report.candidate_manifest_path).is_file()
    assert Path(report.extraction_report_path).is_file()
    assert report.motion_frame_count == 3
    provenance = (output_dir / "portrait_video_provenance.md").read_text(encoding="utf-8")
    assert "Gemini Portrait Video Prompt" in provenance
    assert "VN neutral candidate" in provenance


def test_process_portrait_video_source_pack_reports_missing_frames(tmp_path: Path):
    from tools.art.process_portrait_video_source_pack import process_portrait_video_source_pack

    source_pack = _write_source_pack(tmp_path)

    report = process_portrait_video_source_pack(source_pack_dir=source_pack, output_dir=tmp_path / "motion-candidate")

    assert report.ok is False
    assert "no png frames found" in report.errors


def test_process_portrait_video_source_pack_rejects_unsafe_metadata_paths(tmp_path: Path):
    from tools.art.process_portrait_video_source_pack import process_portrait_video_source_pack

    source_pack = _write_source_pack(tmp_path)
    metadata_path = source_pack / "source_pack.json"
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload["reference_image"] = "../outside.png"
    payload["frames_dir"] = "frames"
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")

    report = process_portrait_video_source_pack(source_pack_dir=source_pack, output_dir=tmp_path / "motion-candidate")

    assert report.ok is False
    assert "source_pack.json.reference_image must be a safe relative path" in report.errors


def test_process_portrait_video_source_pack_cli_runs_from_repo_root(tmp_path: Path):
    source_pack = _write_source_pack(tmp_path)
    _write_frames(source_pack / "frames")
    output_dir = tmp_path / "motion-candidate"

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/process_portrait_video_source_pack.py",
            str(source_pack),
            "--output-dir",
            str(output_dir),
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
    assert payload["motion_frame_count"] == 3
    assert (output_dir / "portrait_candidate.json").is_file()
