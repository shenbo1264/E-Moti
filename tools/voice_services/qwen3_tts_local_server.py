from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_QWEN3_TTS_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
DEFAULT_QWEN3_TTS_VOICE = "Vivian"
QWEN_LANGUAGE_ALIASES = {
    "zh": "chinese",
    "zh-cn": "chinese",
    "zh_cn": "chinese",
    "cn": "chinese",
    "en": "english",
    "en-us": "english",
    "en_us": "english",
    "ja": "japanese",
    "jp": "japanese",
    "ko": "korean",
    "kr": "korean",
}


class Qwen3TTSServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], model: str, voice: str, output_dir: Path) -> None:
        super().__init__(server_address, Qwen3TTSHandler)
        self.model = model
        self.voice = voice
        self.output_dir = output_dir
        self.synthesizer: Any | None = None
        self.startup_error = ""


class Qwen3TTSHandler(BaseHTTPRequestHandler):
    server: Qwen3TTSServer

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        self._json(
            200,
            {
                "ok": not self.server.startup_error,
                "provider": "qwen3_tts_local",
                "model": self.server.model,
                "startup_error": self.server.startup_error,
            },
        )

    def do_POST(self) -> None:
        if self.path not in {"/tts", "/generate", "/v1/audio/speech"}:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        text = str(payload.get("text") or "").strip()
        if not text:
            self._json(400, {"ok": False, "message": "missing text"})
            return
        try:
            audio = _synthesize(
                self.server,
                text,
                str(payload.get("voice") or self.server.voice),
                str(payload.get("language") or "zh"),
                str(payload.get("instruct") or ""),
                _reference_audio_payload(payload.get("ref_audio", payload.get("reference_audio"))),
                _reference_text_payload(payload.get("ref_text", payload.get("reference_text"))),
            )
        except Exception as exc:
            self._json(503, {"ok": False, "message": f"qwen3-tts synthesis failed: {exc}"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("[qwen3-tts] " + format % args + "\n")

    def _json(self, status: int, payload: dict[str, object]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _synthesize(
    server: Qwen3TTSServer,
    text: str,
    voice: str,
    language: str,
    instruct: str,
    reference_audio: object | None = None,
    reference_text: object | None = None,
) -> bytes:
    synthesizer = server.synthesizer
    if synthesizer is None:
        synthesizer = _load_qwen3_tts(server.model)
        server.synthesizer = synthesizer
    result = _call_synthesizer(
        synthesizer,
        text,
        voice,
        language,
        instruct,
        reference_audio=reference_audio,
        reference_text=reference_text,
    )
    if isinstance(result, bytes):
        return result
    if isinstance(result, str):
        return Path(result).read_bytes()
    if isinstance(result, Path):
        return result.read_bytes()
    if isinstance(result, dict):
        for key in ("audio", "wav", "path", "audio_path"):
            value = result.get(key)
            if isinstance(value, bytes):
                return value
            if isinstance(value, str) and Path(value).exists():
                return Path(value).read_bytes()
    raise RuntimeError("qwen-tts returned an unsupported audio result")


def _load_qwen3_tts(model: str) -> object:
    try:
        from qwen_tts import Qwen3TTSModel  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("qwen-tts is not installed; run start_qwen3_tts_server.ps1 -Install") from exc
    return Qwen3TTSModel.from_pretrained(model)


def _call_synthesizer(
    synthesizer: object,
    text: str,
    voice: str,
    language: str,
    instruct: str,
    *,
    reference_audio: object | None = None,
    reference_text: object | None = None,
) -> object:
    qwen_language = _normalize_qwen_language(language)
    if reference_audio:
        generate_voice_clone = getattr(synthesizer, "generate_voice_clone", None)
        if not callable(generate_voice_clone):
            raise RuntimeError("qwen-tts synthesizer has no supported voice clone method")
        arrays, sample_rate = generate_voice_clone(
            text=text,
            language=qwen_language,
            ref_audio=reference_audio,
            ref_text=reference_text,
            non_streaming_mode=True,
        )
        return _audio_arrays_to_wav_bytes(arrays, sample_rate)
    if instruct:
        generate_voice_design = getattr(synthesizer, "generate_voice_design", None)
        if callable(generate_voice_design):
            try:
                arrays, sample_rate = generate_voice_design(
                    text=text,
                    instruct=instruct,
                    language=qwen_language,
                    non_streaming_mode=True,
                )
                return _audio_arrays_to_wav_bytes(arrays, sample_rate)
            except Exception as exc:
                if "does not support generate_voice_design" not in str(exc):
                    raise
    generate_custom_voice = getattr(synthesizer, "generate_custom_voice", None)
    if callable(generate_custom_voice):
        arrays, sample_rate = generate_custom_voice(
            text=text,
            speaker=voice,
            language=qwen_language,
            non_streaming_mode=True,
        )
        return _audio_arrays_to_wav_bytes(arrays, sample_rate)
    for method_name in ("synthesize", "generate", "tts", "__call__"):
        method = getattr(synthesizer, method_name, None)
        if callable(method):
            try:
                return method(text=text, voice=voice)
            except TypeError:
                return method(text, voice=voice)
    raise RuntimeError("qwen-tts synthesizer has no supported synthesis method")


def _normalize_qwen_language(language: str) -> str:
    cleaned = (language or "auto").strip().lower()
    if not cleaned:
        return "auto"
    return QWEN_LANGUAGE_ALIASES.get(cleaned, cleaned)


def _reference_audio_payload(value: object) -> object | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, list):
        refs = [str(item).strip() for item in value if str(item).strip()]
        if not refs:
            return None
        return refs[0] if len(refs) == 1 else refs
    return None


def _reference_text_payload(value: object) -> object | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, list):
        texts = [str(item).strip() if item is not None else None for item in value]
        return texts or None
    return None


def _audio_arrays_to_wav_bytes(arrays: object, sample_rate: int) -> bytes:
    import io

    import soundfile as sf  # type: ignore[import-not-found]

    if isinstance(arrays, list):
        audio = arrays[0] if arrays else []
    else:
        audio = arrays
    output = io.BytesIO()
    sf.write(output, audio, int(sample_rate), format="WAV")
    return output.getvalue()


def create_qwen3_tts_server(
    host: str,
    port: int,
    model: str,
    voice: str,
    output_dir: Path,
) -> Qwen3TTSServer:
    synthesizer = None
    startup_error = ""
    try:
        synthesizer = _load_qwen3_tts(model)
    except Exception as exc:
        startup_error = str(exc)
        print(startup_error, file=sys.stderr)
    server = Qwen3TTSServer((host, port), model, voice, output_dir)
    server.synthesizer = synthesizer
    server.startup_error = startup_error
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Qwen3-TTS through E-Moti's local HTTP TTS contract.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9880)
    parser.add_argument("--model", default=DEFAULT_QWEN3_TTS_MODEL)
    parser.add_argument("--voice", default=DEFAULT_QWEN3_TTS_VOICE)
    parser.add_argument("--output-dir", default=".voice-services/qwen3-tts/output")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    server = create_qwen3_tts_server(args.host, args.port, args.model, args.voice, output_dir)
    print(f"Qwen3-TTS local server listening on http://{args.host}:{args.port}/tts")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
