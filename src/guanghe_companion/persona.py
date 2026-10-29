"""Read-only, versioned character identity, separate from memory and mood.

Existing character packs work unchanged. An explicitly supplied pack directory
may contain ``persona.json`` with schema_version=1, optional character_id,
identity_version, speech_style, traits, preferences, interaction_habits and
boundaries. For example, an author may opt into traits ["好奇", "有主见"] and
speech_style "自然，偶尔轻轻吐槽"; these are not imposed on other characters.

Only author/user configuration is read here. There is deliberately no mutation
API, model-output input, memory extraction, or mood/relationship parameter.
Future personality growth should produce a sourced proposal for user approval,
then create a new configuration version outside the dialogue path.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .character_pack import CharacterPack
from .character_performance_profile import CharacterPerformanceProfile


PERSONA_SCHEMA_VERSION = 1
MAX_PERSONA_FILE_BYTES = 32_768
MAX_PERSONA_TEXT = 500
MAX_PERSONA_ITEMS = 12
MAX_PERSONA_ITEM_TEXT = 160


@dataclass(frozen=True, slots=True)
class PersonaProfile:
    character_id: str
    character_name: str
    title: str
    description: str
    speech_style: str
    traits: tuple[str, ...]
    preferences: tuple[str, ...]
    interaction_habits: tuple[str, ...]
    boundaries: tuple[str, ...]
    identity_version: str
    config_hash: str
    source: str
    validation_warnings: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        """Return a detached snapshot; changing it cannot mutate this identity."""
        return {
            "schema_version": PERSONA_SCHEMA_VERSION,
            "character_id": self.character_id,
            "character_name": self.character_name,
            "title": self.title,
            "description": self.description,
            "speech_style": self.speech_style,
            "traits": list(self.traits),
            "preferences": list(self.preferences),
            "interaction_habits": list(self.interaction_habits),
            "boundaries": list(self.boundaries),
            "identity_version": self.identity_version,
            "config_hash": self.config_hash,
            "source": self.source,
            "validation_warnings": list(self.validation_warnings),
        }


def build_persona_payload(
    pack: CharacterPack,
    performance_profile: CharacterPerformanceProfile | None = None,
    *,
    pack_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Build model-facing identity from the active pack and optional local file.

    ``pack_dir`` must be the directory resolved by CharacterResources, never a
    path supplied by a model. Without it this function performs no file I/O.
    No chat history or user facts are consumed or synthesized.
    """
    return load_persona_profile(pack, performance_profile, pack_dir=pack_dir).to_payload()


def load_persona_profile(
    pack: CharacterPack,
    performance_profile: CharacterPerformanceProfile | None = None,
    *,
    pack_dir: Path | str | None = None,
) -> PersonaProfile:
    warnings: list[str] = []
    if performance_profile is not None and performance_profile.character_id != pack.character_id:
        warnings.append("performance_character_mismatch")
        performance_profile = None

    config, file_warning = _read_persona_config(pack_dir, pack.character_id)
    if file_warning:
        warnings.append(file_warning)
    source = "persona.json" if config is not None else "character_pack"
    config = config or {}

    title = _clean_text(pack.title, MAX_PERSONA_ITEM_TEXT)
    description = _clean_text(pack.description)
    legacy_style = _clean_text(performance_profile.speech_style) if performance_profile else ""
    if not legacy_style:
        legacy_style = _clean_text(" / ".join(value for value in (title, description) if value))

    # Identity names remain authoritative in character.json. The optional file
    # configures expression, not a second character or a user profile.
    identity: dict[str, Any] = {
        "schema_version": PERSONA_SCHEMA_VERSION,
        "character_id": _clean_text(pack.character_id, MAX_PERSONA_ITEM_TEXT),
        "character_name": _clean_text(pack.name, MAX_PERSONA_ITEM_TEXT),
        "title": title,
        "description": description,
        "speech_style": _clean_text(config.get("speech_style")) or legacy_style or "compact companion speech",
        "traits": _clean_items(config.get("traits")),
        "preferences": _clean_items(config.get("preferences")),
        "interaction_habits": _clean_items(config.get("interaction_habits")),
        "boundaries": _clean_items([
            *(performance_profile.forbidden_claims if performance_profile else ()),
            *_clean_items(config.get("boundaries")),
        ]),
        "identity_version": _clean_text(config.get("identity_version"), 64) or "pack-v1",
    }
    # Hash only the effective authored identity. File location, validation
    # diagnostics, incidental JSON key order, mood and memory are excluded.
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return PersonaProfile(
        character_id=identity["character_id"],
        character_name=identity["character_name"],
        title=identity["title"],
        description=identity["description"],
        speech_style=identity["speech_style"],
        traits=tuple(identity["traits"]),
        preferences=tuple(identity["preferences"]),
        interaction_habits=tuple(identity["interaction_habits"]),
        boundaries=tuple(identity["boundaries"]),
        identity_version=identity["identity_version"],
        config_hash=hashlib.sha256(encoded).hexdigest(),
        source=source,
        validation_warnings=tuple(warnings),
    )


def _read_persona_config(
    pack_dir: Path | str | None,
    character_id: str,
) -> tuple[dict[str, Any] | None, str]:
    if pack_dir is None:
        return None, ""
    try:
        root = Path(pack_dir).resolve(strict=True)
        candidate = root / "persona.json"
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            return None, ""
        # A character file must be a bounded regular file inside its pack.
        # Reject symlinks (including internal ones) to keep imports portable.
        if not stat.S_ISREG(metadata.st_mode):
            return None, "persona_not_regular_file"
        if metadata.st_size > MAX_PERSONA_FILE_BYTES:
            return None, "persona_file_too_large"
        descriptor = os.open(candidate, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return None, "persona_not_regular_file"
            raw = handle.read(MAX_PERSONA_FILE_BYTES + 1)
        if len(raw) > MAX_PERSONA_FILE_BYTES:
            return None, "persona_file_too_large"
        payload = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError, UnicodeError, RecursionError):
        return None, "persona_file_unreadable"
    if not isinstance(payload, dict):
        return None, "persona_not_object"
    version = payload.get("schema_version", PERSONA_SCHEMA_VERSION)
    if type(version) is not int or version != PERSONA_SCHEMA_VERSION:
        return None, "persona_schema_unsupported"
    if "character_id" in payload and payload["character_id"] != character_id:
        return None, "persona_character_mismatch"
    return payload, ""


def _clean_text(value: object, limit: int = MAX_PERSONA_TEXT) -> str:
    if not isinstance(value, str):
        return ""
    # Character-pack text is data. Normalize controls and whitespace before it
    # enters a bounded prompt field; this is not a prompt-injection detector.
    text = "".join(" " if unicodedata.category(char).startswith("C") else char for char in value)
    return " ".join(text.split())[:limit].strip()


def _clean_items(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    result: list[str] = []
    for item in value:
        cleaned = _clean_text(item, MAX_PERSONA_ITEM_TEXT)
        if cleaned and cleaned not in result:
            result.append(cleaned)
        if len(result) >= MAX_PERSONA_ITEMS:
            break
    return result
