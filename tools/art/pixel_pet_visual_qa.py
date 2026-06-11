from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError


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
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def inspect_pixel_pet_visual_qa(
    spritesheet_path: Path | str,
    motion_manifest_path: Path | str,
    *,
    report_path: Path | str | None = None,
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
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    if not report.ok:
        return 1
    if args.fail_on_warnings and report.warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
