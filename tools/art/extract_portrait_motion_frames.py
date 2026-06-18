from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageChops, ImageStat, UnidentifiedImageError

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.art.validate_portrait_candidates import validate_portrait_candidate


DEFAULT_EYE_BOXES = (
    (0.425, 0.155, 0.492, 0.205),
    (0.528, 0.155, 0.595, 0.205),
)
DEFAULT_MAX_BODY_DRIFT = 16.0
DEFAULT_IDLE_FRAME_COUNT = 12
DEFAULT_VIDEO_FPS = 12


@dataclass(frozen=True, slots=True)
class FrameScore:
    name: str
    path: str
    eye_delta: float
    body_delta: float
    accepted: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": self.path,
            "eye_delta": round(self.eye_delta, 4),
            "body_delta": round(self.body_delta, 4),
            "accepted": self.accepted,
        }


@dataclass(frozen=True, slots=True)
class PortraitMotionFrameExtractionReport:
    ok: bool
    reference_image: str
    frames_dir: str
    video_path: str
    output_dir: str
    manifest_path: str
    report_path: str
    provenance_path: str
    selected_open_frame: str
    selected_blink_half_frame: str
    selected_blink_closed_frame: str
    frame_count: int
    accepted_frame_count: int
    rejected_frame_count: int
    generated_frames: tuple[str, ...]
    motion_frames: tuple[str, ...]
    frame_scores: tuple[FrameScore, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "reference_image": self.reference_image,
            "frames_dir": self.frames_dir,
            "video_path": self.video_path,
            "output_dir": self.output_dir,
            "manifest_path": self.manifest_path,
            "report_path": self.report_path,
            "provenance_path": self.provenance_path,
            "selected_open_frame": self.selected_open_frame,
            "selected_blink_half_frame": self.selected_blink_half_frame,
            "selected_blink_closed_frame": self.selected_blink_closed_frame,
            "frame_count": self.frame_count,
            "accepted_frame_count": self.accepted_frame_count,
            "rejected_frame_count": self.rejected_frame_count,
            "generated_frames": list(self.generated_frames),
            "motion_frames": list(self.motion_frames),
            "frame_scores": [score.to_dict() for score in self.frame_scores],
            "errors": list(self.errors),
        }


def extract_portrait_motion_frames(
    *,
    reference_image_path: Path | str,
    output_dir: Path | str,
    frames_dir: Path | str | None = None,
    video_path: Path | str | None = None,
    report_path: Path | str | None = None,
    idle_frame_count: int = DEFAULT_IDLE_FRAME_COUNT,
    max_body_drift: float = DEFAULT_MAX_BODY_DRIFT,
    video_fps: int = DEFAULT_VIDEO_FPS,
    source_tool: str = "",
    generation_prompt: str = "",
    eye_boxes: tuple[tuple[float, float, float, float], ...] = DEFAULT_EYE_BOXES,
) -> PortraitMotionFrameExtractionReport:
    reference_path = Path(reference_image_path)
    output = Path(output_dir)
    report_target = Path(report_path) if report_path is not None else output / "candidate-motion-frame-report.json"
    source_frames_dir = Path(frames_dir) if frames_dir is not None else None
    source_video = Path(video_path) if video_path is not None else None
    if (source_frames_dir is None) == (source_video is None):
        return _write_report(
            _empty_report(
                ok=False,
                reference_path=reference_path,
                frames_dir=source_frames_dir,
                video_path=source_video,
                output=output,
                report_path=report_target,
                errors=("provide exactly one of frames_dir or video_path",),
            )
        )

    try:
        with Image.open(reference_path) as image:
            reference = image.convert("RGBA")
    except (OSError, UnidentifiedImageError) as exc:
        return _write_report(
            _empty_report(
                ok=False,
                reference_path=reference_path,
                frames_dir=source_frames_dir,
                video_path=source_video,
                output=output,
                report_path=report_target,
                errors=(f"reference image invalid: {exc}",),
            )
        )

    if source_frames_dir is not None:
        return _extract_from_frames_dir(
            reference=reference,
            reference_path=reference_path,
            frames_dir=source_frames_dir,
            video_path=source_video,
            output=output,
            report_path=report_target,
            idle_frame_count=idle_frame_count,
            max_body_drift=max_body_drift,
            eye_boxes=eye_boxes,
            source_tool=source_tool,
            generation_prompt=generation_prompt,
        )

    with TemporaryDirectory() as tmp:
        extracted_dir = Path(tmp) / "frames"
        ffmpeg_error = _extract_video_frames(source_video, extracted_dir, video_fps=video_fps)
        if ffmpeg_error:
            return _write_report(
                _empty_report(
                    ok=False,
                    reference_path=reference_path,
                    frames_dir=extracted_dir,
                    video_path=source_video,
                    output=output,
                    report_path=report_target,
                    errors=(ffmpeg_error,),
                )
            )
        return _extract_from_frames_dir(
            reference=reference,
            reference_path=reference_path,
            frames_dir=extracted_dir,
            video_path=source_video,
            output=output,
            report_path=report_target,
            idle_frame_count=idle_frame_count,
            max_body_drift=max_body_drift,
            eye_boxes=eye_boxes,
            source_tool=source_tool,
            generation_prompt=generation_prompt,
        )


def _extract_from_frames_dir(
    *,
    reference: Image.Image,
    reference_path: Path,
    frames_dir: Path,
    video_path: Path | None,
    output: Path,
    report_path: Path,
    idle_frame_count: int,
    max_body_drift: float,
    eye_boxes: tuple[tuple[float, float, float, float], ...],
    source_tool: str,
    generation_prompt: str,
) -> PortraitMotionFrameExtractionReport:
    errors: list[str] = []
    frame_paths = _frame_paths(frames_dir)
    if not frame_paths:
        errors.append("no png frames found")
        return _write_report(
            _empty_report(
                ok=False,
                reference_path=reference_path,
                frames_dir=frames_dir,
                video_path=video_path,
                output=output,
                report_path=report_path,
                errors=tuple(errors),
            )
        )

    masks = _analysis_masks(reference, eye_boxes)
    scores: list[FrameScore] = []
    frame_images: dict[str, Image.Image] = {}
    for frame_path in frame_paths:
        try:
            with Image.open(frame_path) as image:
                frame = image.convert("RGBA")
        except (OSError, UnidentifiedImageError):
            continue
        normalized = _normalize_frame_to_reference(frame, reference)
        name = frame_path.name
        eye_delta = _masked_mean_delta(reference, normalized, masks["eye"])
        body_delta = _masked_mean_delta(reference, normalized, masks["body"])
        accepted = body_delta <= max_body_drift
        scores.append(
            FrameScore(
                name=name,
                path=str(frame_path),
                eye_delta=eye_delta,
                body_delta=body_delta,
                accepted=accepted,
            )
        )
        frame_images[name] = normalized

    accepted_scores = [score for score in scores if score.accepted]
    if len(accepted_scores) < 2:
        errors.append("not enough stable frames after body drift filtering")
        return _write_report(
            _empty_report(
                ok=False,
                reference_path=reference_path,
                frames_dir=frames_dir,
                video_path=video_path,
                output=output,
                report_path=report_path,
                scores=tuple(scores),
                errors=tuple(errors),
            )
        )

    half, closed = _select_blink_frames(accepted_scores)
    generated_frames = (
        "portraits/neutral_open.png",
        "portraits/neutral_blink_half.png",
        "portraits/neutral_blink_closed.png",
    )
    motion_frames = _write_candidate_outputs(
        reference=reference,
        half_frame=frame_images[half.name],
        closed_frame=frame_images[closed.name],
        accepted_scores=accepted_scores,
        frame_images=frame_images,
        output=output,
        generated_frames=generated_frames,
        idle_frame_count=max(0, int(idle_frame_count)),
        provenance_path=Path("portrait_video_provenance.md"),
    )
    provenance_path = output / "portrait_video_provenance.md"
    _write_provenance(
        provenance_path,
        source_tool=source_tool,
        generation_prompt=generation_prompt,
        reference_path=reference_path,
        frames_dir=frames_dir,
        video_path=video_path,
        half_frame=half.name,
        closed_frame=closed.name,
        motion_frames=motion_frames,
    )
    validation = validate_portrait_candidate(output / "portrait_candidate.json")
    errors.extend(validation.errors)
    report = PortraitMotionFrameExtractionReport(
        ok=not errors,
        reference_image=str(reference_path),
        frames_dir=str(frames_dir),
        video_path=str(video_path) if video_path is not None else "",
        output_dir=str(output),
        manifest_path=str(output / "portrait_candidate.json"),
        report_path=str(report_path),
        provenance_path=str(provenance_path),
        selected_open_frame="reference",
        selected_blink_half_frame=half.name,
        selected_blink_closed_frame=closed.name,
        frame_count=len(scores),
        accepted_frame_count=len(accepted_scores),
        rejected_frame_count=len(scores) - len(accepted_scores),
        generated_frames=generated_frames,
        motion_frames=motion_frames,
        frame_scores=tuple(scores),
        errors=tuple(errors),
    )
    return _write_report(report)


def _frame_paths(frames_dir: Path) -> list[Path]:
    if not frames_dir.is_dir():
        return []
    return sorted(path for path in frames_dir.iterdir() if path.is_file() and path.suffix.lower() == ".png")


def _extract_video_frames(video_path: Path | None, output_dir: Path, *, video_fps: int) -> str:
    if video_path is None:
        return "video_path missing"
    if not video_path.is_file():
        return "video file not found"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return "ffmpeg_not_found: install ffmpeg or export PNG frames and use --frames-dir"
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "frame_%05d.png"
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"fps={max(1, int(video_fps))}",
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


def _analysis_masks(reference: Image.Image, eye_boxes: tuple[tuple[float, float, float, float], ...]) -> dict[str, Image.Image]:
    alpha = reference.getchannel("A")
    eye = Image.new("L", reference.size, 0)
    for box in eye_boxes:
        x1, y1, x2, y2 = _absolute_box(reference.size, box)
        region = Image.new("L", reference.size, 0)
        region.paste(255, (x1, y1, x2, y2))
        eye = ImageChops.lighter(eye, region)
    eye = ImageChops.multiply(eye, alpha)
    body = ImageChops.subtract(alpha, eye)
    return {"eye": eye, "body": body}


def _absolute_box(size: tuple[int, int], box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    width, height = size
    x1, y1, x2, y2 = box
    return (
        max(0, min(width, int(round(width * x1)))),
        max(0, min(height, int(round(height * y1)))),
        max(0, min(width, int(round(width * x2)))),
        max(0, min(height, int(round(height * y2)))),
    )


def _normalize_frame_to_reference(frame: Image.Image, reference: Image.Image) -> Image.Image:
    if frame.size != reference.size:
        frame = frame.resize(reference.size, Image.Resampling.LANCZOS)
    rgb = frame.convert("RGB")
    normalized = Image.new("RGBA", reference.size, (0, 0, 0, 0))
    normalized.paste(rgb.convert("RGBA"), (0, 0))
    normalized.putalpha(reference.getchannel("A"))
    return normalized


def _masked_mean_delta(reference: Image.Image, frame: Image.Image, mask: Image.Image) -> float:
    bbox = mask.getbbox()
    if bbox is None:
        return 0.0
    diff = ImageChops.difference(reference.convert("RGB"), frame.convert("RGB"))
    stat = ImageStat.Stat(diff, mask)
    return sum(stat.mean) / 3.0


def _select_blink_frames(accepted_scores: list[FrameScore]) -> tuple[FrameScore, FrameScore]:
    peak_index, peak = max(enumerate(accepted_scores), key=lambda item: item[1].eye_delta)
    if peak_index + 1 < len(accepted_scores):
        next_score = accepted_scores[peak_index + 1]
        if next_score.eye_delta >= peak.eye_delta * 0.75:
            return peak, next_score
    return _select_half_blink_frame(accepted_scores, peak), peak


def _select_half_blink_frame(accepted_scores: list[FrameScore], closed: FrameScore) -> FrameScore:
    candidates = [score for score in accepted_scores if score.name != closed.name]
    if not candidates:
        return closed
    low = min(score.eye_delta for score in candidates)
    target = (low + closed.eye_delta) / 2.0
    return min(candidates, key=lambda score: abs(score.eye_delta - target))


def _write_candidate_outputs(
    *,
    reference: Image.Image,
    half_frame: Image.Image,
    closed_frame: Image.Image,
    accepted_scores: list[FrameScore],
    frame_images: dict[str, Image.Image],
    output: Path,
    generated_frames: tuple[str, str, str],
    idle_frame_count: int,
    provenance_path: Path,
) -> tuple[str, ...]:
    portraits = output / "portraits"
    motion_dir = output / "motion_frames"
    portraits.mkdir(parents=True, exist_ok=True)
    motion_dir.mkdir(parents=True, exist_ok=True)
    reference.save(output / generated_frames[0])
    half_frame.save(output / generated_frames[1])
    closed_frame.save(output / generated_frames[2])

    idle_source = accepted_scores[:idle_frame_count]
    motion_frames: list[str] = []
    for index, score in enumerate(idle_source, 1):
        relative = f"motion_frames/idle_{index:04d}.png"
        frame_images[score.name].save(output / relative)
        motion_frames.append(relative)

    payload = {
        "status": "candidate",
        "approval_required": True,
        "runtime_manifest_safe": False,
        "source": "ai_video_frame_extraction",
        "provenance": provenance_path.as_posix(),
        "expressions": {
            "neutral": {
                "open": generated_frames[0],
                "blink_half": generated_frames[1],
                "blink_closed": generated_frames[2],
            },
        },
        "motion_frames": motion_frames,
    }
    (output / "portrait_candidate.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return tuple(motion_frames)


def _write_provenance(
    target: Path,
    *,
    source_tool: str,
    generation_prompt: str,
    reference_path: Path,
    frames_dir: Path,
    video_path: Path | None,
    half_frame: str,
    closed_frame: str,
    motion_frames: tuple[str, ...],
) -> None:
    lines = [
        "# Portrait Video Provenance",
        "",
        f"- Source tool: {_markdown_value(source_tool) or 'unspecified'}",
        f"- Reference image: `{reference_path}`",
        f"- Exported frames directory: `{frames_dir}`",
        f"- Source video: `{video_path}`" if video_path is not None else "- Source video: `not recorded`",
        f"- Selected blink half frame: `{half_frame}`",
        f"- Selected blink closed frame: `{closed_frame}`",
        f"- Idle frame count: `{len(motion_frames)}`",
        "",
        "## Generation Prompt",
        "",
        _markdown_value(generation_prompt) or "Not recorded.",
        "",
        "## QA Note",
        "",
        "This is a local review candidate generated from AI video frames. Do not promote it to a runtime manifest without human visual QA, provenance approval, and the strict portrait promotion gate.",
        "",
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")


def _markdown_value(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def _empty_report(
    *,
    ok: bool,
    reference_path: Path,
    frames_dir: Path | None,
    video_path: Path | None,
    output: Path,
    report_path: Path,
    scores: tuple[FrameScore, ...] = (),
    errors: tuple[str, ...],
) -> PortraitMotionFrameExtractionReport:
    return PortraitMotionFrameExtractionReport(
        ok=ok,
        reference_image=str(reference_path),
        frames_dir=str(frames_dir) if frames_dir is not None else "",
        video_path=str(video_path) if video_path is not None else "",
        output_dir=str(output),
        manifest_path="",
        report_path=str(report_path),
        provenance_path="",
        selected_open_frame="",
        selected_blink_half_frame="",
        selected_blink_closed_frame="",
        frame_count=len(scores),
        accepted_frame_count=sum(1 for score in scores if score.accepted),
        rejected_frame_count=sum(1 for score in scores if not score.accepted),
        generated_frames=(),
        motion_frames=(),
        frame_scores=scores,
        errors=errors,
    )


def _write_report(report: PortraitMotionFrameExtractionReport) -> PortraitMotionFrameExtractionReport:
    report_path = Path(report.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract blink and idle candidate frames from AI video frames.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--frames-dir", default="")
    source.add_argument("--video", default="")
    parser.add_argument("--reference-image", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report", default="")
    parser.add_argument("--idle-frame-count", type=int, default=DEFAULT_IDLE_FRAME_COUNT)
    parser.add_argument("--max-body-drift", type=float, default=DEFAULT_MAX_BODY_DRIFT)
    parser.add_argument("--video-fps", type=int, default=DEFAULT_VIDEO_FPS)
    parser.add_argument("--source-tool", default="")
    parser.add_argument("--generation-prompt", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = extract_portrait_motion_frames(
        reference_image_path=args.reference_image,
        frames_dir=args.frames_dir or None,
        video_path=args.video or None,
        output_dir=args.output_dir,
        report_path=args.report or None,
        idle_frame_count=args.idle_frame_count,
        max_body_drift=args.max_body_drift,
        video_fps=args.video_fps,
        source_tool=args.source_tool,
        generation_prompt=args.generation_prompt,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
