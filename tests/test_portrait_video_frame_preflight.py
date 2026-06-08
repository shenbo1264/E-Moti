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
    image.save(path)


def _write_frame(path: Path, *, size: tuple[int, int] = (240, 480)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, (245, 247, 250))
    draw = ImageDraw.Draw(image)
    scale_x = size[0] / 240
    scale_y = size[1] / 480
    draw.rounded_rectangle(
        (
            int(72 * scale_x),
            int(28 * scale_y),
            int(168 * scale_x),
            int(456 * scale_y),
        ),
        radius=max(4, int(24 * min(scale_x, scale_y))),
        fill=(64, 92, 148),
    )
    image.save(path)


def _write_source_pack(root: Path, set_id: str) -> Path:
    from tools.art.create_portrait_video_source_pack import create_portrait_video_source_pack

    source = root / "source" / f"{set_id}.png"
    _write_reference(source)
    report = create_portrait_video_source_pack(
        source_image_path=source,
        output_root=root / "portrait-video-source",
        set_id=set_id,
        character_name="Xingxi",
        source_label=set_id,
    )
    return Path(report.output_dir)


def test_inspect_portrait_video_source_frames_reports_ready_pack(tmp_path: Path):
    from tools.art.inspect_portrait_video_source_frames import inspect_portrait_video_source_frames

    source_root = tmp_path / "portrait-video-source"
    pack = _write_source_pack(tmp_path, "xingxi-ready-20260609")
    for index in range(4):
        _write_frame(pack / "frames" / f"frame_{index + 1:04d}.png")

    report = inspect_portrait_video_source_frames(source_root=source_root)

    assert report.ok is True
    assert report.ready_count == 1
    assert report.invalid_count == 0
    item = report.items[0]
    assert item.status == "ready"
    assert item.frame_count == 4
    assert item.readable_frame_count == 4
    assert item.invalid_frame_count == 0
    assert item.size_mismatch_count == 0
    assert item.next_action == "process_frames"


def test_inspect_portrait_video_source_frames_rejects_invalid_png(tmp_path: Path):
    from tools.art.inspect_portrait_video_source_frames import inspect_portrait_video_source_frames

    source_root = tmp_path / "portrait-video-source"
    pack = _write_source_pack(tmp_path, "xingxi-invalid-20260609")
    _write_frame(pack / "frames" / "frame_0001.png")
    _write_frame(pack / "frames" / "frame_0002.png")
    (pack / "frames" / "frame_0003.png").write_text("not a png", encoding="utf-8")

    report = inspect_portrait_video_source_frames(source_root=source_root)

    assert report.ok is False
    assert report.invalid_count == 1
    item = report.items[0]
    assert item.status == "invalid_frames"
    assert item.frame_count == 3
    assert item.readable_frame_count == 2
    assert item.invalid_frame_count == 1
    assert item.next_action == "replace_invalid_frames"
    assert any("frame_0003.png" in error for error in item.errors)


def test_inspect_portrait_video_source_frames_warns_on_size_mismatch(tmp_path: Path):
    from tools.art.inspect_portrait_video_source_frames import inspect_portrait_video_source_frames

    source_root = tmp_path / "portrait-video-source"
    pack = _write_source_pack(tmp_path, "xingxi-mismatch-20260609")
    _write_frame(pack / "frames" / "frame_0001.png")
    _write_frame(pack / "frames" / "frame_0002.png", size=(320, 480))
    _write_frame(pack / "frames" / "frame_0003.png")

    report = inspect_portrait_video_source_frames(source_root=source_root)

    assert report.ok is True
    assert report.warning_count == 1
    item = report.items[0]
    assert item.status == "ready_with_warnings"
    assert item.size_mismatch_count == 1
    assert item.next_action == "review_frame_warnings"
    assert any("frame_0002.png size 320x480 differs from reference 240x480" in warning for warning in item.warnings)


def test_inspect_portrait_video_source_frames_cli_writes_report(tmp_path: Path):
    source_root = tmp_path / "portrait-video-source"
    pack = _write_source_pack(tmp_path, "xingxi-ready-20260609")
    for index in range(3):
        _write_frame(pack / "frames" / f"frame_{index + 1:04d}.png")
    report_path = tmp_path / "frame-preflight.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/inspect_portrait_video_source_frames.py",
            str(source_root),
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
    assert payload["ready_count"] == 1
    assert report_path.is_file()
