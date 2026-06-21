from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .runtime_paths import companion_assets_root


ASSETS_ROOT = companion_assets_root()
DEFAULT_CHARACTER_ID = "xingxi_pixel_pet"


@dataclass(frozen=True, slots=True)
class CharacterRendererProfile:
    backend: str = "sprite"
    model: str = ""
    portrait_manifest: str = ""
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
    tts_profile: dict[str, object] = field(default_factory=dict)


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
        tts_profile=_tts_profile_from_payload(payload.get("tts_profile")),
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
    model = value.get("model")
    portrait_manifest = value.get("portrait_manifest")
    return CharacterRendererProfile(
        backend=backend if isinstance(backend, str) and backend else "sprite",
        model=model if isinstance(model, str) else "",
        portrait_manifest=portrait_manifest if isinstance(portrait_manifest, str) else "",
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


def _tts_profile_from_payload(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    profile: dict[str, object] = {}
    voice = _clean_string(value.get("voice"), max_length=120)
    if voice:
        profile["voice"] = voice
    rate = _clean_int(value.get("rate"), minimum=-10, maximum=10)
    if rate is not None:
        profile["rate"] = rate
    volume = _clean_float(value.get("volume"), minimum=0.0, maximum=1.0)
    if volume is not None:
        profile["volume"] = volume
    return profile


def _clean_string(value: object, *, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value.strip())
    return cleaned[:max_length].strip()


def _clean_int(value: object, *, minimum: int, maximum: int) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(minimum, min(maximum, parsed))


def _clean_float(value: object, *, minimum: float, maximum: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return max(minimum, min(maximum, parsed))
