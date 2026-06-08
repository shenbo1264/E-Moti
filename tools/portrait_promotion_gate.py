from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.character_registry import REQUIRED_PORTRAIT_EXPRESSIONS, validate_character_pack_dir
from guanghe_companion.spirit_stage import PortraitManifestError, load_portrait_manifest

MAX_PROMOTION_IMAGE_WIDTH = 4096
MAX_PROMOTION_IMAGE_HEIGHT = 4096
MIN_PROMOTION_ASPECT_RATIO = 1.2


@dataclass(frozen=True, slots=True)
class PortraitPromotionReport:
    ok: bool
    character_id: str
    path: str
    image_count: int
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "character_id": self.character_id,
            "path": self.path,
            "image_count": self.image_count,
            "errors": list(self.errors),
        }


def validate_portrait_promotion_candidate(pack_dir: Path | str) -> PortraitPromotionReport:
    root = Path(pack_dir)
    errors: list[str] = []
    pack_report = validate_character_pack_dir(root, source="promotion_candidate")
    errors.extend(f"character pack: {error}" for error in pack_report.errors)

    character = _read_json_object(root / "character.json", errors, label="character.json")
    renderer = character.get("renderer") if isinstance(character, dict) else {}
    if not isinstance(renderer, dict) or renderer.get("backend") != "portrait":
        errors.append("character renderer backend must be portrait")
    manifest_name = renderer.get("portrait_manifest") if isinstance(renderer, dict) else ""
    if not isinstance(manifest_name, str) or not manifest_name.strip():
        errors.append("character renderer portrait_manifest is required")
        manifest_name = "portrait_manifest.json"

    _validate_approval_metadata(root / "portrait_candidate.json", errors)
    _validate_provenance(root, errors)

    image_entries = _portrait_manifest_image_entries(root, manifest_name, errors)
    _validate_promotion_images(image_entries, errors)
    _validate_expression_distinctness(image_entries, errors)
    _validate_neutral_blink_frames(image_entries, errors)

    return PortraitPromotionReport(
        ok=not errors,
        character_id=pack_report.character_id,
        path=str(root),
        image_count=len({path.resolve() for _, path in image_entries}),
        errors=tuple(errors),
    )


def _read_json_object(path: Path, errors: list[str], *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} json invalid: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be an object")
        return {}
    return payload


def _validate_approval_metadata(path: Path, errors: list[str]) -> None:
    payload = _read_json_object(path, errors, label="portrait_candidate.json")
    if not payload:
        return
    if payload.get("status") != "approved":
        errors.append("portrait_candidate.status must be approved before promotion")
    if payload.get("approval_required") is not False:
        errors.append("portrait_candidate.approval_required must be false before promotion")
    if payload.get("runtime_manifest_safe") is not True:
        errors.append("portrait_candidate.runtime_manifest_safe must be true before promotion")


def _validate_provenance(root: Path, errors: list[str]) -> None:
    for filename in ("portrait_assets_provenance.md", "provenance.md"):
        path = root / filename
        if path.is_file() and path.stat().st_size > 0:
            return
    errors.append("portrait promotion requires a non-empty provenance note")


def _portrait_manifest_image_entries(root: Path, manifest_name: str, errors: list[str]) -> list[tuple[str, Path]]:
    try:
        manifest = load_portrait_manifest(root, manifest_name)
    except PortraitManifestError as exc:
        errors.append(f"portrait manifest invalid: {exc}")
        return []

    entries: list[tuple[str, Path]] = []
    manifest_root = root / Path(manifest.manifest_path).parent
    for expression in REQUIRED_PORTRAIT_EXPRESSIONS:
        frames = manifest.expressions.get(expression)
        if frames is None:
            errors.append(f"portrait_manifest.expressions missing required portrait expression: {expression}")
            continue
        entries.append((f"{expression}.open", _resolve_manifest_image_path(manifest_root, frames.open_path)))
        if expression == "neutral":
            if not frames.can_blink:
                errors.append("neutral expression requires blink_half and blink_closed frames before promotion")
            else:
                entries.append(("neutral.blink_half", _resolve_manifest_image_path(manifest_root, frames.blink_half_path)))
                entries.append(("neutral.blink_closed", _resolve_manifest_image_path(manifest_root, frames.blink_closed_path)))
    if not manifest.animation.blink_enabled:
        errors.append("portrait_manifest.animation.blink.enabled must be true before promotion")
    return entries


def _resolve_manifest_image_path(manifest_root: Path, relative_path: str) -> Path:
    return (manifest_root / relative_path).resolve()


def _validate_promotion_images(entries: list[tuple[str, Path]], errors: list[str]) -> None:
    for label, path in entries:
        if not path.is_file():
            errors.append(f"portrait image not found: {label}")
            continue
        try:
            with Image.open(path) as image:
                mode = image.mode
                width, height = image.size
                image.verify()
            alpha_extrema = None
            if mode == "RGBA":
                with Image.open(path) as image:
                    alpha_extrema = image.getchannel("A").getextrema()
        except (OSError, UnidentifiedImageError) as exc:
            errors.append(f"portrait image invalid: {label}: {exc}")
            continue
        if mode != "RGBA":
            errors.append(f"portrait image mode must be RGBA: {label}")
            continue
        if width > MAX_PROMOTION_IMAGE_WIDTH or height > MAX_PROMOTION_IMAGE_HEIGHT:
            errors.append(f"portrait image too large: {label}")
        if height <= width or height / max(width, 1) < MIN_PROMOTION_ASPECT_RATIO:
            errors.append(f"portrait image must be tall VN portrait: {label}")
        if alpha_extrema is None:
            continue
        min_alpha, max_alpha = alpha_extrema
        if max_alpha == 0:
            errors.append(f"portrait image must include visible opaque pixels: {label}")
        if min_alpha == 255:
            errors.append(f"portrait image must include transparent alpha pixels: {label}")


def _validate_expression_distinctness(entries: list[tuple[str, Path]], errors: list[str]) -> None:
    open_entries = [(label.removesuffix(".open"), path) for label, path in entries if label.endswith(".open")]
    digests: dict[str, list[str]] = {}
    for expression, path in open_entries:
        digest = _image_digest(path)
        if not digest:
            continue
        digests.setdefault(digest, []).append(expression)
    for expressions in digests.values():
        if len(expressions) > 1:
            errors.append(f"portrait expression images must be visually distinct: {', '.join(sorted(expressions))}")


def _validate_neutral_blink_frames(entries: list[tuple[str, Path]], errors: list[str]) -> None:
    blink_entries = [(label, path) for label, path in entries if label.startswith("neutral.")]
    digests = {_image_digest(path) for _, path in blink_entries}
    digests.discard("")
    if len(digests) != len(blink_entries):
        errors.append("neutral blink frames must be visually distinct before promotion")


def _image_digest(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        with Image.open(path) as image:
            frame = image.convert("RGBA")
            return hashlib.sha256(frame.tobytes()).hexdigest()
    except (OSError, UnidentifiedImageError):
        return ""


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a portrait character pack before official manifest promotion.")
    parser.add_argument("pack_dir")
    parser.add_argument("--report", default="", help="Optional JSON report output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = validate_portrait_promotion_candidate(args.pack_dir)
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
