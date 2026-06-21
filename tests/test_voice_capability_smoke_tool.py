from __future__ import annotations

import json


def test_voice_smoke_tool_writes_tts_report_without_playback(tmp_path, monkeypatch) -> None:
    from guanghe_companion.voice_tts import TTSResult
    from tools import voice_capability_smoke

    calls = []

    class FakeProvider:
        def speak(self, text, settings):
            calls.append((text, settings.provider, settings.voice))
            return TTSResult(True, "朗读完成", str(tmp_path / "out.mp3"))

        def stop(self):
            pass

    monkeypatch.setattr(
        voice_capability_smoke,
        "default_tts_provider_factory",
        lambda provider: FakeProvider(),
    )
    report = tmp_path / "report.json"

    code = voice_capability_smoke.main(
        [
            "--tts-provider",
            "edge_tts",
            "--tts-text",
            "星汐语音测试",
            "--tts-voice",
            "zh-CN-XiaoxiaoNeural",
            "--report",
            str(report),
        ]
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["tts"]["ok"] is True
    assert calls == [("星汐语音测试", "edge_tts", "zh-CN-XiaoxiaoNeural")]


def test_voice_smoke_tool_can_skip_qt_playback_for_edge_tts(tmp_path, monkeypatch) -> None:
    from guanghe_companion.voice_tts import TTSResult
    from tools import voice_capability_smoke

    constructed = {}

    class FakeEdgeProvider:
        def __init__(self, *, audio_player):
            constructed["audio_player"] = audio_player

        def speak(self, text, settings):
            constructed["spoken"] = (text, settings.provider)
            return TTSResult(True, "朗读完成", str(tmp_path / "out.mp3"))

        def stop(self):
            pass

    monkeypatch.setattr(voice_capability_smoke, "EdgeNeuralTTSProvider", FakeEdgeProvider)
    report = tmp_path / "report.json"

    code = voice_capability_smoke.main(
        [
            "--tts-provider",
            "edge_tts",
            "--tts-text",
            "星汐语音测试",
            "--skip-playback",
            "--report",
            str(report),
        ]
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["tts"]["ok"] is True
    assert constructed["spoken"] == ("星汐语音测试", "edge_tts")
    assert callable(constructed["audio_player"])


def test_voice_smoke_tool_writes_asr_report_from_audio_file(tmp_path, monkeypatch) -> None:
    from guanghe_companion.voice_asr import ASRResult
    from tools import voice_capability_smoke

    audio = tmp_path / "speech.wav"
    audio.write_bytes(b"wav")
    report = tmp_path / "report.json"

    class FakeTranscriber:
        def transcribe(self, audio_bytes, settings):
            assert audio_bytes == b"wav"
            assert settings.provider == "funasr_openai"
            return ASRResult(True, "识别完成", "你好星汐")

    monkeypatch.setattr(voice_capability_smoke, "default_asr_transcriber", lambda provider: FakeTranscriber())

    code = voice_capability_smoke.main(
        [
            "--asr-provider",
            "funasr_openai",
            "--asr-base-url",
            "http://127.0.0.1:8899/v1",
            "--asr-api-key",
            "local",
            "--asr-audio",
            str(audio),
            "--report",
            str(report),
        ]
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, ensure_ascii=False)
    assert code == 0
    assert payload["asr"]["ok"] is True
    assert payload["asr"]["text"] == "你好星汐"
    assert "local" not in serialized
