from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


EXPECTED_COLUMNS = 8
EXPECTED_ROWS = 9
EXPECTED_FRAME_WIDTH = 192
EXPECTED_FRAME_HEIGHT = 208
EXPECTED_WIDTH = EXPECTED_COLUMNS * EXPECTED_FRAME_WIDTH
EXPECTED_HEIGHT = EXPECTED_ROWS * EXPECTED_FRAME_HEIGHT


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

    with Image.open(atlas) as image:
        width, height = image.size
        mode = image.mode

    if (width, height) != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
        errors.append(f"atlas size must be 1536x1872, got {width}x{height}")
    if mode != "RGBA":
        errors.append(f"atlas mode must be RGBA, got {mode}")

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("sheet_columns") != EXPECTED_COLUMNS:
        errors.append(f"sheet_columns must be 8, got {payload.get('sheet_columns')}")
    if payload.get("sheet_rows") != EXPECTED_ROWS:
        errors.append(f"sheet_rows must be 9, got {payload.get('sheet_rows')}")
    if payload.get("frame_width") != EXPECTED_FRAME_WIDTH:
        errors.append(f"frame_width must be 192, got {payload.get('frame_width')}")
    if payload.get("frame_height") != EXPECTED_FRAME_HEIGHT:
        errors.append(f"frame_height must be 208, got {payload.get('frame_height')}")

    for name, motion in payload.get("motions", {}).items():
        row = motion.get("row")
        frame_count = motion.get("frame_count")
        if not isinstance(row, int) or row < 0 or row >= EXPECTED_ROWS:
            errors.append(f"{name}.row must be between 0 and 8, got {row}")
        if not isinstance(frame_count, int) or frame_count < 1 or frame_count > EXPECTED_COLUMNS:
            errors.append(f"{name}.frame_count must be between 1 and 8, got {frame_count}")

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
