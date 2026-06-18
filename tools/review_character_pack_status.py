from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.character_registry import (
    ALLOWED_DISTRIBUTION_BOUNDARIES,
    DEFAULT_DISTRIBUTION_BOUNDARY,
    summarize_character_pack_dir,
    validate_character_pack_dir,
)
from tools.validate_character_draft import validate_character_draft_dir


def review_character_pack_status(path: Path | str) -> dict[str, object]:
    root = Path(path)
    pack_type = _detect_pack_type(root)
    if pack_type == "draft":
        return _review_draft(root)
    return _review_runtime_pack(root)


def render_character_pack_status_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Character Pack Status Review",
        "",
        f"- Status: `{payload.get('status', 'unknown')}`",
        f"- Pack type: `{payload.get('pack_type', 'unknown')}`",
        f"- Character ID: `{payload.get('character_id', '')}`",
        f"- Validation: `{'passed' if payload.get('validation_ok') is True else 'failed'}`",
        f"- Import ready: `{'yes' if payload.get('import_ready') is True else 'no'}`",
        f"- Manual QA required: `{'yes' if payload.get('manual_qa_required') is True else 'no'}`",
        f"- Distribution boundary: `{payload.get('distribution_boundary', 'unknown')}`",
        "",
        "## Provenance",
        "",
        f"- Provenance files: `{_inline_list(payload.get('provenance_files'))}`",
        f"- License files: `{_inline_list(payload.get('license_files'))}`",
    ]
    errors = _string_list(payload.get("errors"))
    if errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in errors)
    warnings = _string_list(payload.get("warnings"))
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in warnings)
    next_actions = _string_list(payload.get("next_actions"))
    if next_actions:
        lines.extend(["", "## Next Actions", ""])
        lines.extend(f"- {item}" for item in next_actions)
    lines.append("")
    return "\n".join(lines)


def _review_draft(root: Path) -> dict[str, object]:
    report = validate_character_draft_dir(root)
    distribution_boundary = _distribution_boundary(root)
    warnings = list(report.warnings)
    if distribution_boundary == "private_local_fanwork":
        warnings.append("local fanwork pack is private-only; do not commit, bundle, or distribute")
    next_actions = _next_actions(
        pack_type="draft",
        errors=report.errors,
        warnings=warnings,
        distribution_boundary=distribution_boundary,
    )
    status = _status(
        validation_ok=report.ok,
        import_ready=report.import_ready,
        warnings=warnings,
        distribution_boundary=distribution_boundary,
        pack_type="draft",
    )
    return _payload(
        ok=status == "ready",
        status=status,
        pack_type="draft",
        character_id=report.character_id,
        path=root,
        validation_ok=report.ok,
        import_ready=report.import_ready,
        manual_qa_required=report.manual_qa_required,
        distribution_boundary=distribution_boundary,
        provenance_files=_existing_file_names(root, ("provenance.md", "portrait_assets_provenance.md", "portrait_video_provenance.md")),
        license_files=_existing_file_names(root, ("LICENSE", "LICENSE.md", "license.md")),
        errors=report.errors,
        warnings=warnings,
        next_actions=next_actions,
    )


def _review_runtime_pack(root: Path) -> dict[str, object]:
    report = validate_character_pack_dir(root, source="local")
    summary = summarize_character_pack_dir(root, source="local")
    distribution_boundary = _distribution_boundary(root)
    provenance_files = [path.name for path in summary.provenance_paths] if summary else []
    license_files = [path.name for path in summary.license_paths] if summary else []
    warnings: list[str] = []
    if report.ok and not provenance_files:
        warnings.append("provenance file missing; distribution review required")
    if report.ok and not license_files:
        warnings.append("license file missing; distribution review required")
    if distribution_boundary == "private_local_fanwork":
        warnings.append("local fanwork pack is private-only; do not commit, bundle, or distribute")
    next_actions = _next_actions(
        pack_type="runtime_pack",
        errors=list(report.errors),
        warnings=warnings,
        distribution_boundary=distribution_boundary,
    )
    status = _status(
        validation_ok=report.ok,
        import_ready=report.ok,
        warnings=warnings,
        distribution_boundary=distribution_boundary,
        pack_type="runtime_pack",
    )
    return _payload(
        ok=status == "ready",
        status=status,
        pack_type="runtime_pack",
        character_id=report.character_id,
        path=root,
        validation_ok=report.ok,
        import_ready=report.ok,
        manual_qa_required=bool(warnings or report.errors),
        distribution_boundary=distribution_boundary,
        provenance_files=provenance_files,
        license_files=license_files,
        errors=list(report.errors),
        warnings=warnings,
        next_actions=next_actions,
    )


def _payload(
    *,
    ok: bool,
    status: str,
    pack_type: str,
    character_id: str,
    path: Path,
    validation_ok: bool,
    import_ready: bool,
    manual_qa_required: bool,
    distribution_boundary: str,
    provenance_files: list[str],
    license_files: list[str],
    errors: Iterable[str],
    warnings: Iterable[str],
    next_actions: Iterable[str],
) -> dict[str, object]:
    return {
        "ok": ok,
        "status": status,
        "pack_type": pack_type,
        "character_id": character_id,
        "path": str(path),
        "validation_ok": validation_ok,
        "import_ready": import_ready,
        "manual_qa_required": manual_qa_required,
        "distribution_boundary": distribution_boundary,
        "provenance_files": list(provenance_files),
        "license_files": list(license_files),
        "errors": list(errors),
        "warnings": _dedupe(warnings),
        "next_actions": _dedupe(next_actions),
    }


def _detect_pack_type(root: Path) -> str:
    draft_markers = ("art_prompts.json", "portrait_candidate.json", "qa_checklist.md")
    if any((root / marker).exists() for marker in draft_markers):
        return "draft"
    return "runtime_pack"


def _distribution_boundary(root: Path) -> str:
    explicit_boundary = _character_json_distribution_boundary(root)
    if explicit_boundary:
        return explicit_boundary
    text_parts: list[str] = []
    for filename in ("character_card.md", "provenance.md", "qa_checklist.md", "art_prompts.json"):
        path = root / filename
        if not path.is_file():
            continue
        try:
            text_parts.append(path.read_text(encoding="utf-8", errors="replace").casefold())
        except OSError:
            continue
    joined = "\n".join(text_parts)
    if "local fanwork" in joined or "private local fanwork" in joined:
        return "private_local_fanwork"
    return DEFAULT_DISTRIBUTION_BOUNDARY


def _character_json_distribution_boundary(root: Path) -> str:
    path = root / "character.json"
    if not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    value = payload.get("distribution_boundary")
    if isinstance(value, str) and value in ALLOWED_DISTRIBUTION_BOUNDARIES:
        return value
    return ""


def _status(
    *,
    validation_ok: bool,
    import_ready: bool,
    warnings: list[str],
    distribution_boundary: str,
    pack_type: str,
) -> str:
    if not validation_ok:
        return "invalid"
    if distribution_boundary == "private_local_fanwork":
        return "private_only"
    if not import_ready and pack_type == "draft":
        return "needs_manual_qa"
    if warnings:
        return "needs_distribution_review" if pack_type == "runtime_pack" else "needs_manual_qa"
    return "ready"


def _next_actions(
    *,
    pack_type: str,
    errors: list[str],
    warnings: list[str],
    distribution_boundary: str,
) -> list[str]:
    actions: list[str] = []
    if errors:
        actions.append("fix validation errors before importing or sharing")
    if any("spritesheet.png missing" in item or "item icon missing" in item for item in warnings):
        actions.append("generate spritesheet and item icons")
    if any("portrait candidate" in item for item in warnings):
        actions.append("complete portrait candidate QA and approval")
    if any("provenance file missing" in item for item in warnings):
        actions.append("add provenance note before sharing or bundling")
    if any("license file missing" in item for item in warnings):
        actions.append("add license or usage-rights note before sharing or bundling")
    if distribution_boundary == "private_local_fanwork":
        actions.append("keep local fanwork private and out of open-source commits")
    if not actions and pack_type == "runtime_pack":
        actions.append("pack is ready for local import or distribution review")
    return actions


def _existing_file_names(root: Path, filenames: Iterable[str]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for filename in filenames:
        path = root / filename
        if not path.is_file():
            continue
        key = path.name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(path.name)
    return names


def _dedupe(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _inline_list(value: object) -> str:
    items = _string_list(value)
    return "[" + ", ".join(items) + "]"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _write_text(path: str, text: str) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review a character draft or runtime pack status.")
    parser.add_argument("path", help="Character draft or runtime pack directory.")
    parser.add_argument("--json", default="", help="Optional JSON output path.")
    parser.add_argument("--markdown", default="", help="Optional Markdown output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = review_character_pack_status(Path(args.path))
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    _write_text(args.json, text + "\n")
    _write_text(args.markdown, render_character_pack_status_markdown(payload))
    print(text)
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
