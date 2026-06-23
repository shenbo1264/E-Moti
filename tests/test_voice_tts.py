from __future__ import annotations

from pathlib import Path

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
            profile_id="xingxi_qwen_vivian_v1",
            voice="xingxi",
            model_variant="qwen3tts_0.6b_customvoice",
            instruct="gentle companion tone",
        ),
    )

    assert result.ok is True
    assert requests[0][0] == "http://127.0.0.1:9880/tts"
    assert requests[0][1]["text"] == "测试文本"
    assert requests[0][1]["language"] == "zh"
    assert requests[0][1]["voice"] == "xingxi"
    assert requests[0][1]["model"] == "qwen3tts_0.6b_customvoice"
    assert requests[0][1]["model_size"] == "0.6B-CustomVoice"
    assert requests[0][1]["profile_id"] == "xingxi_qwen_vivian_v1"
    assert requests[0][1]["instruct"] == "gentle companion tone"
    assert requests[0][2] == 180
    assert played
    assert (tmp_path / "qwen3tts_latest.wav").read_bytes() == b"RIFFdemo-wave-bytes"


def test_http_qwen3tts_provider_posts_reference_audio_for_clone_route(tmp_path) -> None:
    from guanghe_companion.voice_tts import HttpQwen3TTSProvider

    requests: list[tuple[str, dict[str, object], int]] = []

    def fake_post(url: str, payload: dict[str, object], timeout: int) -> bytes:
        requests.append((url, payload, timeout))
        return b"RIFFdemo-wave-bytes"

    provider = HttpQwen3TTSProvider(
        post=fake_post,
        cache_dir=tmp_path,
        audio_player=lambda path: None,
    )

    result = provider.speak(
        "本地克隆试听",
        TTSSettings(
            enabled=True,
            provider="http_qwen3tts",
            model_variant="qwen3tts_0.6b_base",
            reference_audio=("D:/voice-packs/nairong/reference.wav",),
            reference_text="参考台词。",
        ),
    )

    assert result.ok is True
    assert requests[0][1]["ref_audio"] == "D:/voice-packs/nairong/reference.wav"
    assert requests[0][1]["ref_text"] == "参考台词。"


def test_edge_neural_tts_provider_uses_character_voice_profile(tmp_path) -> None:
    from guanghe_companion.voice_tts import EdgeNeuralTTSProvider

    requests: list[dict[str, object]] = []
    played: list[str] = []

    class FakeCommunicate:
        def __init__(self, text: str, voice: str) -> None:
            requests.append({"text": text, "voice": voice})

        async def save(self, path: str) -> None:
            Path(path).write_bytes(b"demo-edge-mp3")

    provider = EdgeNeuralTTSProvider(
        communicate_factory=FakeCommunicate,
        cache_dir=tmp_path,
        audio_player=lambda path: played.append(str(path)),
    )

    result = provider.speak(
        "星汐语音测试",
        TTSSettings(
            enabled=True,
            provider="edge_tts",
            voice="zh-CN-XiaoxiaoNeural",
            rate=2,
            volume=0.7,
        ),
    )

    assert result.ok is True
    assert requests == [
        {
            "text": "星汐语音测试",
            "voice": "zh-CN-XiaoxiaoNeural",
        }
    ]
    assert played == [str(tmp_path / "edge_tts_latest.mp3")]
    assert (tmp_path / "edge_tts_latest.mp3").read_bytes() == b"demo-edge-mp3"


def test_edge_neural_tts_provider_returns_failure_for_provider_exception(tmp_path) -> None:
    from guanghe_companion.voice_tts import EdgeNeuralTTSProvider

    class ProviderFailure(Exception):
        pass

    class BrokenCommunicate:
        def __init__(self, text: str, voice: str) -> None:
            pass

        async def save(self, path: str) -> None:
            raise ProviderFailure("network unavailable")

    provider = EdgeNeuralTTSProvider(communicate_factory=BrokenCommunicate, cache_dir=tmp_path)

    result = provider.speak(
        "星汐语音测试",
        TTSSettings(enabled=True, provider="edge_tts", voice="zh-CN-XiaoxiaoNeural"),
    )

    assert result.ok is False
    assert "edge-tts 朗读失败" in result.message

