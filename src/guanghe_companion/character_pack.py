from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


ASSETS_ROOT = Path(__file__).resolve().parents[2] / "assets" / "companion"
DEFAULT_CHARACTER_ID = "original_oc"


@dataclass(frozen=True, slots=True)
class CharacterPack:
    character_id: str
    name: str
    title: str
    description: str
    default_mode: str
    modes: tuple[str, ...]
    mode_descriptions: dict[str, str]
    motion_labels: dict[str, str]


def load_default_character_pack() -> CharacterPack:
    return load_character_pack(DEFAULT_CHARACTER_ID)


def load_character_pack(character_id: str) -> CharacterPack:
    manifest_path = ASSETS_ROOT / character_id / "character.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return CharacterPack(
        character_id=payload["character_id"],
        name=payload["name"],
        title=payload["title"],
        description=payload["description"],
        default_mode=payload["default_mode"],
        modes=tuple(payload["modes"]),
        mode_descriptions=dict(payload["mode_descriptions"]),
        motion_labels=dict(payload["motion_labels"]),
    )


def resolve_motion_caption(pack: CharacterPack, motion: str, mode: str, allowed: bool) -> str:
    label = pack.motion_labels.get(motion, motion)
    mode_text = pack.mode_descriptions.get(mode, mode)
    if allowed:
        return f"{label} | {mode} | {mode_text}"
    return f"{label} | {mode} | 当前动作被拒绝"
