from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.capability_runtime import apply_character_tts_profile
from guanghe_companion.capability_settings import ASRSettings, TTSSettings
from guanghe_companion.character_pack import load_character_pack, load_character_pack_from_dir
from guanghe_companion.voice_asr import default_asr_transcriber
from guanghe_companion.voice_tts import EdgeNeuralTTSProvider, HttpQwen3TTSProvider, default_tts_provider_factory


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test E-Moti voice providers.")
    parser.add_argument("--tts-provider", default="")
    parser.add_argument("--tts-text", default="")
    parser.add_argument("--tts-voice", default="")
    parser.add_argument("--tts-api-url", default="")
    parser.add_argument("--tts-model-variant", default="qwen3tts_0.6b_customvoice")
    parser.add_argument("--skip-playback", action="store_true")
    parser.add_argument("--character-id", default="")
    parser.add_argument("--character-pack-dir", default="")
    parser.add_argument("--asr-provider", default="")
    parser.add_argument("--asr-model", default="whisper-1")
    parser.add_argument("--asr-base-url", default="")
    parser.add_argument("--asr-api-key", default="")
    parser.add_argument("--asr-audio", default="")
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)

    report: dict[str, object] = {"tts": None, "asr": None}
    exit_code = 0

    character_pack = None
    character_profile: dict[str, object] = {}
    if args.character_pack_dir or args.character_id:
        try:
            character_pack = (
                load_character_pack_from_dir(Path(args.character_pack_dir))
                if args.character_pack_dir
                else load_character_pack(args.character_id)
            )
            character_profile = character_pack.tts_profile.to_runtime_dict()
        except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
            report["tts"] = {"ok": False, "message": f"character voice profile load failed: {exc}"}
            exit_code = 1

    if args.tts_provider or character_profile:
        tts_settings = apply_character_tts_profile(
            TTSSettings(
                enabled=True,
                provider=args.tts_provider,
                voice=args.tts_voice,
                api_url=args.tts_api_url,
                model_variant=args.tts_model_variant,
            ),
            character_profile,
        )
        provider = _tts_provider(tts_settings.provider, skip_playback=args.skip_playback)
        if provider is None:
            report["tts"] = {"ok": False, "message": f"TTS provider unavailable: {tts_settings.provider}"}
            exit_code = 1
        else:
            result = provider.speak(args.tts_text or _default_tts_text(character_pack), tts_settings)
            report["tts"] = {
                "ok": result.ok,
                "message": result.message,
                "audio_path": result.audio_path,
                "character_id": character_pack.character_id if character_pack is not None else "",
                "profile_id": tts_settings.profile_id,
                "provider": tts_settings.provider,
                "voice": tts_settings.voice,
                "model_variant": tts_settings.model_variant,
                "instruct_present": bool(tts_settings.instruct),
                "reference_audio_count": len(tts_settings.reference_audio),
                "reference_text_present": bool(tts_settings.reference_text),
            }
            if not result.ok:
                exit_code = 1

    if args.asr_provider:
        audio_path = Path(args.asr_audio)
        if not audio_path.exists():
            report["asr"] = {"ok": False, "message": "ASR audio file not found", "text": ""}
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


def _default_tts_text(character_pack) -> str:
    if character_pack is None:
        return "E-Moti voice test."
    return f"{character_pack.name} voice audition."


if __name__ == "__main__":
    raise SystemExit(main())
