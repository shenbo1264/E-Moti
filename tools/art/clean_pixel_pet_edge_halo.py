from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.art.pixel_pet_visual_qa import (  # noqa: E402
    VISIBLE_ALPHA_THRESHOLD,
    _is_suspicious_halo_color,
    _touches_transparent_neighbor,
    inspect_pixel_pet_visual_qa,
)
from tools.validate_pixel_pet_pack import validate_pixel_pet_pack_dir  # noqa: E402


@dataclass(frozen=True, slots=True)
class PixelPetEdgeHaloCleanupReport:
    ok: bool
    source_pack_dir: str
    output_dir: str
    spritesheet_path: str
    changed_pixel_count: int
    pass_changed_pixel_counts: tuple[int, ...]
    visual_qa_before: dict[str, object]
    visual_qa_after: dict[str, object]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "source_pack_dir": self.source_pack_dir,
            "output_dir": self.output_dir,
            "spritesheet_path": self.spritesheet_path,
            "changed_pixel_count": self.changed_pixel_count,
            "pass_changed_pixel_counts": list(self.pass_changed_pixel_counts),
            "visual_qa_before": self.visual_qa_before,
            "visual_qa_after": self.visual_qa_after,
            "errors": list(self.errors),
        }


def clean_pixel_pet_edge_halo(
    pack_dir: Path | str,
    output_dir: Path | str,
    *,
    report_path: Path | str | None = None,
    max_passes: int = 8,
) -> PixelPetEdgeHaloCleanupReport:
    source_root = Path(pack_dir)
    output_root = Path(output_dir)
    errors: list[str] = []
    _validate_output_root(source_root, output_root, errors)
    source_validation = validate_pixel_pet_pack_dir(source_root)
    errors.extend(source_validation.errors)

    if errors:
        report = _report(
            source_root=source_root,
            output_root=output_root,
            spritesheet_path=output_root / "spritesheet.png",
            pass_counts=(),
            before={},
            after={},
            errors=errors,
        )
        _write_report(report, report_path)
        return report

    motion_manifest = source_root / "motion_manifest.json"
    before = inspect_pixel_pet_visual_qa(source_root / "spritesheet.png", motion_manifest)

    shutil.copytree(source_root, output_root)
    target_spritesheet = output_root / "spritesheet.png"
    pass_counts = _clean_suspicious_edge_pixels(target_spritesheet, max_passes=max(1, max_passes))
    _update_qa_report(output_root / "qa_report.json", pass_counts)

    target_manifest = output_root / "motion_manifest.json"
    output_validation = validate_pixel_pet_pack_dir(output_root)
    errors.extend(output_validation.errors)
    after = inspect_pixel_pet_visual_qa(target_spritesheet, target_manifest)
    errors.extend(after.errors)

    report = _report(
        source_root=source_root,
        output_root=output_root,
        spritesheet_path=target_spritesheet,
        pass_counts=tuple(pass_counts),
        before=before.to_dict(),
        after=after.to_dict(),
        errors=errors,
    )
    _write_report(report, report_path)
    return report


def _clean_suspicious_edge_pixels(path: Path, *, max_passes: int) -> tuple[int, ...]:
    try:
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError(f"spritesheet image invalid: {exc}") from exc

    pass_counts: list[int] = []
    width, height = rgba.size
    for _ in range(max_passes):
        source = rgba.copy()
        source_pixels = source.load()
        target_pixels = rgba.load()
        changed = 0
        for y in range(height):
            for x in range(width):
                red, green, blue, alpha = source_pixels[x, y]
                if alpha < VISIBLE_ALPHA_THRESHOLD:
                    continue
                if not _touches_transparent_neighbor(source_pixels, x, y, width, height):
                    continue
                if _is_suspicious_halo_color(red, green, blue):
                    target_pixels[x, y] = (0, 0, 0, 0)
                    changed += 1
                    continue
                if _is_dark_purple_outline(red, green, blue):
                    target_pixels[x, y] = (14, 22, 44, alpha)
                    changed += 1
        pass_counts.append(changed)
        if changed == 0:
            break
    transparent_rgb_changes = _clear_near_transparent_pixel_rgb(rgba)
    if transparent_rgb_changes:
        pass_counts.append(transparent_rgb_changes)
    rgba.save(path)
    return tuple(pass_counts)


def _is_dark_purple_outline(red: int, green: int, blue: int) -> bool:
    return green <= 16 and red >= 16 and blue >= 16 and abs(red - blue) <= 48


def _clear_near_transparent_pixel_rgb(image: Image.Image) -> int:
    pixels = image.load()
    width, height = image.size
    changed = 0
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if alpha >= VISIBLE_ALPHA_THRESHOLD or (red, green, blue, alpha) == (0, 0, 0, 0):
                continue
            pixels[x, y] = (0, 0, 0, 0)
            changed += 1
    return changed


def _update_qa_report(path: Path, pass_counts: tuple[int, ...]) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return
    payload["edge_halo_cleanup"] = {
        "method": "delete_suspicious_edge_halo_pixels_and_recolor_dark_purple_outline",
        "changed_pixel_count": sum(pass_counts),
        "pass_changed_pixel_counts": list(pass_counts),
        "manual_qa_required": True,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _validate_output_root(source_root: Path, output_root: Path, errors: list[str]) -> None:
    if output_root.exists():
        errors.append("output_dir already exists")
        return
    if not source_root.is_dir():
        errors.append(f"source pack directory not found: {source_root}")
        return
    source_resolved = source_root.resolve()
    output_resolved = output_root.resolve()
    if source_resolved == output_resolved:
        errors.append("output_dir must be different from source pack directory")
        return
    try:
        output_resolved.relative_to(source_resolved)
    except ValueError:
        pass
    else:
        errors.append("output_dir must not be inside source pack directory")


def _report(
    *,
    source_root: Path,
    output_root: Path,
    spritesheet_path: Path,
    pass_counts: tuple[int, ...],
    before: dict[str, object],
    after: dict[str, object],
    errors: list[str],
) -> PixelPetEdgeHaloCleanupReport:
    return PixelPetEdgeHaloCleanupReport(
        ok=not errors,
        source_pack_dir=str(source_root),
        output_dir=str(output_root),
        spritesheet_path=str(spritesheet_path),
        changed_pixel_count=sum(pass_counts),
        pass_changed_pixel_counts=tuple(pass_counts),
        visual_qa_before=before,
        visual_qa_after=after,
        errors=tuple(errors),
    )


def _write_report(report: PixelPetEdgeHaloCleanupReport, report_path: Path | str | None) -> None:
    if report_path is None:
        return
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clone a pixel-pet pack and remove suspicious red/purple edge halo.")
    parser.add_argument("pack_dir")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", default="")
    parser.add_argument("--max-passes", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = clean_pixel_pet_edge_halo(
            args.pack_dir,
            args.output,
            report_path=args.report or None,
            max_passes=args.max_passes,
        )
    except ValueError as exc:
        report = PixelPetEdgeHaloCleanupReport(
            ok=False,
            source_pack_dir=str(Path(args.pack_dir)),
            output_dir=str(Path(args.output)),
            spritesheet_path=str(Path(args.output) / "spritesheet.png"),
            changed_pixel_count=0,
            pass_changed_pixel_counts=(),
            visual_qa_before={},
            visual_qa_after={},
            errors=(str(exc),),
        )
        _write_report(report, args.report or None)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
