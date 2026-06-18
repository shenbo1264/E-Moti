from __future__ import annotations

from pathlib import Path

from .character_registry import CharacterPackSummary


def character_pack_distribution_text(pack: CharacterPackSummary) -> str:
    return "\n".join(
        (
            "Distribution",
            f"Source: {pack.source}",
            f"Distribution: {pack.distribution_boundary}",
            f"Provenance: {_relative_pack_paths(pack, pack.provenance_paths)}",
            f"License: {_relative_pack_paths(pack, pack.license_paths)}",
        )
    )


def character_pack_import_review_text(pack: CharacterPackSummary) -> str:
    return "\n\n".join(
        (
            f"Import character pack: {pack.character_id}",
            f"{pack.name}\n{pack.title}",
            character_pack_distribution_text(pack),
            "Only import packs you have rights to use and distribute.",
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
