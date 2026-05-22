from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_EXPRESSION_PROVIDER = "openai"
DEFAULT_EXPRESSION_MODEL = "gpt-5.5"
DEFAULT_EXPRESSION_BASE_URL = "https://api.openai.com/v1/responses"
DEFAULT_EXPRESSION_TIMEOUT_SECONDS = 2.0
DISABLED_VOICE_PROVIDER = "disabled"
MAX_EXPRESSION_MODEL_LENGTH = 80
MAX_EXPRESSION_BASE_URL_LENGTH = 240
MAX_EXPRESSION_API_KEY_LENGTH = 512
MIN_EXPRESSION_TIMEOUT_SECONDS = 0.1
MAX_EXPRESSION_TIMEOUT_SECONDS = 5.0
CURRENT_EXPRESSION_SETTINGS_SCHEMA_VERSION = 1
ALLOWED_EXPRESSION_PROVIDERS = frozenset({"openai"})


@dataclass(frozen=True, slots=True)
class ExpressionSettings:
    enabled: bool = False
    provider: str = DEFAULT_EXPRESSION_PROVIDER
    model: str = DEFAULT_EXPRESSION_MODEL
    base_url: str = DEFAULT_EXPRESSION_BASE_URL
    api_key: str = ""
    timeout_seconds: float = DEFAULT_EXPRESSION_TIMEOUT_SECONDS
    tts_provider: str = DISABLED_VOICE_PROVIDER
    asr_provider: str = DISABLED_VOICE_PROVIDER

    def to_dict(self, *, include_api_key: bool = True) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "api_key": self.api_key if include_api_key else "",
            "api_key_set": bool(self.api_key),
            "timeout_seconds": self.timeout_seconds,
            "tts_provider": self.tts_provider,
            "asr_provider": self.asr_provider,
        }

    def to_public_dict(self) -> dict[str, object]:
        return self.to_dict(include_api_key=False)


@dataclass(frozen=True, slots=True)
class ExpressionSettingsStore:
    path: Path | str

    def load(self) -> ExpressionSettings:
        target = Path(self.path)
        if not target.exists():
            return ExpressionSettings()
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return ExpressionSettings()
        return normalize_expression_settings(payload)

    def save(self, settings: ExpressionSettings) -> None:
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": CURRENT_EXPRESSION_SETTINGS_SCHEMA_VERSION,
            **settings.to_dict(include_api_key=True),
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_expression_settings(payload: Mapping[str, Any] | object) -> ExpressionSettings:
    if not isinstance(payload, Mapping):
        return ExpressionSettings()
    return ExpressionSettings(
        enabled=_normalize_enabled(payload.get("enabled")),
        provider=_normalize_provider(payload.get("provider")),
        model=_normalize_model(payload.get("model")),
        base_url=_normalize_base_url(payload.get("base_url")),
        api_key=_normalize_api_key(payload.get("api_key")),
        timeout_seconds=_normalize_timeout(payload.get("timeout_seconds", payload.get("timeout"))),
        tts_provider=_normalize_disabled_voice_provider(payload.get("tts_provider")),
        asr_provider=_normalize_disabled_voice_provider(payload.get("asr_provider")),
    )


def _normalize_enabled(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and not _has_control_character(value):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _normalize_provider(value: object) -> str:
    provider = _clean_string(value, 40).lower()
    if provider in ALLOWED_EXPRESSION_PROVIDERS:
        return provider
    return DEFAULT_EXPRESSION_PROVIDER


def _normalize_model(value: object) -> str:
    model = _clean_string(value, MAX_EXPRESSION_MODEL_LENGTH)
    return model or DEFAULT_EXPRESSION_MODEL


def _normalize_base_url(value: object) -> str:
    base_url = _clean_string(value, MAX_EXPRESSION_BASE_URL_LENGTH)
    if base_url.startswith(("https://", "http://")):
        return base_url
    return DEFAULT_EXPRESSION_BASE_URL


def _normalize_api_key(value: object) -> str:
    return _clean_string(value, MAX_EXPRESSION_API_KEY_LENGTH)


def _normalize_disabled_voice_provider(value: object) -> str:
    return DISABLED_VOICE_PROVIDER


def _normalize_timeout(value: object) -> float:
    if isinstance(value, str):
        if _has_control_character(value):
            return DEFAULT_EXPRESSION_TIMEOUT_SECONDS
        value = value.strip()
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return DEFAULT_EXPRESSION_TIMEOUT_SECONDS
    if not math.isfinite(parsed):
        return DEFAULT_EXPRESSION_TIMEOUT_SECONDS
    if parsed < MIN_EXPRESSION_TIMEOUT_SECONDS or parsed > MAX_EXPRESSION_TIMEOUT_SECONDS:
        return DEFAULT_EXPRESSION_TIMEOUT_SECONDS
    return round(parsed, 2)


def _clean_string(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if _has_control_character(text) or len(text) > max_length:
        return ""
    return text


def _has_control_character(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)
