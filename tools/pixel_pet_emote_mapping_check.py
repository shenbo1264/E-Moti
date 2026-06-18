from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.visual_actions import PIXEL_EXPRESSION_MOTION_IDS


@dataclass(frozen=True, slots=True)
class PixelPetEmoteMappingReport:
    ok: bool
    status: str
    character_pack_path: str
    motion_manifest_path: str
    available_motion_ids: tuple[str, ...]
    required_motion_ids: tuple[str, ...]
    missing_motion_ids: tuple[str, ...]
    supported_expression_ids: tuple[str, ...]
    unsupported_expression_ids: tuple[str, ...]
    expression_motion_map: dict[str, str]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    next_actions: tuple[str, ...]


def inspect_pixel_pet_emote_mapping(
    character_pack: Path | str,
    *,
    motion_manifest_path: Path | str | None = None,
) -> PixelPetEmoteMappingReport:
    pack_root = Path(character_pack)
    manifest_path = Path(motion_manifest_path) if motion_manifest_path is not None else pack_root / "motion_manifest.json"
    expression_motion_map = dict(sorted(PIXEL_EXPRESSION_MOTION_IDS.items()))
    required_motion_ids = tuple(sorted(set(expression_motion_map.values())))
    errors: list[str] = []
    warnings: list[str] = []
    available_motion_ids = _available_motion_ids(manifest_path, errors)
    missing_motion_ids = tuple(motion_id for motion_id in required_motion_ids if motion_id not in available_motion_ids)
    supported_expression_ids = tuple(
        expression_id
        for expression_id, motion_id in expression_motion_map.items()
        if motion_id in available_motion_ids
    )
    unsupported_expression_ids = tuple(
        expression_id
        for expression_id, motion_id in expression_motion_map.items()
        if motion_id not in available_motion_ids
    )
    next_actions = _next_actions(errors=errors, missing_motion_ids=missing_motion_ids)
    status = _status(errors=errors, missing_motion_ids=missing_motion_ids)
    return PixelPetEmoteMappingReport(
        ok=status == "ready",
        status=status,
        character_pack_path=str(pack_root),
        motion_manifest_path=str(manifest_path),
        available_motion_ids=available_motion_ids,
        required_motion_ids=required_motion_ids,
        missing_motion_ids=missing_motion_ids,
        supported_expression_ids=supported_expression_ids,
        unsupported_expression_ids=unsupported_expression_ids,
        expression_motion_map=expression_motion_map,
        errors=tuple(errors),
        warnings=tuple(warnings),
        next_actions=tuple(next_actions),
    )


def render_pixel_pet_emote_mapping_markdown(report: PixelPetEmoteMappingReport) -> str:
    lines = [
        "# Pixel Pet Emote Mapping Check",
        "",
        f"- Status: `{report.status}`",
        f"- OK: `{'yes' if report.ok else 'no'}`",
        f"- Character pack: `{report.character_pack_path}`",
        f"- Motion manifest: `{report.motion_manifest_path}`",
        f"- Required motions: `{', '.join(report.required_motion_ids)}`",
        f"- Available motions: `{', '.join(report.available_motion_ids)}`",
        f"- Missing motions: `{', '.join(report.missing_motion_ids)}`",
        f"- Supported expressions: `{', '.join(report.supported_expression_ids)}`",
        f"- Unsupported expressions: `{', '.join(report.unsupported_expression_ids)}`",
    ]
    if report.errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in report.errors)
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in report.warnings)
    if report.next_actions:
        lines.extend(["", "## Next Actions", ""])
        lines.extend(f"- {item}" for item in report.next_actions)
    lines.append("")
    return "\n".join(lines)


def report_to_dict(report: PixelPetEmoteMappingReport) -> dict[str, Any]:
    return asdict(report)


def _available_motion_ids(manifest_path: Path, errors: list[str]) -> tuple[str, ...]:
    if not manifest_path.is_file():
        errors.append(f"motion_manifest.json not found: {manifest_path}")
        return ()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        errors.append(f"motion_manifest.json is not readable JSON: {manifest_path}")
        return ()
    if not isinstance(payload, dict):
        errors.append("motion_manifest.json must contain a JSON object")
        return ()
    motions = payload.get("motions")
    if not isinstance(motions, dict):
        errors.append("motion_manifest.json must contain a motions object")
        return ()
    motion_ids = sorted(motion_id for motion_id in motions if isinstance(motion_id, str) and motion_id)
    if not motion_ids:
        errors.append("motion_manifest.json motions object is empty")
        return ()
    return tuple(motion_ids)


def _status(*, errors: list[str], missing_motion_ids: tuple[str, ...]) -> str:
    if errors:
        return "invalid_manifest"
    if missing_motion_ids:
        return "missing_motion_families"
    return "ready"


def _next_actions(*, errors: list[str], missing_motion_ids: tuple[str, ...]) -> list[str]:
    actions: list[str] = []
    if errors:
        actions.append("fix motion_manifest.json before checking LLM pixel emote coverage")
    if missing_motion_ids:
        actions.append("add motion_manifest entries for: " + ", ".join(missing_motion_ids))
    return actions


def _write_text(path: str, text: str) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check pixel-pet motion coverage for LLM expression cues.")
    parser.add_argument("character_pack", help="Pixel-pet character pack directory.")
    parser.add_argument("--motion-manifest", default="", help="Optional explicit motion_manifest.json path.")
    parser.add_argument("--json", default="", help="Optional JSON output path.")
    parser.add_argument("--markdown", default="", help="Optional Markdown output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = inspect_pixel_pet_emote_mapping(
        Path(args.character_pack),
        motion_manifest_path=Path(args.motion_manifest) if args.motion_manifest else None,
    )
    payload = report_to_dict(report)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    _write_text(args.json, text + "\n")
    _write_text(args.markdown, render_pixel_pet_emote_mapping_markdown(report))
    print(text)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
