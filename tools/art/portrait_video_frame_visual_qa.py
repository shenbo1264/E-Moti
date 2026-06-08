from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat, UnidentifiedImageError


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.art.inspect_portrait_video_source_frames import inspect_portrait_video_source_frames


DEFAULT_MAX_FRAMES = 12
THUMBNAIL_SIZE = (180, 300)
LABEL_HEIGHT = 48
PADDING = 12


@dataclass(frozen=True, slots=True)
class PortraitVideoFrameVisualQaReport:
    ok: bool
    source_pack_dir: str
    set_id: str
    status: str
    next_action: str
    preview_path: str
    reference_image: str
    reference_size: tuple[int, int] | tuple[()]
    frame_count: int
    sampled_frame_count: int
    size_mismatch_count: int
    max_body_drift: float
    frames: tuple[dict[str, object], ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "source_pack_dir": self.source_pack_dir,
            "set_id": self.set_id,
            "status": self.status,
            "next_action": self.next_action,
            "preview_path": self.preview_path,
            "reference_image": self.reference_image,
            "reference_size": list(self.reference_size),
            "frame_count": self.frame_count,
            "sampled_frame_count": self.sampled_frame_count,
            "size_mismatch_count": self.size_mismatch_count,
            "max_body_drift": self.max_body_drift,
            "frames": list(self.frames),
            "errors": list(self.errors),
        }


def build_portrait_video_frame_visual_qa(
    source_pack_dir: Path | str,
    *,
    preview_path: Path | str,
    report_path: Path | str | None = None,
    max_frames: int = DEFAULT_MAX_FRAMES,
) -> PortraitVideoFrameVisualQaReport:
    source_pack = Path(source_pack_dir)
    preview = Path(preview_path)
    errors: list[str] = []
    if not (source_pack / "source_pack.json").is_file():
        report = _error_report(source_pack, preview, errors=("source_pack.json not found",))
        _write_report(report, report_path)
        return report

    preflight = inspect_portrait_video_source_frames(source_root=source_pack.parent)
    item = next((entry for entry in preflight.items if Path(entry.source_pack_dir).resolve() == source_pack.resolve()), None)
    if item is None:
        report = _error_report(source_pack, preview, errors=("source pack not found in frame preflight",))
        _write_report(report, report_path)
        return report

    reference = Path(item.reference_image)
    reference_image = _load_rgba(reference)
    if reference_image is None:
        errors.append("reference image invalid or missing")
    frame_paths = _sample_paths(_frame_paths(Path(item.frames_dir)), max_frames=max_frames)
    frame_reports = tuple(_frame_report(path, reference_image=reference_image, reference_size=reference_image.size if reference_image else None) for path in frame_paths)
    errors.extend(str(error) for frame in frame_reports for error in frame.get("errors", []))
    if reference_image is not None and not errors:
        _write_preview(reference_image, frame_reports, preview)

    max_body_drift = max((float(frame["body_drift"]) for frame in frame_reports if frame.get("body_drift") is not None), default=0.0)
    report = PortraitVideoFrameVisualQaReport(
        ok=not errors,
        source_pack_dir=str(source_pack),
        set_id=item.set_id,
        status=item.status,
        next_action=item.next_action,
        preview_path=str(preview) if not errors else "",
        reference_image=str(reference),
        reference_size=reference_image.size if reference_image is not None else (),
        frame_count=item.frame_count,
        sampled_frame_count=len(frame_reports),
        size_mismatch_count=item.size_mismatch_count,
        max_body_drift=round(max_body_drift, 2),
        frames=frame_reports,
        errors=tuple(errors),
    )
    _write_report(report, report_path)
    return report


def _error_report(
    source_pack: Path,
    preview: Path,
    *,
    errors: tuple[str, ...],
) -> PortraitVideoFrameVisualQaReport:
    return PortraitVideoFrameVisualQaReport(
        ok=False,
        source_pack_dir=str(source_pack),
        set_id=source_pack.name,
        status="invalid_source_pack",
        next_action="fix_source_pack",
        preview_path="",
        reference_image="",
        reference_size=(),
        frame_count=0,
        sampled_frame_count=0,
        size_mismatch_count=0,
        max_body_drift=0.0,
        frames=(),
        errors=errors,
    )


def _frame_paths(frames_dir: Path) -> tuple[Path, ...]:
    if not frames_dir.is_dir():
        return ()
    return tuple(sorted(path for path in frames_dir.iterdir() if path.is_file() and path.suffix.lower() == ".png"))


def _sample_paths(paths: tuple[Path, ...], *, max_frames: int) -> tuple[Path, ...]:
    if max_frames <= 0 or len(paths) <= max_frames:
        return paths
    if max_frames == 1:
        return (paths[0],)
    last = len(paths) - 1
    indexes = sorted({int(index * last / (max_frames - 1)) for index in range(max_frames)})
    return tuple(paths[index] for index in indexes)


def _frame_report(
    frame_path: Path,
    *,
    reference_image: Image.Image | None,
    reference_size: tuple[int, int] | None,
) -> dict[str, object]:
    errors: list[str] = []
    frame = _load_rgba(frame_path)
    if frame is None:
        return {"path": str(frame_path), "size": [], "body_drift": None, "errors": ["frame is not readable"]}
    body_drift: float | None = None
    if reference_image is not None and reference_size == frame.size:
        body_drift = round(_body_drift(reference_image, frame), 2)
    return {
        "path": str(frame_path),
        "size": [frame.width, frame.height],
        "body_drift": body_drift,
        "errors": errors,
    }


def _load_rgba(path: Path) -> Image.Image | None:
    try:
        with Image.open(path) as image:
            loaded = image.convert("RGBA")
            loaded.load()
            return loaded
    except (OSError, UnidentifiedImageError):
        return None


def _body_drift(reference: Image.Image, frame: Image.Image) -> float:
    alpha = reference.getchannel("A")
    if alpha.getbbox() is None:
        return 0.0
    diff = ImageChops.difference(reference.convert("RGB"), frame.convert("RGB"))
    stat = ImageStat.Stat(diff, alpha)
    return sum(stat.mean) / 3.0


def _write_preview(reference: Image.Image, frames: tuple[dict[str, object], ...], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[str, Image.Image]] = [("reference", reference)]
    for index, frame in enumerate(frames, start=1):
        image = _load_rgba(Path(str(frame["path"])))
        if image is None:
            continue
        drift = frame.get("body_drift")
        label = f"{index}: drift {drift}" if drift is not None else f"{index}: size {'x'.join(map(str, frame['size']))}"
        entries.append((label, image))
    if not entries:
        return

    cell_width = THUMBNAIL_SIZE[0] + PADDING * 2
    cell_height = THUMBNAIL_SIZE[1] + LABEL_HEIGHT + PADDING * 2
    sheet = Image.new("RGBA", (cell_width * len(entries), cell_height), (245, 247, 250, 255))
    draw = ImageDraw.Draw(sheet)
    for column, (label, image) in enumerate(entries):
        thumbnail = image.copy()
        thumbnail.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        left = column * cell_width + (cell_width - thumbnail.width) // 2
        top = PADDING
        sheet.alpha_composite(thumbnail, (left, top))
        draw.text((column * cell_width + PADDING, THUMBNAIL_SIZE[1] + PADDING), label[:28], fill=(32, 37, 48, 255))
    sheet.save(target)


def _write_report(report: PortraitVideoFrameVisualQaReport, report_path: Path | str | None) -> None:
    if report_path is None:
        return
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a visual QA sheet for one portrait AI-video frame source pack.")
    parser.add_argument("source_pack_dir")
    parser.add_argument("--preview", required=True)
    parser.add_argument("--report", default="")
    parser.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = build_portrait_video_frame_visual_qa(
        args.source_pack_dir,
        preview_path=args.preview,
        report_path=args.report or None,
        max_frames=args.max_frames,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
