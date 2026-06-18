from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat, UnidentifiedImageError


CELL_WIDTH = 192
CELL_HEIGHT = 208
ALLOWED_DECISIONS = {"candidate", "accepted_for_row_testing", "needs_regeneration", "rejected"}


@dataclass(frozen=True, slots=True)
class PixelPetRowReviewReport:
    ok: bool
    state: str
    expected_frames: int
    actual_frames: int
    extraction_method: str
    decision: str
    asset_boundary: str
    runtime_manifest_updated: bool
    average_frame_delta: float
    median_frame_area: int
    frame_size: dict[str, int]
    frames_root: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    frames: tuple[dict[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "state": self.state,
            "expected_frames": self.expected_frames,
            "actual_frames": self.actual_frames,
            "extraction_method": self.extraction_method,
            "decision": self.decision,
            "asset_boundary": self.asset_boundary,
            "runtime_manifest_updated": self.runtime_manifest_updated,
            "average_frame_delta": self.average_frame_delta,
            "median_frame_area": self.median_frame_area,
            "frame_size": dict(self.frame_size),
            "frames_root": self.frames_root,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "frames": [dict(frame) for frame in self.frames],
        }


def review_pixel_pet_row_candidate(
    *,
    frames_root: Path | str,
    state: str,
    expected_frames: int,
    decision: str = "candidate",
    require_components: bool = False,
    min_used_pixels: int = 400,
    min_average_delta: float = 8.0,
    edge_margin: int = 2,
    edge_pixel_threshold: int = 24,
    report_path: Path | str | None = None,
    markdown_path: Path | str | None = None,
    preview_path: Path | str | None = None,
) -> PixelPetRowReviewReport:
    root = Path(frames_root)
    errors: list[str] = []
    warnings: list[str] = []

    if decision not in ALLOWED_DECISIONS:
        errors.append("decision must be one of: accepted_for_row_testing, candidate, needs_regeneration, rejected")
    if expected_frames < 1:
        errors.append("expected_frames must be at least 1")

    manifest = _load_manifest(root, errors)
    method = _row_extraction_method(manifest, state)
    if require_components and method and method != "components":
        errors.append(f"{state} used extraction method {method}; component extraction is required")
    elif method and method != "components":
        warnings.append(f"{state} used extraction method {method}; component extraction is preferred")

    frame_files = _frame_files(root / state)
    if len(frame_files) != expected_frames:
        errors.append(f"expected {expected_frames} frames for {state}, found {len(frame_files)}")

    frames, average_delta, median_area = _inspect_frames(
        frame_files[:expected_frames],
        errors,
        warnings,
        min_used_pixels=min_used_pixels,
        min_average_delta=min_average_delta,
        edge_margin=edge_margin,
        edge_pixel_threshold=edge_pixel_threshold,
    )

    report = PixelPetRowReviewReport(
        ok=not errors,
        state=state,
        expected_frames=expected_frames,
        actual_frames=len(frame_files),
        extraction_method=method,
        decision=decision,
        asset_boundary="ignored_candidate_only",
        runtime_manifest_updated=False,
        average_frame_delta=round(average_delta, 4),
        median_frame_area=median_area,
        frame_size={"width": CELL_WIDTH, "height": CELL_HEIGHT},
        frames_root=str(root),
        errors=tuple(errors),
        warnings=tuple(warnings),
        frames=tuple(frames),
    )

    if report_path:
        _write_json_report(Path(report_path), report)
    if markdown_path:
        _write_markdown_report(Path(markdown_path), report)
    if preview_path:
        _write_preview(Path(preview_path), report, frame_files[:expected_frames])
    return report


def _load_manifest(root: Path, errors: list[str]) -> dict[str, object]:
    path = root / "frames-manifest.json"
    if not path.is_file():
        errors.append("frames-manifest.json not found")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"frames-manifest.json invalid: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append("frames-manifest.json must be a JSON object")
        return {}
    return payload


def _row_extraction_method(manifest: dict[str, object], state: str) -> str:
    rows = manifest.get("rows")
    if not isinstance(rows, list):
        return ""
    for row in rows:
        if isinstance(row, dict) and row.get("state") == state:
            method = row.get("method")
            return method if isinstance(method, str) else ""
    return ""


def _frame_files(state_dir: Path) -> list[Path]:
    if not state_dir.is_dir():
        return []
    return sorted(path for path in state_dir.iterdir() if path.suffix.lower() in {".png", ".webp"})


def _inspect_frames(
    frame_files: list[Path],
    errors: list[str],
    warnings: list[str],
    *,
    min_used_pixels: int,
    min_average_delta: float,
    edge_margin: int,
    edge_pixel_threshold: int,
) -> tuple[list[dict[str, object]], float, int]:
    frames: list[dict[str, object]] = []
    areas: list[int] = []
    delta_values: list[float] = []
    previous: Image.Image | None = None

    for index, path in enumerate(frame_files):
        try:
            with Image.open(path) as image:
                frame = image.convert("RGBA")
        except (OSError, UnidentifiedImageError) as exc:
            errors.append(f"frame {index:02d} invalid: {exc}")
            continue

        alpha_count = _alpha_nonzero_count(frame)
        edge_pixels = _edge_alpha_count(frame, edge_margin)
        bbox = frame.getbbox()
        if frame.size != (CELL_WIDTH, CELL_HEIGHT):
            errors.append(
                f"frame {index:02d} is {frame.width}x{frame.height}; expected {CELL_WIDTH}x{CELL_HEIGHT}"
            )
        if alpha_count < min_used_pixels:
            errors.append(f"frame {index:02d} is empty or too sparse ({alpha_count} pixels)")
        if edge_pixels > edge_pixel_threshold:
            warnings.append(f"frame {index:02d} has {edge_pixels} non-transparent pixels near the cell edge")
        if previous is not None:
            delta_values.append(_frame_delta(previous, frame))
        previous = frame
        areas.append(alpha_count)
        frames.append(
            {
                "index": index,
                "file": str(path),
                "width": frame.width,
                "height": frame.height,
                "nontransparent_pixels": alpha_count,
                "bbox": list(bbox) if bbox else None,
                "edge_pixels": edge_pixels,
            }
        )

    average_delta = mean(delta_values) if delta_values else 0.0
    if len(frame_files) > 1 and average_delta < min_average_delta:
        warnings.append(
            f"average frame delta is low ({average_delta:.2f}); visual motion may be too subtle"
        )
    median_area = int(median(areas)) if areas else 0
    return frames, average_delta, median_area


def _alpha_nonzero_count(image: Image.Image) -> int:
    alpha = image if image.mode == "L" else image.getchannel("A")
    return sum(alpha.histogram()[1:])


def _edge_alpha_count(image: Image.Image, margin: int) -> int:
    alpha = image.getchannel("A")
    width, height = alpha.size
    return sum(
        _alpha_nonzero_count(alpha.crop(box))
        for box in (
            (0, 0, width, margin),
            (0, height - margin, width, height),
            (0, 0, margin, height),
            (width - margin, 0, width, height),
        )
    )


def _frame_delta(left: Image.Image, right: Image.Image) -> float:
    diff = ImageChops.difference(left, right).convert("L")
    return float(ImageStat.Stat(diff).mean[0])


def _write_json_report(path: Path, report: PixelPetRowReviewReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_markdown_report(path: Path, report: PixelPetRowReviewReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Pixel Pet Row Review",
        "",
        f"- State: `{report.state}`",
        f"- Decision: `{report.decision}`",
        f"- OK: `{'yes' if report.ok else 'no'}`",
        f"- Extraction method: `{report.extraction_method or 'unknown'}`",
        f"- Frames: `{report.actual_frames}/{report.expected_frames}`",
        f"- Average frame delta: `{report.average_frame_delta}`",
        f"- Median frame area: `{report.median_frame_area}`",
        f"- Asset boundary: `{report.asset_boundary}`",
        f"- Runtime manifest updated: `{'yes' if report.runtime_manifest_updated else 'no'}`",
    ]
    if report.errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{error}`" for error in report.errors)
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in report.warnings)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_preview(path: Path, report: PixelPetRowReviewReport, frame_files: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = max(1, len(frame_files))
    cell_width = CELL_WIDTH
    label_height = 80
    sheet = Image.new("RGBA", (columns * cell_width, CELL_HEIGHT + label_height), (245, 245, 245, 255))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    for index, frame_path in enumerate(frame_files):
        x = index * cell_width
        try:
            with Image.open(frame_path) as image:
                frame = image.convert("RGBA")
            checker = _checkerboard((CELL_WIDTH, CELL_HEIGHT))
            checker.alpha_composite(frame)
            sheet.alpha_composite(checker, (x, 0))
        except (OSError, UnidentifiedImageError):
            pass
        draw.rectangle((x, CELL_HEIGHT, x + cell_width, CELL_HEIGHT + label_height), fill=(30, 35, 42, 255))
        draw.text((x + 8, CELL_HEIGHT + 8), f"{report.state} {index:02d}", fill=(255, 255, 255, 255), font=font)
        if index < len(report.frames):
            area = report.frames[index].get("nontransparent_pixels", 0)
            draw.text((x + 8, CELL_HEIGHT + 30), f"area {area}", fill=(230, 235, 240, 255), font=font)
    sheet.save(path)


def _checkerboard(size: tuple[int, int]) -> Image.Image:
    width, height = size
    tile = 16
    image = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, height, tile):
        for x in range(0, width, tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle((x, y, min(width, x + tile), min(height, y + tile)), fill=(220, 225, 230, 255))
    return image


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review extracted frames for a single pixel-pet row candidate.")
    parser.add_argument("frames_root")
    parser.add_argument("--state", required=True)
    parser.add_argument("--expected-frames", required=True, type=int)
    parser.add_argument("--decision", default="candidate", choices=sorted(ALLOWED_DECISIONS))
    parser.add_argument("--require-components", action="store_true")
    parser.add_argument("--min-average-delta", type=float, default=8.0)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--report", default="")
    parser.add_argument("--markdown", default="")
    parser.add_argument("--preview", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    output_dir = Path(args.output_dir) if args.output_dir else None
    report_path = Path(args.report) if args.report else (output_dir / f"{args.state}-row-review.json" if output_dir else None)
    markdown_path = Path(args.markdown) if args.markdown else (output_dir / f"{args.state}-row-review.md" if output_dir else None)
    preview_path = Path(args.preview) if args.preview else (output_dir / f"{args.state}-row-review.png" if output_dir else None)
    report = review_pixel_pet_row_candidate(
        frames_root=Path(args.frames_root),
        state=args.state,
        expected_frames=args.expected_frames,
        decision=args.decision,
        require_components=args.require_components,
        min_average_delta=args.min_average_delta,
        report_path=report_path,
        markdown_path=markdown_path,
        preview_path=preview_path,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
