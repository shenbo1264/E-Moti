from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def test_desktop_prompt_keeps_character_and_history_without_forcing_staged_speech(tmp_path):
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    try:
        controller._current_player_message = "只是随便聊聊。"
        controller.last_feedback = "唔，我听见了。你刚才说：只是随便聊聊。"
        request = ExpressionRequest.from_snapshot(
            controller.get_typed_snapshot(), context=controller._expression_context()
        )
        prompt = controller.ai_expressor.build_prompt(request)
        assert "xingxi_pixel_pet" in prompt
        assert "只是随便聊聊。" in prompt
        assert "slightly shy" in prompt or "微害羞" in prompt
        assert "recent_dialogue:" in prompt
        assert "唔，我听见了。你刚才说" not in prompt
        assert prompt.count(str(request.persona["speech_style"])) == 1
        assert "such as 从桌角探头" not in prompt
        assert "无需为每句添加" in prompt
        assert "不要替用户安排" in prompt
        assert "用户明确求助时" in prompt
        assert "不把猜测的情绪" in prompt
    finally:
        controller.close()
