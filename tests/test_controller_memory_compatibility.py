"""Existing desktop/host entry points must use the authoritative memory path."""
import pytest

from guanghe_companion.controller import CompanionController
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def _prompt(controller, query="称呼和饮品偏好"):
    controller._current_player_message = query
    try:
        context = controller.get_expression_context()
        request = ExpressionRequest.from_snapshot(controller.get_typed_snapshot(), context=context)
        return controller.ai_expressor.build_prompt(request)
    finally:
        controller._current_player_message = ""


def _active(controller):
    return [entry for entry in controller.story_runtime.memory.store.load_memories() if not entry.deleted]


def test_alias_edit_after_unrelated_forget_reaches_prompt_and_retires_previous_alias(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        unrelated = c.story_runtime.memory.remember(kind="玩家希望被记住", title="杯子",
            summary="用户喜欢绿杯子", source="explicit_user_request", now=1)
        c.story_runtime.memory.forget(unrelated.memory_id, now=2)
        c.set_player_alias("阿蓝")
        first_alias = next(entry for entry in _active(c) if "阿蓝" in entry.summary)
        assert "阿蓝" in _prompt(c)

        c.set_player_alias("阿紫")
        text = _prompt(c)
        assert "阿紫" in text and "阿蓝" not in text
        assert c.state.player_alias == "阿紫"
        assert c.story_runtime.memory.valid_profile(now=c.now).player_alias == "阿紫"
        assert next(entry for entry in c.story_runtime.memory.store.load_memories()
                    if entry.memory_id == first_alias.memory_id).deleted

        c.set_player_alias("")
        assert c.state.player_alias == ""
        assert c.story_runtime.memory.valid_profile(now=c.now).player_alias == ""
        assert "阿紫" not in _prompt(c)
    finally:
        c.close()


def test_forgetting_alias_does_not_reimport_state_but_explicit_reentry_is_new_evidence(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        c.set_player_alias("小梧桐")
        old = next(entry for entry in _active(c) if "小梧桐" in entry.summary)
        c.memory_album_controller.forget(old.memory_id, now=1)
        assert "小梧桐" not in _prompt(c)
    finally:
        c.close()

    c = PluginEnabledCompanionController(user_data_root=tmp_path)
    try:
        assert "小梧桐" not in _prompt(c)
        c.set_player_alias("小梧桐")  # Explicit user action, even at the same logical clock.
        assert "小梧桐" in _prompt(c)
        assert all(entry.memory_id != old.memory_id for entry in _active(c))
    finally:
        c.close()


def test_existing_saved_alias_is_migrated_once_to_evidenced_profile(tmp_path):
    old = CompanionController(user_data_root=tmp_path, auto_load=False)
    old.set_player_alias("小青柚")
    old.close()
    c = PluginEnabledCompanionController(user_data_root=tmp_path)
    try:
        assert c.state.player_alias == "小青柚"
        assert c.story_runtime.memory.valid_profile(now=c.now).player_alias == "小青柚"
        assert "小青柚" in _prompt(c)
    finally:
        c.close()


def test_legacy_keyed_write_updates_one_authoritative_fact_and_keeps_return_contract(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        snapshot = c.upsert_long_term_memory(key="preference:drink", category="preference",
            summary="用户喜欢焙茶拿铁", source="explicit_user_request")
        assert isinstance(snapshot, dict) and snapshot["character_id"] == c.state.character_id
        assert "焙茶拿铁" in _prompt(c, "饮品偏好")
        original = _active(c)
        assert len(original) == 1
        assert original[0].user_confirmed is False
        assert "用户确认" not in original[0].tags
        assert not c.long_term_memory_service.entries  # No second active write target.

        c.upsert_long_term_memory(key="preference:drink", category="preference",
            summary="用户喜欢白桃乌龙", source="explicit_user_request")
        assert len(_active(c)) == 1
        assert _active(c)[0].version > original[0].version
        text = _prompt(c, "饮品偏好")
        assert "白桃乌龙" in text and "焙茶拿铁" not in text
    finally:
        c.close()


def test_retired_legacy_key_cannot_replay_but_independent_explicit_source_can(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        c.upsert_long_term_memory(key="preference:drink", category="preference", summary="用户喜欢焙茶拿铁")
        old = _active(c)[0]
        c.story_runtime.memory.forget(old.memory_id, now=1)
        with pytest.raises(ValueError, match="retired"):
            c.upsert_long_term_memory(key="preference:drink", category="preference", summary="用户喜欢焙茶拿铁")
        assert "焙茶拿铁" not in _prompt(c, "饮品偏好")
        c.story_runtime.memory.remember(kind="玩家希望被记住", title="用户重新确认饮品",
            summary="用户喜欢焙茶拿铁", source="explicit_user_request", now=2,
            source_ids=("new-explicit-confirmation",))
        assert "焙茶拿铁" in _prompt(c, "饮品偏好")
    finally:
        c.close()


@pytest.mark.parametrize("kwargs", [
    {"key": "task:build", "category": "task", "summary": "临时编译状态"},
    {"key": "preference:drink", "category": "preference", "summary": "虚构的偏好", "source": "model"},
])
def test_legacy_host_api_rejects_unsupported_or_unconfirmed_model_fact(tmp_path, kwargs):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        with pytest.raises(ValueError):
            c.upsert_long_term_memory(**kwargs)
        assert not _active(c)
    finally:
        c.close()


def test_expression_settings_replacement_keeps_actual_character_performance_profile(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        c.switch_character("original_oc", include_ai_expression=False)
        original = c.ai_expressor.dialogue_policy.performance_profile
        identity = dict(c._persona_payload)
        c.update_expression_settings(c.get_expression_settings())
        assert c.ai_expressor.dialogue_policy.performance_profile == original
        assert original.character_id == c.state.character_id == "original_oc"
        assert c._persona_payload == identity
        assert "Profile character:" in _prompt(c)
    finally:
        c.close()
