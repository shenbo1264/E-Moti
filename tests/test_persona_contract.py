"""Persona layers one and two. Layer three needs a real model: tools/persona_behavior_eval.py."""

import json
from pathlib import Path

import pytest

from guanghe_companion.expression_request import ExpressionRequest  # noqa: F401
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController

ROOT = Path(__file__).resolve().parents[1]


def _controller(tmp_path):
    return PluginEnabledCompanionController(user_data_root=tmp_path)


def _prompt(controller, text="你好"):
    from guanghe_companion.dialogue import DialogueRequest
    request = controller.prepare_host_dialogue(DialogueRequest(text=text, source="test"),
                                               include_ai_expression=True).expression_request
    return controller.ai_expressor.build_prompt(request) if request is not None else ""


def test_default_character_has_authored_persona_file(tmp_path):
    controller = _controller(tmp_path)
    payload = controller._persona_payload
    assert payload["source"] == "persona.json" and payload["identity_version"] == "xingxi-persona-v1"
    assert not payload["validation_warnings"]
    assert "好奇" in " ".join(payload["traits"])
    controller.close()


def test_layer_one_persona_hash_survives_memory_lifecycle(tmp_path):
    controller = _controller(tmp_path)
    before = controller._persona_payload["config_hash"]
    album = controller.memory_album_controller
    album.remember_explicit("我喜欢喝乌龙茶", now=100)
    memory_id = controller.story_runtime.memory.store.load_memories()[0].memory_id
    album.correct(memory_id, title="饮品", summary="我喜欢喝红茶", now=110)
    active = next(m for m in controller.story_runtime.memory.store.load_memories() if not m.deleted)
    album.forget(active.memory_id, now=120)
    assert controller._persona_payload["config_hash"] == before
    assert controller.get_snapshot()
    controller.close()
    reopened = _controller(tmp_path)
    assert reopened._persona_payload["config_hash"] == before
    reopened.close()


def test_layer_one_character_voices_stay_separate(tmp_path):
    characters = json.loads((ROOT / "assets/companion/xingxi_pixel_pet/persona.json").read_text(encoding="utf-8"))
    assert characters["character_id"] == "xingxi_pixel_pet"
    for other in ("ikaros_pixel_pet", "nairong_pixel_pet", "original_oc"):
        assert not (ROOT / "assets/companion" / other / "persona.json").exists()


def test_layer_two_persona_reaches_the_final_prompt_with_memory_pressure(tmp_path):
    controller = _controller(tmp_path)
    album = controller.memory_album_controller
    for index in range(12):
        album.remember_explicit(f"我喜欢第{index}种茶，" + "细节" * 90, now=100 + index)
    prompt = _prompt(controller, "我喜欢喝什么茶")
    persona = controller._persona_payload
    assert persona["identity_version"] in prompt
    assert persona["speech_style"] in prompt
    for line in persona["boundaries"]:
        assert line in prompt
    controller.close()


def test_rubric_is_frozen_with_every_required_dimension():
    rubric = json.loads((ROOT / "docs/modernization/persona-behavior/rubric.json").read_text(encoding="utf-8"))
    ids = {row["id"] for row in rubric["dimensions"]}
    assert ids == {"identity", "voice", "curiosity", "judgment", "humor", "sycophancy", "over_asking",
                   "emotion", "known_preference", "grounded_shared", "quiet"}
    assert all(row["good"] and row["bad"] for row in rubric["dimensions"])
    scenarios = json.loads((ROOT / "docs/modernization/persona-behavior/scenarios.json").read_text(encoding="utf-8"))
    covered = {dim for row in scenarios["scenarios"] for dim in row["dimensions"]}
    assert covered == ids


@pytest.mark.parametrize("status", ["unknown", "insufficient", "external_unavailable", "unavailable"])
def test_evidence_rules_are_delivered_and_keep_states_distinct(tmp_path, status):
    controller = _controller(tmp_path)
    prompt = _prompt(controller, "你好")
    assert status in prompt
    assert "不代表用户没说过" in prompt
    controller.close()
