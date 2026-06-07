from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, UnidentifiedImageError

ALLOWED_CANDIDATE_STATUSES = ("approved", "candidate", "rejected")
MAX_PORTRAIT_WIDTH = 4096
MAX_PORTRAIT_HEIGHT = 4096
THUMBNAIL_WIDTH = 256
THUMBNAIL_HEIGHT = 512
LABEL_HEIGHT = 28
CONTACT_SHEET_COLUMNS = 2


@dataclass(frozen=True, slots=True)
class PortraitCandidateReport:
    ok: bool
    status: str
    path: str
    image_count: int
    errors: list[str]
    contact_sheet_path: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "status": self.status,
            "path": self.path,
            "image_count": self.image_count,
            "errors": list(self.errors),
            "contact_sheet_path": self.contact_sheet_path,
        }


def validate_portrait_candidate(
    candidate_manifest_path: Path | str,
    *,
    runtime_manifest_path: Path | str | None = None,
    contact_sheet_path: Path | str | None = None,
) -> PortraitCandidateReport:
    manifest_path = Path(candidate_manifest_path)
    root = manifest_path.parent
    errors: list[str] = []
    payload = _read_json_object(manifest_path, errors, "portrait_candidate.json")
    status = _candidate_status(payload, errors)
    image_entries = _candidate_image_entries(root, payload, errors)

    if runtime_manifest_path is not None:
        _validate_runtime_manifest_references(
            root=root,
            candidate_status=status,
            candidate_paths=[path for _, path in image_entries],
            runtime_manifest_path=Path(runtime_manifest_path),
            errors=errors,
        )

    written_contact_sheet = ""
    if contact_sheet_path is not None and not errors:
        target = Path(contact_sheet_path)
        _write_contact_sheet(image_entries, target)
        written_contact_sheet = str(target)

    return PortraitCandidateReport(
        ok=not errors,
        status=status,
        path=str(manifest_path),
        image_count=len(image_entries),
        errors=errors,
        contact_sheet_path=written_contact_sheet,
    )


def _read_json_object(path: Path, errors: list[str], label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} json invalid: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be an object")
        return {}
    return payload


def _candidate_status(payload: dict[str, object], errors: list[str]) -> str:
    status = payload.get("status", "")
    if not isinstance(status, str):
        status = ""
    status = status.strip().lower()
    if status not in ALLOWED_CANDIDATE_STATUSES:
        errors.append("status must be one of: approved, candidate, rejected")
        return ""
    return status


def _candidate_image_entries(
    root: Path,
    payload: dict[str, object],
    errors: list[str],
) -> list[tuple[str, Path]]:
    expressions = payload.get("expressions")
    if not isinstance(expressions, dict) or not expressions:
        errors.append("expressions must be a non-empty object")
        return []

    entries: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for expression, value in expressions.items():
        if not isinstance(expression, str) or not expression:
            errors.append("expressions keys must be non-empty strings")
            continue
        for frame_name, frame_path in _portrait_frame_paths(value):
            label = expression if not frame_name else f"{expression}.{frame_name}"
            resolved = _safe_candidate_image_path(root, frame_path)
            if resolved is None:
                errors.append(f"expressions.{label} path must stay inside candidate directory")
                continue
            _validate_candidate_image(resolved, label, errors)
            if resolved not in seen:
                seen.add(resolved)
                entries.append((label, resolved))
    if not entries and not errors:
        errors.append("expressions must include at least one image")
    return entries


def _portrait_frame_paths(value: object) -> tuple[tuple[str, object], ...]:
    if isinstance(value, str):
        return (("", value),)
    if not isinstance(value, dict):
        return (("", value),)
    frames: list[tuple[str, object]] = []
    open_path = value.get("open")
    frames.append(("open", open_path))
    for key in ("blink_half", "blink_closed"):
        if key in value:
            frames.append((key, value.get(key)))
    for key, item in value.items():
        if key not in {"open", "blink_half", "blink_closed"}:
            frames.append((str(key), item))
    return tuple(frames)


def _safe_candidate_image_path(root: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip() or len(value) > 180:
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
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


def _validate_candidate_image(path: Path, label: str, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"portrait image not found: {label}")
        return
    alpha_extrema: tuple[int, int] | None = None
    try:
        with Image.open(path) as image:
            size = image.size
            mode = image.mode
            image.verify()
        if mode == "RGBA":
            with Image.open(path) as image:
                alpha_extrema = image.getchannel("A").getextrema()
    except (OSError, UnidentifiedImageError) as exc:
        errors.append(f"portrait image invalid: {label}: {exc}")
        return
    if mode != "RGBA":
        errors.append(f"portrait image mode must be RGBA: {label}")
    elif alpha_extrema is not None:
        min_alpha, max_alpha = alpha_extrema
        if max_alpha == 0:
            errors.append(f"portrait image must include visible opaque pixels: {label}")
        if min_alpha == 255:
            errors.append(f"portrait image must include transparent alpha pixels: {label}")
    if size[1] <= size[0]:
        errors.append(f"portrait image must be taller than wide for Spirit/VN staging: {label}")
    if size[0] > MAX_PORTRAIT_WIDTH or size[1] > MAX_PORTRAIT_HEIGHT:
        errors.append(f"portrait image too large: {label}")


def _validate_runtime_manifest_references(
    *,
    root: Path,
    candidate_status: str,
    candidate_paths: Iterable[Path],
    runtime_manifest_path: Path,
    errors: list[str],
) -> None:
    payload = _read_json_object(runtime_manifest_path, errors, "runtime portrait_manifest.json")
    if not payload:
        return
    runtime_root = runtime_manifest_path.parent.resolve()
    candidate_path_set = {path.resolve() for path in candidate_paths}
    for runtime_path in _runtime_manifest_image_paths(payload):
        if not isinstance(runtime_path, str):
            continue
        resolved = (runtime_root / runtime_path).resolve()
        if resolved not in candidate_path_set:
            continue
        if candidate_status != "approved":
            try:
                label = resolved.relative_to(root.resolve()).as_posix()
            except ValueError:
                label = resolved.name
            errors.append(f"runtime manifest references unapproved candidate image: {label}")


def _runtime_manifest_image_paths(payload: dict[str, object]) -> tuple[str, ...]:
    expressions = payload.get("expressions")
    if not isinstance(expressions, dict):
        return ()
    paths: list[str] = []
    for value in expressions.values():
        for _, frame_path in _portrait_frame_paths(value):
            if isinstance(frame_path, str):
                paths.append(frame_path)
    return tuple(paths)


def _write_contact_sheet(image_entries: list[tuple[str, Path]], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    columns = min(CONTACT_SHEET_COLUMNS, max(1, len(image_entries)))
    rows = (len(image_entries) + columns - 1) // columns
    cell_height = THUMBNAIL_HEIGHT + LABEL_HEIGHT
    sheet = Image.new("RGBA", (columns * THUMBNAIL_WIDTH, rows * cell_height), (245, 247, 250, 255))
    draw = ImageDraw.Draw(sheet)
    for index, (label, path) in enumerate(image_entries):
        column = index % columns
        row = index // columns
        x = column * THUMBNAIL_WIDTH
        y = row * cell_height
        with Image.open(path) as image:
            frame = image.convert("RGBA")
            frame.thumbnail((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), Image.Resampling.LANCZOS)
            paste_x = x + (THUMBNAIL_WIDTH - frame.width) // 2
            paste_y = y + (THUMBNAIL_HEIGHT - frame.height) // 2
            sheet.alpha_composite(frame, (paste_x, paste_y))
        draw.rectangle((x, y + THUMBNAIL_HEIGHT, x + THUMBNAIL_WIDTH, y + cell_height), fill=(28, 33, 40, 255))
        draw.text((x + 8, y + THUMBNAIL_HEIGHT + 7), label[:36], fill=(255, 255, 255, 255))
    sheet.save(target)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate portrait candidate assets before manifest promotion.")
    parser.add_argument("candidate_manifest")
    parser.add_argument("--runtime-manifest", default="")
    parser.add_argument("--contact-sheet", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = validate_portrait_candidate(
        args.candidate_manifest,
        runtime_manifest_path=args.runtime_manifest or None,
        contact_sheet_path=args.contact_sheet or None,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
