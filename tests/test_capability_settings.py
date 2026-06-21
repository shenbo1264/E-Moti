from __future__ import annotations

import json


def test_default_capabilities_are_disabled() -> None:
    from guanghe_companion.capability_settings import CapabilitySettings

    settings = CapabilitySettings.default()

    assert settings.screen_observation.enabled is False
    assert settings.screen_observation.auto_enabled is False
    assert settings.web_search.enabled is False
    assert settings.tts.enabled is False
    assert settings.tts.auto_speak is False
    assert settings.tts.model_variant == "qwen3tts_1.6b"
    assert settings.asr.enabled is False
    assert settings.asr.auto_send is False
    assert settings.proactive_companion.enabled is False
    assert settings.proactive_companion.interval_seconds == 900
    assert settings.proactive_companion.global_cooldown_seconds == 1800
    assert settings.proactive_companion.daily_limit == 8
    assert settings.proactive_companion.quiet_hours_enabled is False
    assert settings.proactive_companion.quiet_start == "23:00"
    assert settings.proactive_companion.quiet_end == "08:00"
    assert settings.proactive_companion.allow_context_topic is True


def test_store_round_trips_bom_json_and_redacts_secrets(tmp_path) -> None:
    from guanghe_companion.capability_settings import CapabilitySettingsStore

    path = tmp_path / "capability_settings.json"
    path.write_text(
        "\ufeff"
        + json.dumps(
            {
                "screen_observation": {
                    "enabled": True,
                    "auto_enabled": True,
                    "interval_seconds": 1,
                    "max_screenshot_width": 9999,
                    "vision_base_url": " https://vision.example.test/v1/ ",
                    "vision_api_key": "vision-secret",
                    "timeout_seconds": 999,
                },
                "web_search": {"enabled": True, "engine": "ddg", "max_results": 99},
                "tts": {
                    "enabled": True,
                    "provider": "http-qwen3tts",
                    "model_variant": "0.7B",
                    "volume": 2.5,
                },
                "asr": {
                    "enabled": True,
                    "provider": "OPENAI",
                    "api_key": "asr-secret",
                    "max_record_seconds": 99,
                },
                "proactive_companion": {
                    "enabled": True,
                    "interval_seconds": 1,
                    "global_cooldown_seconds": 1,
                    "daily_limit": 99,
                    "quiet_hours_enabled": True,
                    "quiet_start": "25:99",
                    "quiet_end": "bad",
                    "allow_context_topic": False,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    settings = CapabilitySettingsStore(path).load()

    assert settings.screen_observation.enabled is True
    assert settings.screen_observation.interval_seconds == 10
    assert settings.screen_observation.max_screenshot_width == 1920
    assert settings.screen_observation.vision_base_url == "https://vision.example.test/v1/"
    assert settings.screen_observation.timeout_seconds == 120
    assert settings.web_search.engine == "duckduckgo"
    assert settings.web_search.max_results == 5
    assert settings.tts.provider == "http_qwen3tts"
    assert settings.tts.model_variant == "qwen3tts_0.7b"
    assert settings.tts.volume == 1.0
    assert settings.asr.provider == "openai_compatible"
    assert settings.asr.max_record_seconds == 30
    assert settings.proactive_companion.enabled is True
    assert settings.proactive_companion.interval_seconds == 60
    assert settings.proactive_companion.global_cooldown_seconds == 60
    assert settings.proactive_companion.daily_limit == 24
    assert settings.proactive_companion.quiet_hours_enabled is True
    assert settings.proactive_companion.quiet_start == "23:00"
    assert settings.proactive_companion.quiet_end == "08:00"
    assert settings.proactive_companion.allow_context_topic is False

    public = settings.to_public_dict()
    assert public["screen_observation"]["vision_api_key"] == "***"
    assert public["asr"]["api_key"] == "***"
    assert "vision-secret" not in repr(public)
    assert "asr-secret" not in repr(public)


def test_store_save_creates_parent_and_writes_normalized_json(tmp_path) -> None:
    from guanghe_companion.capability_settings import (
        ASRSettings,
        CapabilitySettings,
        CapabilitySettingsStore,
        ScreenObservationSettings,
        TTSSettings,
        WebSearchSettings,
        ProactiveCompanionSettings,
    )

    path = tmp_path / "nested" / "capability_settings.json"
    store = CapabilitySettingsStore(path)
    settings = CapabilitySettings(
        screen_observation=ScreenObservationSettings(enabled=True, interval_seconds=3),
        web_search=WebSearchSettings(enabled=True, max_results=0),
        tts=TTSSettings(enabled=True, provider="http-qwen3tts", model_variant="1.6B", volume=-1),
        asr=ASRSettings(enabled=True, max_record_seconds=99),
        proactive_companion=ProactiveCompanionSettings(
            enabled=True,
            interval_seconds=30,
            global_cooldown_seconds=30,
            daily_limit=0,
            quiet_start="7:05",
            quiet_end="24:00",
        ),
    )

    saved = store.save(settings)
    reloaded = store.load()

    assert saved.screen_observation.interval_seconds == 10
    assert reloaded.web_search.max_results == 1
    assert reloaded.tts.provider == "http_qwen3tts"
    assert reloaded.tts.model_variant == "qwen3tts_1.6b"
    assert reloaded.tts.volume == 0.0
    assert reloaded.asr.max_record_seconds == 30
    assert reloaded.proactive_companion.interval_seconds == 60
    assert reloaded.proactive_companion.global_cooldown_seconds == 60
    assert reloaded.proactive_companion.daily_limit == 1
    assert reloaded.proactive_companion.quiet_start == "07:05"
    assert reloaded.proactive_companion.quiet_end == "08:00"
    assert json.loads(path.read_text(encoding="utf-8"))["tts"]["provider"] == "http_qwen3tts"


def test_store_returns_defaults_for_invalid_or_missing_json(tmp_path) -> None:
    from guanghe_companion.capability_settings import CapabilitySettingsStore

    missing = CapabilitySettingsStore(tmp_path / "missing.json").load()
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{not json", encoding="utf-8")

    invalid = CapabilitySettingsStore(invalid_path).load()

    assert missing == invalid
    assert missing.web_search.enabled is False


def test_tts_settings_accepts_edge_tts_provider_alias() -> None:
    from guanghe_companion.capability_settings import TTSSettings

    settings = TTSSettings.from_dict({"enabled": True, "provider": "edge-tts"})

    assert settings.enabled is True
    assert settings.provider == "edge_tts"
