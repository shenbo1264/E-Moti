from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError


DEFAULT_OUTPUT_ROOT = Path("artifacts") / "portrait-video-source"
SAFE_SET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,78}[A-Za-z0-9]$")


@dataclass(frozen=True, slots=True)
class PortraitVideoSourcePackReport:
    ok: bool
    set_id: str
    output_dir: str
    reference_image: str
    prompt_path: str
    metadata_path: str
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "set_id": self.set_id,
            "output_dir": self.output_dir,
            "reference_image": self.reference_image,
            "prompt_path": self.prompt_path,
            "metadata_path": self.metadata_path,
            "errors": list(self.errors),
        }


def create_portrait_video_source_pack(
    *,
    source_image_path: Path | str,
    output_root: Path | str = DEFAULT_OUTPUT_ROOT,
    set_id: str,
    character_name: str = "Xingxi",
    source_label: str = "",
) -> PortraitVideoSourcePackReport:
    errors: list[str] = []
    safe_set_id = _safe_set_id(set_id)
    source = Path(source_image_path)
    root = Path(output_root)
    output = root / safe_set_id if safe_set_id else root / "_invalid"

    if not safe_set_id:
        errors.append("set_id must be a safe folder name")
    if not _is_png_image(source):
        errors.append("source_image must be a readable PNG image")
    if errors:
        return PortraitVideoSourcePackReport(
            ok=False,
            set_id=set_id,
            output_dir="",
            reference_image="",
            prompt_path="",
            metadata_path="",
            errors=tuple(errors),
        )

    reference_dir = output / "reference"
    frames_dir = output / "frames"
    video_dir = output / "video"
    reference_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)

    reference_target = reference_dir / source.name
    shutil.copy2(source, reference_target)

    prompt_path = output / "gemini_prompt.md"
    metadata_path = output / "source_pack.json"
    frames_readme = frames_dir / "README.md"
    video_readme = video_dir / "README.md"

    prompt_path.write_text(
        _render_gemini_prompt(
            character_name=character_name,
            reference_image=reference_target.relative_to(output).as_posix(),
            source_label=source_label,
        ),
        encoding="utf-8",
    )
    frames_readme.write_text(_frames_readme_text(), encoding="utf-8")
    video_readme.write_text(_video_readme_text(), encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "set_id": safe_set_id,
                "source_label": source_label,
                "character_name": character_name,
                "reference_image": reference_target.relative_to(output).as_posix(),
                "prompt_path": "gemini_prompt.md",
                "frames_dir": "frames",
                "video_dir": "video",
                "next_command": (
                    "python tools\\art\\extract_portrait_motion_frames.py "
                    f"--reference-image \"{reference_target}\" "
                    f"--frames-dir \"{frames_dir}\" "
                    f"--output-dir \"artifacts\\portrait-candidate-{safe_set_id}-motion\" "
                    f"--report \"artifacts\\portrait-candidate-{safe_set_id}-motion\\candidate-motion-frame-report.json\" "
                    "--source-tool \"Gemini video\" --generation-prompt \"see gemini_prompt.md\""
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return PortraitVideoSourcePackReport(
        ok=True,
        set_id=safe_set_id,
        output_dir=str(output),
        reference_image=str(reference_target),
        prompt_path=str(prompt_path),
        metadata_path=str(metadata_path),
    )


def _safe_set_id(value: str) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not SAFE_SET_ID.fullmatch(value):
        return ""
    return value


def _is_png_image(path: Path) -> bool:
    if path.suffix.lower() != ".png" or not path.is_file():
        return False
    try:
        with Image.open(path) as image:
            image.verify()
    except (OSError, UnidentifiedImageError):
        return False
    return True


def _render_gemini_prompt(*, character_name: str, reference_image: str, source_label: str) -> str:
    clean_name = character_name.strip() or "Xingxi"
    clean_label = source_label.strip() or "portrait reference"
    return "\n".join(
        [
            "# Gemini Portrait Video Prompt",
            "",
            f"Reference image: `{reference_image}`",
            f"Character: {clean_name}",
            f"Source label: {clean_label}",
            "",
            "Use the provided reference image as the identity anchor.",
            "",
            "Prompt:",
            "",
            (
                "Static camera, same character, outfit, pose, and proportions as the reference image. "
                "Create a short 3-4 second transparent-background or clean plain-background portrait video. "
                "The character should stay in place with subtle breathing, one natural blink, and a very slight hair sway. "
                "Keep the face, eyes, hairstyle, outfit details, colors, and silhouette consistent. "
                "No camera movement, no zoom, no scene change, no hand gesture, no mouth talking, no extra objects, no text, no logo, no watermark."
            ),
            "",
            "Negative prompt:",
            "",
            (
                "Do not redesign the character. Do not change age, body proportion, face shape, hairstyle, eye color, costume, or palette. "
                "Do not add background characters, speech bubbles, UI, subtitles, glowing borders, red edge halos, blur, heavy motion, or dramatic lighting."
            ),
            "",
            "Export request:",
            "",
            "- Prefer 24 fps or higher.",
            "- Keep the first frame close to the reference pose.",
            "- Download the video into `video/`.",
            "- Export PNG frames into `frames/` using sequential names such as `frame_0001.png`.",
            "",
        ]
    )


def _frames_readme_text() -> str:
    return "\n".join(
        [
            "# Exported PNG Frames",
            "",
            "Put Gemini-exported PNG frames here.",
            "",
            "Expected naming:",
            "",
            "```text",
            "frame_0001.png",
            "frame_0002.png",
            "frame_0003.png",
            "```",
            "",
            "After frames are present, run the `next_command` from `../source_pack.json` or adapt it with the exact paths.",
            "",
        ]
    )


def _video_readme_text() -> str:
    return "\n".join(
        [
            "# Gemini Video Downloads",
            "",
            "Put the downloaded Gemini video here before exporting frames.",
            "",
            "Do not commit raw generated video unless it has been explicitly approved for release.",
            "",
        ]
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a local Gemini video source pack for one portrait set.")
    parser.add_argument("--source-image", required=True)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--set-id", required=True)
    parser.add_argument("--character-name", default="Xingxi")
    parser.add_argument("--source-label", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = create_portrait_video_source_pack(
        source_image_path=args.source_image,
        output_root=args.output_root,
        set_id=args.set_id,
        character_name=args.character_name,
        source_label=args.source_label,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
