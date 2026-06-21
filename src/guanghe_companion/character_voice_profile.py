from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .capability_settings import (
    TTS_MODEL_VARIANT_ALIASES,
    TTS_PROVIDER_ALIASES,
)

ALLOWED_VOICE_SOURCE_TYPES = frozenset(
    {
        "original_design",
        "licensed_voice",
        "local_generated",
        "local_trained_clone",
        "third_party_reference",
    }
)
ALLOWED_TRAINING_STATUSES = frozenset(
    {"not_trained", "designed", "candidate", "trained_local", "blocked_rights"}
)
ALLOWED_DISTRIBUTION_POLICIES = frozenset({"public_ok", "local_only", "blocked"})
VOICE_REFERENCE_SUFFIXES = frozenset({".wav", ".mp3", ".flac", ".ogg", ".m4a"})


@dataclass(frozen=True, slots=True)
class CharacterVoiceProfile:
    profile_id: str = ""
    display_name: str = ""
    provider: str = ""
    api_url: str = ""
    language: str = ""
    voice: str = ""
    model_variant: str = ""
    rate: int | None = None
    volume: float | None = None
    instruct: str = ""
    voice_source_type: str = "original_design"
    training_status: str = "not_trained"
    distribution_policy: str = "public_ok"
    rights_note: str = ""
    reference_audio: tuple[str, ...] = ()
    defined: bool = False

    @classmethod
    def from_payload(cls, value: object) -> "CharacterVoiceProfile":
        if not isinstance(value, Mapping):
            return cls()
        provider = _clean_provider(
            value.get("provider"),
            default="",
            aliases=TTS_PROVIDER_ALIASES,
        )
        model_variant = _clean_provider(
            value.get("model_variant"),
            default="",
            aliases=TTS_MODEL_VARIANT_ALIASES,
        )
        return cls(
            profile_id=_clean_string(value.get("profile_id"), max_length=80),
            display_name=_clean_string(value.get("display_name"), max_length=120),
            provider=provider,
            api_url=_clean_string(value.get("api_url"), max_length=240),
            language=_clean_string(value.get("language"), max_length=16),
            voice=_clean_string(value.get("voice"), max_length=120),
            model_variant=model_variant,
            rate=_clean_int(value.get("rate"), minimum=-10, maximum=10),
            volume=_clean_float(value.get("volume"), minimum=0.0, maximum=1.0),
            instruct=_clean_string(value.get("instruct"), max_length=360),
            voice_source_type=_clean_choice(
                value.get("voice_source_type"),
                allowed=ALLOWED_VOICE_SOURCE_TYPES,
                default="original_design",
            ),
            training_status=_clean_choice(
                value.get("training_status"),
                allowed=ALLOWED_TRAINING_STATUSES,
                default="not_trained",
            ),
            distribution_policy=_clean_choice(
                value.get("distribution_policy"),
                allowed=ALLOWED_DISTRIBUTION_POLICIES,
                default="public_ok",
            ),
            rights_note=_clean_string(value.get("rights_note"), max_length=500),
            reference_audio=_reference_audio_tuple(value.get("reference_audio")),
            defined=True,
        )

    def to_runtime_dict(self) -> dict[str, object]:
        if not self.defined:
            return {}
        result: dict[str, object] = {}
        for key in (
            "profile_id",
            "display_name",
            "provider",
            "api_url",
            "language",
            "voice",
            "model_variant",
            "instruct",
            "voice_source_type",
            "training_status",
            "distribution_policy",
        ):
            value = getattr(self, key)
            if value:
                result[key] = value
        if self.rate is not None:
            result["rate"] = self.rate
        if self.volume is not None:
            result["volume"] = self.volume
        return result


def validate_voice_profile_payload(
    root: Path,
    payload: object,
    distribution_boundary: str,
    errors: list[str],
) -> None:
    if payload is None:
        return
    if not isinstance(payload, Mapping):
        errors.append("character.json.tts_profile must be an object")
        return

    _validate_choice(
        payload.get("voice_source_type"),
        allowed=ALLOWED_VOICE_SOURCE_TYPES,
        label="character.json.tts_profile.voice_source_type",
        errors=errors,
    )
    _validate_choice(
        payload.get("training_status"),
        allowed=ALLOWED_TRAINING_STATUSES,
        label="character.json.tts_profile.training_status",
        errors=errors,
    )
    _validate_choice(
        payload.get("distribution_policy"),
        allowed=ALLOWED_DISTRIBUTION_POLICIES,
        label="character.json.tts_profile.distribution_policy",
        errors=errors,
    )

    _ = distribution_boundary
    _validate_reference_audio(root, payload.get("reference_audio"), errors)


def _validate_reference_audio(root: Path, value: object, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        errors.append("character.json.tts_profile.reference_audio must be a list")
        return
    for index, item in enumerate(value):
        label = f"character.json.tts_profile.reference_audio.{index}"
        if not _safe_voice_reference_path(item):
            errors.append(f"{label} must stay inside voice/")
            continue
        resolved = (root / str(item)).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            errors.append(f"{label} must stay inside voice/")
            continue
        if not resolved.is_file():
            errors.append(f"{label} file not found: {item}")


def _safe_voice_reference_path(value: object) -> bool:
    if not isinstance(value, str) or not value.strip() or len(value) > 180:
        return False
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    path = Path(value)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and len(path.parts) >= 2
        and path.parts[0] == "voice"
        and path.suffix.lower() in VOICE_REFERENCE_SUFFIXES
    )


def _reference_audio_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    result: list[str] = []
    for item in value:
        cleaned = _clean_string(item, max_length=180)
        if cleaned:
            result.append(cleaned)
    return tuple(result)


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


def _clean_provider(value: object, *, default: str, aliases: Mapping[str, str]) -> str:
    raw = _clean_string(value, max_length=80).lower().replace("-", "_").replace(" ", "_")
    if not raw:
        return default
    return aliases.get(raw, default)


def _clean_choice(value: object, *, allowed: frozenset[str], default: str) -> str:
    raw = _clean_string(value, max_length=80)
    return raw if raw in allowed else default


def _validate_choice(
    value: object,
    *,
    allowed: frozenset[str],
    label: str,
    errors: list[str],
) -> None:
    if value is None:
        return
    if not isinstance(value, str) or value not in allowed:
        errors.append(f"{label} invalid")
