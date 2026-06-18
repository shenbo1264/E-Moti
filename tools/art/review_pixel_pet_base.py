from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError


MAGENTA = (255, 0, 255)
ALLOWED_DECISIONS = {"candidate", "accepted_for_row_testing", "rejected"}
BACKGROUND_TOLERANCE = 32
BACKGROUND_FLAT_TOLERANCE = 8
BACKGROUND_CANDIDATE_TOLERANCE = 48
MAX_BASE_ASPECT_RATIO = 1.8


@dataclass(frozen=True, slots=True)
class PixelPetBaseReviewReport:
    ok: bool
    character_id: str
    decision: str
    asset_boundary: str
    runtime_manifest_updated: bool
    image: dict[str, object]
    prompt_path: str
    character_definition_path: str
    prior_qa_path: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "character_id": self.character_id,
            "decision": self.decision,
            "asset_boundary": self.asset_boundary,
            "runtime_manifest_updated": self.runtime_manifest_updated,
            "image": dict(self.image),
            "prompt_path": self.prompt_path,
            "character_definition_path": self.character_definition_path,
            "prior_qa_path": self.prior_qa_path,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def review_pixel_pet_base_candidate(
    *,
    candidate_image: Path | str,
    character_id: str,
    prompt_path: Path | str,
    character_definition_path: Path | str,
    prior_qa_path: Path | str | None = None,
    decision: str = "candidate",
    report_path: Path | str | None = None,
    markdown_path: Path | str | None = None,
    preview_path: Path | str | None = None,
) -> PixelPetBaseReviewReport:
    candidate = Path(candidate_image)
    prompt = Path(prompt_path)
    definition = Path(character_definition_path)
    prior_qa = Path(prior_qa_path) if prior_qa_path else None
    errors: list[str] = []
    warnings: list[str] = []

    if decision not in ALLOWED_DECISIONS:
        errors.append("decision must be one of: accepted_for_row_testing, candidate, rejected")

    image_info = _inspect_candidate_image(candidate, errors, warnings)
    _validate_prompt(prompt, errors)
    _validate_character_definition(definition, character_id, errors, warnings)
    _validate_prior_qa(prior_qa, character_id, warnings)

    report = PixelPetBaseReviewReport(
        ok=not errors,
        character_id=character_id,
        decision=decision,
        asset_boundary="ignored_candidate_only",
        runtime_manifest_updated=False,
        image=image_info,
        prompt_path=str(prompt),
        character_definition_path=str(definition),
        prior_qa_path=str(prior_qa) if prior_qa else "",
        errors=tuple(errors),
        warnings=tuple(warnings),
    )

    if report_path:
        _write_json_report(Path(report_path), report)
    if markdown_path:
        _write_markdown_report(Path(markdown_path), report)
    if preview_path:
        _write_preview(Path(preview_path), candidate, report)
    return report


def _inspect_candidate_image(path: Path, errors: list[str], warnings: list[str]) -> dict[str, object]:
    if not path.is_file():
        errors.append("candidate image not found")
        return {
            "path": str(path),
            "mode": "",
            "width": 0,
            "height": 0,
            "background_rgb": [],
            "subject_bbox": [],
            "subject_coverage": 0.0,
        }
    try:
        with Image.open(path) as image:
            mode = image.mode
            width, height = image.size
            image.verify()
        with Image.open(path) as image:
            sample = image.convert("RGB")
            corners = _corner_pixels(sample)
            background = corners[0] if corners else MAGENTA
            subject_bbox, coverage = _subject_bbox_and_coverage(sample, background=background)
    except (OSError, UnidentifiedImageError) as exc:
        errors.append(f"candidate image invalid: {exc}")
        return {
            "path": str(path),
            "mode": "",
            "width": 0,
            "height": 0,
            "background_rgb": [],
            "subject_bbox": [],
            "subject_coverage": 0.0,
        }

    if mode not in {"RGB", "RGBA"}:
        errors.append(f"candidate image mode must be RGB or RGBA, got {mode}")
    if width < 128 or height < 128:
        errors.append("candidate image is too small for base review")
    if width > 2048 or height > 2048:
        errors.append("candidate image is too large for ignored base review")
    aspect_ratio = max(width / max(1, height), height / max(1, width))
    if aspect_ratio > MAX_BASE_ASPECT_RATIO:
        errors.append("candidate image aspect ratio suggests a row strip or atlas, not a single base pet")
    if any(not _near_rgb(pixel, MAGENTA, BACKGROUND_CANDIDATE_TOLERANCE) for pixel in corners):
        errors.append("candidate background corners should be flat #FF00FF chroma key")
    elif any(not _near_rgb(pixel, MAGENTA, BACKGROUND_TOLERANCE) for pixel in corners) or any(
        not _near_rgb(pixel, corners[0], BACKGROUND_FLAT_TOLERANCE) for pixel in corners
    ):
        warnings.append("candidate background is near #FF00FF but cleanup required before sprite slicing")
    if not subject_bbox:
        errors.append("candidate image must contain non-background subject pixels")
    if coverage < 0.03:
        errors.append("candidate subject coverage is too small")
    if coverage > 0.85:
        warnings.append("candidate subject coverage is high; verify it still fits a 192x208 sprite cell")
    return {
        "path": str(path),
        "mode": mode,
        "width": width,
        "height": height,
        "aspect_ratio": round(aspect_ratio, 4),
        "background_rgb": list(corners[0]) if corners else [],
        "subject_bbox": list(subject_bbox) if subject_bbox else [],
        "subject_coverage": round(coverage, 4),
    }


def _corner_pixels(image: Image.Image) -> tuple[tuple[int, int, int], ...]:
    width, height = image.size
    return (
        image.getpixel((0, 0)),
        image.getpixel((width - 1, 0)),
        image.getpixel((0, height - 1)),
        image.getpixel((width - 1, height - 1)),
    )


def _subject_bbox_and_coverage(
    image: Image.Image,
    *,
    background: tuple[int, int, int],
) -> tuple[tuple[int, int, int, int], float]:
    width, height = image.size
    pixels = image.load()
    left, top = width, height
    right, bottom = -1, -1
    count = 0
    for y in range(height):
        for x in range(width):
            if _near_rgb(pixels[x, y], background, BACKGROUND_TOLERANCE):
                continue
            count += 1
            left = min(left, x)
            top = min(top, y)
            right = max(right, x)
            bottom = max(bottom, y)
    if count == 0:
        return (), 0.0
    return (left, top, right + 1, bottom + 1), count / max(1, width * height)


def _near_rgb(left: tuple[int, int, int], right: tuple[int, int, int], tolerance: int) -> bool:
    return all(abs(int(left[index]) - int(right[index])) <= tolerance for index in range(3))


def _validate_prompt(path: Path, errors: list[str]) -> None:
    if not path.is_file():
        errors.append("prompt file not found")
        return
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"prompt file unreadable: {exc}")
        return
    if not text.strip():
        errors.append("prompt file must be non-empty")
    lowered = text.lower()
    if "pixel" not in lowered or "pet" not in lowered:
        errors.append("prompt file must describe pixel-pet intent")


def _validate_character_definition(
    path: Path,
    character_id: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    if not path.is_file():
        errors.append("character definition file not found")
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"character definition json invalid: {exc}")
        return
    if not isinstance(payload, dict):
        errors.append("character definition must be a JSON object")
        return
    definition_id = payload.get("character_id")
    if isinstance(definition_id, str) and definition_id and definition_id != character_id:
        warnings.append(f"character definition id is {definition_id}, expected {character_id}")
    distribution = payload.get("distribution")
    if not isinstance(distribution, str) or not distribution.strip():
        errors.append("character definition distribution must be present")


def _validate_prior_qa(prior_qa: Path | None, character_id: str, warnings: list[str]) -> None:
    if prior_qa is None:
        return
    if not prior_qa.is_file():
        warnings.append("prior QA report not found")
        return
    try:
        payload = json.loads(prior_qa.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        warnings.append(f"prior QA report unreadable: {exc}")
        return
    if not isinstance(payload, dict):
        warnings.append("prior QA report must be a JSON object")
        return
    qa_character_id = payload.get("character_id")
    if isinstance(qa_character_id, str) and qa_character_id and qa_character_id != character_id:
        warnings.append(f"prior QA character_id is {qa_character_id}, expected {character_id}")
    decision = payload.get("base_decision")
    if decision != "accepted_for_row_testing":
        warnings.append(f"prior QA base_decision is {decision or 'missing'}")


def _write_json_report(path: Path, report: PixelPetBaseReviewReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_markdown_report(path: Path, report: PixelPetBaseReviewReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Pixel Pet Base Review",
        "",
        f"- Character: `{report.character_id}`",
        f"- Decision: `{report.decision}`",
        f"- OK: `{'yes' if report.ok else 'no'}`",
        f"- Asset boundary: `{report.asset_boundary}`",
        f"- Runtime manifest updated: `{'yes' if report.runtime_manifest_updated else 'no'}`",
        f"- Candidate: `{report.image.get('path', '')}`",
        f"- Image: `{report.image.get('width', 0)}x{report.image.get('height', 0)} {report.image.get('mode', '')}`",
        f"- Subject coverage: `{report.image.get('subject_coverage', 0.0)}`",
    ]
    if report.errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{error}`" for error in report.errors)
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in report.warnings)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_preview(path: Path, candidate: Path, report: PixelPetBaseReviewReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (720, 420), "#f5f5f5")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    if candidate.is_file():
        try:
            with Image.open(candidate) as image:
                preview = image.convert("RGB")
                preview.thumbnail((360, 360), Image.Resampling.LANCZOS)
            canvas.paste(preview, (24 + (360 - preview.width) // 2, 24 + (360 - preview.height) // 2))
        except (OSError, UnidentifiedImageError):
            pass
    x = 420
    y = 36
    for line in (
        f"Character: {report.character_id}",
        f"Decision: {report.decision}",
        f"OK: {'yes' if report.ok else 'no'}",
        f"Mode: {report.image.get('mode', '')}",
        f"Size: {report.image.get('width', 0)}x{report.image.get('height', 0)}",
        f"Coverage: {report.image.get('subject_coverage', 0.0)}",
        "Runtime manifest: unchanged",
    ):
        draw.text((x, y), line, fill="#222222", font=font)
        y += 34
    canvas.save(path)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review a pixel-pet canonical base candidate.")
    parser.add_argument("candidate_image")
    parser.add_argument("--character-id", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--character-definition", required=True)
    parser.add_argument("--prior-qa", default="")
    parser.add_argument("--decision", default="candidate", choices=sorted(ALLOWED_DECISIONS))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--report", default="")
    parser.add_argument("--markdown", default="")
    parser.add_argument("--preview", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    output_dir = Path(args.output_dir) if args.output_dir else None
    report_path = Path(args.report) if args.report else (output_dir / "base-review.json" if output_dir else None)
    markdown_path = Path(args.markdown) if args.markdown else (output_dir / "base-review.md" if output_dir else None)
    preview_path = Path(args.preview) if args.preview else (output_dir / "base-review.png" if output_dir else None)
    report = review_pixel_pet_base_candidate(
        candidate_image=Path(args.candidate_image),
        character_id=args.character_id,
        prompt_path=Path(args.prompt),
        character_definition_path=Path(args.character_definition),
        prior_qa_path=Path(args.prior_qa) if args.prior_qa else None,
        decision=args.decision,
        report_path=report_path,
        markdown_path=markdown_path,
        preview_path=preview_path,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
