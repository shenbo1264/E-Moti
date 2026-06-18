from __future__ import annotations

from pathlib import Path

from guanghe_companion.character_library_view_model import (
    character_pack_distribution_text,
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


def test_character_pack_distribution_text_keeps_provenance_and_license_relative() -> None:
    text = character_pack_distribution_text(_summary())

    assert "Distribution" in text
    assert "Source: builtin" in text
    assert "Distribution: shareable_after_review" in text
    assert "Provenance: provenance.md" in text
    assert "License: LICENSE.md" in text


def test_character_pack_import_review_text_warns_about_rights() -> None:
    text = character_pack_import_review_text(_summary())

    assert "Import character pack: xingxi_pixel_pet" in text
    assert "Only import packs you have rights to use and distribute." in text
