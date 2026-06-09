from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_FPS = 12
FrameExtractor = Callable[[Path, Path, int], str]


@dataclass(frozen=True, slots=True)
class PortraitVideoSourcePackImportReport:
    ok: bool
    set_id: str
    source_pack_dir: str
    input_video_path: str
    copied_video_path: str
    frames_dir: str
    report_path: str
    source_tool: str
    fps: int
    replace_frames: bool
    frame_count: int
    next_commands: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "set_id": self.set_id,
            "source_pack_dir": self.source_pack_dir,
            "input_video_path": self.input_video_path,
            "copied_video_path": self.copied_video_path,
            "frames_dir": self.frames_dir,
            "report_path": self.report_path,
            "source_tool": self.source_tool,
            "fps": self.fps,
            "replace_frames": self.replace_frames,
            "frame_count": self.frame_count,
            "next_commands": list(self.next_commands),
            "errors": list(self.errors),
        }


def import_portrait_video_to_source_pack(
    *,
    source_pack_dir: Path | str,
    video_path: Path | str,
    report_path: Path | str | None = None,
    fps: int = DEFAULT_FPS,
    source_tool: str = "AI video",
    replace_frames: bool = False,
    ffmpeg_extractor: FrameExtractor | None = None,
) -> PortraitVideoSourcePackImportReport:
    source_root = Path(source_pack_dir)
    input_video = Path(video_path)
    report_target = Path(report_path) if report_path is not None else source_root / "video_import_report.json"
    metadata, metadata_errors = _read_metadata(source_root / "source_pack.json")
    set_id = _metadata_string(metadata, "set_id")
    frames_rel = _metadata_string(metadata, "frames_dir") or "frames"
    video_rel = _metadata_string(metadata, "video_dir") or "video"
    path_errors = _metadata_path_errors({"frames_dir": frames_rel, "video_dir": video_rel})
    errors = [*metadata_errors, *path_errors]
    frames_dir = source_root / frames_rel
    video_dir = source_root / video_rel
    copied_video = video_dir / input_video.name
    if not input_video.is_file():
        errors.append(f"video file not found: {input_video}")
    if errors:
        return _write_report(
            _report(
                ok=False,
                set_id=set_id,
                source_root=source_root,
                input_video=input_video,
                copied_video=copied_video,
                frames_dir=frames_dir,
                report_path=report_target,
                source_tool=source_tool,
                fps=fps,
                replace_frames=replace_frames,
                frame_count=_frame_count(frames_dir),
                errors=tuple(errors),
            )
        )

    existing_frames = _frame_paths(frames_dir)
    if existing_frames and not replace_frames:
        return _write_report(
            _report(
                ok=False,
                set_id=set_id,
                source_root=source_root,
                input_video=input_video,
                copied_video=copied_video,
                frames_dir=frames_dir,
                report_path=report_target,
                source_tool=source_tool,
                fps=fps,
                replace_frames=replace_frames,
                frame_count=len(existing_frames),
                errors=("frames_dir already contains PNG frames; pass replace_frames=True to overwrite",),
            )
        )

    video_dir.mkdir(parents=True, exist_ok=True)
    if _same_path(input_video, copied_video):
        copied_video = input_video
    else:
        shutil.copy2(input_video, copied_video)
    frames_dir.mkdir(parents=True, exist_ok=True)
    if replace_frames:
        for frame in existing_frames:
            frame.unlink()

    extractor = ffmpeg_extractor or _extract_video_frames
    extraction_error = extractor(copied_video, frames_dir, max(1, int(fps)))
    frame_count = _frame_count(frames_dir)
    if extraction_error:
        errors.append(extraction_error)
    if not extraction_error and frame_count == 0:
        errors.append("no PNG frames extracted")

    return _write_report(
        _report(
            ok=not errors,
            set_id=set_id,
            source_root=source_root,
            input_video=input_video,
            copied_video=copied_video,
            frames_dir=frames_dir,
            report_path=report_target,
            source_tool=source_tool,
            fps=fps,
            replace_frames=replace_frames,
            frame_count=frame_count,
            next_commands=_next_commands(source_root, set_id) if not errors else (),
            errors=tuple(errors),
        )
    )


def _extract_video_frames(video_path: Path, frames_dir: Path, fps: int) -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return "ffmpeg_not_found: install ffmpeg or export PNG frames manually into frames/"
    pattern = frames_dir / "frame_%05d.png"
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"fps={max(1, int(fps))}",
            str(pattern),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        return f"ffmpeg_failed:{result.stderr[-400:]}"
    return ""


def _read_metadata(path: Path) -> tuple[dict[str, object], tuple[str, ...]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, (f"source_pack.json invalid: {exc}",)
    if not isinstance(payload, dict):
        return {}, ("source_pack.json must be an object",)
    errors: list[str] = []
    if not isinstance(payload.get("set_id"), str) or not str(payload.get("set_id")).strip():
        errors.append("source_pack.json.set_id must be a non-empty string")
    return payload, tuple(errors)


def _metadata_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def _metadata_path_errors(paths: dict[str, str]) -> tuple[str, ...]:
    errors: list[str] = []
    for key, value in paths.items():
        path = Path(value)
        if (
            not value
            or path.is_absolute()
            or ".." in path.parts
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
        ):
            errors.append(f"source_pack.json.{key} must be a safe relative path")
    return tuple(errors)


def _frame_paths(frames_dir: Path) -> list[Path]:
    if not frames_dir.is_dir():
        return []
    return sorted(path for path in frames_dir.iterdir() if path.is_file() and path.suffix.lower() == ".png")


def _frame_count(frames_dir: Path) -> int:
    return len(_frame_paths(frames_dir))


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left == right


def _next_commands(source_root: Path, set_id: str) -> tuple[str, ...]:
    escaped_source_root = str(source_root)
    escaped_source_parent = str(source_root.parent)
    return (
        (
            "python tools\\art\\inspect_portrait_video_source_frames.py "
            f"\"{escaped_source_parent}\" --report artifacts\\portrait-video-frame-preflight.json"
        ),
        (
            "python tools\\art\\portrait_video_frame_visual_qa.py "
            f"\"{escaped_source_root}\" --preview artifacts\\portrait-video-frame-qa-{set_id}.png "
            f"--report artifacts\\portrait-video-frame-qa-{set_id}.json"
        ),
        (
            "python tools\\art\\process_portrait_video_source_pack.py "
            f"\"{escaped_source_root}\" --output-dir artifacts\\portrait-candidate-{set_id}-motion"
        ),
    )


def _report(
    *,
    ok: bool,
    set_id: str,
    source_root: Path,
    input_video: Path,
    copied_video: Path,
    frames_dir: Path,
    report_path: Path,
    source_tool: str,
    fps: int,
    replace_frames: bool,
    frame_count: int,
    next_commands: tuple[str, ...] = (),
    errors: tuple[str, ...],
) -> PortraitVideoSourcePackImportReport:
    return PortraitVideoSourcePackImportReport(
        ok=ok,
        set_id=set_id,
        source_pack_dir=str(source_root),
        input_video_path=str(input_video),
        copied_video_path=str(copied_video),
        frames_dir=str(frames_dir),
        report_path=str(report_path),
        source_tool=source_tool.strip() or "AI video",
        fps=max(1, int(fps)),
        replace_frames=replace_frames,
        frame_count=frame_count,
        next_commands=next_commands,
        errors=errors,
    )


def _write_report(report: PortraitVideoSourcePackImportReport) -> PortraitVideoSourcePackImportReport:
    report_path = Path(report.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a downloaded AI video into a portrait video source pack.")
    parser.add_argument("source_pack_dir")
    parser.add_argument("--video", required=True)
    parser.add_argument("--report", default="")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS)
    parser.add_argument("--source-tool", default="AI video")
    parser.add_argument("--replace-frames", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = import_portrait_video_to_source_pack(
        source_pack_dir=args.source_pack_dir,
        video_path=args.video,
        report_path=args.report or None,
        fps=args.fps,
        source_tool=args.source_tool,
        replace_frames=args.replace_frames,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
