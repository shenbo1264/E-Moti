def test_expression_settings_store_round_trips_safe_local_config(tmp_path):
    from guanghe_companion.expression_settings import (
        DEFAULT_EXPRESSION_BASE_URL,
        DEFAULT_EXPRESSION_PROVIDER,
        ExpressionSettingsStore,
        normalize_expression_settings,
    )

    settings = normalize_expression_settings(
        {
            "enabled": True,
            "provider": " openai ",
            "model": " demo-model ",
            "base_url": " https://example.test/v1/responses ",
            "api_key": " sk-demo ",
            "timeout_seconds": "0.75",
        }
    )
    store = ExpressionSettingsStore(tmp_path / "expression-settings.json")

    store.save(settings)
    loaded = store.load()

    assert loaded == settings
    assert loaded.enabled is True
    assert loaded.provider == "openai"
    assert loaded.model == "demo-model"
    assert loaded.base_url == "https://example.test/v1/responses"
    assert loaded.api_key == "sk-demo"
    assert loaded.timeout_seconds == 0.75
    assert loaded.to_public_dict()["api_key"] == ""
    assert loaded.to_public_dict()["api_key_set"] is True

    fallback = normalize_expression_settings(
        {
            "enabled": True,
            "provider": "bad\nprovider",
            "model": "m" * 400,
            "base_url": "ftp://unsafe.example",
            "api_key": "bad\nkey",
            "timeout_seconds": "999",
        }
    )

    assert fallback.enabled is True
    assert fallback.provider == DEFAULT_EXPRESSION_PROVIDER
    assert fallback.model
    assert fallback.base_url == DEFAULT_EXPRESSION_BASE_URL
    assert fallback.api_key == ""
    assert fallback.timeout_seconds == 2.0


def test_expression_settings_path_uses_user_data_dir(monkeypatch, tmp_path):
    from guanghe_companion.runtime_paths import expression_settings_path

    override = tmp_path / "runtime-data"
    monkeypatch.setenv("E_MOTI_USER_DATA_DIR", str(override))

    assert expression_settings_path() == override / "expression_settings.json"


def test_voice_settings_are_explicitly_disabled_by_default():
    from guanghe_companion.expression_settings import ExpressionSettings, normalize_expression_settings

    settings = ExpressionSettings()

    assert settings.tts_provider == "disabled"
    assert settings.asr_provider == "disabled"

    normalized = normalize_expression_settings(
        {
            "tts_provider": "openai",
            "asr_provider": "local_mic",
        }
    )

    assert normalized.tts_provider == "disabled"
    assert normalized.asr_provider == "disabled"


def test_expression_settings_supports_provider_presets_for_openai_compatible_services():
    from guanghe_companion.expression_settings import EXPRESSION_PROVIDER_PRESETS, normalize_expression_settings

    assert set(EXPRESSION_PROVIDER_PRESETS) >= {"openai", "deepseek", "openrouter", "custom"}

    deepseek = normalize_expression_settings(
        {
            "enabled": True,
            "provider": " deepseek ",
            "model": "",
            "base_url": "",
            "api_key": " sk-deepseek ",
        }
    )

    assert deepseek.enabled is True
    assert deepseek.provider == "deepseek"
    assert deepseek.model == "deepseek-v4-flash"
    assert deepseek.base_url == "https://api.deepseek.com"
    assert deepseek.api_key == "sk-deepseek"

    openrouter = normalize_expression_settings({"provider": "openrouter", "model": "", "base_url": ""})

    assert openrouter.provider == "openrouter"
    assert openrouter.model == "openai/gpt-5.5"
    assert openrouter.base_url == "https://openrouter.ai/api/v1"

    slow_provider = normalize_expression_settings(
        {
            "provider": "deepseek",
            "timeout_seconds": "30",
        }
    )

    assert slow_provider.timeout_seconds == 30.0
