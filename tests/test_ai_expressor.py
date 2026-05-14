from guanghe_companion.ai_expressor import ShinsekaiAIExpressor
from guanghe_companion.controller import CompanionController


def make_snapshot() -> dict[str, object]:
    controller = CompanionController(auto_load=False)
    return controller.perform_action("touch")


def test_prompt_builder_includes_state_action_and_ai_boundaries():
    snapshot = make_snapshot()
    expressor = ShinsekaiAIExpressor()

    prompt = expressor.build_prompt(snapshot)

    assert "星汐" in prompt
    assert "motion: TouchHead" in prompt
    assert "focus: 70" in prompt
    assert "mood: 62" in prompt
    assert "AI 只能生成表达事件" in prompt
    assert "不能修改状态数值" in prompt
    assert '"character_name"' in prompt


def test_expressor_uses_valid_llm_json_events_without_changing_snapshot():
    snapshot = make_snapshot()
    original_focus = snapshot["focus"]
    payload = (
        '[{"character_name":"星汐","speech":"我听见你靠近了。",'
        '"sprite":"1","effect":"ATTENTION"}]'
    )
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: payload)

    events = expressor.express(snapshot)

    assert events == [
        {"character_name": "星汐", "speech": "我听见你靠近了。", "sprite": "1", "effect": "ATTENTION"}
    ]
    assert snapshot["focus"] == original_focus


def test_expressor_falls_back_when_llm_json_is_invalid():
    snapshot = make_snapshot()
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: "not json")

    events = expressor.express(snapshot)

    assert len(events) == 3
    assert events[0]["character_name"] == "星汐"
    assert events[0]["speech"] == snapshot["feedback"]
    assert events[0]["effect"] == "DISAPPOINTED"
    assert events[1]["character_name"] == "STAT"
    assert events[2]["character_name"] == "CHOICE"
