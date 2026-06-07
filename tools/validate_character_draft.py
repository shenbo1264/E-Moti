from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.character_session import is_safe_character_id

REQUIRED_DRAFT_FILES = (
    "character.json",
    "dialogue_style.json",
    "shop_items.json",
    "motion_manifest.json",
    "art_prompts.json",
    "portrait_candidate.json",
    "character_card.md",
    "provenance.md",
    "qa_checklist.md",
)
REQUIRED_DRAFT_DIRS = ("item_icons", "preview", "portraits")
ALLOWED_PORTRAIT_CANDIDATE_STATUSES = {"approved", "candidate", "rejected"}


@dataclass(frozen=True, slots=True)
class CharacterDraftValidationReport:
    ok: bool
    character_id: str
    path: Path
    import_ready: bool
    manual_qa_required: bool
    portrait_candidate_status: str
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "character_id": self.character_id,
            "path": str(self.path),
            "import_ready": self.import_ready,
            "manual_qa_required": self.manual_qa_required,
            "portrait_candidate_status": self.portrait_candidate_status,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def validate_character_draft_dir(draft_dir: Path | str) -> CharacterDraftValidationReport:
    root = Path(draft_dir)
    errors: list[str] = []
    warnings: list[str] = []
    if not root.is_dir():
        errors.append(f"draft directory not found: {root}")

    for filename in REQUIRED_DRAFT_FILES:
        if not (root / filename).is_file():
            errors.append(f"missing required draft file: {filename}")
    for dirname in REQUIRED_DRAFT_DIRS:
        if not (root / dirname).is_dir():
            errors.append(f"missing required draft directory: {dirname}")

    character = _read_json_object(root / "character.json", errors, label="character.json")
    character_id = _character_id_from_payload(character, root)
    if not is_safe_character_id(character_id):
        errors.append(f"unsafe character_id: {character_id!r}")
    if character_id != root.name:
        errors.append(f"character_id must match draft directory name: {root.name}")

    shop_items = _read_json_list(root / "shop_items.json", errors, label="shop_items.json")
    missing_item_icons = _missing_item_icons(root, shop_items)
    for icon in missing_item_icons:
        warnings.append(f"item icon missing: {icon}")

    if not (root / "spritesheet.png").is_file():
        warnings.append("spritesheet.png missing; draft is not import-ready")

    portrait_candidate = _read_json_object(
        root / "portrait_candidate.json",
        errors,
        label="portrait_candidate.json",
        missing_ok=True,
    )
    portrait_status, portrait_missing = _validate_portrait_candidate(root, portrait_candidate, errors)
    if portrait_status and portrait_status != "approved":
        warnings.append("portrait candidate still requires human approval")
    for image_path in portrait_missing:
        warnings.append(f"portrait candidate image missing: {image_path}")

    import_ready = (
        not errors
        and not warnings
        and bool(character_id)
        and portrait_status == "approved"
        and (root / "spritesheet.png").is_file()
    )
    return CharacterDraftValidationReport(
        ok=not errors,
        character_id=character_id,
        path=root,
        import_ready=import_ready,
        manual_qa_required=not import_ready,
        portrait_candidate_status=portrait_status,
        errors=errors,
        warnings=warnings,
    )


def _read_json_object(
    path: Path,
    errors: list[str],
    *,
    label: str,
    missing_ok: bool = False,
) -> dict[str, object]:
    if missing_ok and not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} json invalid: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be an object")
        return {}
    return payload


def _read_json_list(path: Path, errors: list[str], *, label: str) -> list[object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} json invalid: {exc}")
        return []
    if not isinstance(payload, list):
        errors.append(f"{label} must be a list")
        return []
    return payload


def _character_id_from_payload(payload: dict[str, object], root: Path) -> str:
    if isinstance(payload.get("character_id"), str):
        return str(payload["character_id"])
    return root.name


def _missing_item_icons(root: Path, shop_items: list[object]) -> list[str]:
    missing: list[str] = []
    for item in shop_items:
        if not isinstance(item, dict):
            continue
        icon = item.get("icon")
        if not isinstance(icon, str) or not icon:
            continue
        icon_path = Path(icon)
        if icon_path.is_absolute() or ".." in icon_path.parts:
            continue
        if not (root / icon_path).is_file():
            missing.append(icon_path.as_posix())
    return missing


def _validate_portrait_candidate(
    root: Path,
    payload: dict[str, object],
    errors: list[str],
) -> tuple[str, list[str]]:
    if not payload:
        return "", []
    status = payload.get("status")
    if not isinstance(status, str):
        status = ""
    status = status.strip().lower()
    if status not in ALLOWED_PORTRAIT_CANDIDATE_STATUSES:
        errors.append("portrait_candidate.status must be one of: approved, candidate, rejected")
        status = ""

    expressions = payload.get("expressions")
    if not isinstance(expressions, dict) or not expressions:
        errors.append("portrait_candidate.expressions must be a non-empty object")
        return status, []

    missing: list[str] = []
    for expression, value in expressions.items():
        if not isinstance(expression, str) or not expression:
            errors.append("portrait_candidate.expressions keys must be non-empty strings")
            continue
        for frame_name, frame_path in _portrait_frame_paths(value):
            label = expression if not frame_name else f"{expression}.{frame_name}"
            safe_path = _safe_portrait_candidate_path(frame_path)
            if safe_path is None:
                errors.append(f"portrait_candidate.expressions.{label} path must stay inside portraits")
                continue
            if not (root / safe_path).is_file():
                missing.append(safe_path.as_posix())
    return status, missing


def _portrait_frame_paths(value: object) -> tuple[tuple[str, object], ...]:
    if isinstance(value, str):
        return (("", value),)
    if not isinstance(value, dict):
        return (("", value),)
    frames: list[tuple[str, object]] = []
    frames.append(("open", value.get("open")))
    for key in ("blink_half", "blink_closed"):
        if key in value:
            frames.append((key, value.get(key)))
    for key, item in value.items():
        if key not in {"open", "blink_half", "blink_closed"}:
            frames.append((str(key), item))
    return tuple(frames)


def _safe_portrait_candidate_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip() or len(value) > 180:
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    path = Path(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or len(path.parts) < 2
        or path.parts[0] != "portraits"
        or path.suffix.lower() != ".png"
    ):
        return None
    return path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate an E-Moti generated character draft directory.")
    parser.add_argument("draft_dir", help="Path to a generated character draft directory.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = validate_character_draft_dir(Path(args.draft_dir))
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
