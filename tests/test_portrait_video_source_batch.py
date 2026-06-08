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


def _write_frame(path: Path, *, eye: str, drift: int = 0, size: tuple[int, int] = (240, 480)) -> None:
    image = Image.new("RGB", size, (245, 247, 250))
    draw = ImageDraw.Draw(image)
    scale_x = size[0] / 240
    scale_y = size[1] / 480
    offset = drift
    draw.rounded_rectangle(
        (
            int((72 + offset) * scale_x),
            int(28 * scale_y),
            int((168 + offset) * scale_x),
            int(456 * scale_y),
        ),
        radius=max(4, int(24 * min(scale_x, scale_y))),
        fill=(64, 92, 148),
    )
    draw.ellipse(
        (
            int((84 + offset) * scale_x),
            int(42 * scale_y),
            int((156 + offset) * scale_x),
            int(126 * scale_y),
        ),
        fill=(238, 210, 194),
    )
    if eye == "open":
        draw.ellipse(
            (
                int((103 + offset) * scale_x),
                int(78 * scale_y),
                int((115 + offset) * scale_x),
                int(94 * scale_y),
            ),
            fill=(94, 66, 38),
        )
        draw.ellipse(
            (
                int((128 + offset) * scale_x),
                int(78 * scale_y),
                int((140 + offset) * scale_x),
                int(94 * scale_y),
            ),
            fill=(94, 66, 38),
        )
    elif eye == "half":
        draw.line(
            (
                int((102 + offset) * scale_x),
                int(84 * scale_y),
                int((116 + offset) * scale_x),
                int(88 * scale_y),
            ),
            fill=(68, 50, 48),
            width=max(1, int(3 * min(scale_x, scale_y))),
        )
        draw.line(
            (
                int((127 + offset) * scale_x),
                int(84 * scale_y),
                int((141 + offset) * scale_x),
                int(88 * scale_y),
            ),
            fill=(68, 50, 48),
            width=max(1, int(3 * min(scale_x, scale_y))),
        )
    elif eye == "closed":
        draw.line(
            (
                int((102 + offset) * scale_x),
                int(88 * scale_y),
                int((116 + offset) * scale_x),
                int(88 * scale_y),
            ),
            fill=(68, 50, 48),
            width=max(1, int(4 * min(scale_x, scale_y))),
        )
        draw.line(
            (
                int((127 + offset) * scale_x),
                int(88 * scale_y),
                int((141 + offset) * scale_x),
                int(88 * scale_y),
            ),
            fill=(68, 50, 48),
            width=max(1, int(4 * min(scale_x, scale_y))),
        )
    image.save(path)


def _write_frames(root: Path, *, count: int = 4) -> None:
    root.mkdir(parents=True, exist_ok=True)
    frames = (
        ("frame_0001.png", "open", 0),
        ("frame_0002.png", "half", 0),
        ("frame_0003.png", "closed", 0),
        ("frame_0004.png", "open", 22),
    )
    for filename, eye, drift in frames[:count]:
        _write_frame(root / filename, eye=eye, drift=drift)


def _write_source_pack(root: Path, set_id: str, *, frame_count: int) -> Path:
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
    if frame_count:
        _write_frames(pack / "frames", count=frame_count)
    return pack


def test_scan_portrait_video_source_packs_reports_ready_waiting_and_insufficient(tmp_path: Path):
    from tools.art.batch_process_portrait_video_source_packs import scan_portrait_video_source_packs

    source_root = tmp_path / "portrait-video-source"
    _write_source_pack(tmp_path, "xingxi-ready-20260608", frame_count=4)
    _write_source_pack(tmp_path, "xingxi-waiting-20260608", frame_count=0)
    _write_source_pack(tmp_path, "xingxi-short-20260608", frame_count=2)

    report = scan_portrait_video_source_packs(source_root=source_root)

    assert report.ok is True
    assert report.insufficient_count == 1
    statuses = {pack.set_id: pack.status for pack in report.packs}
    assert statuses == {
        "xingxi-ready-20260608": "ready",
        "xingxi-short-20260608": "insufficient_frames",
        "xingxi-waiting-20260608": "waiting_for_frames",
    }
    frame_counts = {pack.set_id: pack.frame_count for pack in report.packs}
    assert frame_counts["xingxi-ready-20260608"] == 4
    assert frame_counts["xingxi-short-20260608"] == 2
    assert frame_counts["xingxi-waiting-20260608"] == 0


def test_batch_process_portrait_video_source_packs_processes_ready_only(tmp_path: Path):
    from tools.art.batch_process_portrait_video_source_packs import scan_portrait_video_source_packs

    source_root = tmp_path / "portrait-video-source"
    _write_source_pack(tmp_path, "xingxi-ready-20260608", frame_count=4)
    _write_source_pack(tmp_path, "xingxi-waiting-20260608", frame_count=0)
    _write_source_pack(tmp_path, "xingxi-short-20260608", frame_count=2)
    output_root = tmp_path / "candidates"

    report = scan_portrait_video_source_packs(
        source_root=source_root,
        process_ready=True,
        output_root=output_root,
    )

    statuses = {pack.set_id: pack.status for pack in report.packs}
    assert report.insufficient_count == 1
    assert statuses["xingxi-ready-20260608"] == "processed"
    assert statuses["xingxi-short-20260608"] == "insufficient_frames"
    assert statuses["xingxi-waiting-20260608"] == "waiting_for_frames"
    assert (output_root / "portrait-candidate-xingxi-ready-20260608-motion" / "portrait_candidate.json").is_file()
    assert not (output_root / "portrait-candidate-xingxi-short-20260608-motion").exists()
    assert not (output_root / "portrait-candidate-xingxi-waiting-20260608-motion").exists()


def test_batch_process_portrait_video_source_packs_skips_frame_warnings(tmp_path: Path):
    from tools.art.batch_process_portrait_video_source_packs import scan_portrait_video_source_packs

    source_root = tmp_path / "portrait-video-source"
    pack = _write_source_pack(tmp_path, "xingxi-warning-20260609", frame_count=0)
    frames = pack / "frames"
    _write_frame(frames / "frame_0001.png", eye="open")
    _write_frame(frames / "frame_0002.png", eye="half", size=(320, 480))
    _write_frame(frames / "frame_0003.png", eye="closed")
    output_root = tmp_path / "candidates"

    scan = scan_portrait_video_source_packs(source_root=source_root)
    process = scan_portrait_video_source_packs(
        source_root=source_root,
        process_ready=True,
        output_root=output_root,
    )

    assert scan.ok is True
    assert scan.ready_count == 0
    assert scan.warning_count == 1
    assert scan.packs[0].status == "ready_with_warnings"
    assert scan.packs[0].warnings
    assert process.ok is True
    assert process.processed_count == 0
    assert process.warning_count == 1
    assert process.packs[0].status == "ready_with_warnings"
    assert not (output_root / "portrait-candidate-xingxi-warning-20260609-motion").exists()


def test_batch_process_portrait_video_source_packs_cli_writes_report(tmp_path: Path):
    source_root = tmp_path / "portrait-video-source"
    _write_source_pack(tmp_path, "xingxi-ready-20260608", frame_count=4)
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
