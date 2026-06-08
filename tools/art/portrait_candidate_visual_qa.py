from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, UnidentifiedImageError

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.art.validate_portrait_candidates import validate_portrait_candidate


LABEL_HEIGHT = 32
CHECKER_SIZE = 32
BACKGROUND_SPECS = (
    ("checker", None),
    ("light", (246, 247, 250, 255)),
    ("dark", (31, 37, 50, 255)),
)
LIGHT_EDGE_LUMA_THRESHOLD = 220
LIGHT_EDGE_RATIO_WARNING_THRESHOLD = 0.35


@dataclass(frozen=True, slots=True)
class PortraitCandidateVisualQaReport:
    ok: bool
    manifest_path: str
    preview_path: str
    image_count: int
    images: tuple[dict[str, object], ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "manifest_path": self.manifest_path,
            "preview_path": self.preview_path,
            "image_count": self.image_count,
            "images": list(self.images),
            "errors": list(self.errors),
        }


def build_portrait_candidate_visual_qa(
    candidate_manifest_path: Path | str,
    *,
    preview_path: Path | str,
    report_path: Path | str | None = None,
) -> PortraitCandidateVisualQaReport:
    manifest = Path(candidate_manifest_path)
    preview = Path(preview_path)
    errors: list[str] = []
    validation = validate_portrait_candidate(manifest)
    errors.extend(validation.errors)

    image_entries = _manifest_image_entries(manifest, errors) if not errors else []
    image_reports = tuple(_image_metrics(label, path, root=manifest.parent) for label, path in image_entries)
    for image_report in image_reports:
        errors.extend(str(error) for error in image_report.get("errors", []))

    if not errors:
        _write_visual_preview(image_entries, preview)

    report = PortraitCandidateVisualQaReport(
        ok=not errors,
        manifest_path=str(manifest),
        preview_path=str(preview) if not errors else "",
        image_count=len(image_entries),
        images=image_reports,
        errors=tuple(errors),
    )
    if report_path is not None:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _manifest_image_entries(manifest_path: Path, errors: list[str]) -> list[tuple[str, Path]]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"portrait_candidate.json invalid: {exc}")
        return []
    expressions = payload.get("expressions") if isinstance(payload, dict) else None
    if not isinstance(expressions, dict):
        errors.append("expressions must be an object")
        return []

    root = manifest_path.parent
    entries: list[tuple[str, Path]] = []
    for expression, value in expressions.items():
        for frame_name, frame_path in _frame_paths(value):
            label = expression if not frame_name else f"{expression}.{frame_name}"
            resolved = _safe_image_path(root, frame_path)
            if resolved is None:
                errors.append(f"expressions.{label} path must stay inside candidate directory")
                continue
            entries.append((label, resolved))
    return entries


def _frame_paths(value: object) -> Iterable[tuple[str, object]]:
    if isinstance(value, str):
        yield "", value
        return
    if not isinstance(value, dict):
        yield "", value
        return
    yield "open", value.get("open")
    for key in ("blink_half", "blink_closed"):
        if key in value:
            yield key, value.get(key)
    for key, item in value.items():
        if key not in {"open", "blink_half", "blink_closed"}:
            yield str(key), item


def _safe_image_path(root: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".png":
        return None
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def _image_metrics(label: str, path: Path, *, root: Path) -> dict[str, object]:
    errors: list[str] = []
    try:
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
    except (OSError, UnidentifiedImageError) as exc:
        return {"label": label, "path": _relative_report_path(path, root), "errors": [f"image invalid: {exc}"]}

    alpha = rgba.getchannel("A")
    histogram = alpha.histogram()
    alpha_extrema = list(alpha.getextrema())
    transparent_pixels = histogram[0]
    opaque_pixels = histogram[255]
    edge_alpha_pixels = rgba.width * rgba.height - transparent_pixels - opaque_pixels
    light_edge_alpha_pixels = _count_light_edge_alpha_pixels(rgba)
    light_edge_ratio = light_edge_alpha_pixels / edge_alpha_pixels if edge_alpha_pixels else 0.0
    corners = [
        alpha.getpixel((0, 0)),
        alpha.getpixel((rgba.width - 1, 0)),
        alpha.getpixel((0, rgba.height - 1)),
        alpha.getpixel((rgba.width - 1, rgba.height - 1)),
    ]
    bbox = alpha.getbbox()
    warnings = []
    if light_edge_ratio >= LIGHT_EDGE_RATIO_WARNING_THRESHOLD:
        warnings.append("light_edge_halo_risk")
    return {
        "label": label,
        "path": _relative_report_path(path, root),
        "mode": rgba.mode,
        "size": [rgba.width, rgba.height],
        "alpha_extrema": alpha_extrema,
        "transparent_corner_count": sum(1 for value in corners if value == 0),
        "transparent_pixel_count": transparent_pixels,
        "opaque_pixel_count": opaque_pixels,
        "edge_alpha_pixel_count": edge_alpha_pixels,
        "light_edge_alpha_pixel_count": light_edge_alpha_pixels,
        "light_edge_alpha_ratio": round(light_edge_ratio, 4),
        "subject_bbox": list(bbox) if bbox else [],
        "warnings": warnings,
        "errors": errors,
    }


def _count_light_edge_alpha_pixels(image: Image.Image) -> int:
    payload = image.convert("RGBA").tobytes()
    count = 0
    for index in range(0, len(payload), 4):
        alpha = payload[index + 3]
        if alpha == 0 or alpha == 255:
            continue
        red = payload[index]
        green = payload[index + 1]
        blue = payload[index + 2]
        luma = (red * 299 + green * 587 + blue * 114) // 1000
        if luma >= LIGHT_EDGE_LUMA_THRESHOLD:
            count += 1
    return count


def _relative_report_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _write_visual_preview(image_entries: list[tuple[str, Path]], target: Path) -> None:
    frames: list[tuple[str, Image.Image]] = []
    for label, path in image_entries:
        with Image.open(path) as image:
            frames.append((label, image.convert("RGBA")))
    if not frames:
        return

    cell_width = max(frame.width for _, frame in frames)
    image_height = max(frame.height for _, frame in frames)
    row_height = image_height + LABEL_HEIGHT
    sheet = Image.new("RGBA", (cell_width * len(BACKGROUND_SPECS), row_height * len(frames)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sheet)

    for row, (label, frame) in enumerate(frames):
        row_y = row * row_height
        for column, (background_name, color) in enumerate(BACKGROUND_SPECS):
            x = column * cell_width
            background = _background_cell(cell_width, image_height, color)
            paste_x = x + (cell_width - frame.width) // 2
            paste_y = row_y + (image_height - frame.height) // 2
            sheet.alpha_composite(background, (x, row_y))
            sheet.alpha_composite(frame, (paste_x, paste_y))
            draw.rectangle((x, row_y + image_height, x + cell_width, row_y + row_height), fill=(18, 23, 32, 255))
            draw.text((x + 8, row_y + image_height + 8), f"{label} / {background_name}", fill=(255, 255, 255, 255))

    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target)


def _background_cell(width: int, height: int, color: tuple[int, int, int, int] | None) -> Image.Image:
    if color is not None:
        return Image.new("RGBA", (width, height), color)
    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, height, CHECKER_SIZE):
        for x in range(0, width, CHECKER_SIZE):
            fill = (226, 230, 236, 255) if ((x // CHECKER_SIZE) + (y // CHECKER_SIZE)) % 2 else (250, 251, 253, 255)
            draw.rectangle((x, y, x + CHECKER_SIZE - 1, y + CHECKER_SIZE - 1), fill=fill)
    return image


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build visual QA preview and alpha metrics for portrait candidates.")
    parser.add_argument("candidate_manifest")
    parser.add_argument("--preview", required=True)
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = build_portrait_candidate_visual_qa(
        args.candidate_manifest,
        preview_path=args.preview,
        report_path=args.report or None,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
