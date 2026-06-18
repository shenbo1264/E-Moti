from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .runtime_paths import user_data_dir

SAFE_CHARACTER_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
CURRENT_CHARACTER_SESSION_METADATA_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class CharacterSessionPaths:
    character_id: str
    character_dir: Path
    save_path: Path
    dialogue_history_path: Path
    long_term_memory_path: Path
    expression_settings_path: Path
    pack_metadata_path: Path


def is_safe_character_id(character_id: str) -> bool:
    return isinstance(character_id, str) and bool(SAFE_CHARACTER_ID_PATTERN.fullmatch(character_id))


def build_character_session_paths(
    character_id: str,
    *,
    user_data_root: Path | str | None = None,
) -> CharacterSessionPaths:
    if not is_safe_character_id(character_id):
        raise ValueError(f"unsafe character_id: {character_id!r}")

    root = Path(user_data_root) if user_data_root is not None else user_data_dir()
    character_dir = root / "characters" / character_id
    return CharacterSessionPaths(
        character_id=character_id,
        character_dir=character_dir,
        save_path=character_dir / "companion_save.json",
        dialogue_history_path=character_dir / "dialogue_history.json",
        long_term_memory_path=character_dir / "long_term_memory.json",
        expression_settings_path=character_dir / "expression_settings.json",
        pack_metadata_path=character_dir / "pack_metadata.json",
    )


def write_character_session_pack_metadata(
    paths: CharacterSessionPaths,
    *,
    pack_name: str,
    asset_dir: Path | str,
    renderer_backend: str,
    spritesheet: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": CURRENT_CHARACTER_SESSION_METADATA_SCHEMA_VERSION,
        "character_id": paths.character_id,
        "pack_name": str(pack_name),
        "asset_dir": str(Path(asset_dir)),
        "renderer_backend": str(renderer_backend),
        "spritesheet": str(spritesheet),
    }
    paths.character_dir.mkdir(parents=True, exist_ok=True)
    paths.pack_metadata_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload
