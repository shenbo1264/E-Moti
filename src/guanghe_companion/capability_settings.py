from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

DEFAULT_SCREEN_OBSERVATION_PROVIDER = "openai_compatible"
DEFAULT_WEB_SEARCH_ENGINE = "duckduckgo"
DEFAULT_TTS_PROVIDER = "http_qwen3tts"
DEFAULT_TTS_API_URL = "http://127.0.0.1:9880/"
DEFAULT_TTS_MODEL_VARIANT = "qwen3tts_0.6b_customvoice"
DEFAULT_ASR_PROVIDER = "sensevoice_openai"
DEFAULT_ASR_MODEL = "sensevoice"
DEFAULT_ASR_BASE_URL = "http://127.0.0.1:8899/v1"
DEFAULT_ASR_API_KEY = "local"
DEFAULT_ASR_HOTKEY_SEQUENCE = "Ctrl+Alt+M"

SCREEN_OBSERVATION_PROVIDER_ALIASES = {
    "openai": "openai_compatible",
    "openai_compatible": "openai_compatible",
}
WEB_SEARCH_ENGINE_ALIASES = {
    "ddg": "duckduckgo",
    "duckduckgo": "duckduckgo",
}
TTS_PROVIDER_ALIASES = {
    "windows_sapi": "windows_sapi",
    "sapi": "windows_sapi",
    "edge": "edge_tts",
    "edge_tts": "edge_tts",
    "edge_neural": "edge_tts",
    "http_qwen3tts": "http_qwen3tts",
    "qwen3tts": "http_qwen3tts",
    "qwen3_tts": "http_qwen3tts",
}
TTS_MODEL_VARIANT_ALIASES = {
    "1.7b": "qwen3tts_1.7b_customvoice",
    "1_7b": "qwen3tts_1.7b_customvoice",
    "1.6b": "qwen3tts_1.7b_customvoice",
    "1_6b": "qwen3tts_1.7b_customvoice",
    "qwen3tts_1.7b": "qwen3tts_1.7b_customvoice",
    "qwen3tts_1_7b": "qwen3tts_1.7b_customvoice",
    "qwen3tts_1.7b_customvoice": "qwen3tts_1.7b_customvoice",
    "qwen3tts_1_7b_customvoice": "qwen3tts_1.7b_customvoice",
    "qwen3tts_1.6b": "qwen3tts_1.7b_customvoice",
    "qwen3tts_1_6b": "qwen3tts_1.7b_customvoice",
    "standard": "qwen3tts_1.7b_customvoice",
    "std": "qwen3tts_1.7b_customvoice",
    "0.6b": "qwen3tts_0.6b_customvoice",
    "0_6b": "qwen3tts_0.6b_customvoice",
    "0.7b": "qwen3tts_0.6b_customvoice",
    "0_7b": "qwen3tts_0.6b_customvoice",
    "qwen3tts_0.6b": "qwen3tts_0.6b_customvoice",
    "qwen3tts_0_6b": "qwen3tts_0.6b_customvoice",
    "qwen3tts_0.6b_customvoice": "qwen3tts_0.6b_customvoice",
    "qwen3tts_0_6b_customvoice": "qwen3tts_0.6b_customvoice",
    "qwen3tts_0.7b": "qwen3tts_0.6b_customvoice",
    "qwen3tts_0_7b": "qwen3tts_0.6b_customvoice",
    "low": "qwen3tts_0.6b_customvoice",
    "lite": "qwen3tts_0.6b_customvoice",
}
ASR_PROVIDER_ALIASES = {
    "openai": "openai_compatible",
    "openai_compatible": "openai_compatible",
    "whisper": "openai_compatible",
    "funasr": "funasr_openai",
    "funasr_openai": "funasr_openai",
    "sensevoice": "sensevoice_openai",
    "sensevoice_openai": "sensevoice_openai",
    "qwen3_asr": "qwen3_asr_openai",
    "qwen3_asr_openai": "qwen3_asr_openai",
    "vosk": "vosk",
}


@dataclass(frozen=True, slots=True)
class ScreenObservationSettings:
    enabled: bool = False
    auto_enabled: bool = False
    interval_seconds: int = 60
    max_screenshot_width: int = 1280
    send_screenshot_to_vision: bool = True
    vision_provider: str = DEFAULT_SCREEN_OBSERVATION_PROVIDER
    vision_model: str = ""
    vision_base_url: str = ""
    vision_api_key: str = ""
    timeout_seconds: int = 30

    @classmethod
    def from_dict(cls, data: object) -> "ScreenObservationSettings":
        source = _mapping(data)
        return cls(
            enabled=_clean_bool(source.get("enabled")),
            auto_enabled=_clean_bool(source.get("auto_enabled")),
            interval_seconds=_clean_int(source.get("interval_seconds"), default=60, minimum=10, maximum=600),
            max_screenshot_width=_clean_int(
                source.get("max_screenshot_width"),
                default=1280,
                minimum=640,
                maximum=1920,
            ),
            send_screenshot_to_vision=_clean_bool(source.get("send_screenshot_to_vision"), default=True),
            vision_provider=_clean_provider(
                source.get("vision_provider"),
                default=DEFAULT_SCREEN_OBSERVATION_PROVIDER,
                aliases=SCREEN_OBSERVATION_PROVIDER_ALIASES,
            ),
            vision_model=_clean_string(source.get("vision_model"), max_length=120),
            vision_base_url=_clean_string(source.get("vision_base_url"), max_length=240),
            vision_api_key=_clean_string(source.get("vision_api_key"), max_length=400),
            timeout_seconds=_clean_int(source.get("timeout_seconds"), default=30, minimum=5, maximum=120),
        )


@dataclass(frozen=True, slots=True)
class WebSearchSettings:
    enabled: bool = False
    engine: str = DEFAULT_WEB_SEARCH_ENGINE
    max_results: int = 3
    timeout_seconds: int = 10
    show_sources: bool = True

    @classmethod
    def from_dict(cls, data: object) -> "WebSearchSettings":
        source = _mapping(data)
        return cls(
            enabled=_clean_bool(source.get("enabled")),
            engine=_clean_provider(
                source.get("engine"),
                default=DEFAULT_WEB_SEARCH_ENGINE,
                aliases=WEB_SEARCH_ENGINE_ALIASES,
            ),
            max_results=_clean_int(source.get("max_results"), default=3, minimum=1, maximum=5),
            timeout_seconds=_clean_int(source.get("timeout_seconds"), default=10, minimum=3, maximum=60),
            show_sources=_clean_bool(source.get("show_sources"), default=True),
        )


@dataclass(frozen=True, slots=True)
class TTSSettings:
    enabled: bool = False
    provider: str = DEFAULT_TTS_PROVIDER
    api_url: str = DEFAULT_TTS_API_URL
    language: str = "zh"
    profile_id: str = ""
    voice: str = ""
    model_variant: str = DEFAULT_TTS_MODEL_VARIANT
    instruct: str = ""
    rate: int = 0
    volume: float = 1.0
    auto_speak: bool = False

    @classmethod
    def from_dict(cls, data: object) -> "TTSSettings":
        source = _mapping(data)
        return cls(
            enabled=_clean_bool(source.get("enabled")),
            provider=_clean_provider(
                source.get("provider"),
                default=DEFAULT_TTS_PROVIDER,
                aliases=TTS_PROVIDER_ALIASES,
            ),
            api_url=_clean_string(source.get("api_url"), max_length=240) or DEFAULT_TTS_API_URL,
            language=_clean_string(source.get("language"), max_length=16) or "zh",
            profile_id=_clean_string(source.get("profile_id"), max_length=80),
            voice=_clean_string(source.get("voice"), max_length=120),
            model_variant=_clean_provider(
                source.get("model_variant"),
                default=DEFAULT_TTS_MODEL_VARIANT,
                aliases=TTS_MODEL_VARIANT_ALIASES,
            ),
            instruct=_clean_string(source.get("instruct"), max_length=360),
            rate=_clean_int(source.get("rate"), default=0, minimum=-10, maximum=10),
            volume=_clean_float(source.get("volume"), default=1.0, minimum=0.0, maximum=1.0),
            auto_speak=_clean_bool(source.get("auto_speak")),
        )


@dataclass(frozen=True, slots=True)
class ASRSettings:
    enabled: bool = False
    provider: str = DEFAULT_ASR_PROVIDER
    model: str = DEFAULT_ASR_MODEL
    base_url: str = DEFAULT_ASR_BASE_URL
    api_key: str = DEFAULT_ASR_API_KEY
    language: str = "zh"
    vosk_model_path: str = ""
    auto_send: bool = False
    hotkey_enabled: bool = False
    hotkey_sequence: str = DEFAULT_ASR_HOTKEY_SEQUENCE
    max_record_seconds: int = 12

    @classmethod
    def from_dict(cls, data: object) -> "ASRSettings":
        source = _mapping(data)
        provider = _clean_provider(
            source.get("provider"),
            default=DEFAULT_ASR_PROVIDER,
            aliases=ASR_PROVIDER_ALIASES,
        )
        return cls(
            enabled=_clean_bool(source.get("enabled")),
            provider=provider,
            model=_clean_string(source.get("model"), max_length=120) or _default_asr_model(provider),
            base_url=_clean_string(source.get("base_url"), max_length=240) or _default_asr_base_url(provider),
            api_key=_clean_string(source.get("api_key"), max_length=400) or _default_asr_api_key(provider),
            language=_clean_string(source.get("language"), max_length=16) or "zh",
            vosk_model_path=_clean_string(source.get("vosk_model_path"), max_length=500),
            auto_send=_clean_bool(source.get("auto_send")),
            hotkey_enabled=_clean_bool(source.get("hotkey_enabled")),
            hotkey_sequence=_clean_string(source.get("hotkey_sequence"), max_length=80)
            or DEFAULT_ASR_HOTKEY_SEQUENCE,
            max_record_seconds=_clean_int(source.get("max_record_seconds"), default=12, minimum=1, maximum=30),
        )


@dataclass(frozen=True, slots=True)
class ProactiveCompanionSettings:
    enabled: bool = False
    interval_seconds: int = 900
    global_cooldown_seconds: int = 1800
    daily_limit: int = 8
    quiet_hours_enabled: bool = False
    quiet_start: str = "23:00"
    quiet_end: str = "08:00"
    allow_context_topic: bool = True

    @classmethod
    def from_dict(cls, data: object) -> "ProactiveCompanionSettings":
        source = _mapping(data)
        return cls(
            enabled=_clean_bool(source.get("enabled")),
            interval_seconds=_clean_int(
                source.get("interval_seconds"),
                default=900,
                minimum=60,
                maximum=86_400,
            ),
            global_cooldown_seconds=_clean_int(
                source.get("global_cooldown_seconds"),
                default=1800,
                minimum=60,
                maximum=86_400,
            ),
            daily_limit=_clean_int(source.get("daily_limit"), default=8, minimum=1, maximum=24),
            quiet_hours_enabled=_clean_bool(source.get("quiet_hours_enabled")),
            quiet_start=_clean_time_string(source.get("quiet_start"), default="23:00"),
            quiet_end=_clean_time_string(source.get("quiet_end"), default="08:00"),
            allow_context_topic=_clean_bool(source.get("allow_context_topic"), default=True),
        )


@dataclass(frozen=True, slots=True)
class CapabilitySettings:
    screen_observation: ScreenObservationSettings = field(default_factory=ScreenObservationSettings)
    web_search: WebSearchSettings = field(default_factory=WebSearchSettings)
    tts: TTSSettings = field(default_factory=TTSSettings)
    asr: ASRSettings = field(default_factory=ASRSettings)
    proactive_companion: ProactiveCompanionSettings = field(default_factory=ProactiveCompanionSettings)

    @classmethod
    def default(cls) -> "CapabilitySettings":
        return cls()

    @classmethod
    def from_dict(cls, data: object) -> "CapabilitySettings":
        source = _mapping(data)
        return cls(
            screen_observation=ScreenObservationSettings.from_dict(source.get("screen_observation")),
            web_search=WebSearchSettings.from_dict(source.get("web_search")),
            tts=TTSSettings.from_dict(source.get("tts")),
            asr=ASRSettings.from_dict(source.get("asr")),
            proactive_companion=ProactiveCompanionSettings.from_dict(source.get("proactive_companion")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_public_dict(self) -> dict[str, Any]:
        public = self.to_dict()
        if public["screen_observation"].get("vision_api_key"):
            public["screen_observation"]["vision_api_key"] = "***"
        if public["asr"].get("api_key"):
            public["asr"]["api_key"] = "***"
        return public


@dataclass(frozen=True, slots=True)
class CapabilitySettingsStore:
    path: Path | str

    def load(self) -> CapabilitySettings:
        target = Path(self.path)
        if not target.exists():
            return CapabilitySettings.default()
        try:
            raw = json.loads(target.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return CapabilitySettings.default()
        return CapabilitySettings.from_dict(raw)

    def save(self, settings: CapabilitySettings) -> CapabilitySettings:
        normalized = CapabilitySettings.from_dict(settings.to_dict())
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(normalized.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return normalized


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _clean_bool(value: object, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def _clean_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _clean_float(value: object, *, default: float, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _clean_provider(value: object, *, default: str, aliases: Mapping[str, str]) -> str:
    raw = _clean_string(value, max_length=80).lower().replace("-", "_").replace(" ", "_")
    if not raw:
        return default
    return aliases.get(raw, default)


def _clean_string(value: object, *, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value.strip())
    return cleaned[:max_length]


def _default_asr_model(provider: str) -> str:
    if provider == "sensevoice_openai":
        return "sensevoice"
    if provider == "funasr_openai":
        return "paraformer-zh"
    if provider == "qwen3_asr_openai":
        return "qwen3-asr"
    if provider == "vosk":
        return ""
    return "whisper-1"


def _default_asr_base_url(provider: str) -> str:
    if provider in {"funasr_openai", "sensevoice_openai"}:
        return "http://127.0.0.1:8899/v1"
    if provider == "qwen3_asr_openai":
        return "http://127.0.0.1:10096/v1"
    return ""


def _default_asr_api_key(provider: str) -> str:
    if provider in {"funasr_openai", "sensevoice_openai", "qwen3_asr_openai"}:
        return "local"
    return ""


def _clean_time_string(value: object, *, default: str) -> str:
    raw = _clean_string(value, max_length=5)
    if len(raw) not in {4, 5} or ":" not in raw:
        return default
    hour_text, minute_text = raw.split(":", 1)
    if not hour_text.isdigit() or not minute_text.isdigit():
        return default
    hour = int(hour_text)
    minute = int(minute_text)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return default
    return f"{hour:02d}:{minute:02d}"
