import pytest

from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


@pytest.mark.parametrize("mode", ["auto", "review"])
@pytest.mark.parametrize("explicit_seed", [False, True])
def test_weekly_change_survives_empty_history_restart(tmp_path, mode, explicit_seed):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    if explicit_seed:
        c.memory_album_controller.remember_explicit("我每周六去游泳。", now=0)
    else:
        c.submit_dialogue_request(DialogueRequest("我每周六去游泳。"))
    c.submit_dialogue_request(DialogueRequest("我每周三去跑步。"))
    c.set_chat_memory_mode(mode)
    c.submit_dialogue_request(DialogueRequest("我以后改成周日去游泳了。"))
    assert c.last_chat_memory_result.status == ("saved" if mode == "auto" else "pending")
    if mode == "review":
        c.memory_album_controller.confirm_pending(next(iter(c.story_runtime.memory.pending_candidates)), now=0)
    c.clear_dialogue_history()
    c.close()
    c = PluginEnabledCompanionController(user_data_root=tmp_path)
    try:
        active = [m.summary for m in c.story_runtime.memory.store.load_memories() if not m.deleted]
        assert "用户每周日去游泳" in active and "用户每周三去跑步" in active
        assert not any("周六" in s for s in active)
        c._current_player_message = "我每周几去游泳？"
        def prompt():
            context = c.get_expression_context()
            assert not context["recent_dialogue"]
            return c.ai_expressor.build_prompt(ExpressionRequest.from_snapshot(c.get_typed_snapshot(), context=context))
        assert "周日" in prompt() and "周六" not in prompt()
        c.submit_dialogue_request(DialogueRequest("请忘记我的游泳安排。"))
        assert "周日" not in prompt() and "周六" not in prompt()
        assert any("跑步" in m.summary for m in c.story_runtime.memory.store.load_memories() if not m.deleted)
    finally:
        c.close()


@pytest.mark.parametrize("text", ["我以后改成周日去游泳了。", "如果我每周日去游泳。", "我每周日不去游泳。"])
def test_no_weekly_schedule_is_invented_without_grounding(tmp_path, text):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        c.submit_dialogue_request(DialogueRequest(text))
        assert not [m for m in c.story_runtime.memory.store.load_memories() if not m.deleted]
    finally:
        c.close()
