from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TTSProviderOption:
    provider_id: str
    label: str
    recommended_use: str
    default_model: str
    default_api_url: str
    route_note: str


@dataclass(frozen=True, slots=True)
class ASRProviderOption:
    provider_id: str
    label: str
    transcriber_family: str
    recommended_use: str
    default_model: str
    default_base_url: str
    route_note: str


TTS_PROVIDER_OPTIONS: tuple[TTSProviderOption, ...] = (
    TTSProviderOption(
        provider_id="http_qwen3tts",
        label="Qwen3-TTS HTTP",
        recommended_use="formal_character_voice",
        default_model="qwen3tts_0.6b_customvoice",
        default_api_url="http://127.0.0.1:9880/",
        route_note="Formal route for original character voice through a local HTTP service.",
    ),
    TTSProviderOption(
        provider_id="http_gptsovits",
        label="GPT-SoVITS HTTP",
        recommended_use="trained_character_voice",
        default_model="gptsovits_v2",
        default_api_url="http://127.0.0.1:9882/",
        route_note="Local trained-character route that uses reference audio and prompt text.",
    ),
    TTSProviderOption(
        provider_id="edge_tts",
        label="Edge Neural TTS",
        recommended_use="manual_fallback",
        default_model="",
        default_api_url="",
        route_note="Zero-key online fallback for private preview only; not the formal default route.",
    ),
    TTSProviderOption(
        provider_id="windows_sapi",
        label="Windows SAPI",
        recommended_use="offline_fallback",
        default_model="",
        default_api_url="",
        route_note="Windows built-in fallback; limited character expressiveness.",
    ),
)

ASR_PROVIDER_OPTIONS: tuple[ASRProviderOption, ...] = (
    ASRProviderOption(
        provider_id="sensevoice_openai",
        label="SenseVoice OpenAI-compatible",
        transcriber_family="openai_compatible",
        recommended_use="emotion_aware_asr",
        default_model="sensevoice",
        default_base_url="http://127.0.0.1:8899/v1",
        route_note="Emotion-aware ASR route; transcript still enters only as player text.",
    ),
    ASRProviderOption(
        provider_id="funasr_openai",
        label="FunASR OpenAI-compatible",
        transcriber_family="openai_compatible",
        recommended_use="local_asr_first",
        default_model="paraformer-zh",
        default_base_url="http://127.0.0.1:8899/v1",
        route_note="Local ASR route that reuses the multipart transcription adapter.",
    ),
    ASRProviderOption(
        provider_id="qwen3_asr_openai",
        label="Qwen3-ASR OpenAI-compatible",
        transcriber_family="openai_compatible",
        recommended_use="high_quality_asr",
        default_model="qwen3-asr",
        default_base_url="http://127.0.0.1:10096/v1",
        route_note="Higher-quality follow-up route when a local gateway is available.",
    ),
    ASRProviderOption(
        provider_id="openai_compatible",
        label="OpenAI-compatible ASR",
        transcriber_family="openai_compatible",
        recommended_use="generic_cloud_or_local",
        default_model="whisper-1",
        default_base_url="",
        route_note="Generic transcription endpoint adapter.",
    ),
    ASRProviderOption(
        provider_id="vosk",
        label="Vosk offline",
        transcriber_family="vosk",
        recommended_use="offline_fallback",
        default_model="",
        default_base_url="",
        route_note="Offline fallback; requires local model path.",
    ),
)


def tts_provider_ids() -> tuple[str, ...]:
    return tuple(option.provider_id for option in TTS_PROVIDER_OPTIONS)


def asr_provider_ids() -> tuple[str, ...]:
    return tuple(option.provider_id for option in ASR_PROVIDER_OPTIONS)


def tts_provider_option(provider_id: str) -> TTSProviderOption:
    for option in TTS_PROVIDER_OPTIONS:
        if option.provider_id == provider_id:
            return option
    return TTS_PROVIDER_OPTIONS[0]


def asr_provider_option(provider_id: str) -> ASRProviderOption:
    for option in ASR_PROVIDER_OPTIONS:
        if option.provider_id == provider_id:
            return option
    return ASR_PROVIDER_OPTIONS[0]
