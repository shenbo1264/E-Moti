from __future__ import annotations


def test_voice_provider_catalog_exposes_formal_and_preview_tts_routes() -> None:
    from guanghe_companion.voice_provider_catalog import tts_provider_ids, tts_provider_option

    assert tts_provider_ids() == ("edge_tts", "http_qwen3tts", "windows_sapi")
    assert tts_provider_option("edge_tts").label == "Edge Neural TTS"
    assert tts_provider_option("http_qwen3tts").recommended_use == "formal_character_voice"
    assert tts_provider_option("http_qwen3tts").default_model == "qwen3tts_1.6b"


def test_voice_provider_catalog_exposes_openai_compatible_asr_routes() -> None:
    from guanghe_companion.voice_provider_catalog import asr_provider_ids, asr_provider_option

    assert asr_provider_ids() == (
        "openai_compatible",
        "funasr_openai",
        "sensevoice_openai",
        "qwen3_asr_openai",
        "vosk",
    )
    assert asr_provider_option("funasr_openai").transcriber_family == "openai_compatible"
    assert asr_provider_option("sensevoice_openai").default_model == "iic/SenseVoiceSmall"
    assert asr_provider_option("qwen3_asr_openai").recommended_use == "high_quality_asr"
