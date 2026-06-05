from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .runtime_paths import companion_assets_root


ASSETS_ROOT = companion_assets_root()
DEFAULT_CHARACTER_ID = "original_oc"


@dataclass(frozen=True, slots=True)
class CharacterRendererProfile:
    backend: str = "sprite"
    motion_map: dict[str, str] = field(default_factory=dict)
    expression_map: dict[str, str] = field(default_factory=dict)
    intent_map: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CharacterPack:
    character_id: str
    name: str
    title: str
    description: str
    spritesheet: str
    default_mode: str
    modes: tuple[str, ...]
    mode_descriptions: dict[str, str]
    motion_labels: dict[str, str]
    relationship_decorations: tuple[dict[str, str], ...] = ()
    renderer: CharacterRendererProfile = field(default_factory=CharacterRendererProfile)


def load_default_character_pack() -> CharacterPack:
    return load_character_pack(DEFAULT_CHARACTER_ID)


def load_character_pack(character_id: str) -> CharacterPack:
    return load_character_pack_from_dir(ASSETS_ROOT / character_id)


def load_character_pack_from_dir(asset_dir: Path | str) -> CharacterPack:
    manifest_path = Path(asset_dir) / "character.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return CharacterPack(
        character_id=payload["character_id"],
        name=payload["name"],
        title=payload["title"],
        description=payload["description"],
        spritesheet=payload["spritesheet"],
        default_mode=payload["default_mode"],
        modes=tuple(payload["modes"]),
        mode_descriptions=dict(payload["mode_descriptions"]),
        motion_labels=dict(payload["motion_labels"]),
        relationship_decorations=tuple(
            dict(entry)
            for entry in payload.get("relationship_decorations", [])
            if isinstance(entry, dict)
        ),
        renderer=_renderer_profile_from_payload(payload.get("renderer")),
    )


def resolve_motion_caption(pack: CharacterPack, motion: str, mode: str, allowed: bool) -> str:
    label = pack.motion_labels.get(motion, motion)
    mode_text = pack.mode_descriptions.get(mode, mode)
    if allowed:
        return f"{label} | {mode} | {mode_text}"
    return f"{label} | {mode} | 当前动作被拒绝"


def _renderer_profile_from_payload(value: object) -> CharacterRendererProfile:
    if not isinstance(value, dict):
        return CharacterRendererProfile()
    backend = value.get("backend")
    return CharacterRendererProfile(
        backend=backend if isinstance(backend, str) and backend else "sprite",
        motion_map=_string_map(value.get("motion_map")),
        expression_map=_string_map(value.get("expression_map")),
        intent_map=_string_map(value.get("intent_map")),
    )


def _string_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, str):
            result[key] = item
    return result
