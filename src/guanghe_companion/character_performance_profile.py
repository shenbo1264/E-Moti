from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MAX_PROFILE_TEXT = 160
MAX_PROFILE_ITEMS = 24


@dataclass(frozen=True, slots=True)
class CharacterPerformanceProfile:
    character_id: str
    character_name: str
    speech_style: str
    allowed_expression_ids: tuple[str, ...]
    preferred_motion_ids: tuple[str, ...]
    forbidden_claims: tuple[str, ...] = ()


def load_character_performance_profile(pack_dir: Path | str) -> CharacterPerformanceProfile:
    root = Path(pack_dir)
    payload = _read_json(root / "character.json")
    style_payload = _read_json(root / "dialogue_style.json") if (root / "dialogue_style.json").exists() else {}
    renderer = payload.get("renderer") if isinstance(payload.get("renderer"), dict) else {}
    expression_map = renderer.get("expression_map") if isinstance(renderer.get("expression_map"), dict) else {}
    motion_map = renderer.get("motion_map") if isinstance(renderer.get("motion_map"), dict) else {}
    motion_labels = payload.get("motion_labels") if isinstance(payload.get("motion_labels"), dict) else {}
    motion_ids = tuple(
        _unique_clean_strings(
            [
                *(str(value) for value in motion_map.values()),
                *(str(key) for key in motion_labels),
            ]
        )
    )
    return CharacterPerformanceProfile(
        character_id=_clean_text(payload.get("character_id")) or root.name,
        character_name=_clean_text(payload.get("name")) or _clean_text(payload.get("character_id")) or root.name,
        speech_style=_clean_text(style_payload.get("speech_style"))
        or _default_speech_style(payload),
        allowed_expression_ids=tuple(_unique_clean_strings(str(key) for key in expression_map))[:MAX_PROFILE_ITEMS],
        preferred_motion_ids=motion_ids[:MAX_PROFILE_ITEMS],
        forbidden_claims=tuple(_unique_clean_strings(_style_list(style_payload.get("forbidden_claims")))),
    )


def profile_prompt_lines(profile: CharacterPerformanceProfile | None) -> tuple[str, ...]:
    if profile is None:
        return ()
    lines = [
        "Character performance profile:",
        f"Profile character: {_clean_text(profile.character_name) or 'unknown'}",
        f"Speech style: {_clean_text(profile.speech_style) or 'compact companion speech'}",
    ]
    if profile.allowed_expression_ids:
        lines.append(f"Allowed expression ids: {', '.join(profile.allowed_expression_ids)}")
    if profile.preferred_motion_ids:
        lines.append(f"Preferred motion ids: {', '.join(profile.preferred_motion_ids)}")
    for claim in profile.forbidden_claims[:8]:
        cleaned = _clean_text(claim)
        if cleaned:
            lines.append(f"Forbidden claim: {cleaned}")
    return tuple(lines)


def _default_speech_style(payload: dict[str, Any]) -> str:
    title = _clean_text(payload.get("title"))
    description = _clean_text(payload.get("description"))
    parts = [part for part in (title, description) if part]
    return " / ".join(parts)[:MAX_PROFILE_TEXT] if parts else "compact companion speech"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _style_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _unique_clean_strings(values) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
        if len(result) >= MAX_PROFILE_ITEMS:
            break
    return result


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split()).strip()
    return text[:MAX_PROFILE_TEXT]
