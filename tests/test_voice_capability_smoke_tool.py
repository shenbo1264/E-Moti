from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_voice_smoke_tool_runs_as_direct_script_from_repo_root(tmp_path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    report = tmp_path / "report.json"

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "tools" / "voice_capability_smoke.py"),
            "--report",
            str(report),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(report.read_text(encoding="utf-8")) == {"tts": None, "asr": None}


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


def test_voice_smoke_tool_reads_tts_text_from_utf8_file(tmp_path, monkeypatch) -> None:
    from guanghe_companion.voice_tts import TTSResult
    from tools import voice_capability_smoke

    text_file = tmp_path / "tts.txt"
    text = "\u30de\u30b9\u30bf\u30fc\u3001\u305d\u3070\u306b\u3044\u307e\u3059\u3002"
    text_file.write_text(text, encoding="utf-8")
    calls = []

    class FakeProvider:
        def speak(self, text, settings):
            calls.append(text)
            return TTSResult(True, "spoken", str(tmp_path / "out.wav"))

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
            "http_gptsovits",
            "--tts-text-file",
            str(text_file),
            "--report",
            str(report),
        ]
    )

    assert code == 0
    assert calls == [text]


def test_voice_smoke_tool_uses_character_tts_profile_from_pack_dir(tmp_path, monkeypatch) -> None:
    from PIL import Image

    from guanghe_companion.voice_tts import TTSResult
    from tools import voice_capability_smoke

    pack_dir = tmp_path / "custom_character"
    (pack_dir / "item_icons").mkdir(parents=True)
    (pack_dir / "preview").mkdir()
    (pack_dir / "voice").mkdir()
    (pack_dir / "voice" / "reference.wav").write_bytes(b"RIFFdemo")
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(pack_dir / "item_icons" / "snack.png")
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(pack_dir / "preview" / "contact-sheet.png")
    (pack_dir / "character.json").write_text(
        json.dumps(
            {
                "character_id": "custom_character",
                "name": "Custom",
                "title": "Voice pack",
                "description": "A test character.",
                "spritesheet": "spritesheet.png",
                "motion_manifest": "motion_manifest.json",
                "default_mode": "Calm",
                "modes": ["Calm"],
                "mode_descriptions": {"Calm": "Calm reply."},
                "motion_labels": {"Default": "Idle"},
                "tts_profile": {
                    "profile_id": "custom_qwen_voice_v1",
                    "display_name": "Custom Qwen voice",
                    "provider": "http-qwen3tts",
                    "api_url": "http://127.0.0.1:9880/",
                    "language": "zh",
                    "voice": "Serena",
                    "model_variant": "qwen3tts_0.6b_base",
                    "rate": -1,
                    "volume": 0.75,
                    "instruct": "soft, clear, character-specific",
                    "voice_source_type": "local_generated",
                    "training_status": "candidate",
                    "distribution_policy": "public_ok",
                    "reference_audio": ["voice/reference.wav"],
                    "reference_text": "reference line",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (pack_dir / "dialogue_style.json").write_text(
        json.dumps({"tone": "calm", "keywords": ["voice"], "fallback_style": "short"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (pack_dir / "motion_manifest.json").write_text(
        json.dumps(
            {
                "sheet_columns": 8,
                "sheet_rows": 9,
                "frame_width": 192,
                "frame_height": 208,
                "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
            }
        ),
        encoding="utf-8",
    )
    (pack_dir / "shop_items.json").write_text(
        json.dumps(
            [
                {
                    "item_id": "snack",
                    "name": "Snack",
                    "category": "food",
                    "icon": "item_icons/snack.png",
                    "price": 1,
                    "effects": {"mood": 1},
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    calls = []

    class FakeProvider:
        def speak(self, text, settings):
            calls.append((text, settings))
            return TTSResult(True, "spoken", str(tmp_path / "voice.wav"))

        def stop(self):
            pass

    monkeypatch.setattr(voice_capability_smoke, "_tts_provider", lambda provider, *, skip_playback: FakeProvider())
    report = tmp_path / "report.json"

    code = voice_capability_smoke.main(
        [
            "--character-pack-dir",
            str(pack_dir),
            "--tts-text",
            "role audition",
            "--skip-playback",
            "--report",
            str(report),
        ]
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert code == 0
    assert calls
    assert calls[0][0] == "role audition"
    assert calls[0][1].profile_id == "custom_qwen_voice_v1"
    assert calls[0][1].provider == "http_qwen3tts"
    assert calls[0][1].voice == "Serena"
    assert calls[0][1].model_variant == "qwen3tts_0.6b_base"
    assert calls[0][1].rate == -1
    assert calls[0][1].volume == 0.75
    assert calls[0][1].instruct == "soft, clear, character-specific"
    assert calls[0][1].reference_audio == (str((pack_dir / "voice" / "reference.wav").resolve()),)
    assert calls[0][1].reference_text == "reference line"
    assert payload["tts"]["character_id"] == "custom_character"
    assert payload["tts"]["profile_id"] == "custom_qwen_voice_v1"
    assert payload["tts"]["voice"] == "Serena"
    assert payload["tts"]["model_variant"] == "qwen3tts_0.6b_base"
    assert payload["tts"]["instruct_present"] is True
    assert payload["tts"]["reference_audio_count"] == 1
    assert payload["tts"]["reference_text_present"] is True


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


def test_voice_smoke_tool_can_skip_qt_playback_for_gptsovits(tmp_path, monkeypatch) -> None:
    from guanghe_companion.voice_tts import TTSResult
    from tools import voice_capability_smoke

    constructed = {}

    class FakeGPTSoVITSProvider:
        def __init__(self, *, audio_player):
            constructed["audio_player"] = audio_player

        def speak(self, text, settings):
            constructed["spoken"] = (text, settings.provider)
            return TTSResult(True, "spoken", str(tmp_path / "out.wav"))

        def stop(self):
            pass

    monkeypatch.setattr(voice_capability_smoke, "HttpGPTSoVITSProvider", FakeGPTSoVITSProvider)
    report = tmp_path / "report.json"

    code = voice_capability_smoke.main(
        [
            "--tts-provider",
            "http_gptsovits",
            "--tts-text",
            "Ikaros voice smoke.",
            "--skip-playback",
            "--report",
            str(report),
        ]
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["tts"]["ok"] is True
    assert constructed["spoken"] == ("Ikaros voice smoke.", "http_gptsovits")
    assert callable(constructed["audio_player"])


def test_voice_smoke_tool_can_skip_qt_playback_for_emoti_voice_gateway(tmp_path, monkeypatch) -> None:
    from guanghe_companion.voice_tts import TTSResult
    from tools import voice_capability_smoke

    constructed = {}

    class FakeGatewayProvider:
        def __init__(self, *, audio_player):
            constructed["audio_player"] = audio_player

        def speak(self, text, settings):
            constructed["spoken"] = (text, settings.provider)
            return TTSResult(True, "spoken", str(tmp_path / "out.wav"))

        def stop(self):
            pass

    monkeypatch.setattr(voice_capability_smoke, "EmotiVoiceGatewayProvider", FakeGatewayProvider)
    report = tmp_path / "report.json"

    code = voice_capability_smoke.main(
        [
            "--tts-provider",
            "http_emoti_voice",
            "--tts-text",
            "Unified gateway smoke.",
            "--skip-playback",
            "--report",
            str(report),
        ]
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["tts"]["ok"] is True
    assert constructed["spoken"] == ("Unified gateway smoke.", "http_emoti_voice")
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
