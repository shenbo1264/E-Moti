from __future__ import annotations

import json
from pathlib import Path

from .character_pack import DEFAULT_CHARACTER_ID
from .character_registry import CharacterPackSummary
from .distribution_boundaries import distribution_warning_for_boundary


def character_pack_role_label(
    pack: CharacterPackSummary,
    *,
    default_character_id: str = DEFAULT_CHARACTER_ID,
) -> str:
    if pack.character_id == default_character_id and pack.source == "builtin":
        return "Default official"
    if pack.distribution_boundary == "private_local_fanwork":
        return "Fanwork UGC"
    if pack.source in {"user", "import_source"} or pack.distribution_boundary == "local_ugc_only":
        return "Local UGC"
    if pack.source == "builtin":
        return "Optional official candidate"
    return "External candidate"


def character_pack_list_item_text(pack: CharacterPackSummary) -> str:
    return f"{pack.name} | {character_pack_role_label(pack)} | {pack.title}"


def character_pack_distribution_text(pack: CharacterPackSummary) -> str:
    return "\n".join(
        (
            "Distribution",
            f"Role: {character_pack_role_label(pack)}",
            f"Source: {pack.source}",
            f"Distribution: {pack.distribution_boundary}",
            f"Warning: {character_pack_distribution_warning(pack)}",
            f"Provenance: {_relative_pack_paths(pack, pack.provenance_paths)}",
            f"License: {_relative_pack_paths(pack, pack.license_paths)}",
            character_pack_readiness_text(pack),
        )
    )


def character_pack_readiness_text(pack: CharacterPackSummary) -> str:
    return "\n".join(
        (
            "Readiness",
            f"Provenance: {_ready_or_missing(pack.provenance_paths)}",
            f"License: {_ready_or_missing(pack.license_paths)}",
            f"Visual QA: {_visual_qa_status(pack)}",
            f"Manual QA: {_manual_qa_status(pack)}",
        )
    )


def character_pack_distribution_warning(pack: CharacterPackSummary) -> str:
    return distribution_warning_for_boundary(pack.distribution_boundary)


def character_pack_import_review_text(pack: CharacterPackSummary) -> str:
    return "\n\n".join(
        (
            f"Import character pack: {pack.character_id}",
            f"{pack.name}\n{pack.title}",
            character_pack_distribution_text(pack),
            "Keep provenance and source notes with shared fanwork packs.",
        )
    )


def _relative_pack_paths(pack: CharacterPackSummary, paths: tuple[Path, ...]) -> str:
    if not paths:
        return "missing"
    labels: list[str] = []
    for path in paths:
        try:
            labels.append(path.relative_to(pack.path).as_posix())
        except ValueError:
            labels.append(path.name)
    return ", ".join(labels)


def _ready_or_missing(paths: tuple[Path, ...]) -> str:
    return "ready" if paths else "missing"


def _visual_qa_status(pack: CharacterPackSummary) -> str:
    report = _read_json_object(pack.path / "qa_report.json")
    if report is None:
        return "not recorded"
    status = report.get("visual_qa_status")
    if isinstance(status, str) and status:
        return status
    ok = report.get("ok")
    if ok is True:
        return "ready"
    if ok is False:
        return "needs attention"
    return "not recorded"


def _manual_qa_status(pack: CharacterPackSummary) -> str:
    report = _read_json_object(pack.path / "manual_qa.json")
    if report is not None:
        decision = report.get("manual_decision")
        if isinstance(decision, str) and decision:
            return decision
    qa_report = _read_json_object(pack.path / "qa_report.json")
    if qa_report is not None and qa_report.get("manual_qa_required") is True:
        return "required"
    return "not recorded"


def _read_json_object(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None
