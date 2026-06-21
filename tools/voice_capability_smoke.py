from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from guanghe_companion.capability_settings import ASRSettings, TTSSettings
from guanghe_companion.voice_asr import default_asr_transcriber
from guanghe_companion.voice_tts import EdgeNeuralTTSProvider, HttpQwen3TTSProvider, default_tts_provider_factory


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test E-Moti voice providers.")
    parser.add_argument("--tts-provider", default="")
    parser.add_argument("--tts-text", default="")
    parser.add_argument("--tts-voice", default="")
    parser.add_argument("--tts-api-url", default="")
    parser.add_argument("--tts-model-variant", default="qwen3tts_1.6b")
    parser.add_argument("--skip-playback", action="store_true")
    parser.add_argument("--asr-provider", default="")
    parser.add_argument("--asr-model", default="whisper-1")
    parser.add_argument("--asr-base-url", default="")
    parser.add_argument("--asr-api-key", default="")
    parser.add_argument("--asr-audio", default="")
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)

    report: dict[str, object] = {"tts": None, "asr": None}
    exit_code = 0

    if args.tts_provider:
        provider = _tts_provider(args.tts_provider, skip_playback=args.skip_playback)
        if provider is None:
            report["tts"] = {"ok": False, "message": f"TTS provider 不可用：{args.tts_provider}"}
            exit_code = 1
        else:
            result = provider.speak(
                args.tts_text,
                TTSSettings(
                    enabled=True,
                    provider=args.tts_provider,
                    voice=args.tts_voice,
                    api_url=args.tts_api_url,
                    model_variant=args.tts_model_variant,
                ),
            )
            report["tts"] = {
                "ok": result.ok,
                "message": result.message,
                "audio_path": result.audio_path,
            }
            if not result.ok:
                exit_code = 1

    if args.asr_provider:
        audio_path = Path(args.asr_audio)
        if not audio_path.exists():
            report["asr"] = {"ok": False, "message": "ASR 音频文件不存在", "text": ""}
            exit_code = 1
        else:
            transcriber = default_asr_transcriber(args.asr_provider)
            result = transcriber.transcribe(
                audio_path.read_bytes(),
                ASRSettings(
                    enabled=True,
                    provider=args.asr_provider,
                    model=args.asr_model,
                    base_url=args.asr_base_url,
                    api_key=args.asr_api_key,
                ),
            )
            report["asr"] = {
                "ok": result.ok,
                "message": result.message,
                "text": result.text,
            }
            if not result.ok:
                exit_code = 1

    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return exit_code


def _tts_provider(provider_id: str, *, skip_playback: bool):
    if not skip_playback:
        return default_tts_provider_factory(provider_id)
    if provider_id == "edge_tts":
        return EdgeNeuralTTSProvider(audio_player=lambda path: None)
    if provider_id == "http_qwen3tts":
        return HttpQwen3TTSProvider(audio_player=lambda path: None)
    return default_tts_provider_factory(provider_id)


if __name__ == "__main__":
    raise SystemExit(main())
