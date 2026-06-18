from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, UnidentifiedImageError


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.art.validate_companion_atlas import validate_atlas


TRANSPARENT_ALPHA = 0
VISIBLE_ALPHA_THRESHOLD = 16
SUSPICIOUS_EDGE_HALO_RATIO_WARNING_THRESHOLD = 0.015
SUSPICIOUS_EDGE_HALO_PIXEL_WARNING_THRESHOLD = 48


@dataclass(frozen=True, slots=True)
class PixelPetVisualQaReport:
    ok: bool
    status: str
    spritesheet_path: str
    motion_manifest_path: str
    width: int
    height: int
    mode: str
    visible_pixel_count: int
    edge_pixel_count: int
    suspicious_edge_halo_pixel_count: int
    suspicious_edge_halo_ratio: float
    preview_path: str
    warnings: tuple[str, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "status": self.status,
            "spritesheet_path": self.spritesheet_path,
            "motion_manifest_path": self.motion_manifest_path,
            "width": self.width,
            "height": self.height,
            "mode": self.mode,
            "visible_pixel_count": self.visible_pixel_count,
            "edge_pixel_count": self.edge_pixel_count,
            "suspicious_edge_halo_pixel_count": self.suspicious_edge_halo_pixel_count,
            "suspicious_edge_halo_ratio": self.suspicious_edge_halo_ratio,
            "preview_path": self.preview_path,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def inspect_pixel_pet_visual_qa(
    spritesheet_path: Path | str,
    motion_manifest_path: Path | str,
    *,
    report_path: Path | str | None = None,
    preview_path: Path | str | None = None,
) -> PixelPetVisualQaReport:
    spritesheet = Path(spritesheet_path)
    manifest = Path(motion_manifest_path)
    errors: list[str] = []
    warnings: list[str] = []

    atlas_report = validate_atlas(spritesheet, manifest)
    errors.extend(atlas_report.errors)

    width = atlas_report.width
    height = atlas_report.height
    mode = atlas_report.mode
    visible_pixels = 0
    edge_pixels = 0
    suspicious_pixels = 0
    preview = Path(preview_path) if preview_path is not None else None

    if not errors:
        try:
            with Image.open(spritesheet) as image:
                rgba = image.convert("RGBA")
        except (OSError, UnidentifiedImageError) as exc:
            errors.append(f"spritesheet image is invalid: {exc}")
        else:
            width, height = rgba.size
            mode = rgba.mode
            visible_pixels, edge_pixels, suspicious_pixels = _edge_halo_metrics(rgba)
            if preview is not None:
                _write_preview(rgba, preview)
            suspicious_ratio = suspicious_pixels / edge_pixels if edge_pixels else 0.0
            if (
                suspicious_pixels >= SUSPICIOUS_EDGE_HALO_PIXEL_WARNING_THRESHOLD
                and suspicious_ratio >= SUSPICIOUS_EDGE_HALO_RATIO_WARNING_THRESHOLD
            ):
                warnings.append("suspicious_edge_halo_risk")

    suspicious_ratio = suspicious_pixels / edge_pixels if edge_pixels else 0.0
    status = "blocked" if errors else "ready_with_warnings" if warnings else "ready"
    report = PixelPetVisualQaReport(
        ok=not errors,
        status=status,
        spritesheet_path=str(spritesheet),
        motion_manifest_path=str(manifest),
        width=width,
        height=height,
        mode=mode,
        visible_pixel_count=visible_pixels,
        edge_pixel_count=edge_pixels,
        suspicious_edge_halo_pixel_count=suspicious_pixels,
        suspicious_edge_halo_ratio=round(suspicious_ratio, 6),
        preview_path=str(preview) if preview is not None and not errors else "",
        warnings=tuple(warnings),
        errors=tuple(errors),
    )
    if report_path is not None:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _edge_halo_metrics(image: Image.Image) -> tuple[int, int, int]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    visible_pixels = 0
    edge_pixels = 0
    suspicious_pixels = 0
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if alpha < VISIBLE_ALPHA_THRESHOLD:
                continue
            visible_pixels += 1
            if not _touches_transparent_neighbor(pixels, x, y, width, height):
                continue
            edge_pixels += 1
            if _is_suspicious_halo_color(red, green, blue):
                suspicious_pixels += 1
    return visible_pixels, edge_pixels, suspicious_pixels


def _write_preview(image: Image.Image, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    rgba = image.convert("RGBA")
    preview = _checkerboard(rgba.size)
    preview.alpha_composite(rgba)
    overlay = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    overlay_pixels = overlay.load()
    source_pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = source_pixels[x, y]
            if alpha < VISIBLE_ALPHA_THRESHOLD:
                continue
            if _touches_transparent_neighbor(source_pixels, x, y, width, height) and _is_suspicious_halo_color(
                red,
                green,
                blue,
            ):
                overlay_pixels[x, y] = (255, 32, 24, 220)
    preview.alpha_composite(overlay)
    preview.save(target)


def _checkerboard(size: tuple[int, int]) -> Image.Image:
    width, height = size
    tile = 16
    image = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, height, tile):
        for x in range(0, width, tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle(
                    (x, y, min(width, x + tile) - 1, min(height, y + tile) - 1),
                    fill=(220, 225, 230, 255),
                )
    return image


def _touches_transparent_neighbor(pixels, x: int, y: int, width: int, height: int) -> bool:
    for neighbor_x, neighbor_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if neighbor_x < 0 or neighbor_y < 0 or neighbor_x >= width or neighbor_y >= height:
            return True
        if pixels[neighbor_x, neighbor_y][3] <= TRANSPARENT_ALPHA:
            return True
    return False


def _is_suspicious_halo_color(red: int, green: int, blue: int) -> bool:
    purple_or_magenta = red >= 120 and blue >= 120 and green <= 95 and blue - green >= 55
    saturated_red = red >= 170 and green <= 90 and blue <= 120 and red - green >= 80
    return purple_or_magenta or saturated_red


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect pixel-pet spritesheet visual edge QA metrics.")
    parser.add_argument("spritesheet")
    parser.add_argument("--motion-manifest", required=True)
    parser.add_argument("--report", default="")
    parser.add_argument("--preview", default="")
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Return a failing exit code when visual warnings are present.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = inspect_pixel_pet_visual_qa(
        args.spritesheet,
        args.motion_manifest,
        report_path=args.report or None,
        preview_path=args.preview or None,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    if not report.ok:
        return 1
    if args.fail_on_warnings and report.warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
