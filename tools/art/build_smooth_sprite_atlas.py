from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.art.validate_companion_atlas import MAX_SHEET_COLUMNS, validate_atlas


class SmoothAtlasError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SmoothAtlasResult:
    atlas_path: Path
    manifest_path: Path
    sheet_columns: int


def build_smooth_sprite_atlas(
    atlas_path: Path | str,
    manifest_path: Path | str,
    output_atlas_path: Path | str,
    output_manifest_path: Path | str,
) -> SmoothAtlasResult:
    atlas = Path(atlas_path)
    manifest = Path(manifest_path)
    output_atlas = Path(output_atlas_path)
    output_manifest = Path(output_manifest_path)

    report = validate_atlas(atlas, manifest)
    if not report.ok:
        raise SmoothAtlasError("; ".join(report.errors))

    payload = _read_manifest(manifest)
    frame_width = int(payload["frame_width"])
    frame_height = int(payload["frame_height"])
    rows = int(payload["sheet_rows"])
    motions = _motion_payloads(payload)
    row_source_counts = _max_frame_counts_by_row(motions)
    motion_frame_counts = {
        name: _smoothed_frame_count(int(motion["frame_count"]))
        for name, motion in motions.items()
    }
    sheet_columns = max(motion_frame_counts.values(), default=1)
    if sheet_columns > MAX_SHEET_COLUMNS:
        raise SmoothAtlasError(
            f"smoothed sheet_columns would be {sheet_columns}, max is {MAX_SHEET_COLUMNS}"
        )

    with Image.open(atlas) as image:
        source = image.convert("RGBA")
    output = Image.new("RGBA", (sheet_columns * frame_width, rows * frame_height), (0, 0, 0, 0))

    for row, source_count in row_source_counts.items():
        frames = _extract_row_frames(source, row, source_count, frame_width, frame_height)
        for index, frame in enumerate(_smooth_frames(frames)):
            output.paste(frame, (index * frame_width, row * frame_height))

    output_payload = copy.deepcopy(payload)
    output_payload["sheet_columns"] = sheet_columns
    for name, motion in _motion_payloads(output_payload).items():
        source_frame_count = int(motion["frame_count"])
        smoothed_frame_count = _smoothed_frame_count(source_frame_count)
        source_fps = int(motion["fps"])
        motion["frame_count"] = smoothed_frame_count
        motion["fps"] = max(1, round(source_fps * smoothed_frame_count / source_frame_count))

    output_atlas.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output.save(output_atlas)
    output_manifest.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    output_report = validate_atlas(output_atlas, output_manifest)
    if not output_report.ok:
        raise SmoothAtlasError("; ".join(output_report.errors))
    return SmoothAtlasResult(output_atlas, output_manifest, sheet_columns)


def _read_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SmoothAtlasError("manifest must be an object")
    return payload


def _motion_payloads(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    motions = payload["motions"]
    if not isinstance(motions, dict):
        raise SmoothAtlasError("motions must be an object")
    return {
        str(name): motion
        for name, motion in motions.items()
        if isinstance(motion, dict)
    }


def _max_frame_counts_by_row(motions: dict[str, dict[str, Any]]) -> dict[int, int]:
    by_row: dict[int, int] = {}
    for motion in motions.values():
        row = int(motion["row"])
        frame_count = int(motion["frame_count"])
        by_row[row] = max(by_row.get(row, 0), frame_count)
    return by_row


def _extract_row_frames(
    source: Image.Image,
    row: int,
    frame_count: int,
    frame_width: int,
    frame_height: int,
) -> list[Image.Image]:
    return [
        source.crop(
            (
                index * frame_width,
                row * frame_height,
                (index + 1) * frame_width,
                (row + 1) * frame_height,
            )
        )
        for index in range(frame_count)
    ]


def _smooth_frames(frames: list[Image.Image]) -> list[Image.Image]:
    if len(frames) <= 1:
        return [frame.copy() for frame in frames]
    smoothed: list[Image.Image] = []
    for index, frame in enumerate(frames[:-1]):
        smoothed.append(frame.copy())
        smoothed.append(Image.blend(frame, frames[index + 1], 0.5))
    smoothed.append(frames[-1].copy())
    return smoothed


def _smoothed_frame_count(source_frame_count: int) -> int:
    return max(1, source_frame_count * 2 - 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a wider companion atlas with blended in-between frames.")
    parser.add_argument("--atlas", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-atlas", required=True, type=Path)
    parser.add_argument("--output-manifest", required=True, type=Path)
    args = parser.parse_args()

    try:
        result = build_smooth_sprite_atlas(
            args.atlas,
            args.manifest,
            args.output_atlas,
            args.output_manifest,
        )
    except SmoothAtlasError as exc:
        print(f"ERROR {exc}")
        return 1
    print(f"OK atlas {result.sheet_columns} columns -> {result.atlas_path}")
    print(f"OK manifest -> {result.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
