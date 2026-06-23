from __future__ import annotations

import json
from pathlib import Path

from .character_pack import DEFAULT_CHARACTER_ID
from .character_registry import CharacterPackSummary


def character_pack_role_label(
    pack: CharacterPackSummary,
    *,
    default_character_id: str = DEFAULT_CHARACTER_ID,
) -> str:
    if pack.character_id == default_character_id and pack.source == "builtin":
        return "默认提交角色"
    if pack.distribution_boundary == "private_local_fanwork":
        return "扩展角色"
    if pack.source in {"user", "import_source"} or pack.distribution_boundary == "local_ugc_only":
        return "用户导入角色"
    if pack.source == "builtin":
        return "课程提交角色"
    return "外部角色"


def character_pack_list_item_text(pack: CharacterPackSummary) -> str:
    return f"{pack.name} | {character_pack_role_label(pack)} | {pack.title}"


def character_pack_distribution_text(pack: CharacterPackSummary) -> str:
    return "\n".join(
        (
            "角色包信息",
            f"角色定位: {character_pack_role_label(pack)}",
            f"来源: {_source_label(pack.source)}",
            f"交付状态: {character_pack_distribution_warning(pack)}",
            f"来源记录: {_relative_pack_paths(pack, pack.provenance_paths)}",
            f"说明文件: {_relative_pack_paths(pack, pack.license_paths)}",
            character_pack_readiness_text(pack),
        )
    )


def character_pack_readiness_text(pack: CharacterPackSummary) -> str:
    return "\n".join(
        (
            "QA 状态",
            f"来源记录: {_ready_or_missing(pack.provenance_paths)}",
            f"说明文件: {_ready_or_missing(pack.license_paths)}",
            f"视觉 QA: {_visual_qa_status(pack)}",
            f"人工 QA: {_manual_qa_status(pack)}",
        )
    )


def character_pack_distribution_warning(pack: CharacterPackSummary) -> str:
    if pack.source == "builtin":
        return "已纳入课程提交角色库，可直接在角色库中展示和切换。"
    if pack.distribution_boundary == "local_ugc_only":
        return "用户导入角色包，可在本机角色库中展示和切换。"
    if pack.distribution_boundary == "private_local_fanwork":
        return "扩展角色包，可作为本机角色库示例展示。"
    return "外部角色包，导入后可在本机角色库中展示和切换。"


def character_pack_import_review_text(pack: CharacterPackSummary) -> str:
    return "\n\n".join(
        (
            f"导入角色包: {pack.character_id}",
            f"{pack.name}\n{pack.title}",
            character_pack_distribution_text(pack),
            "导入后会保留来源记录和 QA 说明，并可在角色库中切换体验。",
        )
    )


def _source_label(source: str) -> str:
    if source == "builtin":
        return "内置角色库"
    return source


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
    return "已记录" if paths else "未记录"


def _visual_qa_status(pack: CharacterPackSummary) -> str:
    report = _read_json_object(pack.path / "qa_report.json")
    if report is None:
        return "未记录"
    status = report.get("visual_qa_status")
    if isinstance(status, str) and status:
        return _status_label(status)
    ok = report.get("ok")
    if ok is True:
        return "已通过"
    if ok is False:
        return "需要处理"
    return "未记录"


def _manual_qa_status(pack: CharacterPackSummary) -> str:
    report = _read_json_object(pack.path / "manual_qa.json")
    if report is not None:
        decision = report.get("manual_decision")
        if isinstance(decision, str) and decision:
            return decision
    qa_report = _read_json_object(pack.path / "qa_report.json")
    if qa_report is not None and qa_report.get("manual_qa_required") is True:
        return "待人工确认"
    return "未记录"


def _status_label(status: str) -> str:
    if status == "ready":
        return "已通过"
    if status == "needs attention":
        return "需要处理"
    if status == "not recorded":
        return "未记录"
    return status


def _read_json_object(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None
