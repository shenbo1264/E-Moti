from __future__ import annotations


def test_qwen3_tts_local_server_defaults_to_existing_custom_voice_model() -> None:
    from tools.voice_services import qwen3_tts_local_server

    assert qwen3_tts_local_server.DEFAULT_QWEN3_TTS_MODEL == "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"


def test_qwen3_tts_local_server_loads_model_before_binding(monkeypatch, tmp_path) -> None:
    from tools.voice_services import qwen3_tts_local_server

    calls: list[str] = []
    loaded = object()

    class FakeServer:
        def __init__(self, address, model, voice, output_dir):
            calls.append("bind")
            self.address = address
            self.model = model
            self.voice = voice
            self.output_dir = output_dir
            self.synthesizer = None
            self.startup_error = ""

    def fake_load(model):
        calls.append("load")
        assert model == "model-id"
        return loaded

    monkeypatch.setattr(qwen3_tts_local_server, "_load_qwen3_tts", fake_load)
    monkeypatch.setattr(qwen3_tts_local_server, "Qwen3TTSServer", FakeServer)

    server = qwen3_tts_local_server.create_qwen3_tts_server(
        "127.0.0.1",
        9880,
        "model-id",
        "Cherry",
        tmp_path,
    )

    assert calls == ["load", "bind"]
    assert server.synthesizer is loaded
    assert server.startup_error == ""


def test_qwen3_tts_local_server_normalizes_language_codes() -> None:
    from tools.voice_services import qwen3_tts_local_server

    assert qwen3_tts_local_server._normalize_qwen_language("zh") == "chinese"
    assert qwen3_tts_local_server._normalize_qwen_language("en-US") == "english"
    assert qwen3_tts_local_server._normalize_qwen_language("ja") == "japanese"
    assert qwen3_tts_local_server._normalize_qwen_language("Auto") == "auto"


def test_qwen3_tts_local_server_uses_qwen3_custom_voice_api(monkeypatch) -> None:
    from tools.voice_services import qwen3_tts_local_server

    calls = []

    class FakeQwen3Model:
        def generate_custom_voice(self, *, text, speaker, language, non_streaming_mode):
            calls.append((text, speaker, language, non_streaming_mode))
            return [["audio-array"]], 24000

    monkeypatch.setattr(qwen3_tts_local_server, "_audio_arrays_to_wav_bytes", lambda arrays, sample_rate: b"wav")

    result = qwen3_tts_local_server._call_synthesizer(FakeQwen3Model(), "你好星汐", "Vivian", "zh", "")

    assert result == b"wav"
    assert calls == [("你好星汐", "Vivian", "chinese", True)]


def test_qwen3_tts_local_server_uses_voice_design_when_instruct_is_supplied(monkeypatch) -> None:
    from tools.voice_services import qwen3_tts_local_server

    calls = []

    class FakeQwen3Model:
        def generate_voice_design(self, *, text, instruct, language, non_streaming_mode):
            calls.append((text, instruct, language, non_streaming_mode))
            return [["audio-array"]], 24000

    monkeypatch.setattr(qwen3_tts_local_server, "_audio_arrays_to_wav_bytes", lambda arrays, sample_rate: b"wav")

    result = qwen3_tts_local_server._call_synthesizer(
        FakeQwen3Model(),
        "你好星汐",
        "Cherry",
        "zh",
        "温柔、清澈、像星光一样轻声说话",
    )

    assert result == b"wav"
    assert calls == [("你好星汐", "温柔、清澈、像星光一样轻声说话", "chinese", True)]


def test_qwen3_tts_local_server_falls_back_to_custom_voice_when_voice_design_is_unsupported(monkeypatch) -> None:
    from tools.voice_services import qwen3_tts_local_server

    calls = []

    class FakeQwen3Model:
        def generate_voice_design(self, *, text, instruct, language, non_streaming_mode):
            calls.append(("design", text, instruct, language, non_streaming_mode))
            raise RuntimeError("does not support generate_voice_design")

        def generate_custom_voice(self, *, text, speaker, language, non_streaming_mode):
            calls.append(("custom", text, speaker, language, non_streaming_mode))
            return [["audio-array"]], 24000

    monkeypatch.setattr(qwen3_tts_local_server, "_audio_arrays_to_wav_bytes", lambda arrays, sample_rate: b"wav")

    result = qwen3_tts_local_server._call_synthesizer(
        FakeQwen3Model(),
        "hello",
        "Vivian",
        "zh",
        "warm character voice",
    )

    assert result == b"wav"
    assert calls == [
        ("design", "hello", "warm character voice", "chinese", True),
        ("custom", "hello", "Vivian", "chinese", True),
    ]
