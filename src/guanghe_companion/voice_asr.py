from __future__ import annotations

import io
import json
import uuid
import wave
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .capability_settings import ASRSettings
from .dialogue import MAX_DIALOGUE_INPUT_LENGTH

OPENAI_COMPATIBLE_ASR_PROVIDERS = frozenset(
    {
        "openai_compatible",
        "funasr_openai",
        "sensevoice_openai",
        "qwen3_asr_openai",
    }
)


@dataclass(frozen=True, slots=True)
class ASRResult:
    ok: bool
    message: str
    text: str = ""


class ASRRecorder(Protocol):
    def start(self, max_seconds: int) -> None:
        ...

    def stop(self) -> bytes:
        ...


class ASRTranscriber(Protocol):
    def transcribe(self, audio: bytes, settings: ASRSettings) -> ASRResult:
        ...


class ASRService:
    def __init__(
        self,
        *,
        recorder_factory: Callable[[], ASRRecorder | None] | None = None,
        transcriber: Callable[[bytes, ASRSettings], ASRResult] | ASRTranscriber | None = None,
    ) -> None:
        self._recorder_factory = recorder_factory or (lambda: QtAudioWavRecorder())
        self._transcriber = transcriber
        self._active_recorder: ASRRecorder | None = None

    def start_recording(self, settings: ASRSettings) -> ASRResult:
        if not settings.enabled:
            return ASRResult(False, "ASR 未启用")
        try:
            recorder = self._recorder_factory()
            if recorder is None:
                return ASRResult(False, "录音依赖未安装或不可用")
            recorder.start(settings.max_record_seconds)
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            self._active_recorder = None
            return ASRResult(False, f"录音失败：{exc}")
        self._active_recorder = recorder
        return ASRResult(True, "录音中")

    def stop_and_transcribe(self, settings: ASRSettings) -> ASRResult:
        if not settings.enabled:
            return ASRResult(False, "ASR 未启用")
        recorder = self._active_recorder
        if recorder is None:
            return ASRResult(False, "尚未开始录音")
        self._active_recorder = None
        try:
            audio = recorder.stop()
        except (OSError, RuntimeError, ValueError) as exc:
            return ASRResult(False, f"录音失败：{exc}")
        if not audio:
            return ASRResult(False, "录音为空")
        return self._transcribe(audio, settings)

    def _transcribe(self, audio: bytes, settings: ASRSettings) -> ASRResult:
        transcriber = self._transcriber
        if transcriber is None:
            transcriber = default_asr_transcriber(settings.provider)
        try:
            if callable(transcriber):
                result = transcriber(audio, settings)
            else:
                result = transcriber.transcribe(audio, settings)
        except (OSError, RuntimeError, ValueError, urllib.error.URLError, TimeoutError) as exc:
            return ASRResult(False, f"ASR 识别失败：{exc}")
        if not isinstance(result, ASRResult):
            return ASRResult(False, "ASR provider 返回无效结果")
        return result


class QtAudioWavRecorder:
    def __init__(
        self,
        *,
        sample_rate: int = 16_000,
        channels: int = 1,
        audio_source_factory: Callable[[object], object] | None = None,
        buffer_factory: Callable[[], object] | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._audio_source_factory = audio_source_factory
        self._buffer_factory = buffer_factory
        self._audio_source = None
        self._buffer = None

    def start(self, max_seconds: int) -> None:
        if max_seconds <= 0:
            raise ValueError("max_seconds must be positive")
        audio_format = self._audio_format()
        buffer = self._create_buffer()
        if not buffer.open(self._qt_read_write_mode()):
            raise RuntimeError("无法创建录音缓存")
        audio_source = self._create_audio_source(audio_format)
        audio_source.start(buffer)
        self._audio_source = audio_source
        self._buffer = buffer

    def stop(self) -> bytes:
        audio_source = self._audio_source
        buffer = self._buffer
        self._audio_source = None
        self._buffer = None
        if audio_source is None or buffer is None:
            return b""
        audio_source.stop()
        data = bytes(buffer.data())
        buffer.close()
        return _pcm_bytes_to_wav_bytes(data, self.sample_rate, self.channels)

    def _audio_format(self):
        from PySide6.QtMultimedia import QAudioFormat

        audio_format = QAudioFormat()
        audio_format.setSampleRate(self.sample_rate)
        audio_format.setChannelCount(self.channels)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        return audio_format

    def _create_buffer(self):
        if self._buffer_factory is not None:
            return self._buffer_factory()
        from PySide6.QtCore import QBuffer

        return QBuffer()

    def _qt_read_write_mode(self):
        from PySide6.QtCore import QIODevice

        return QIODevice.OpenModeFlag.ReadWrite

    def _create_audio_source(self, audio_format):
        if self._audio_source_factory is not None:
            return self._audio_source_factory(audio_format)
        from PySide6.QtMultimedia import QAudioSource, QMediaDevices

        device = QMediaDevices.defaultAudioInput()
        if device.isNull():
            raise RuntimeError("没有可用麦克风")
        if not device.isFormatSupported(audio_format):
            raise RuntimeError("麦克风不支持 16kHz/16-bit mono 录音")
        return QAudioSource(device, audio_format)


class OpenAICompatibleASRTranscriber:
    def __init__(
        self,
        *,
        post: Callable[[str, dict[str, str], dict[str, str], bytes, int], dict[str, object]] | None = None,
    ) -> None:
        self._post = post or _post_multipart_json

    def transcribe(self, audio: bytes, settings: ASRSettings) -> ASRResult:
        if not settings.base_url or not settings.api_key:
            return ASRResult(False, "缺少 ASR Base URL 或 API Key")
        fields = {"model": settings.model, "language": settings.language}
        headers = {"Authorization": f"Bearer {settings.api_key}"}
        try:
            response = self._post(_asr_endpoint(settings.base_url), headers, fields, audio, 30)
        except (OSError, ValueError, urllib.error.URLError, TimeoutError) as exc:
            return ASRResult(False, f"ASR 请求失败：{exc}")
        text = _sanitize_recognized_text(response.get("text"))
        if not text:
            return ASRResult(False, "ASR 未返回文本")
        return ASRResult(True, "识别完成", text)


class VoskASRTranscriber:
    def transcribe(self, audio: bytes, settings: ASRSettings) -> ASRResult:
        model_path = Path(settings.vosk_model_path)
        if not settings.vosk_model_path or not model_path.exists():
            return ASRResult(False, "Vosk 模型路径不存在")
        try:
            from vosk import KaldiRecognizer, Model
        except ImportError:
            return ASRResult(False, "vosk 未安装")
        try:
            with wave.open(io.BytesIO(audio), "rb") as wav_file:
                recognizer = KaldiRecognizer(Model(str(model_path)), wav_file.getframerate())
                while True:
                    data = wav_file.readframes(4000)
                    if not data:
                        break
                    recognizer.AcceptWaveform(data)
                result = json.loads(recognizer.FinalResult())
        except Exception as exc:
            return ASRResult(False, f"Vosk 识别失败：{exc}")
        text = _sanitize_recognized_text(result.get("text"))
        return ASRResult(True, "识别完成", text) if text else ASRResult(False, "Vosk 未返回文本")


def default_asr_transcriber(provider: str) -> ASRTranscriber:
    if provider == "vosk":
        return VoskASRTranscriber()
    if provider in OPENAI_COMPATIBLE_ASR_PROVIDERS:
        return OpenAICompatibleASRTranscriber()
    return OpenAICompatibleASRTranscriber()


def _sanitize_recognized_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value.strip())
    return cleaned[:MAX_DIALOGUE_INPUT_LENGTH].strip()


def _asr_endpoint(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if base.endswith("/audio/transcriptions"):
        return base
    return f"{base}/audio/transcriptions"


def _post_multipart_json(
    url: str,
    headers: dict[str, str],
    fields: dict[str, str],
    audio: bytes,
    timeout: int,
) -> dict[str, object]:
    boundary = f"----emoti-asr-{uuid.uuid4().hex}"
    body = _multipart_body(boundary, fields, audio)
    request_headers = {
        **headers,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    request = urllib.request.Request(url, data=body, method="POST", headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _multipart_body(boundary: str, fields: dict[str, str], audio: bytes) -> bytes:
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("ascii"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}\r\n".encode("ascii"))
    chunks.append(b'Content-Disposition: form-data; name="file"; filename="speech.wav"\r\n')
    chunks.append(b"Content-Type: audio/wav\r\n\r\n")
    chunks.append(audio)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(chunks)


def _pcm_bytes_to_wav_bytes(recording: bytes, sample_rate: int, channels: int) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(recording)
    return output.getvalue()
