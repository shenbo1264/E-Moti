import pytest


@pytest.fixture()
def qt_app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_capability_settings_panel_preserves_hidden_fields(qt_app):
    from guanghe_companion.capability_panels import CapabilitySettingsPanel
    from guanghe_companion.capability_settings import (
        CapabilitySettings,
        ScreenObservationSettings,
        WebSearchSettings,
    )

    base = CapabilitySettings(
        screen_observation=ScreenObservationSettings(
            timeout_seconds=77,
            send_screenshot_to_vision=False,
            vision_provider="openai_compatible",
        ),
        web_search=WebSearchSettings(timeout_seconds=22, show_sources=False),
    )
    panel = CapabilitySettingsPanel(base)

    panel.screen_observation_enabled_check.setChecked(True)
    panel.screen_observation_interval_input.setValue(120)
    panel.web_search_enabled_check.setChecked(True)
    panel.web_search_max_results_input.setValue(5)
    panel.proactive_companion_enabled_check.setChecked(True)

    settings = panel.collect_settings(base)

    assert settings.screen_observation.enabled is True
    assert settings.screen_observation.interval_seconds == 120
    assert settings.screen_observation.timeout_seconds == 77
    assert settings.screen_observation.send_screenshot_to_vision is False
    assert settings.screen_observation.vision_provider == "openai_compatible"
    assert settings.web_search.enabled is True
    assert settings.web_search.max_results == 5
    assert settings.web_search.timeout_seconds == 22
    assert settings.web_search.show_sources is False
    assert settings.proactive_companion.enabled is True


def test_voice_settings_panel_preserves_hidden_fields_and_syncs_controls(qt_app):
    from guanghe_companion.capability_panels import VoiceSettingsPanel
    from guanghe_companion.capability_settings import ASRSettings, CapabilitySettings, TTSSettings

    base = CapabilitySettings(
        tts=TTSSettings(language="ja", voice="test-voice", rate=3, volume=0.4),
        asr=ASRSettings(
            language="en",
            vosk_model_path="models/vosk",
            max_record_seconds=22,
            hotkey_enabled=True,
            hotkey_sequence="Ctrl+Alt+Space",
        ),
    )
    panel = VoiceSettingsPanel(base, {"tts_provider": "disabled", "asr_provider": "disabled"})

    assert panel.tts_test_button.isEnabled() is False
    assert panel.asr_start_button.isEnabled() is False
    assert panel.asr_hotkey_input.isEnabled() is False

    panel.tts_enabled_check.setChecked(True)
    panel.asr_enabled_check.setChecked(True)
    panel.tts_model_variant_combo.setCurrentText("qwen3tts_1.7b_customvoice")
    panel.asr_model_input.setText("whisper-large")
    panel.asr_hotkey_input.setText("Alt+M")

    settings = panel.collect_settings(base)

    assert panel.tts_test_button.isEnabled() is True
    assert panel.asr_start_button.isEnabled() is True
    assert panel.asr_hotkey_input.isEnabled() is True
    assert settings.tts.enabled is True
    assert settings.tts.model_variant == "qwen3tts_1.7b_customvoice"
    assert settings.tts.language == "ja"
    assert settings.tts.voice == "test-voice"
    assert settings.tts.rate == 3
    assert settings.tts.volume == 0.4
    assert settings.asr.enabled is True
    assert settings.asr.model == "whisper-large"
    assert settings.asr.language == "en"
    assert settings.asr.vosk_model_path == "models/vosk"
    assert settings.asr.max_record_seconds == 22
    assert settings.asr.hotkey_enabled is True
    assert settings.asr.hotkey_sequence == "Alt+M"


def test_voice_settings_panel_shows_current_character_voice_profile(qt_app):
    from guanghe_companion.capability_panels import VoiceSettingsPanel
    from guanghe_companion.capability_settings import CapabilitySettings

    panel = VoiceSettingsPanel(
        CapabilitySettings.default(),
        {},
        {
            "profile_id": "xingxi_pixel_pet_qwen_vivian_v1",
            "display_name": "Xingxi designed voice",
            "provider": "http_qwen3tts",
            "voice": "Vivian",
            "model_variant": "qwen3tts_0.6b_customvoice",
            "voice_source_type": "original_design",
            "training_status": "designed",
        },
    )

    text = panel.voice_character_profile_label.text()
    assert "Xingxi designed voice" in text
    assert "xingxi_pixel_pet_qwen_vivian_v1" in text
    assert "http_qwen3tts" in text
    assert "Vivian" in text
    assert "designed" in text

    panel.set_character_voice_profile({})

    assert "not defined" in panel.voice_character_profile_label.text()


def test_voice_settings_panel_uses_catalog_provider_choices(qt_app):
    from guanghe_companion.capability_panels import VoiceSettingsPanel

    panel = VoiceSettingsPanel()

    tts_values = [panel.tts_provider_combo.itemText(index) for index in range(panel.tts_provider_combo.count())]
    asr_values = [panel.asr_provider_combo.itemText(index) for index in range(panel.asr_provider_combo.count())]

    assert tts_values == ["http_emoti_voice", "http_qwen3tts", "http_gptsovits", "edge_tts", "windows_sapi"]
    assert asr_values == [
        "sensevoice_openai",
        "funasr_openai",
        "qwen3_asr_openai",
        "openai_compatible",
        "vosk",
    ]


def test_capability_panels_emit_user_action_signals(qt_app):
    from guanghe_companion.capability_panels import CapabilitySettingsPanel, ManualPerceptionPanel, VoiceSettingsPanel
    from guanghe_companion.capability_settings import CapabilitySettings

    capability_panel = CapabilitySettingsPanel(CapabilitySettings.default())
    manual_panel = ManualPerceptionPanel()
    voice_panel = VoiceSettingsPanel(CapabilitySettings.default(), {})
    captured = []

    capability_panel.saveRequested.connect(lambda: captured.append(("save", "")))
    capability_panel.screenObservationRequested.connect(lambda: captured.append(("screen", "")))
    capability_panel.webSearchRequested.connect(lambda query: captured.append(("search", query)))
    manual_panel.manualPerceptionRequested.connect(lambda: captured.append(("manual", "")))
    voice_panel.ttsTestRequested.connect(lambda: captured.append(("tts-test", "")))
    voice_panel.asrStartRequested.connect(lambda: captured.append(("asr-start", "")))

    capability_panel.web_search_query_input.setText("星汐")
    capability_panel.capability_save_button.click()
    capability_panel.screen_observation_run_button.click()
    capability_panel.web_search_run_button.click()
    manual_panel.observe_screen_button.click()
    voice_panel.tts_enabled_check.setChecked(True)
    voice_panel.asr_enabled_check.setChecked(True)
    voice_panel.tts_test_button.click()
    voice_panel.asr_start_button.click()

    assert captured == [
        ("save", ""),
        ("screen", ""),
        ("search", "星汐"),
        ("manual", ""),
        ("tts-test", ""),
        ("asr-start", ""),
    ]
