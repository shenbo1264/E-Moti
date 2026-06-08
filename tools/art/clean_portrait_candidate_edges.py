from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, UnidentifiedImageError

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.art.portrait_candidate_visual_qa import LIGHT_EDGE_LUMA_THRESHOLD
from tools.art.validate_portrait_candidates import validate_portrait_candidate


@dataclass(frozen=True, slots=True)
class PortraitCandidateEdgeCleanupReport:
    ok: bool
    source_manifest_path: str
    output_dir: str
    manifest_path: str
    cleaned_image_count: int
    changed_pixel_count: int
    image_reports: tuple[dict[str, object], ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "source_manifest_path": self.source_manifest_path,
            "output_dir": self.output_dir,
            "manifest_path": self.manifest_path,
            "cleaned_image_count": self.cleaned_image_count,
            "changed_pixel_count": self.changed_pixel_count,
            "image_reports": list(self.image_reports),
            "errors": list(self.errors),
        }


def clean_portrait_candidate_edges(
    candidate_manifest_path: Path | str,
    output_dir: Path | str,
    *,
    report_path: Path | str | None = None,
) -> PortraitCandidateEdgeCleanupReport:
    source_manifest = Path(candidate_manifest_path)
    source_root = source_manifest.parent
    output_root = Path(output_dir)
    errors: list[str] = []

    payload = _read_candidate_manifest(source_manifest, errors)
    source_validation = validate_portrait_candidate(source_manifest)
    errors.extend(source_validation.errors)
    image_paths = _manifest_image_paths(payload, errors) if not errors else []
    _validate_output_root(source_root, output_root, errors)

    if errors:
        report = _build_report(
            source_manifest=source_manifest,
            output_root=output_root,
            image_reports=(),
            errors=errors,
        )
        _write_report(report, report_path)
        return report

    shutil.copytree(source_root, output_root)
    cloned_manifest = output_root / source_manifest.name

    image_reports: list[dict[str, object]] = []
    total_changed_pixels = 0
    for label, relative_path in image_paths:
        target = output_root / relative_path
        image_report = _clean_image_edges(label, target, root=output_root)
        image_reports.append(image_report)
        total_changed_pixels += int(image_report.get("changed_pixel_count", 0))

    clone_validation = validate_portrait_candidate(cloned_manifest)
    errors.extend(clone_validation.errors)
    report = PortraitCandidateEdgeCleanupReport(
        ok=not errors,
        source_manifest_path=str(source_manifest),
        output_dir=str(output_root),
        manifest_path=str(cloned_manifest),
        cleaned_image_count=sum(1 for image_report in image_reports if image_report.get("changed_pixel_count", 0)),
        changed_pixel_count=total_changed_pixels,
        image_reports=tuple(image_reports),
        errors=tuple(errors),
    )
    _write_report(report, report_path)
    return report


def _build_report(
    *,
    source_manifest: Path,
    output_root: Path,
    image_reports: tuple[dict[str, object], ...],
    errors: list[str],
) -> PortraitCandidateEdgeCleanupReport:
    return PortraitCandidateEdgeCleanupReport(
        ok=False,
        source_manifest_path=str(source_manifest),
        output_dir=str(output_root),
        manifest_path=str(output_root / source_manifest.name),
        cleaned_image_count=0,
        changed_pixel_count=0,
        image_reports=image_reports,
        errors=tuple(errors),
    )


def _read_candidate_manifest(path: Path, errors: list[str]) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"portrait_candidate.json invalid: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append("portrait_candidate.json must be an object")
        return {}
    return payload


def _manifest_image_paths(
    payload: dict[str, object],
    errors: list[str],
) -> tuple[tuple[str, Path], ...]:
    expressions = payload.get("expressions")
    if not isinstance(expressions, dict) or not expressions:
        errors.append("expressions must be a non-empty object")
        return ()

    entries: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for expression, value in expressions.items():
        for frame_name, frame_path in _portrait_frame_paths(value):
            label = str(expression) if not frame_name else f"{expression}.{frame_name}"
            relative_path = _safe_relative_image_path(frame_path)
            if relative_path is None:
                errors.append(f"expressions.{label} path must stay inside candidate directory")
                continue
            if relative_path not in seen:
                seen.add(relative_path)
                entries.append((label, relative_path))
    for label, frame_path in _motion_frame_paths(payload, errors):
        relative_path = _safe_relative_image_path(frame_path)
        if relative_path is None:
            errors.append(f"{label} path must stay inside candidate directory")
            continue
        if relative_path not in seen:
            seen.add(relative_path)
            entries.append((label, relative_path))
    return tuple(entries)


def _portrait_frame_paths(value: object) -> Iterable[tuple[str, object]]:
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


def _motion_frame_paths(payload: dict[str, object], errors: list[str]) -> tuple[tuple[str, object], ...]:
    value = payload.get("motion_frames")
    if value is None:
        return ()
    if not isinstance(value, list):
        errors.append("motion_frames must be an array")
        return ()
    return tuple((f"motion_frames.{index}", item) for index, item in enumerate(value))


def _safe_relative_image_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip() or len(value) > 180:
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".png":
        return None
    return path


def _validate_output_root(source_root: Path, output_root: Path, errors: list[str]) -> None:
    if output_root.exists():
        errors.append("output_dir already exists")
        return
    source_resolved = source_root.resolve()
    output_resolved = output_root.resolve()
    if source_resolved == output_resolved:
        errors.append("output_dir must be different from source candidate directory")
        return
    try:
        output_resolved.relative_to(source_resolved)
    except ValueError:
        pass
    else:
        errors.append("output_dir must not be inside source candidate directory")


def _clean_image_edges(label: str, path: Path, *, root: Path) -> dict[str, object]:
    try:
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
    except (OSError, UnidentifiedImageError) as exc:
        return {
            "label": label,
            "path": _relative_report_path(path, root),
            "changed_pixel_count": 0,
            "errors": [f"image invalid: {exc}"],
        }

    payload = bytearray(rgba.tobytes())
    changed_pixels = 0
    for index in range(0, len(payload), 4):
        alpha = payload[index + 3]
        if alpha == 0 or alpha == 255:
            continue
        red = payload[index]
        green = payload[index + 1]
        blue = payload[index + 2]
        luma = (red * 299 + green * 587 + blue * 114) // 1000
        if luma < LIGHT_EDGE_LUMA_THRESHOLD:
            continue
        payload[index] = 0
        payload[index + 1] = 0
        payload[index + 2] = 0
        payload[index + 3] = 0
        changed_pixels += 1

    if changed_pixels:
        cleaned = Image.frombytes("RGBA", rgba.size, bytes(payload))
        cleaned.save(path)

    return {
        "label": label,
        "path": _relative_report_path(path, root),
        "changed_pixel_count": changed_pixels,
        "errors": [],
    }


def _relative_report_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _write_report(report: PortraitCandidateEdgeCleanupReport, report_path: Path | str | None) -> None:
    if report_path is None:
        return
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clone a portrait candidate and remove bright semi-transparent edge halo pixels.")
    parser.add_argument("candidate_manifest")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = clean_portrait_candidate_edges(
        args.candidate_manifest,
        args.output,
        report_path=args.report or None,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
