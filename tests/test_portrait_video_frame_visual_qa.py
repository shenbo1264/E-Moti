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


def _write_frame(path: Path, *, drift: int = 0, size: tuple[int, int] = (240, 480)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size, (245, 247, 250, 255))
    draw = ImageDraw.Draw(image)
    scale_x = size[0] / 240
    scale_y = size[1] / 480
    draw.rounded_rectangle(
        (
            int((72 + drift) * scale_x),
            int(28 * scale_y),
            int((168 + drift) * scale_x),
            int(456 * scale_y),
        ),
        radius=max(4, int(24 * min(scale_x, scale_y))),
        fill=(64, 92, 148, 255),
    )
    draw.ellipse(
        (
            int((84 + drift) * scale_x),
            int(42 * scale_y),
            int((156 + drift) * scale_x),
            int(126 * scale_y),
        ),
        fill=(238, 210, 194, 255),
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


def test_build_portrait_video_frame_visual_qa_writes_preview_and_metrics(tmp_path: Path):
    from tools.art.portrait_video_frame_visual_qa import build_portrait_video_frame_visual_qa

    pack = _write_source_pack(tmp_path, "xingxi-frame-qa-20260609")
    _write_frame(pack / "frames" / "frame_0001.png")
    _write_frame(pack / "frames" / "frame_0002.png", drift=44)
    _write_frame(pack / "frames" / "frame_0003.png")
    _write_frame(pack / "frames" / "frame_0004.png")
    preview = tmp_path / "frame-qa.png"
    report_path = tmp_path / "frame-qa.json"

    report = build_portrait_video_frame_visual_qa(
        pack,
        preview_path=preview,
        report_path=report_path,
        max_frames=3,
    )

    assert report.ok is True
    assert report.status == "ready_with_warnings"
    assert report.frame_count == 4
    assert report.sampled_frame_count == 3
    assert report.max_body_drift > 16.0
    assert any(frame["body_drift"] and frame["body_drift"] > 16.0 for frame in report.frames)
    assert preview.is_file()
    assert report_path.is_file()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["sampled_frame_count"] == 3
    with Image.open(preview) as image:
        assert image.size[0] > image.size[1] // 2
        assert image.mode == "RGBA"


def test_build_portrait_video_frame_visual_qa_reports_size_mismatch_without_drift(tmp_path: Path):
    from tools.art.portrait_video_frame_visual_qa import build_portrait_video_frame_visual_qa

    pack = _write_source_pack(tmp_path, "xingxi-size-qa-20260609")
    _write_frame(pack / "frames" / "frame_0001.png", size=(120, 240))
    _write_frame(pack / "frames" / "frame_0002.png", size=(120, 240))
    _write_frame(pack / "frames" / "frame_0003.png", size=(120, 240))

    report = build_portrait_video_frame_visual_qa(
        pack,
        preview_path=tmp_path / "size-qa.png",
        max_frames=2,
    )

    assert report.ok is True
    assert report.status == "ready_with_warnings"
    assert report.size_mismatch_count == 3
    assert report.max_body_drift == 0.0
    assert all(frame["body_drift"] is None for frame in report.frames)


def test_build_portrait_video_frame_visual_qa_rejects_missing_pack(tmp_path: Path):
    from tools.art.portrait_video_frame_visual_qa import build_portrait_video_frame_visual_qa

    report = build_portrait_video_frame_visual_qa(
        tmp_path / "missing-pack",
        preview_path=tmp_path / "missing.png",
    )

    assert report.ok is False
    assert report.status == "invalid_source_pack"
    assert "source_pack.json not found" in report.errors
    assert not (tmp_path / "missing.png").exists()


def test_portrait_video_frame_visual_qa_cli_writes_outputs(tmp_path: Path):
    pack = _write_source_pack(tmp_path, "xingxi-cli-qa-20260609")
    for index in range(3):
        _write_frame(pack / "frames" / f"frame_{index + 1:04d}.png")
    preview = tmp_path / "cli-frame-qa.png"
    report_path = tmp_path / "cli-frame-qa.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/portrait_video_frame_visual_qa.py",
            str(pack),
            "--preview",
            str(preview),
            "--report",
            str(report_path),
            "--max-frames",
            "2",
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
    assert payload["sampled_frame_count"] == 2
    assert preview.is_file()
    assert report_path.is_file()
