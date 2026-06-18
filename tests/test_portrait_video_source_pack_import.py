from __future__ import annotations

import json
import os
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


def _write_video(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake mp4")


def test_import_portrait_video_to_source_pack_copies_video_and_extracts_frames(tmp_path: Path):
    from tools.art.import_portrait_video_to_source_pack import import_portrait_video_to_source_pack

    source_pack = _write_source_pack(tmp_path)
    video = tmp_path / "downloads" / "pika blink.mp4"
    _write_video(video)

    def fake_extractor(video_path: Path, frames_dir: Path, fps: int) -> str:
        assert video_path == source_pack / "video" / "pika blink.mp4"
        assert fps == 8
        frames_dir.mkdir(parents=True, exist_ok=True)
        for index in range(1, 4):
            (frames_dir / f"frame_{index:05d}.png").write_bytes(b"png")
        return ""

    report = import_portrait_video_to_source_pack(
        source_pack_dir=source_pack,
        video_path=video,
        fps=8,
        source_tool="Pika",
        ffmpeg_extractor=fake_extractor,
    )

    assert report.ok is True
    assert report.set_id == "xingxi-vn-neutral-20260608"
    assert Path(report.copied_video_path).is_file()
    assert Path(report.frames_dir).is_dir()
    assert report.frame_count == 3
    assert Path(report.report_path).is_file()
    assert "python tools\\art\\inspect_portrait_video_source_frames.py" in report.next_commands[0]
    payload = json.loads(Path(report.report_path).read_text(encoding="utf-8"))
    assert payload["source_tool"] == "Pika"
    assert payload["frame_count"] == 3


def test_import_portrait_video_to_source_pack_does_not_overwrite_frames_by_default(tmp_path: Path):
    from tools.art.import_portrait_video_to_source_pack import import_portrait_video_to_source_pack

    source_pack = _write_source_pack(tmp_path)
    video = tmp_path / "downloads" / "runway.mp4"
    _write_video(video)
    frames_dir = source_pack / "frames"
    existing = frames_dir / "frame_00001.png"
    existing.write_bytes(b"existing")
    calls: list[str] = []

    def fake_extractor(video_path: Path, frames_dir: Path, fps: int) -> str:
        calls.append(str(video_path))
        return ""

    report = import_portrait_video_to_source_pack(
        source_pack_dir=source_pack,
        video_path=video,
        ffmpeg_extractor=fake_extractor,
    )

    assert report.ok is False
    assert calls == []
    assert existing.read_bytes() == b"existing"
    assert "frames_dir already contains PNG frames; pass replace_frames=True to overwrite" in report.errors


def test_import_portrait_video_to_source_pack_rejects_unsafe_metadata_paths(tmp_path: Path):
    from tools.art.import_portrait_video_to_source_pack import import_portrait_video_to_source_pack

    source_pack = _write_source_pack(tmp_path)
    metadata_path = source_pack / "source_pack.json"
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload["video_dir"] = "../video"
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")
    video = tmp_path / "downloads" / "krea.mp4"
    _write_video(video)

    report = import_portrait_video_to_source_pack(source_pack_dir=source_pack, video_path=video)

    assert report.ok is False
    assert "source_pack.json.video_dir must be a safe relative path" in report.errors


def test_import_portrait_video_to_source_pack_cli_runs_from_repo_root(tmp_path: Path):
    source_pack = _write_source_pack(tmp_path)
    video = tmp_path / "downloads" / "pika.mp4"
    _write_video(video)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_py = fake_bin / "fake_ffmpeg.py"
    fake_py.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "pattern = Path(sys.argv[-1])",
                "pattern.parent.mkdir(parents=True, exist_ok=True)",
                "for index in range(1, 4):",
                "    (pattern.parent / f'frame_{index:05d}.png').write_bytes(b'png')",
            ]
        ),
        encoding="utf-8",
    )
    (fake_bin / "ffmpeg.cmd").write_text(
        f'@echo off\r\n"{sys.executable}" "{fake_py}" %*\r\n',
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/import_portrait_video_to_source_pack.py",
            str(source_pack),
            "--video",
            str(video),
            "--source-tool",
            "Pika",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["frame_count"] == 3
    assert (source_pack / "video" / "pika.mp4").is_file()
