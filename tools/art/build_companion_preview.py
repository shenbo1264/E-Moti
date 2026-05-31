from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.art.validate_companion_atlas import validate_atlas


class PreviewValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _ensure_distinct_gif_frames(frames: list[Image.Image]) -> list[Image.Image]:
    if len({frame.tobytes() for frame in frames}) == len(frames):
        return frames

    marked_frames = [frame.copy() for frame in frames]
    marker_x = marked_frames[0].width - 1
    marker_y = marked_frames[0].height - 1
    for index, frame in enumerate(marked_frames):
        frame.putpixel((marker_x, marker_y), ((index + 1) % 256, 0, 0, 255))
    return marked_frames


def build_previews(
    atlas_path: Path | str, manifest_path: Path | str, output_dir: Path | str
) -> list[Path]:
    atlas = Path(atlas_path)
    manifest = Path(manifest_path)
    output = Path(output_dir)

    report = validate_atlas(atlas, manifest)
    if not report.ok:
        raise PreviewValidationError(report.errors)

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    frame_width = int(payload["frame_width"])
    frame_height = int(payload["frame_height"])
    columns = int(payload["sheet_columns"])
    rows = int(payload["sheet_rows"])
    generated: list[Path] = []

    output.mkdir(parents=True, exist_ok=True)
    gif_dir = output / "gifs"
    gif_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(atlas) as source:
        sheet = source.convert("RGBA")

    contact = sheet.copy()
    draw = ImageDraw.Draw(contact)
    for x in range(0, columns * frame_width + 1, frame_width):
        draw.line((x, 0, x, rows * frame_height), fill=(255, 64, 64, 180), width=2)
    for y in range(0, rows * frame_height + 1, frame_height):
        draw.line((0, y, columns * frame_width, y), fill=(255, 64, 64, 180), width=2)
    contact_path = output / "contact-sheet.png"
    contact.save(contact_path)
    generated.append(contact_path)

    for name, motion in payload["motions"].items():
        row = int(motion["row"])
        frame_count = int(motion["frame_count"])
        fps = max(int(motion.get("fps", 6)), 1)
        frames = [
            sheet.crop(
                (
                    index * frame_width,
                    row * frame_height,
                    (index + 1) * frame_width,
                    (row + 1) * frame_height,
                )
            )
            for index in range(frame_count)
        ]
        gif_frames = _ensure_distinct_gif_frames(frames)
        gif_path = gif_dir / f"{name}.gif"
        gif_frames[0].save(
            gif_path,
            save_all=True,
            append_images=gif_frames[1:],
            duration=max(int(1000 / fps), 16),
            loop=0,
        )
        generated.append(gif_path)

    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description="Build companion atlas preview files.")
    parser.add_argument("--atlas", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        generated = build_previews(args.atlas, args.manifest, args.output)
    except PreviewValidationError as exc:
        for error in exc.errors:
            print(f"ERROR {error}")
        return 1
    for path in generated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
