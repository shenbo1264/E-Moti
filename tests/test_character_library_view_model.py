from __future__ import annotations

from pathlib import Path

from guanghe_companion.character_library_view_model import (
    character_pack_list_item_text,
    character_pack_readiness_text,
    character_pack_role_label,
    character_pack_distribution_text,
    character_pack_distribution_warning,
    character_pack_import_review_text,
)
from guanghe_companion.character_registry import CharacterPackSummary


def _summary() -> CharacterPackSummary:
    root = Path("assets/companion/xingxi_pixel_pet")
    return CharacterPackSummary(
        character_id="xingxi_pixel_pet",
        name="Xingxi Pixel Pet",
        title="Pixel desktop companion candidate",
        description="QA-gated optional candidate.",
        path=root,
        source="builtin",
        distribution_boundary="shareable_after_review",
        preview_path=root / "preview" / "contact-sheet.png",
        provenance_paths=(root / "provenance.md",),
        license_paths=(root / "LICENSE.md",),
    )


def _summary_with(
    *,
    character_id: str,
    source: str,
    distribution_boundary: str,
    root: Path | None = None,
) -> CharacterPackSummary:
    pack_root = root or Path("assets/companion") / character_id
    return CharacterPackSummary(
        character_id=character_id,
        name=character_id,
        title="Character pack",
        description="Pack used by the character library.",
        path=pack_root,
        source=source,
        distribution_boundary=distribution_boundary,
        preview_path=pack_root / "preview" / "contact-sheet.png",
        provenance_paths=(),
        license_paths=(),
    )


def test_character_pack_role_label_distinguishes_default_candidate_ugc_and_fanwork() -> None:
    assert character_pack_role_label(
        _summary_with(
            character_id="xingxi_pixel_pet",
            source="builtin",
            distribution_boundary="shareable_after_review",
        )
    ) == "默认提交角色"
    assert character_pack_role_label(
        _summary_with(
            character_id="original_oc",
            source="builtin",
            distribution_boundary="shareable_after_review",
        )
    ) == "课程提交角色"
    assert character_pack_role_label(
        _summary_with(
            character_id="local_pet",
            source="user",
            distribution_boundary="local_ugc_only",
        )
    ) == "用户导入角色"
    assert character_pack_role_label(
        _summary_with(
            character_id="fanwork_pet",
            source="user",
            distribution_boundary="private_local_fanwork",
        )
    ) == "扩展角色"


def test_character_pack_readiness_text_reports_qa_files(tmp_path: Path) -> None:
    pack_root = tmp_path / "xingxi_pixel_pet"
    pack_root.mkdir()
    (pack_root / "provenance.md").write_text("generated", encoding="utf-8")
    (pack_root / "LICENSE.md").write_text("license", encoding="utf-8")
    (pack_root / "qa_report.json").write_text(
        '{"visual_qa_status":"ready","manual_qa_required":true}',
        encoding="utf-8",
    )
    (pack_root / "manual_qa.json").write_text(
        '{"manual_decision":"promotion_gate_candidate_clean_edge_optional_bundled"}',
        encoding="utf-8",
    )
    pack = CharacterPackSummary(
        character_id="xingxi_pixel_pet",
        name="Xingxi Pixel Pet",
        title="Pixel candidate",
        description="Candidate pack.",
        path=pack_root,
        source="builtin",
        distribution_boundary="shareable_after_review",
        preview_path=pack_root / "preview" / "contact-sheet.png",
        provenance_paths=(pack_root / "provenance.md",),
        license_paths=(pack_root / "LICENSE.md",),
    )

    text = character_pack_readiness_text(pack)

    assert "来源记录: 已记录" in text
    assert "说明文件: 已记录" in text
    assert "视觉 QA: 已通过" in text
    assert "人工 QA: promotion_gate_candidate_clean_edge_optional_bundled" in text


def test_character_pack_distribution_text_keeps_provenance_and_license_relative() -> None:
    text = character_pack_distribution_text(_summary())

    assert "角色包信息" in text
    assert "角色定位: 默认提交角色" in text
    assert "来源: 内置角色库" in text
    assert "交付状态: 已纳入课程提交角色库" in text
    assert "来源记录: provenance.md" in text
    assert "说明文件: LICENSE.md" in text
    assert "QA 状态" in text
    assert "Warning:" not in text


def test_character_pack_list_item_text_includes_role_label() -> None:
    text = character_pack_list_item_text(_summary())

    assert text == "Xingxi Pixel Pet | 默认提交角色 | Pixel desktop companion candidate"


def test_character_pack_distribution_warning_marks_private_fanwork_as_noncommercial_fanwork() -> None:
    pack = _summary_with(
        character_id="fanwork_pet",
        source="user",
        distribution_boundary="private_local_fanwork",
    )

    warning = character_pack_distribution_warning(pack)
    text = character_pack_distribution_text(pack)

    assert "扩展角色包" in warning
    assert "本机角色库示例" in warning
    assert warning in text


def test_character_pack_import_review_text_keeps_source_note_guidance() -> None:
    text = character_pack_import_review_text(_summary())

    assert "导入角色包: xingxi_pixel_pet" in text
    assert "导入后会保留来源记录和 QA 说明" in text
