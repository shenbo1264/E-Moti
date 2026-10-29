import json
from dataclasses import FrozenInstanceError, replace

import pytest

from guanghe_companion.character_pack import CharacterPack, load_default_character_pack
from guanghe_companion.character_performance_profile import CharacterPerformanceProfile
from guanghe_companion.persona import (
    MAX_PERSONA_FILE_BYTES,
    build_persona_payload,
    load_persona_profile,
)


def _pack(character_id="test_pet"):
    return CharacterPack(
        character_id=character_id,
        name="小星",
        title="安静的伙伴",
        description="表达简短，喜欢与用户一起探索。",
        spritesheet="spritesheet.png",
        default_mode="Calm",
        modes=("Calm",),
        mode_descriptions={"Calm": "安静"},
        motion_labels={"Idle": "休息"},
    )


def _performance(character_id="test_pet"):
    return CharacterPerformanceProfile(
        character_id=character_id,
        character_name="小星",
        speech_style="自然，简短，有自己的看法。",
        allowed_expression_ids=("neutral",),
        preferred_motion_ids=("Idle",),
        forbidden_claims=("不声称做过未发生的事情。",),
    )


def _write_persona(root, payload):
    (root / "persona.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_legacy_pack_keeps_existing_identity_and_style_without_new_file(tmp_path):
    pack = _pack()
    before = dict(pack.mode_descriptions)

    payload = build_persona_payload(pack, _performance(), pack_dir=tmp_path)

    assert payload["character_id"] == pack.character_id
    assert payload["character_name"] == pack.name
    assert payload["description"] == pack.description
    assert payload["speech_style"] == _performance().speech_style
    assert payload["traits"] == []  # No blanket personality rewrite of old characters.
    assert payload["boundaries"] == list(_performance().forbidden_claims)
    assert payload["source"] == "character_pack"
    assert payload["validation_warnings"] == []
    assert pack.mode_descriptions == before
    assert not (tmp_path / "persona.json").exists()


def test_bundled_default_pack_has_a_persona_without_migrating_assets():
    pack = load_default_character_pack()
    payload = build_persona_payload(pack)

    assert payload["character_name"] == "星汐"
    assert payload["character_id"] == "xingxi_pixel_pet"
    assert payload["speech_style"]
    assert payload["identity_version"] == "pack-v1"
    assert len(payload["config_hash"]) == 64


def test_optional_persona_configures_expression_without_importing_user_facts(tmp_path):
    _write_persona(tmp_path, {
        "schema_version": 1,
        "character_id": "test_pet",
        "identity_version": "author-v2",
        "speech_style": "好奇、自然，偶尔轻轻吐槽。",
        "traits": ["好奇", "有主见", "好奇"],
        "preferences": ["喜欢探索新事物"],
        "interaction_habits": ["用户安静时保持低频陪伴"],
        "boundaries": ["不以关系变化惩罚用户不回复"],
        "user_facts": ["用户住在一个秘密地点"],
        "mood": "angry",
        "relationship": {"level": 99},
        "memory": "把模型编造的旅行写成人格",
    })

    payload = build_persona_payload(_pack(), _performance(), pack_dir=tmp_path)

    assert payload["source"] == "persona.json"
    assert payload["identity_version"] == "author-v2"
    assert payload["traits"] == ["好奇", "有主见"]
    assert payload["interaction_habits"] == ["用户安静时保持低频陪伴"]
    assert payload["boundaries"] == ["不声称做过未发生的事情。", "不以关系变化惩罚用户不回复"]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "秘密地点" not in serialized
    assert "模型编造的旅行" not in serialized
    assert "mood" not in payload
    assert "relationship" not in payload


def test_config_hash_is_stable_across_location_key_order_and_ignored_runtime_data(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    _write_persona(tmp_path, {"traits": ["好奇"], "speech_style": "自然"})
    _write_persona(other, {"mood": "happy", "speech_style": "自然", "traits": ["好奇"]})

    left = build_persona_payload(_pack(), pack_dir=tmp_path)
    right = build_persona_payload(_pack(), pack_dir=other)

    assert left["config_hash"] == right["config_hash"]
    _write_persona(other, {"speech_style": "严肃", "traits": ["好奇"]})
    assert build_persona_payload(_pack(), pack_dir=other)["config_hash"] != left["config_hash"]
    assert build_persona_payload(replace(_pack(), name="另一角色"), pack_dir=tmp_path)["config_hash"] != left["config_hash"]


def test_persona_object_is_immutable_and_payload_mutations_do_not_change_identity(tmp_path):
    _write_persona(tmp_path, {"traits": ["好奇"]})
    profile = load_persona_profile(_pack(), pack_dir=tmp_path)

    with pytest.raises(FrozenInstanceError):
        profile.speech_style = "由一次聊天改写"
    changed = profile.to_payload()
    changed["traits"].append("讨好")
    assert profile.to_payload()["traits"] == ["好奇"]


@pytest.mark.parametrize("invalid", ["{invalid json", "[]", "null", "\ufeff{bad}"])
def test_bad_optional_file_falls_back_to_legacy_pack(tmp_path, invalid):
    (tmp_path / "persona.json").write_text(invalid, encoding="utf-8")

    payload = build_persona_payload(_pack(), _performance(), pack_dir=tmp_path)

    assert payload["source"] == "character_pack"
    assert payload["speech_style"] == _performance().speech_style
    assert payload["validation_warnings"]


@pytest.mark.parametrize("override", [
    {"character_id": "other_pet", "speech_style": "其他角色的秘密风格"},
    {"schema_version": 99, "speech_style": "未知格式"},
    {"schema_version": True, "speech_style": "布尔值不等于版本1"},
])
def test_mismatched_character_or_schema_cannot_replace_persona(tmp_path, override):
    _write_persona(tmp_path, override)

    payload = build_persona_payload(_pack(), _performance(), pack_dir=tmp_path)

    assert payload["source"] == "character_pack"
    assert payload["speech_style"] == _performance().speech_style
    assert payload["validation_warnings"]


def test_wrong_character_performance_profile_cannot_leak_style_or_claims():
    performance = replace(_performance("other_pet"), speech_style="其他角色的风格", forbidden_claims=("其他角色秘密",))

    payload = build_persona_payload(_pack(), performance)

    assert "其他角色" not in payload["speech_style"]
    assert payload["boundaries"] == []
    assert payload["validation_warnings"]


def test_optional_file_cannot_follow_symlink_outside_pack(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text('{"speech_style": "outside secret"}', encoding="utf-8")
    pack_dir = tmp_path / "pack"
    pack_dir.mkdir()
    try:
        (pack_dir / "persona.json").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")

    payload = build_persona_payload(_pack(), pack_dir=pack_dir)

    assert payload["source"] == "character_pack"
    assert "outside secret" not in json.dumps(payload)
    assert payload["validation_warnings"]


def test_oversized_optional_file_is_not_used(tmp_path):
    _write_persona(tmp_path, {"speech_style": "x" * (MAX_PERSONA_FILE_BYTES + 1)})

    payload = build_persona_payload(_pack(), pack_dir=tmp_path)

    assert payload["source"] == "character_pack"
    assert payload["validation_warnings"]


def test_text_fields_are_bounded_and_only_strings_enter_prompt(tmp_path):
    _write_persona(tmp_path, {
        "speech_style": "自然\n\x00表达\t" + "长" * 4000,
        "traits": ["好奇", {"user_fact": "secret"}, 42, "", "善于\n倾听"] + [str(i) for i in range(100)],
        "preferences": {"user_city": "secret"},
    })

    payload = build_persona_payload(_pack(), pack_dir=tmp_path)

    assert len(payload["speech_style"]) <= 500
    assert len(payload["traits"]) <= 12
    assert all(isinstance(item, str) for item in payload["traits"])
    assert "\n" not in payload["speech_style"]
    assert "\x00" not in payload["speech_style"]
    assert payload["preferences"] == []


def test_optional_config_is_read_only(tmp_path):
    _write_persona(tmp_path, {"traits": ["好奇"]})
    path = tmp_path / "persona.json"
    original = path.read_bytes()

    for _ in range(3):
        build_persona_payload(_pack(), pack_dir=tmp_path)

    assert path.read_bytes() == original
    assert sorted(p.name for p in tmp_path.iterdir()) == ["persona.json"]
