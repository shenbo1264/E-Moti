from __future__ import annotations

from guanghe_companion.capability_settings import TTSSettings


def test_clean_tts_text_removes_action_tags_and_source_json() -> None:
    from guanghe_companion.voice_tts import clean_tts_text

    text = '  星汐在这里。[motion:Wave]\n{"source":"web_search","title":"来源"}\n'

    assert clean_tts_text(text) == "星汐在这里。"


def test_tts_manager_consumes_cleaned_text_in_order() -> None:
    from guanghe_companion.voice_tts import TTSManager, TTSResult

    calls: list[str] = []

    class FakeProvider:
        def speak(self, text: str, settings: TTSSettings) -> TTSResult:
            calls.append(text)
            return TTSResult(True, "done")

        def stop(self) -> None:
            calls.append("stopped")

    manager = TTSManager(provider_factory=lambda provider: FakeProvider())
    settings = TTSSettings(enabled=True, provider="http_qwen3tts")

    first = manager.speak("第一句", settings)
    second = manager.speak("第二句 [effect:ATTENTION]", settings)
    stopped = manager.stop(settings)

    assert first.ok is True
    assert second.ok is True
    assert stopped.ok is True
    assert calls == ["第一句", "第二句", "stopped"]


def test_tts_manager_rejects_disabled_or_empty_text() -> None:
    from guanghe_companion.voice_tts import TTSManager

    manager = TTSManager(provider_factory=lambda provider: None)

    disabled = manager.speak("星汐在这里", TTSSettings(enabled=False))
    empty = manager.speak("[motion:Wave]", TTSSettings(enabled=True, provider="http_qwen3tts"))

    assert disabled.ok is False
    assert "未启用" in disabled.message
    assert empty.ok is False
    assert "没有可朗读文本" in empty.message


def test_http_qwen3tts_provider_posts_model_variant_and_writes_audio(tmp_path) -> None:
    from guanghe_companion.voice_tts import HttpQwen3TTSProvider

    requests: list[tuple[str, dict[str, object], int]] = []
    played: list[str] = []

    def fake_post(url: str, payload: dict[str, object], timeout: int) -> bytes:
        requests.append((url, payload, timeout))
        return b"RIFFdemo-wave-bytes"

    provider = HttpQwen3TTSProvider(
        post=fake_post,
        cache_dir=tmp_path,
        audio_player=lambda path: played.append(str(path)),
    )

    result = provider.speak(
        "测试文本",
        TTSSettings(
            enabled=True,
            provider="http_qwen3tts",
            api_url="http://127.0.0.1:9880/",
            language="zh",
            voice="xingxi",
            model_variant="qwen3tts_0.7b",
        ),
    )

    assert result.ok is True
    assert requests[0][0] == "http://127.0.0.1:9880/tts"
    assert requests[0][1]["text"] == "测试文本"
    assert requests[0][1]["language"] == "zh"
    assert requests[0][1]["voice"] == "xingxi"
    assert requests[0][1]["model"] == "qwen3tts_0.7b"
    assert requests[0][1]["model_size"] == "0.7B"
    assert requests[0][2] == 30
    assert played
    assert (tmp_path / "qwen3tts_latest.wav").read_bytes() == b"RIFFdemo-wave-bytes"

