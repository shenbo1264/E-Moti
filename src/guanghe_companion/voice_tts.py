from __future__ import annotations

import asyncio
import base64
import json
import re
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from .capability_settings import TTSSettings
from .runtime_paths import user_data_dir

TTS_ACTION_TAG_PATTERN = re.compile(r"\[(?:action|motion|effect|sprite|source|tool|search)[^\]]*\]", re.IGNORECASE)
HTTP_TTS_ENDPOINT_SUFFIXES = ("/tts", "/generate", "/v1/audio/speech")


@dataclass(frozen=True, slots=True)
class TTSResult:
    ok: bool
    message: str
    audio_path: str = ""


class TTSProvider(Protocol):
    def speak(self, text: str, settings: TTSSettings) -> TTSResult:
        ...

    def stop(self) -> None:
        ...


def clean_tts_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    lines: list[str] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _looks_like_source_json(line):
            continue
        line = TTS_ACTION_TAG_PATTERN.sub("", line)
        line = _replace_control_characters(line).strip()
        if line:
            lines.append(line)
    return " ".join(lines)[:240].strip()


class TTSManager:
    def __init__(
        self,
        *,
        provider_factory: Callable[[str], TTSProvider | None] | None = None,
    ) -> None:
        self._provider_factory = provider_factory or default_tts_provider_factory
        self._providers: dict[str, TTSProvider] = {}

    def speak(self, text: object, settings: TTSSettings) -> TTSResult:
        if not settings.enabled:
            return TTSResult(False, "TTS 未启用")
        cleaned = clean_tts_text(text)
        if not cleaned:
            return TTSResult(False, "没有可朗读文本")
        provider = self._get_provider(settings.provider)
        if provider is None:
            return TTSResult(False, f"TTS provider 不可用：{settings.provider}")
        return provider.speak(cleaned, settings)

    def stop(self, settings: TTSSettings | None = None) -> TTSResult:
        providers = (
            [self._get_provider(settings.provider)] if settings is not None else list(self._providers.values())
        )
        for provider in providers:
            if provider is None:
                continue
            try:
                provider.stop()
            except Exception:
                continue
        return TTSResult(True, "已停止朗读")

    def _get_provider(self, provider_name: str) -> TTSProvider | None:
        if provider_name not in self._providers:
            provider = self._provider_factory(provider_name)
            if provider is None:
                return None
            self._providers[provider_name] = provider
        return self._providers[provider_name]


class HttpQwen3TTSProvider:
    def __init__(
        self,
        *,
        post: Callable[[str, dict[str, object], int], bytes] | None = None,
        cache_dir: Path | str | None = None,
        audio_player: Callable[[Path], object] | None = None,
    ) -> None:
        self._post = post or _post_json_bytes
        self._cache_dir = Path(cache_dir) if cache_dir is not None else user_data_dir() / "cache" / "tts"
        self._audio_player = audio_player or _QtAudioFilePlayer().play
        self._qt_player: _QtAudioFilePlayer | None = None

    def speak(self, text: str, settings: TTSSettings) -> TTSResult:
        endpoint = _tts_endpoint(settings.api_url)
        payload = _qwen3tts_payload(text, settings)
        try:
            audio = self._post(endpoint, payload, 180)
            if not audio:
                return TTSResult(False, "HTTP TTS 未返回音频")
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            output = self._cache_dir / "qwen3tts_latest.wav"
            output.write_bytes(audio)
            self._audio_player(output)
            return TTSResult(True, "朗读完成", str(output))
        except (OSError, ValueError, urllib.error.URLError, TimeoutError) as exc:
            return TTSResult(False, f"HTTP TTS 失败：{exc}")

    def stop(self) -> None:
        player = getattr(self._audio_player, "__self__", None)
        stop = getattr(player, "stop", None)
        if callable(stop):
            stop()


class HttpGPTSoVITSProvider:
    def __init__(
        self,
        *,
        post: Callable[[str, dict[str, object], int], bytes] | None = None,
        cache_dir: Path | str | None = None,
        audio_player: Callable[[Path], object] | None = None,
    ) -> None:
        self._post = post or _post_json_bytes
        self._cache_dir = Path(cache_dir) if cache_dir is not None else user_data_dir() / "cache" / "tts"
        self._audio_player = audio_player or _QtAudioFilePlayer().play

    def speak(self, text: str, settings: TTSSettings) -> TTSResult:
        if not settings.reference_audio:
            return TTSResult(False, "GPT-SoVITS reference_audio is required")
        if not settings.reference_text:
            return TTSResult(False, "GPT-SoVITS reference_text is required")
        endpoint = _gptsovits_endpoint(settings.api_url)
        payload = _gptsovits_payload(text, settings)
        try:
            audio = self._post(endpoint, payload, 180)
            if not audio:
                return TTSResult(False, "GPT-SoVITS returned empty audio")
            if not _looks_like_gptsovits_audio(audio):
                return TTSResult(False, "GPT-SoVITS returned invalid audio")
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            output = self._cache_dir / "gptsovits_latest.wav"
            output.write_bytes(audio)
            self._audio_player(output)
            return TTSResult(True, "GPT-SoVITS speech complete", str(output))
        except (OSError, ValueError, urllib.error.URLError, TimeoutError) as exc:
            return TTSResult(False, f"GPT-SoVITS speech failed: {exc}")

    def stop(self) -> None:
        player = getattr(self._audio_player, "__self__", None)
        stop = getattr(player, "stop", None)
        if callable(stop):
            stop()


class EmotiVoiceGatewayProvider:
    def __init__(
        self,
        *,
        provider_factory: Callable[[str], TTSProvider | None] | None = None,
        audio_player: Callable[[Path], object] | None = None,
    ) -> None:
        self._audio_player = audio_player
        self._provider_factory = provider_factory or self._default_backend_provider
        self._providers: dict[str, TTSProvider] = {}

    def speak(self, text: str, settings: TTSSettings) -> TTSResult:
        backend_provider = settings.backend_provider
        if not backend_provider or backend_provider == "http_emoti_voice":
            return TTSResult(False, "E-Moti Voice backend_provider is required")
        provider = self._backend_provider(backend_provider)
        if provider is None:
            return TTSResult(False, f"E-Moti Voice backend unavailable: {backend_provider}")
        backend_settings = replace(
            settings,
            provider=backend_provider,
            api_url=settings.backend_api_url or settings.api_url,
            language=settings.synthesis_language or settings.language,
            model_variant=settings.backend_model_variant or settings.model_variant,
        )
        return provider.speak(select_synthesis_text(text, settings), backend_settings)

    def stop(self) -> None:
        for provider in self._providers.values():
            try:
                provider.stop()
            except Exception:
                continue

    def _backend_provider(self, provider_name: str) -> TTSProvider | None:
        if provider_name not in self._providers:
            provider = self._provider_factory(provider_name)
            if provider is None:
                return None
            self._providers[provider_name] = provider
        return self._providers[provider_name]

    def _default_backend_provider(self, provider_name: str) -> TTSProvider | None:
        if self._audio_player is not None:
            if provider_name == "http_qwen3tts":
                return HttpQwen3TTSProvider(audio_player=self._audio_player)
            if provider_name == "http_gptsovits":
                return HttpGPTSoVITSProvider(audio_player=self._audio_player)
            if provider_name == "edge_tts":
                return EdgeNeuralTTSProvider(audio_player=self._audio_player)
        return default_tts_provider_factory(provider_name)


class WindowsSapiTTSProvider:
    def __init__(self, powershell_executable: str = "powershell") -> None:
        self._powershell_executable = powershell_executable
        self._process: subprocess.Popen[bytes] | None = None

    def speak(self, text: str, settings: TTSSettings) -> TTSResult:
        self.stop()
        script = _windows_sapi_script(
            text=text,
            voice=settings.voice,
            rate=settings.rate,
            volume=int(settings.volume * 100),
        )
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        try:
            self._process = subprocess.Popen(
                [
                    self._powershell_executable,
                    "-NoProfile",
                    "-NonInteractive",
                    "-EncodedCommand",
                    encoded,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            return TTSResult(False, f"Windows SAPI TTS 失败：{exc}")
        return TTSResult(True, "朗读已开始")

    def stop(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
        self._process = None


class EdgeNeuralTTSProvider:
    def __init__(
        self,
        *,
        communicate_factory: Callable[..., object] | None = None,
        cache_dir: Path | str | None = None,
        audio_player: Callable[[Path], object] | None = None,
    ) -> None:
        self._communicate_factory = communicate_factory
        self._cache_dir = Path(cache_dir) if cache_dir is not None else user_data_dir() / "cache" / "tts"
        self._audio_player = audio_player or _QtAudioFilePlayer().play

    def speak(self, text: str, settings: TTSSettings) -> TTSResult:
        factory = self._communicate_factory or _edge_tts_communicate_factory()
        if factory is None:
            return TTSResult(False, "edge-tts 未安装，无法使用在线神经语音")
        voice = settings.voice or "zh-CN-XiaoxiaoNeural"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        output = self._cache_dir / "edge_tts_latest.mp3"
        try:
            communicate = factory(
                text,
                voice,
            )
            save = getattr(communicate, "save", None)
            if not callable(save):
                return TTSResult(False, "edge-tts provider 返回无效合成器")
            asyncio.run(save(str(output)))
            self._audio_player(output)
            return TTSResult(True, "朗读完成", str(output))
        except Exception as exc:
            return TTSResult(False, f"edge-tts 朗读失败：{exc}")

    def stop(self) -> None:
        player = getattr(self._audio_player, "__self__", None)
        stop = getattr(player, "stop", None)
        if callable(stop):
            stop()


class _QtAudioFilePlayer:
    def __init__(self) -> None:
        self._player = None
        self._audio_output = None

    def play(self, path: Path) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

        if self._player is None:
            self._player = QMediaPlayer()
            self._audio_output = QAudioOutput()
            self._player.setAudioOutput(self._audio_output)
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player.play()

    def stop(self) -> None:
        if self._player is not None:
            self._player.stop()


def default_tts_provider_factory(provider: str) -> TTSProvider | None:
    if provider == "http_emoti_voice":
        return EmotiVoiceGatewayProvider()
    if provider == "http_qwen3tts":
        return HttpQwen3TTSProvider()
    if provider == "http_gptsovits":
        return HttpGPTSoVITSProvider()
    if provider == "windows_sapi":
        return WindowsSapiTTSProvider()
    if provider == "edge_tts":
        return EdgeNeuralTTSProvider()
    return None


def _qwen3tts_payload(text: str, settings: TTSSettings) -> dict[str, object]:
    payload: dict[str, object] = {
        "text": text,
        "language": settings.language,
        "voice": settings.voice,
        "model": settings.model_variant,
        "model_size": _model_size_label(settings.model_variant),
    }
    if settings.profile_id:
        payload["profile_id"] = settings.profile_id
    if settings.instruct:
        payload["instruct"] = settings.instruct
    if settings.reference_audio:
        payload["ref_audio"] = settings.reference_audio[0] if len(settings.reference_audio) == 1 else list(settings.reference_audio)
    if settings.reference_text:
        payload["ref_text"] = settings.reference_text
    return payload


def _gptsovits_payload(text: str, settings: TTSSettings) -> dict[str, object]:
    return {
        "refer_wav_path": settings.reference_audio[0],
        "prompt_text": settings.reference_text,
        "prompt_language": settings.language,
        "text": text,
        "text_language": settings.language,
        "top_k": 15,
        "top_p": 0.7,
        "temperature": 0.35,
        "speed": _gptsovits_speed(settings.rate),
    }


def _gptsovits_speed(rate: int) -> float:
    return round(max(0.5, min(1.5, 1.0 + (int(rate) * 0.1))), 2)


def select_synthesis_text(text: str, settings: TTSSettings) -> str:
    if settings.synthesis_text_mode == "profile_static_map":
        mapped = settings.synthesis_text_map.get(text)
        if mapped:
            return mapped
    return text


def _model_size_label(model_variant: str) -> str:
    if model_variant == "qwen3tts_1.7b_base":
        return "1.7B-Base"
    if model_variant == "qwen3tts_0.6b_base":
        return "0.6B-Base"
    if model_variant == "qwen3tts_1.7b_customvoice":
        return "1.7B-CustomVoice"
    return "0.6B-CustomVoice"


def _tts_endpoint(api_url: str) -> str:
    base = (api_url or "http://127.0.0.1:9880/").strip().rstrip("/")
    if not base:
        base = "http://127.0.0.1:9880"
    if base.lower().endswith(HTTP_TTS_ENDPOINT_SUFFIXES):
        return base
    return f"{base}/tts"


def _gptsovits_endpoint(api_url: str) -> str:
    base = (api_url or "http://127.0.0.1:9882/").strip().rstrip("/")
    if not base:
        base = "http://127.0.0.1:9882"
    return f"{base}/"


def _post_json_bytes(url: str, payload: dict[str, object], timeout: int) -> bytes:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _looks_like_gptsovits_audio(audio: bytes) -> bool:
    return len(audio) > 44 and audio.startswith(b"RIFF")


def _edge_tts_communicate_factory() -> Callable[..., object] | None:
    try:
        from edge_tts import Communicate
    except ImportError:
        return None
    return Communicate


def _looks_like_source_json(line: str) -> bool:
    if not (line.startswith("{") and line.endswith("}")):
        return False
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict) and "source" in parsed


def _replace_control_characters(value: str) -> str:
    return "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value)


def _windows_sapi_script(*, text: str, voice: str, rate: int, volume: int) -> str:
    text_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    voice_b64 = base64.b64encode(voice.encode("utf-8")).decode("ascii")
    rate = max(-10, min(10, int(rate)))
    volume = max(0, min(100, int(volume)))
    return f"""
Add-Type -AssemblyName System.Speech
$text = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{text_b64}'))
$voice = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{voice_b64}'))
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.Rate = {rate}
$speaker.Volume = {volume}
if ($voice) {{
  try {{ $speaker.SelectVoice($voice) }} catch {{ }}
}}
$speaker.Speak($text)
$speaker.Dispose()
"""

