from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, UnidentifiedImageError

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.art.validate_portrait_candidates import validate_portrait_candidate


DEFAULT_BACKGROUND_TOLERANCE = 42
DEFAULT_EDGE_FEATHER_RADIUS = 1.0


@dataclass(frozen=True, slots=True)
class PortraitCandidatePreparationReport:
    ok: bool
    source_path: str
    output_dir: str
    portrait_path: str
    manifest_path: str
    contact_sheet_path: str
    report_path: str
    background_pixels: int
    visible_pixels: int
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "source_path": self.source_path,
            "output_dir": self.output_dir,
            "portrait_path": self.portrait_path,
            "manifest_path": self.manifest_path,
            "contact_sheet_path": self.contact_sheet_path,
            "report_path": self.report_path,
            "background_pixels": self.background_pixels,
            "visible_pixels": self.visible_pixels,
            "errors": list(self.errors),
        }


def prepare_portrait_candidate(
    source_path: Path | str,
    output_dir: Path | str,
    *,
    expression: str = "neutral",
    background_tolerance: int = DEFAULT_BACKGROUND_TOLERANCE,
    edge_feather_radius: float = DEFAULT_EDGE_FEATHER_RADIUS,
    report_path: Path | str | None = None,
) -> PortraitCandidatePreparationReport:
    source = Path(source_path)
    output = Path(output_dir)
    report_target = Path(report_path) if report_path is not None else None
    errors: list[str] = []

    try:
        with Image.open(source) as image:
            rgba = image.convert("RGBA")
    except (OSError, UnidentifiedImageError) as exc:
        errors.append(f"source image invalid: {exc}")
        return _build_report(
            ok=False,
            source=source,
            output=output,
            portrait_path=Path(),
            manifest_path=Path(),
            contact_sheet_path=Path(),
            report_path=report_target,
            background_pixels=0,
            visible_pixels=0,
            errors=errors,
        )

    processed, background_pixels, visible_pixels = _with_connected_background_alpha(
        rgba,
        tolerance=max(0, min(background_tolerance, 255)),
        edge_feather_radius=max(0.0, edge_feather_radius),
    )

    portraits_dir = output / "portraits"
    preview_dir = output / "preview"
    portrait_path = portraits_dir / f"{_safe_expression_id(expression)}_open.png"
    manifest_path = output / "portrait_candidate.json"
    contact_sheet_path = preview_dir / "portrait-contact-sheet.png"
    report_target = report_target or (output / "candidate-preparation-report.json")

    portraits_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    processed.save(portrait_path)
    _write_candidate_manifest(manifest_path, expression, portrait_path.relative_to(output))

    validation = validate_portrait_candidate(manifest_path, contact_sheet_path=contact_sheet_path)
    errors.extend(validation.errors)

    report = _build_report(
        ok=not errors,
        source=source,
        output=output,
        portrait_path=portrait_path,
        manifest_path=manifest_path,
        contact_sheet_path=contact_sheet_path,
        report_path=report_target,
        background_pixels=background_pixels,
        visible_pixels=visible_pixels,
        errors=errors,
    )
    report_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _with_connected_background_alpha(
    image: Image.Image,
    *,
    tolerance: int,
    edge_feather_radius: float,
) -> tuple[Image.Image, int, int]:
    alpha = image.getchannel("A")
    min_alpha, _ = alpha.getextrema()
    if min_alpha < 255:
        visible_pixels = _count_visible_alpha_pixels(alpha)
        return image.copy(), image.width * image.height - visible_pixels, visible_pixels

    rgb = image.convert("RGB")
    key = _average_border_color(rgb)
    background_mask, background_pixels = _connected_background_mask(rgb, key, tolerance)
    if edge_feather_radius > 0:
        background_mask = background_mask.filter(ImageFilter.GaussianBlur(edge_feather_radius))
    new_alpha = ImageChops.subtract(Image.new("L", image.size, 255), background_mask)
    output = image.copy()
    output.putalpha(new_alpha)
    visible_pixels = _count_visible_alpha_pixels(new_alpha)
    return output, background_pixels, visible_pixels


def _count_visible_alpha_pixels(alpha: Image.Image) -> int:
    histogram = alpha.histogram()
    return alpha.width * alpha.height - histogram[0]


def _average_border_color(image: Image.Image) -> tuple[int, int, int]:
    width, height = image.size
    pixels = image.load()
    samples: list[tuple[int, int, int]] = []
    for x in range(width):
        samples.append(pixels[x, 0])
        samples.append(pixels[x, height - 1])
    for y in range(1, height - 1):
        samples.append(pixels[0, y])
        samples.append(pixels[width - 1, y])
    return tuple(sum(channel) // len(samples) for channel in zip(*samples))


def _connected_background_mask(
    image: Image.Image,
    key: tuple[int, int, int],
    tolerance: int,
) -> tuple[Image.Image, int]:
    width, height = image.size
    pixels = image.load()
    visited = bytearray(width * height)
    mask = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def index_of(x: int, y: int) -> int:
        return y * width + x

    def enqueue_if_background(x: int, y: int) -> None:
        index = index_of(x, y)
        if visited[index]:
            return
        visited[index] = 1
        if _rgb_distance(pixels[x, y], key) <= tolerance:
            mask[index] = 255
            queue.append((x, y))

    for x in range(width):
        enqueue_if_background(x, 0)
        enqueue_if_background(x, height - 1)
    for y in range(1, height - 1):
        enqueue_if_background(0, y)
        enqueue_if_background(width - 1, y)

    while queue:
        x, y = queue.popleft()
        if x > 0:
            enqueue_if_background(x - 1, y)
        if x < width - 1:
            enqueue_if_background(x + 1, y)
        if y > 0:
            enqueue_if_background(x, y - 1)
        if y < height - 1:
            enqueue_if_background(x, y + 1)

    return Image.frombytes("L", image.size, bytes(mask)), sum(1 for value in mask if value)


def _rgb_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    return max(abs(left[index] - right[index]) for index in range(3))


def _safe_expression_id(value: str) -> str:
    cleaned = "".join(char for char in value.lower().strip() if char.isascii() and (char.isalnum() or char == "_"))
    return cleaned or "neutral"


def _write_candidate_manifest(manifest_path: Path, expression: str, portrait_relative_path: Path) -> None:
    payload = {
        "status": "candidate",
        "approval_required": True,
        "runtime_manifest_safe": False,
        "expressions": {
            _safe_expression_id(expression): {
                "open": portrait_relative_path.as_posix(),
            },
        },
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_report(
    *,
    ok: bool,
    source: Path,
    output: Path,
    portrait_path: Path,
    manifest_path: Path,
    contact_sheet_path: Path,
    report_path: Path | None,
    background_pixels: int,
    visible_pixels: int,
    errors: list[str],
) -> PortraitCandidatePreparationReport:
    return PortraitCandidatePreparationReport(
        ok=ok,
        source_path=str(source),
        output_dir=str(output),
        portrait_path=str(portrait_path) if portrait_path else "",
        manifest_path=str(manifest_path) if manifest_path else "",
        contact_sheet_path=str(contact_sheet_path) if contact_sheet_path else "",
        report_path=str(report_path) if report_path is not None else "",
        background_pixels=background_pixels,
        visible_pixels=visible_pixels,
        errors=tuple(errors),
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a local VN portrait candidate pack from a source image.")
    parser.add_argument("source_image")
    parser.add_argument("--output", required=True, help="Ignored candidate directory to write.")
    parser.add_argument("--expression", default="neutral")
    parser.add_argument("--background-tolerance", type=int, default=DEFAULT_BACKGROUND_TOLERANCE)
    parser.add_argument("--edge-feather-radius", type=float, default=DEFAULT_EDGE_FEATHER_RADIUS)
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = prepare_portrait_candidate(
        args.source_image,
        args.output,
        expression=args.expression,
        background_tolerance=args.background_tolerance,
        edge_feather_radius=args.edge_feather_radius,
        report_path=args.report or None,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
