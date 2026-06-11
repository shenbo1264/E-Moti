from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from tools.art.validate_companion_atlas import validate_atlas


ALLOWED_DISTRIBUTION_BOUNDARIES = {
    "official_candidate",
    "local_ugc_only",
    "private_local_fanwork",
}
UGC_DISTRIBUTION_BOUNDARIES = {"local_ugc_only", "private_local_fanwork"}
REQUIRED_FILES = (
    "character.json",
    "dialogue_style.json",
    "motion_manifest.json",
    "spritesheet.png",
    "preview/contact-sheet.png",
    "provenance.md",
    "qa_report.json",
)


@dataclass(frozen=True, slots=True)
class PixelPetPackValidationReport:
    ok: bool
    character_id: str
    path: str
    distribution_boundary: str
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "character_id": self.character_id,
            "path": self.path,
            "distribution_boundary": self.distribution_boundary,
            "errors": list(self.errors),
        }


def validate_pixel_pet_pack_dir(pack_dir: Path | str) -> PixelPetPackValidationReport:
    root = Path(pack_dir)
    errors: list[str] = []
    character_payload = _read_json_object(root / "character.json", errors, label="character.json")
    dialogue_payload = _read_json_object(root / "dialogue_style.json", errors, label="dialogue_style.json")
    qa_payload = _read_json_object(root / "qa_report.json", errors, label="qa_report.json")
    character_id = _character_id(character_payload, root)
    distribution_boundary = _distribution_boundary(qa_payload)

    _validate_required_files(root, errors)
    if character_payload is not None:
        _validate_character_payload(character_payload, errors)
    if dialogue_payload is not None:
        _validate_dialogue_payload(dialogue_payload, errors)
    if qa_payload is not None:
        _validate_qa_payload(character_id, qa_payload, errors)
    _validate_provenance(root / "provenance.md", errors)
    _validate_contact_sheet(root / "preview" / "contact-sheet.png", errors)
    _validate_atlas_contract(root, errors)

    return PixelPetPackValidationReport(
        ok=not errors,
        character_id=character_id,
        path=str(root),
        distribution_boundary=distribution_boundary,
        errors=tuple(errors),
    )


def _validate_required_files(root: Path, errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.is_file():
            errors.append(f"{relative} is required")


def _read_json_object(path: Path, errors: list[str], *, label: str) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} json invalid: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{label} must be an object")
        return None
    return payload


def _character_id(payload: dict[str, object] | None, root: Path) -> str:
    value = payload.get("character_id") if isinstance(payload, dict) else None
    return value if isinstance(value, str) and value else root.name


def _distribution_boundary(payload: dict[str, object] | None) -> str:
    value = payload.get("distribution_boundary") if isinstance(payload, dict) else ""
    return value if isinstance(value, str) else ""


def _validate_character_payload(payload: dict[str, object], errors: list[str]) -> None:
    character_id = payload.get("character_id")
    if not _safe_id(character_id):
        errors.append("character.json.character_id must be a safe non-empty id")
    for key in ("name", "title", "description"):
        if not isinstance(payload.get(key), str) or not str(payload.get(key)).strip():
            errors.append(f"character.json.{key} must be a non-empty string")
    if payload.get("spritesheet") != "spritesheet.png":
        errors.append("character.json.spritesheet must be exactly spritesheet.png")
    if payload.get("motion_manifest") != "motion_manifest.json":
        errors.append("character.json.motion_manifest must be exactly motion_manifest.json")
    renderer = payload.get("renderer")
    if renderer is not None:
        if not isinstance(renderer, dict):
            errors.append("character.json.renderer must be an object")
        elif renderer.get("backend", "sprite") != "sprite":
            errors.append("pixel-pet draft renderer backend must be sprite")


def _validate_dialogue_payload(payload: dict[str, object], errors: list[str]) -> None:
    for key in ("tone", "fallback_style"):
        if not isinstance(payload.get(key), str) or not str(payload.get(key)).strip():
            errors.append(f"dialogue_style.json.{key} must be a non-empty string")
    keywords = payload.get("keywords")
    if not isinstance(keywords, list) or not all(isinstance(item, str) and item for item in keywords):
        errors.append("dialogue_style.json.keywords must be a non-empty string list")


def _validate_qa_payload(character_id: str, payload: dict[str, object], errors: list[str]) -> None:
    status = payload.get("status")
    if status not in {"candidate", "approved", "rejected"}:
        errors.append("qa_report.json.status must be one of: approved, candidate, rejected")
    if payload.get("manual_qa_required") is not True:
        errors.append("qa_report.json.manual_qa_required must be true for draft packs")
    boundary = payload.get("distribution_boundary")
    if boundary not in ALLOWED_DISTRIBUTION_BOUNDARIES:
        errors.append("qa_report.json.distribution_boundary invalid")
        return
    if "_ugc_" in character_id and boundary not in UGC_DISTRIBUTION_BOUNDARIES:
        errors.append(
            "UGC pixel-pet packs must use local_ugc_only or private_local_fanwork distribution_boundary"
        )


def _validate_provenance(path: Path, errors: list[str]) -> None:
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"provenance.md unreadable: {exc}")
        return
    if not text.strip():
        errors.append("provenance.md must be non-empty")


def _validate_contact_sheet(path: Path, errors: list[str]) -> None:
    if not path.is_file():
        return
    try:
        with Image.open(path) as image:
            mode = image.mode
            width, height = image.size
            image.verify()
    except (OSError, UnidentifiedImageError) as exc:
        errors.append(f"preview/contact-sheet.png invalid: {exc}")
        return
    if mode != "RGBA":
        errors.append(f"preview/contact-sheet.png mode must be RGBA, got {mode}")
    if width <= 0 or height <= 0:
        errors.append("preview/contact-sheet.png must have positive size")


def _validate_atlas_contract(root: Path, errors: list[str]) -> None:
    atlas = root / "spritesheet.png"
    manifest = root / "motion_manifest.json"
    if not atlas.is_file() or not manifest.is_file():
        return
    report = validate_atlas(atlas, manifest)
    errors.extend(report.errors)


def _safe_id(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    return all(char.isascii() and (char.islower() or char.isdigit() or char == "_") for char in value)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a draft pixel-pet character pack.")
    parser.add_argument("pack_dir")
    parser.add_argument("--report", default="", help="Optional JSON report output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = validate_pixel_pet_pack_dir(Path(args.pack_dir))
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
