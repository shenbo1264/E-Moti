from guanghe_companion.capability_runtime import CapabilityRuntime
from guanghe_companion.capability_settings import (
    ASRSettings,
    CapabilitySettings,
    ScreenObservationSettings,
    TTSSettings,
    WebSearchSettings,
)
from guanghe_companion.controller import CompanionController
from guanghe_companion.screen_observation import ScreenObservationResult
from guanghe_companion.voice_asr import ASRResult
from guanghe_companion.voice_tts import TTSResult
from guanghe_companion.web_search import WebSearchResult


def test_screen_observation_runtime_saves_settings_and_updates_readonly_context_without_growth_mutation(tmp_path):
    settings = CapabilitySettings(
        screen_observation=ScreenObservationSettings(
            enabled=True,
            vision_model="vision-test",
            vision_base_url="https://vision.example.test/v1",
            vision_api_key="secret",
        )
    )
    saved_calls = []
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)

    class FakeScreenObservationService:
        def __init__(self):
            self.settings = None

        def observe(self, received_settings):
            self.settings = received_settings
            return ScreenObservationResult(True, "屏幕观察完成", "看到 IDE 和测试结果")

    service = FakeScreenObservationService()
    runtime = CapabilityRuntime(
        settings_saver=lambda: saved_calls.append("save") or settings,
        settings_reader=lambda: settings,
        set_perception_summary=controller.set_perception_summary,
        set_tool_results=controller.set_tool_results,
        screen_observation_service=service,
    )
    before = controller.get_typed_snapshot()

    result = runtime.run_screen_observation()

    after = controller.get_typed_snapshot()
    assert saved_calls == ["save"]
    assert service.settings == settings.screen_observation
    assert result.summary == "看到 IDE 和测试结果"
    assert controller._expression_context()["perception_summary"] == "看到 IDE 和测试结果"
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.memory_log == before.memory_log


def test_web_search_runtime_writes_tool_results_and_formats_status_without_growth_mutation(tmp_path):
    settings = CapabilitySettings(web_search=WebSearchSettings(enabled=True, max_results=2))
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    tool_results = [
        {
            "source": "web_search",
            "title": "星汐",
            "summary": "桌面伴侣项目",
            "url": "https://example.test/xingxi",
            "timestamp": "2026-06-04T00:00:00Z",
        }
    ]

    class FakeWebSearchService:
        def __init__(self):
            self.calls = []

        def search(self, query, received_settings):
            self.calls.append((query, received_settings))
            return WebSearchResult(True, "搜索完成，结果已提供给星汐", tool_results)

    service = FakeWebSearchService()
    runtime = CapabilityRuntime(
        settings_saver=lambda: settings,
        settings_reader=lambda: settings,
        set_perception_summary=controller.set_perception_summary,
        set_tool_results=controller.set_tool_results,
        web_search_service=service,
    )
    before = controller.get_typed_snapshot()

    result = runtime.run_web_search("星汐")

    after = controller.get_typed_snapshot()
    assert service.calls == [("星汐", settings.web_search)]
    assert result.tool_results == tool_results
    assert result.display_text == "搜索完成，结果已提供给星汐\n星汐 - 桌面伴侣项目 (https://example.test/xingxi)"
    assert controller._expression_context()["tool_results"] == [
        {
            "source": "web_search",
            "title": "星汐",
            "summary": "桌面伴侣项目",
            "timestamp": "2026-06-04T00:00:00Z",
        }
    ]
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.memory_log == before.memory_log


def test_voice_runtime_saves_settings_for_tts_test_and_reads_settings_for_stop():
    settings = CapabilitySettings(tts=TTSSettings(enabled=True, provider="http_qwen3tts"))
    saved_calls = []
    read_calls = []

    class FakeTTSManager:
        def __init__(self):
            self.speak_calls = []
            self.stop_calls = []

        def speak(self, text, received_settings):
            self.speak_calls.append((text, received_settings))
            return TTSResult(True, "朗读完成")

        def stop(self, received_settings):
            self.stop_calls.append(received_settings)
            return TTSResult(True, "已停止朗读")

    manager = FakeTTSManager()
    runtime = CapabilityRuntime(
        settings_saver=lambda: saved_calls.append("save") or settings,
        settings_reader=lambda: read_calls.append("read") or settings,
        tts_manager=manager,
    )

    speak_result = runtime.run_tts_test("星汐在这里")
    stop_result = runtime.stop_tts()

    assert speak_result.message == "朗读完成"
    assert stop_result.message == "已停止朗读"
    assert saved_calls == ["save"]
    assert read_calls == ["read"]
    assert manager.speak_calls == [("星汐在这里", settings.tts)]
    assert manager.stop_calls == [settings.tts]


def test_voice_runtime_reads_settings_for_validated_auto_speech():
    settings = CapabilitySettings(tts=TTSSettings(enabled=True, auto_speak=True, provider="windows_sapi"))
    read_calls = []

    class FakeTTSManager:
        def __init__(self):
            self.speak_calls = []

        def speak(self, text, received_settings):
            self.speak_calls.append((text, received_settings))
            return TTSResult(True, "朗读已开始")

    manager = FakeTTSManager()
    runtime = CapabilityRuntime(
        settings_reader=lambda: read_calls.append("read") or settings,
        tts_manager=manager,
    )

    result = runtime.speak_text("已经通过事件验证的星汐台词")

    assert result.message == "朗读已开始"
    assert read_calls == ["read"]
    assert manager.speak_calls == [("已经通过事件验证的星汐台词", settings.tts)]


def test_voice_runtime_applies_current_character_tts_profile_for_auto_speech():
    settings = CapabilitySettings(
        tts=TTSSettings(
            enabled=True,
            auto_speak=True,
            provider="windows_sapi",
            voice="global",
            rate=0,
            volume=0.5,
        )
    )

    class FakeTTSManager:
        def __init__(self):
            self.speak_calls = []

        def speak(self, text, received_settings):
            self.speak_calls.append((text, received_settings))
            return TTSResult(True, "started")

    manager = FakeTTSManager()
    runtime = CapabilityRuntime(
        settings_reader=lambda: settings,
        tts_manager=manager,
        tts_profile_reader=lambda: {"voice": "Microsoft Huihui Desktop", "rate": 2, "volume": 0.8},
    )

    result = runtime.speak_text("character voice test")

    assert result.ok is True
    assert manager.speak_calls[0][0] == "character voice test"
    assert manager.speak_calls[0][1].voice == "Microsoft Huihui Desktop"
    assert manager.speak_calls[0][1].rate == 2
    assert manager.speak_calls[0][1].volume == 0.8
    assert settings.tts.voice == "global"


def test_voice_runtime_applies_character_voice_profile_route_and_style_instruction():
    settings = CapabilitySettings(
        tts=TTSSettings(
            enabled=True,
            auto_speak=True,
            provider="edge_tts",
            api_url="https://global-tts.example.invalid/",
            language="en",
            voice="global",
            model_variant="qwen3tts_1.7b_customvoice",
            rate=0,
            volume=0.5,
        )
    )

    class FakeTTSManager:
        def __init__(self):
            self.speak_calls = []

        def speak(self, text, received_settings):
            self.speak_calls.append((text, received_settings))
            return TTSResult(True, "started")

    manager = FakeTTSManager()
    runtime = CapabilityRuntime(
        settings_reader=lambda: settings,
        tts_manager=manager,
        tts_profile_reader=lambda: {
            "profile_id": "xingxi_qwen_vivian_v1",
            "provider": "http-qwen3tts",
            "api_url": "http://127.0.0.1:9880/",
            "language": "zh",
            "voice": "Vivian",
            "model_variant": "0.6B",
            "rate": 1,
            "volume": 0.92,
            "instruct": "gentle companion tone",
        },
    )

    result = runtime.speak_text("character profile route test")

    received_settings = manager.speak_calls[0][1]
    assert result.ok is True
    assert received_settings.profile_id == "xingxi_qwen_vivian_v1"
    assert received_settings.provider == "http_qwen3tts"
    assert received_settings.api_url == "http://127.0.0.1:9880/"
    assert received_settings.language == "zh"
    assert received_settings.voice == "Vivian"
    assert received_settings.model_variant == "qwen3tts_0.6b_customvoice"
    assert received_settings.rate == 1
    assert received_settings.volume == 0.92
    assert received_settings.instruct == "gentle companion tone"
    assert settings.tts.provider == "edge_tts"


def test_voice_runtime_applies_character_reference_audio_for_local_clone():
    settings = CapabilitySettings(tts=TTSSettings(enabled=True, auto_speak=True))

    class FakeTTSManager:
        def __init__(self):
            self.speak_calls = []

        def speak(self, text, received_settings):
            self.speak_calls.append((text, received_settings))
            return TTSResult(True, "started")

    manager = FakeTTSManager()
    runtime = CapabilityRuntime(
        settings_reader=lambda: settings,
        tts_manager=manager,
        tts_profile_reader=lambda: {
            "provider": "http-qwen3tts",
            "model_variant": "qwen3tts_0.6b_base",
            "reference_audio": ["D:/voice-packs/ikaros/reference.wav"],
            "reference_text": "参考台词。",
        },
    )

    result = runtime.speak_text("reference clone route test")

    received_settings = manager.speak_calls[0][1]
    assert result.ok is True
    assert received_settings.model_variant == "qwen3tts_0.6b_base"
    assert received_settings.reference_audio == ("D:/voice-packs/ikaros/reference.wav",)
    assert received_settings.reference_text == "参考台词。"


def test_voice_runtime_applies_unified_gateway_and_bilingual_profile():
    settings = CapabilitySettings(
        tts=TTSSettings(
            enabled=True,
            auto_speak=True,
            provider="http_qwen3tts",
            api_url="http://127.0.0.1:9880/",
            language="zh",
        )
    )

    class FakeTTSManager:
        def __init__(self):
            self.speak_calls = []

        def speak(self, text, received_settings):
            self.speak_calls.append((text, received_settings))
            return TTSResult(True, "started")

    manager = FakeTTSManager()
    runtime = CapabilityRuntime(
        settings_reader=lambda: settings,
        tts_manager=manager,
        tts_profile_reader=lambda: {
            "profile_id": "ikaros_unified_gateway_v1",
            "provider": "http-emoti-voice",
            "backend_provider": "gpt-sovits",
            "backend_api_url": "http://127.0.0.1:9882/",
            "backend_model_variant": "gptsovits-v2",
            "display_language": "zh",
            "synthesis_language": "all_ja",
            "synthesis_text_mode": "profile_static_map",
            "synthesis_text_map": {"我在这里。": "マスター、私はここにいます。"},
        },
    )

    result = runtime.speak_text("我在这里。")

    received_settings = manager.speak_calls[0][1]
    assert result.ok is True
    assert manager.speak_calls[0][0] == "我在这里。"
    assert received_settings.profile_id == "ikaros_unified_gateway_v1"
    assert received_settings.provider == "http_emoti_voice"
    assert received_settings.backend_provider == "http_gptsovits"
    assert received_settings.backend_api_url == "http://127.0.0.1:9882/"
    assert received_settings.backend_model_variant == "gptsovits_v2"
    assert received_settings.display_language == "zh"
    assert received_settings.synthesis_language == "all_ja"
    assert received_settings.synthesis_text_mode == "profile_static_map"
    assert received_settings.synthesis_text_map == {"我在这里。": "マスター、私はここにいます。"}


def test_asr_runtime_returns_dialogue_request_for_auto_send_without_submitting_to_controller():
    settings = CapabilitySettings(asr=ASRSettings(enabled=True, auto_send=True))

    class FakeASRService:
        def __init__(self):
            self.started = []
            self.stopped = []

        def start_recording(self, received_settings):
            self.started.append(received_settings)
            return ASRResult(True, "录音中")

        def stop_and_transcribe(self, received_settings):
            self.stopped.append(received_settings)
            return ASRResult(True, "识别完成", "今天陪我一会儿")

    service = FakeASRService()
    runtime = CapabilityRuntime(
        settings_saver=lambda: settings,
        settings_reader=lambda: settings,
        asr_service=service,
    )

    start = runtime.start_asr()
    stop = runtime.stop_asr()

    assert start.message == "录音中"
    assert stop.message == "识别完成"
    assert stop.text == "今天陪我一会儿"
    assert stop.dialogue_request is not None
    assert stop.dialogue_request.text == "今天陪我一会儿"
    assert stop.dialogue_request.source == "asr"
    assert service.started == [settings.asr]
    assert service.stopped == [settings.asr]
