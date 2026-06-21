from __future__ import annotations

import io
import wave

from guanghe_companion.capability_settings import ASRSettings


def test_asr_service_records_and_transcribes_with_fake_dependencies() -> None:
    from guanghe_companion.voice_asr import ASRResult, ASRService

    class FakeRecorder:
        def __init__(self) -> None:
            self.started_with = 0
            self.stopped = False

        def start(self, max_seconds: int) -> None:
            self.started_with = max_seconds

        def stop(self) -> bytes:
            self.stopped = True
            return b"fake wav"

    recorder = FakeRecorder()
    calls: list[tuple[bytes, ASRSettings]] = []

    def fake_transcriber(audio: bytes, settings: ASRSettings) -> ASRResult:
        calls.append((audio, settings))
        return ASRResult(True, "识别完成", "你好星汐")

    service = ASRService(recorder_factory=lambda: recorder, transcriber=fake_transcriber)
    settings = ASRSettings(enabled=True, max_record_seconds=3)

    started = service.start_recording(settings)
    result = service.stop_and_transcribe(settings)

    assert started.ok is True
    assert "录音中" in started.message
    assert recorder.started_with == 3
    assert recorder.stopped is True
    assert calls == [(b"fake wav", settings)]
    assert result == ASRResult(True, "识别完成", "你好星汐")


def test_asr_service_returns_clear_disabled_or_missing_recording_state() -> None:
    from guanghe_companion.voice_asr import ASRService

    service = ASRService(recorder_factory=lambda: None, transcriber=lambda audio, settings: None)

    disabled = service.start_recording(ASRSettings(enabled=False))
    missing_recording = service.stop_and_transcribe(ASRSettings(enabled=True))

    assert disabled.ok is False
    assert "ASR 未启用" in disabled.message
    assert missing_recording.ok is False
    assert "尚未开始录音" in missing_recording.message


def test_qt_audio_recorder_wraps_recorded_pcm_as_wav() -> None:
    from guanghe_companion.voice_asr import QtAudioWavRecorder

    class FakeBuffer:
        def __init__(self) -> None:
            self.opened = False
            self.closed = False
            self._data = bytearray()

        def open(self, _mode) -> bool:
            self.opened = True
            return True

        def write(self, data: bytes) -> int:
            self._data.extend(data)
            return len(data)

        def data(self) -> bytes:
            return bytes(self._data)

        def close(self) -> None:
            self.closed = True

    class FakeAudioSource:
        def __init__(self, pcm: bytes) -> None:
            self.pcm = pcm
            self.started = False
            self.stopped = False

        def start(self, buffer: FakeBuffer) -> None:
            self.started = True
            buffer.write(self.pcm)

        def stop(self) -> None:
            self.stopped = True

    pcm = b"\x01\x00\x02\x00\x03\x00\x04\x00"
    fake_buffer = FakeBuffer()
    fake_source = FakeAudioSource(pcm)

    recorder = QtAudioWavRecorder(
        audio_source_factory=lambda audio_format: fake_source,
        buffer_factory=lambda: fake_buffer,
    )

    recorder.start(max_seconds=3)
    wav_bytes = recorder.stop()

    assert fake_buffer.opened is True
    assert fake_buffer.closed is True
    assert fake_source.started is True
    assert fake_source.stopped is True
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
        assert wav_file.getframerate() == 16000
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.readframes(4) == pcm


def test_openai_compatible_asr_posts_audio_without_leaking_key() -> None:
    from guanghe_companion.voice_asr import OpenAICompatibleASRTranscriber

    requests: list[tuple[str, dict[str, str], dict[str, str], bytes, int]] = []

    def fake_post(
        url: str,
        headers: dict[str, str],
        fields: dict[str, str],
        audio: bytes,
        timeout: int,
    ) -> dict[str, object]:
        requests.append((url, headers, fields, audio, timeout))
        return {"text": "  你好\n星汐  "}

    transcriber = OpenAICompatibleASRTranscriber(post=fake_post)
    result = transcriber.transcribe(
        b"wav bytes",
        ASRSettings(
            enabled=True,
            provider="openai_compatible",
            model="whisper-1",
            base_url="https://asr.example.test/v1",
            api_key="secret-key",
            language="zh",
        ),
    )

    assert result.ok is True
    assert result.text == "你好 星汐"
    assert requests[0][0] == "https://asr.example.test/v1/audio/transcriptions"
    assert requests[0][1]["Authorization"] == "Bearer secret-key"
    assert requests[0][2] == {"model": "whisper-1", "language": "zh"}
    assert requests[0][3] == b"wav bytes"
    assert requests[0][4] == 30
    assert "secret-key" not in repr(requests[0][2])


def test_vosk_transcriber_returns_clear_missing_model_error(tmp_path) -> None:
    from guanghe_companion.voice_asr import VoskASRTranscriber

    result = VoskASRTranscriber().transcribe(
        b"wav bytes",
        ASRSettings(enabled=True, provider="vosk", vosk_model_path=str(tmp_path / "missing")),
    )

    assert result.ok is False
    assert "Vosk 模型路径不存在" in result.message


def test_default_asr_transcriber_routes_named_openai_compatible_services() -> None:
    from guanghe_companion.voice_asr import (
        OPENAI_COMPATIBLE_ASR_PROVIDERS,
        OpenAICompatibleASRTranscriber,
        default_asr_transcriber,
    )

    assert OPENAI_COMPATIBLE_ASR_PROVIDERS == {
        "openai_compatible",
        "funasr_openai",
        "sensevoice_openai",
        "qwen3_asr_openai",
    }
    assert isinstance(default_asr_transcriber("openai_compatible"), OpenAICompatibleASRTranscriber)
    assert isinstance(default_asr_transcriber("funasr_openai"), OpenAICompatibleASRTranscriber)
    assert isinstance(default_asr_transcriber("sensevoice_openai"), OpenAICompatibleASRTranscriber)
    assert isinstance(default_asr_transcriber("qwen3_asr_openai"), OpenAICompatibleASRTranscriber)
