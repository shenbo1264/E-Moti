from __future__ import annotations


def test_voice_profile_parses_qwen_designed_profile() -> None:
    from guanghe_companion.character_voice_profile import CharacterVoiceProfile

    profile = CharacterVoiceProfile.from_payload(
        {
            "profile_id": "xingxi_qwen_vivian_designed_v1",
            "display_name": "Xingxi Vivian",
            "provider": "http-qwen3tts",
            "api_url": " http://127.0.0.1:9880/ ",
            "language": "zh",
            "voice": "Vivian",
            "model_variant": "0.6B",
            "rate": 2,
            "volume": 0.8,
            "instruct": "gentle companion tone",
            "voice_source_type": "original_design",
            "training_status": "designed",
            "distribution_policy": "public_ok",
            "rights_note": "original voice direction",
        }
    )

    assert profile.profile_id == "xingxi_qwen_vivian_designed_v1"
    assert profile.provider == "http_qwen3tts"
    assert profile.model_variant == "qwen3tts_0.6b_customvoice"
    assert profile.voice == "Vivian"
    assert profile.instruct == "gentle companion tone"
    assert profile.voice_source_type == "original_design"
    assert profile.training_status == "designed"
    assert profile.distribution_policy == "public_ok"
    assert profile.reference_audio == ()
    assert profile.to_runtime_dict() == {
        "profile_id": "xingxi_qwen_vivian_designed_v1",
        "display_name": "Xingxi Vivian",
        "provider": "http_qwen3tts",
        "api_url": "http://127.0.0.1:9880/",
        "language": "zh",
        "voice": "Vivian",
        "model_variant": "qwen3tts_0.6b_customvoice",
        "rate": 2,
        "volume": 0.8,
        "instruct": "gentle companion tone",
        "voice_source_type": "original_design",
        "training_status": "designed",
        "distribution_policy": "public_ok",
    }


def test_voice_profile_exposes_reference_audio_and_text_for_runtime() -> None:
    from guanghe_companion.character_voice_profile import CharacterVoiceProfile

    profile = CharacterVoiceProfile.from_payload(
        {
            "profile_id": "local_clone",
            "provider": "http-qwen3tts",
            "model_variant": "qwen3tts_0.6b_base",
            "voice_source_type": "local_trained_clone",
            "training_status": "trained_local",
            "distribution_policy": "local_only",
            "reference_audio": ["voice/reference.wav"],
            "reference_text": "这是一段用于复刻角色语气的参考台词。",
        }
    )

    assert profile.reference_audio == ("voice/reference.wav",)
    assert profile.reference_text == "这是一段用于复刻角色语气的参考台词。"
    assert profile.to_runtime_dict()["reference_audio"] == ["voice/reference.wav"]
    assert profile.to_runtime_dict()["reference_text"] == "这是一段用于复刻角色语气的参考台词。"


def test_voice_profile_exposes_unified_gateway_and_bilingual_synthesis_fields() -> None:
    from guanghe_companion.character_voice_profile import CharacterVoiceProfile

    profile = CharacterVoiceProfile.from_payload(
        {
            "profile_id": "ikaros_unified_gateway_v1",
            "provider": "emoti-voice",
            "backend_provider": "gpt-sovits",
            "backend_api_url": " http://127.0.0.1:9882/ ",
            "backend_model_variant": "gptsovits-v2",
            "language": "zh",
            "display_language": "zh",
            "synthesis_language": "all_ja",
            "synthesis_text_mode": "profile_static_map",
            "synthesis_text_map": {
                "我在这里。": "マスター、私はここにいます。",
                "  ": "ignored",
                "bad\nkey": "ignored",
            },
        }
    )

    assert profile.provider == "http_emoti_voice"
    assert profile.backend_provider == "http_gptsovits"
    assert profile.backend_api_url == "http://127.0.0.1:9882/"
    assert profile.backend_model_variant == "gptsovits_v2"
    assert profile.display_language == "zh"
    assert profile.synthesis_language == "all_ja"
    assert profile.synthesis_text_mode == "profile_static_map"
    assert profile.synthesis_text_map == {"我在这里。": "マスター、私はここにいます。"}
    runtime = profile.to_runtime_dict()
    assert runtime["provider"] == "http_emoti_voice"
    assert runtime["backend_provider"] == "http_gptsovits"
    assert runtime["backend_api_url"] == "http://127.0.0.1:9882/"
    assert runtime["backend_model_variant"] == "gptsovits_v2"
    assert runtime["display_language"] == "zh"
    assert runtime["synthesis_language"] == "all_ja"
    assert runtime["synthesis_text_mode"] == "profile_static_map"
    assert runtime["synthesis_text_map"] == {"我在这里。": "マスター、私はここにいます。"}


def test_voice_profile_rejects_reference_audio_outside_voice_directory(tmp_path) -> None:
    from guanghe_companion.character_voice_profile import validate_voice_profile_payload

    errors: list[str] = []
    validate_voice_profile_payload(
        tmp_path,
        {
            "profile_id": "unsafe_reference",
            "voice_source_type": "local_trained_clone",
            "training_status": "trained_local",
            "distribution_policy": "local_only",
            "reference_audio": ["../sample.wav"],
        },
        "local_ugc_only",
        errors,
    )

    assert "character.json.tts_profile.reference_audio.0 must stay inside voice/" in errors


def test_voice_profile_allows_public_noncommercial_third_party_reference(tmp_path) -> None:
    from guanghe_companion.character_voice_profile import validate_voice_profile_payload

    errors: list[str] = []
    validate_voice_profile_payload(
        tmp_path,
        {
            "profile_id": "fanwork_public_clone",
            "voice_source_type": "third_party_reference",
            "training_status": "candidate",
            "distribution_policy": "public_ok",
        },
        "shareable_after_review",
        errors,
    )

    assert errors == []


def test_voice_profile_allows_private_local_fanwork_clone_as_local_only(tmp_path) -> None:
    from guanghe_companion.character_voice_profile import validate_voice_profile_payload

    voice_dir = tmp_path / "voice"
    voice_dir.mkdir()
    (voice_dir / "reference.wav").write_bytes(b"RIFFdemo")
    errors: list[str] = []

    validate_voice_profile_payload(
        tmp_path,
        {
            "profile_id": "local_fanwork_clone",
            "voice_source_type": "local_trained_clone",
            "training_status": "trained_local",
            "distribution_policy": "local_only",
            "rights_note": "local user-owned fanwork sample, not for redistribution",
            "reference_audio": ["voice/reference.wav"],
        },
        "private_local_fanwork",
        errors,
    )

    assert errors == []


def test_voice_profile_allows_private_fanwork_with_original_public_voice(tmp_path) -> None:
    from guanghe_companion.character_voice_profile import validate_voice_profile_payload

    errors: list[str] = []

    validate_voice_profile_payload(
        tmp_path,
        {
            "profile_id": "public_safe_original_voice",
            "voice_source_type": "original_design",
            "training_status": "designed",
            "distribution_policy": "public_ok",
        },
        "private_local_fanwork",
        errors,
    )

    assert errors == []
