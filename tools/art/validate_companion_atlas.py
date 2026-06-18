from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError


EXPECTED_ROWS = 9
EXPECTED_FRAME_WIDTH = 192
EXPECTED_FRAME_HEIGHT = 208
EXPECTED_HEIGHT = EXPECTED_ROWS * EXPECTED_FRAME_HEIGHT
MAX_SHEET_COLUMNS = 32


@dataclass(frozen=True, slots=True)
class AtlasValidationReport:
    ok: bool
    width: int
    height: int
    mode: str
    errors: list[str]


def validate_atlas(atlas_path: Path | str, manifest_path: Path | str) -> AtlasValidationReport:
    atlas = Path(atlas_path)
    manifest = Path(manifest_path)
    errors: list[str] = []

    if not atlas.exists():
        return AtlasValidationReport(False, 0, 0, "", [f"atlas not found: {atlas}"])
    if not manifest.exists():
        return AtlasValidationReport(False, 0, 0, "", [f"manifest not found: {manifest}"])

    try:
        with Image.open(atlas) as image:
            width, height = image.size
            mode = image.mode
            image.verify()
        with Image.open(atlas) as image:
            image.load()
    except (OSError, UnidentifiedImageError) as exc:
        return AtlasValidationReport(False, 0, 0, "", [f"atlas image is invalid: {exc}"])

    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return AtlasValidationReport(False, width, height, mode, [f"manifest json is invalid: {exc}"])
    if not isinstance(payload, dict):
        return AtlasValidationReport(False, width, height, mode, ["manifest must be an object"])

    sheet_columns = payload.get("sheet_columns")
    sheet_rows = payload.get("sheet_rows")
    frame_width = payload.get("frame_width")
    frame_height = payload.get("frame_height")
    if isinstance(sheet_columns, bool) or not isinstance(sheet_columns, int) or not 1 <= sheet_columns <= MAX_SHEET_COLUMNS:
        errors.append(f"sheet_columns must be between 1 and {MAX_SHEET_COLUMNS}, got {sheet_columns}")
    if payload.get("sheet_rows") != EXPECTED_ROWS:
        errors.append(f"sheet_rows must be 9, got {sheet_rows}")
    if payload.get("frame_width") != EXPECTED_FRAME_WIDTH:
        errors.append(f"frame_width must be 192, got {frame_width}")
    if payload.get("frame_height") != EXPECTED_FRAME_HEIGHT:
        errors.append(f"frame_height must be 208, got {frame_height}")
    if isinstance(sheet_columns, int) and not isinstance(sheet_columns, bool):
        expected_width = sheet_columns * EXPECTED_FRAME_WIDTH
        if (width, height) != (expected_width, EXPECTED_HEIGHT):
            errors.append(f"atlas size must be {expected_width}x1872, got {width}x{height}")
    if mode != "RGBA":
        errors.append(f"atlas mode must be RGBA, got {mode}")

    motions = payload.get("motions")
    if not isinstance(motions, dict):
        errors.append("motions must be an object")
        return AtlasValidationReport(False, width, height, mode, errors)

    for name, motion in motions.items():
        if not isinstance(motion, dict):
            errors.append(f"{name} must be an object")
            continue
        row = motion.get("row")
        frame_count = motion.get("frame_count")
        if isinstance(row, bool) or not isinstance(row, int) or row < 0 or row >= EXPECTED_ROWS:
            errors.append(f"{name}.row must be between 0 and 8, got {row}")
        if (
            isinstance(frame_count, bool)
            or not isinstance(frame_count, int)
            or frame_count < 1
            or not isinstance(sheet_columns, int)
            or isinstance(sheet_columns, bool)
            or frame_count > sheet_columns
        ):
            max_frame_count = sheet_columns if isinstance(sheet_columns, int) and not isinstance(sheet_columns, bool) else "sheet_columns"
            errors.append(f"{name}.frame_count must be between 1 and {max_frame_count}, got {frame_count}")

    return AtlasValidationReport(not errors, width, height, mode, errors)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate companion atlas geometry.")
    parser.add_argument("--atlas", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    report = validate_atlas(args.atlas, args.manifest)
    if report.ok:
        print(f"OK atlas {report.width}x{report.height} {report.mode}")
        return 0
    for error in report.errors:
        print(f"ERROR {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
