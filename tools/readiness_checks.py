from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tools.review_character_pack_status import review_character_pack_status


def build_source_character_pack_check(character_pack: Path) -> dict[str, object]:
    report = review_character_pack_status(character_pack)
    return {
        "id": "source_character_pack",
        "label": "Source Character Pack",
        "ok": report.get("ok") is True,
        "status": str(report.get("status") or "unknown"),
        "path": str(character_pack),
        "character_id": str(report.get("character_id") or ""),
        "manual_qa_required": report.get("manual_qa_required") is True,
        "distribution_boundary": str(report.get("distribution_boundary") or "unknown"),
        "provenance_files": _string_list(report.get("provenance_files")),
        "license_files": _string_list(report.get("license_files")),
        "errors": _string_list(report.get("errors")),
        "warnings": _string_list(report.get("warnings")),
        "next_actions": _string_list(report.get("next_actions")),
    }


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]
