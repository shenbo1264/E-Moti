from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def _write_reference(path: Path, *, size: tuple[int, int] = (240, 480)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
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
        fill=(64, 92, 148, 255),
    )
    draw.ellipse(
        (
            int(84 * scale_x),
            int(42 * scale_y),
            int(156 * scale_x),
            int(126 * scale_y),
        ),
        fill=(238, 210, 194, 255),
    )
    image.save(path)


def _write_provider_frame(path: Path, *, size: tuple[int, int]) -> None:
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
    draw.ellipse(
        (
            int(84 * scale_x),
            int(42 * scale_y),
            int(156 * scale_x),
            int(126 * scale_y),
        ),
        fill=(238, 210, 194),
    )
    image.save(path)


def _write_source_pack(tmp_path: Path, set_id: str = "xingxi-lowres-20260609") -> Path:
    from tools.art.create_portrait_video_source_pack import create_portrait_video_source_pack

    source = tmp_path / "source" / "neutral_open.png"
    _write_reference(source)
    report = create_portrait_video_source_pack(
        source_image_path=source,
        output_root=tmp_path / "portrait-video-source",
        set_id=set_id,
        character_name="Xingxi",
        source_label="VN neutral candidate",
    )
    return Path(report.output_dir)


def test_normalize_portrait_video_source_pack_creates_ready_clone_from_same_aspect_frames(tmp_path: Path):
    from tools.art.inspect_portrait_video_source_frames import inspect_portrait_video_source_frames
    from tools.art.normalize_portrait_video_source_frames import normalize_portrait_video_source_pack

    source_pack = _write_source_pack(tmp_path)
    for index in range(3):
        _write_provider_frame(source_pack / "frames" / f"frame_{index + 1:04d}.png", size=(120, 240))
    output_pack = tmp_path / "normalized-source" / "xingxi-lowres-normalized"

    report = normalize_portrait_video_source_pack(source_pack_dir=source_pack, output_pack_dir=output_pack)

    assert report.ok is True
    assert report.source_set_id == "xingxi-lowres-20260609"
    assert report.set_id == "xingxi-lowres-20260609-normalized"
    assert report.reference_size == (240, 480)
    assert report.input_frame_count == 3
    assert report.normalized_frame_count == 3
    assert report.resized_frame_count == 3
    assert (output_pack / "source_pack.json").is_file()
    payload = json.loads((output_pack / "source_pack.json").read_text(encoding="utf-8"))
    assert payload["set_id"] == "xingxi-lowres-20260609-normalized"
    assert payload["frames_dir"] == "frames"
    assert str(output_pack) in payload["next_command"]
    assert str(source_pack) not in payload["next_command"]
    assert "portrait-candidate-xingxi-lowres-20260609-normalized-motion" in payload["next_command"]
    with Image.open(output_pack / "frames" / "frame_0001.png") as image:
        assert image.size == (240, 480)

    preflight = inspect_portrait_video_source_frames(source_root=output_pack.parent)

    assert preflight.ready_count == 1
    assert preflight.items[0].status == "ready"


def test_normalize_portrait_video_source_pack_rejects_aspect_mismatch(tmp_path: Path):
    from tools.art.normalize_portrait_video_source_frames import normalize_portrait_video_source_pack

    source_pack = _write_source_pack(tmp_path)
    _write_provider_frame(source_pack / "frames" / "frame_0001.png", size=(120, 300))

    report = normalize_portrait_video_source_pack(source_pack_dir=source_pack)

    assert report.ok is False
    assert report.aspect_mismatch_count == 1
    assert report.normalized_frame_count == 0
    assert any("aspect ratio" in error for error in report.errors)


def test_normalize_portrait_video_source_pack_cli_writes_report(tmp_path: Path):
    source_pack = _write_source_pack(tmp_path)
    for index in range(3):
        _write_provider_frame(source_pack / "frames" / f"frame_{index + 1:04d}.png", size=(120, 240))
    output_pack = tmp_path / "normalized-source" / "xingxi-lowres-normalized"
    report_path = tmp_path / "normalization-report.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/normalize_portrait_video_source_frames.py",
            str(source_pack),
            "--output-pack-dir",
            str(output_pack),
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
    assert payload["set_id"] == "xingxi-lowres-20260609-normalized"
    assert payload["normalized_frame_count"] == 3
    assert report_path.is_file()
