import json
from pathlib import Path

from PIL import Image

from guanghe_companion.character_pack import load_character_pack_from_dir, load_default_character_pack, resolve_motion_caption
from guanghe_companion.character_registry import validate_character_pack_dir
from guanghe_companion.engine import BUYABLE_ITEMS


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_load_default_character_pack_reads_xingxi_pixel_pet_manifest():
    pack = load_default_character_pack()

    assert pack.character_id == "xingxi_pixel_pet"
    assert pack.name == "星汐"
    assert pack.default_mode == "Calm"
    assert "Glow" in pack.modes
    assert pack.motion_labels["TouchHead"] == "招手回应"
    assert pack.tts_profile.profile_id == "xingxi_pixel_pet_qwen_vivian_v1"
    assert pack.tts_profile.provider == "http_emoti_voice"
    assert pack.tts_profile.backend_provider == "http_qwen3tts"
    assert pack.tts_profile.voice == "Vivian"
    assert pack.tts_profile.voice_source_type == "original_design"
    assert pack.tts_profile.distribution_policy == "public_ok"


def test_load_default_character_pack_reads_spritesheet_filename():
    pack = load_default_character_pack()

    assert pack.spritesheet == "spritesheet.png"
    assert pack.renderer.backend == "sprite"
    assert pack.renderer.motion_map["Play"] == "Play"
    assert pack.renderer.expression_map["joy"] == "TouchHead"


def test_load_character_pack_reads_optional_tts_profile(tmp_path):
    pack_dir = tmp_path / "voice_pet"
    pack_dir.mkdir()
    (pack_dir / "character.json").write_text(
        json.dumps(
            {
                "character_id": "voice_pet",
                "name": "Voice Pet",
                "title": "Voice profile test",
                "description": "Character with a TTS profile.",
                "spritesheet": "spritesheet.png",
                "motion_manifest": "motion_manifest.json",
                "default_mode": "Calm",
                "modes": ["Calm"],
                "mode_descriptions": {"Calm": "Calm"},
                "motion_labels": {"Default": "Idle"},
                "tts_profile": {
                    "profile_id": "voice_pet_qwen_v1",
                    "provider": "http-qwen3tts",
                    "model_variant": "0.6B",
                    "voice": "Microsoft Huihui Desktop",
                    "rate": 2,
                    "volume": 0.8,
                    "instruct": "soft test voice",
                    "voice_source_type": "original_design",
                    "training_status": "designed",
                    "distribution_policy": "public_ok",
                },
            }
        ),
        encoding="utf-8",
    )

    pack = load_character_pack_from_dir(pack_dir)

    assert pack.tts_profile.to_runtime_dict() == {
        "profile_id": "voice_pet_qwen_v1",
        "provider": "http_qwen3tts",
        "voice": "Microsoft Huihui Desktop",
        "model_variant": "qwen3tts_0.6b_customvoice",
        "rate": 2,
        "volume": 0.8,
        "instruct": "soft test voice",
        "voice_source_type": "original_design",
        "training_status": "designed",
        "distribution_policy": "public_ok",
    }


def test_bundled_xingxi_pixel_pet_pack_is_valid_sprite_candidate():
    pack_dir = REPO_ROOT / "assets" / "companion" / "xingxi_pixel_pet"

    report = validate_character_pack_dir(pack_dir)
    pack = load_character_pack_from_dir(pack_dir)

    assert report.ok is True
    assert pack.character_id == "xingxi_pixel_pet"
    assert pack.renderer.backend == "sprite"
    assert pack.renderer.expression_map["goofy"] == "Play"


def test_bundled_original_oc_pack_remains_valid_fallback():
    pack_dir = REPO_ROOT / "assets" / "companion" / "original_oc"

    report = validate_character_pack_dir(pack_dir)
    pack = load_character_pack_from_dir(pack_dir)

    assert report.ok is True
    assert pack.character_id == "original_oc"
    assert pack.renderer.backend == "portrait"


def test_bundled_submission_character_packs_are_valid_and_visible():
    expected = {
        "xingxi_pixel_pet": "星汐",
        "ikaros_pixel_pet": "伊卡洛斯",
        "nairong_pixel_pet": "奶龙",
    }

    for character_id, name in expected.items():
        pack_dir = REPO_ROOT / "assets" / "companion" / character_id
        report = validate_character_pack_dir(pack_dir)
        pack = load_character_pack_from_dir(pack_dir)
        payload = json.loads((pack_dir / "character.json").read_text(encoding="utf-8-sig"))

        assert report.ok is True
        assert pack.character_id == character_id
        assert pack.name == name
        assert pack.renderer.backend == "sprite"
        assert payload.get("hide_from_character_library") is not True
        assert (pack_dir / "preview" / "profile.png").is_file()


def test_bundled_characters_use_unified_voice_gateway_profiles():
    for character_id in ("xingxi_pixel_pet", "ikaros_pixel_pet", "nairong_pixel_pet"):
        pack_dir = REPO_ROOT / "assets" / "companion" / character_id
        report = validate_character_pack_dir(pack_dir)
        pack = load_character_pack_from_dir(pack_dir)

        assert report.ok is True
        assert pack.tts_profile.provider == "http_emoti_voice"


def test_bundled_ikaros_keeps_trained_gptsovits_backend_voice_profile():
    pack_dir = REPO_ROOT / "assets" / "companion" / "ikaros_pixel_pet"

    report = validate_character_pack_dir(pack_dir)
    pack = load_character_pack_from_dir(pack_dir)

    assert report.ok is True
    assert pack.tts_profile.provider == "http_emoti_voice"
    assert pack.tts_profile.backend_provider == "http_gptsovits"
    assert pack.tts_profile.backend_model_variant == "gptsovits_v2"
    assert pack.tts_profile.display_language == "zh"
    assert pack.tts_profile.synthesis_language == "all_ja"
    assert pack.tts_profile.synthesis_text_mode == "profile_static_map"
    assert pack.tts_profile.training_status == "trained_local"
    assert pack.tts_profile.reference_text
    assert len(pack.tts_profile.reference_audio) == 1
    assert Path(pack.tts_profile.reference_audio[0]).is_file()

def test_load_character_pack_resolves_voice_references_to_pack_directory(tmp_path):
    pack_dir = tmp_path / "voice_clone_pet"
    (pack_dir / "voice").mkdir(parents=True)
    (pack_dir / "voice" / "reference.wav").write_bytes(b"RIFFdemo")
    (pack_dir / "character.json").write_text(
        json.dumps(
            {
                "character_id": "voice_clone_pet",
                "name": "Voice Clone Pet",
                "title": "Voice clone test",
                "description": "Character with a local reference voice.",
                "spritesheet": "spritesheet.png",
                "motion_manifest": "motion_manifest.json",
                "default_mode": "Calm",
                "modes": ["Calm"],
                "mode_descriptions": {"Calm": "Calm"},
                "motion_labels": {"Default": "Idle"},
                "tts_profile": {
                    "profile_id": "voice_clone_pet_local_v1",
                    "provider": "http-qwen3tts",
                    "model_variant": "qwen3tts_0.6b_base",
                    "voice_source_type": "local_trained_clone",
                    "training_status": "trained_local",
                    "distribution_policy": "local_only",
                    "reference_audio": ["voice/reference.wav"],
                    "reference_text": "参考声音用于本地克隆。",
                },
            }
        ),
        encoding="utf-8",
    )

    pack = load_character_pack_from_dir(pack_dir)

    assert pack.tts_profile.reference_audio == (str((pack_dir / "voice" / "reference.wav").resolve()),)
    assert pack.tts_profile.reference_text == "参考声音用于本地克隆。"



def test_load_character_pack_reads_live2d_renderer_model_path(tmp_path):
    pack_dir = tmp_path / "live2d_character"
    (pack_dir / "live2d").mkdir(parents=True)
    Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    (pack_dir / "motion_manifest.json").write_text(
        json.dumps(
            {
                "sheet_columns": 1,
                "sheet_rows": 1,
                "frame_width": 16,
                "frame_height": 16,
                "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
            }
        ),
        encoding="utf-8",
    )
    (pack_dir / "character.json").write_text(
        json.dumps(
            {
                "character_id": "live2d_character",
                "name": "Live2D",
                "title": "Live2D companion",
                "description": "Live2D test pack",
                "spritesheet": "spritesheet.png",
                "motion_manifest": "motion_manifest.json",
                "default_mode": "Calm",
                "modes": ["Calm"],
                "mode_descriptions": {"Calm": "Calm"},
                "motion_labels": {"Default": "Idle"},
                "renderer": {
                    "backend": "live2d_web",
                    "model": "live2d/Xingxi.model3.json",
                    "motion_map": {"Play": "TapBody"},
                    "expression_map": {"excited": "F02"},
                },
            }
        ),
        encoding="utf-8",
    )

    pack = load_character_pack_from_dir(pack_dir)

    assert pack.renderer.backend == "live2d_web"
    assert pack.renderer.model == "live2d/Xingxi.model3.json"
    assert pack.renderer.motion_map["Play"] == "TapBody"
    assert pack.renderer.expression_map["excited"] == "F02"


def test_load_character_pack_reads_portrait_renderer_manifest_path(tmp_path):
    pack_dir = tmp_path / "portrait_character"
    pack_dir.mkdir()
    Image.new("RGBA", (192, 1872), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    (pack_dir / "motion_manifest.json").write_text(
        json.dumps(
            {
                "sheet_columns": 1,
                "sheet_rows": 9,
                "frame_width": 192,
                "frame_height": 208,
                "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
            }
        ),
        encoding="utf-8",
    )
    (pack_dir / "character.json").write_text(
        json.dumps(
            {
                "character_id": "portrait_character",
                "name": "Portrait",
                "title": "Portrait companion",
                "description": "Portrait test pack",
                "spritesheet": "spritesheet.png",
                "motion_manifest": "motion_manifest.json",
                "default_mode": "Calm",
                "modes": ["Calm"],
                "mode_descriptions": {"Calm": "Calm"},
                "motion_labels": {"Default": "Idle"},
                "renderer": {
                    "backend": "portrait",
                    "portrait_manifest": "portrait_manifest.json",
                    "expression_map": {"focused": "thinking"},
                },
            }
        ),
        encoding="utf-8",
    )

    pack = load_character_pack_from_dir(pack_dir)

    assert pack.renderer.backend == "portrait"
    assert pack.renderer.portrait_manifest == "portrait_manifest.json"
    assert pack.renderer.expression_map["focused"] == "thinking"


def test_load_default_character_pack_reads_relationship_badges_from_existing_item_icons():
    pack = load_default_character_pack()

    assert pack.relationship_decorations == (
        {
            "unlock_id": "unlock_first_nickname",
            "item_id": "star_hairpin",
            "label": "星形发夹",
            "icon": "item_icons/star_hairpin.png",
        },
        {
            "unlock_id": "unlock_shared_ritual",
            "item_id": "comet_ribbon",
            "label": "彗尾丝带",
            "icon": "item_icons/comet_ribbon.png",
        },
    )
    for decoration in pack.relationship_decorations:
        item = BUYABLE_ITEMS[decoration["item_id"]]
        assert decoration["icon"] == item.icon


def test_resolve_motion_caption_uses_pack_motion_labels():
    pack = load_default_character_pack()

    caption = resolve_motion_caption(pack, motion="Study", mode="Calm", allowed=True)
    blocked = resolve_motion_caption(pack, motion="SwitchDown", mode="Overload", allowed=False)

    assert "专注检查" in caption
    assert "Overload" in blocked
