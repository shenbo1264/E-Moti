from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.expression_settings import ExpressionSettingsStore
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController
from tools.eval_chat_memory_benchmark import replay_turn


def test_replay_preserves_assistant_without_turning_it_into_user_fact(tmp_path):
    controller = PluginEnabledCompanionController(user_data_root=tmp_path,
        ai_expressor=ShinsekaiAIExpressor(enabled=False),
        expression_settings_store=ExpressionSettingsStore(tmp_path / "offline.json"))
    try:
        replay_turn(controller, {"轮次": 1, "逻辑时间": "2026-01-01T10:00:00+08:00",
            "用户消息": "我喜欢乌龙茶。", "助手回复": "我喜欢草莓冰激凌。"})
        assert controller.dialogue_history[-1].text == "我喜欢草莓冰激凌。"
        memories = controller.story_runtime.memory.store.load_memories()
        assert any("乌龙茶" in entry.summary for entry in memories)
        assert not any("草莓" in entry.summary for entry in memories)
    finally:
        controller.close()


def test_replay_uses_native_forgetting_history_barrier(tmp_path):
    controller = PluginEnabledCompanionController(user_data_root=tmp_path,
        ai_expressor=ShinsekaiAIExpressor(enabled=False),
        expression_settings_store=ExpressionSettingsStore(tmp_path / "offline.json"))
    try:
        replay_turn(controller, {"轮次": 1, "逻辑时间": "2026-01-01T10:00:00+08:00",
            "用户消息": "我喜欢乌龙茶。", "助手回复": "嗯。"})
        replay_turn(controller, {"轮次": 2, "逻辑时间": "2026-01-02T10:00:00+08:00",
            "用户消息": "忘掉我的饮料偏好。", "助手回复": "好，忘掉了。"})
        assert controller.last_chat_memory_result.status == "forgotten"
        assert all(entry.context_epoch < controller._dialogue_context_epoch()
            for entry in controller.dialogue_history)
    finally:
        controller.close()
