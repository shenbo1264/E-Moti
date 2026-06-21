from __future__ import annotations


def test_voice_provider_catalog_exposes_formal_and_preview_tts_routes() -> None:
    from guanghe_companion.voice_provider_catalog import tts_provider_ids, tts_provider_option

    assert tts_provider_ids() == ("http_qwen3tts", "edge_tts", "windows_sapi")
    assert tts_provider_option("edge_tts").label == "Edge Neural TTS"
    assert tts_provider_option("http_qwen3tts").recommended_use == "formal_character_voice"
    assert tts_provider_option("http_qwen3tts").default_model == "qwen3tts_0.6b_customvoice"


def test_voice_provider_catalog_exposes_openai_compatible_asr_routes() -> None:
    from guanghe_companion.voice_provider_catalog import asr_provider_ids, asr_provider_option

    assert asr_provider_ids() == (
        "sensevoice_openai",
        "funasr_openai",
        "qwen3_asr_openai",
        "openai_compatible",
        "vosk",
    )
    assert asr_provider_option("funasr_openai").transcriber_family == "openai_compatible"
    assert asr_provider_option("sensevoice_openai").default_model == "sensevoice"
    assert asr_provider_option("qwen3_asr_openai").recommended_use == "high_quality_asr"
