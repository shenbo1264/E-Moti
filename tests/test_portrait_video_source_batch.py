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


def _write_source_pack(root: Path, set_id: str, *, with_frames: bool) -> Path:
    from tools.art.create_portrait_video_source_pack import create_portrait_video_source_pack

    source = root / "sources" / f"{set_id}.png"
    _write_reference(source)
    report = create_portrait_video_source_pack(
        source_image_path=source,
        output_root=root / "portrait-video-source",
        set_id=set_id,
        character_name="Xingxi",
        source_label=set_id,
    )
    pack = Path(report.output_dir)
    if with_frames:
        _write_frames(pack / "frames")
    return pack


def test_scan_portrait_video_source_packs_reports_ready_and_waiting(tmp_path: Path):
    from tools.art.batch_process_portrait_video_source_packs import scan_portrait_video_source_packs

    source_root = tmp_path / "portrait-video-source"
    _write_source_pack(tmp_path, "xingxi-ready-20260608", with_frames=True)
    _write_source_pack(tmp_path, "xingxi-waiting-20260608", with_frames=False)

    report = scan_portrait_video_source_packs(source_root=source_root)

    assert report.ok is True
    statuses = {pack.set_id: pack.status for pack in report.packs}
    assert statuses == {
        "xingxi-ready-20260608": "ready",
        "xingxi-waiting-20260608": "waiting_for_frames",
    }
    frame_counts = {pack.set_id: pack.frame_count for pack in report.packs}
    assert frame_counts["xingxi-ready-20260608"] == 4
    assert frame_counts["xingxi-waiting-20260608"] == 0


def test_batch_process_portrait_video_source_packs_processes_ready_only(tmp_path: Path):
    from tools.art.batch_process_portrait_video_source_packs import scan_portrait_video_source_packs

    source_root = tmp_path / "portrait-video-source"
    _write_source_pack(tmp_path, "xingxi-ready-20260608", with_frames=True)
    _write_source_pack(tmp_path, "xingxi-waiting-20260608", with_frames=False)
    output_root = tmp_path / "candidates"

    report = scan_portrait_video_source_packs(
        source_root=source_root,
        process_ready=True,
        output_root=output_root,
    )

    statuses = {pack.set_id: pack.status for pack in report.packs}
    assert statuses["xingxi-ready-20260608"] == "processed"
    assert statuses["xingxi-waiting-20260608"] == "waiting_for_frames"
    assert (output_root / "portrait-candidate-xingxi-ready-20260608-motion" / "portrait_candidate.json").is_file()
    assert not (output_root / "portrait-candidate-xingxi-waiting-20260608-motion").exists()


def test_batch_process_portrait_video_source_packs_cli_writes_report(tmp_path: Path):
    source_root = tmp_path / "portrait-video-source"
    _write_source_pack(tmp_path, "xingxi-ready-20260608", with_frames=True)
    report_path = tmp_path / "batch-report.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/batch_process_portrait_video_source_packs.py",
            str(source_root),
            "--process-ready",
            "--output-root",
            str(tmp_path / "candidates"),
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
    assert payload["processed_count"] == 1
    assert report_path.is_file()
