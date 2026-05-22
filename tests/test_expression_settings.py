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
