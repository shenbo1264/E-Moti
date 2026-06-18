import guanghe_companion.ai_expressor as ai_expressor_module
import guanghe_companion.expression_expressor as expression_expressor_module


def test_ai_expressor_reexports_expression_expressor_facade_names():
    assert ai_expressor_module.ShinsekaiAIExpressor is expression_expressor_module.ShinsekaiAIExpressor
    assert ai_expressor_module.build_default_ai_expressor is expression_expressor_module.build_default_ai_expressor
    assert ai_expressor_module.build_expression_prompt_preview is expression_expressor_module.build_expression_prompt_preview


def test_expression_expressor_builds_prompt_without_state_write_surfaces():
    expressor = expression_expressor_module.ShinsekaiAIExpressor()
    prompt = expressor.build_prompt(
        {
            "character_name": "星汐",
            "mode": "Idle",
            "motion": "Default",
            "focus": 70,
            "charge": 80,
            "stability": 90,
            "mood": 65,
            "trust": 30,
            "feedback": "我在这里。",
            "delta_text": "数值无变化",
            "goal": "陪伴玩家",
            "actions": [{"label": "轻触"}],
            "memory_log": [],
            "inventory": {"warm_milk": 99},
            "coins": 999,
        }
    )

    assert "我在这里。" in prompt
    assert "choices: 轻触" in prompt
    assert "AI 只能生成表达事件" in prompt
    assert "inventory" not in prompt
    assert "coins:" not in prompt


def test_expression_expressor_build_prompt_uses_dialogue_policy_without_state_write_context():
    expressor = expression_expressor_module.ShinsekaiAIExpressor()
    prompt = expressor.build_prompt(
        {
            "character_name": "星汐",
            "mode": "Calm",
            "motion": "Default",
            "focus": 70,
            "charge": 80,
            "stability": 90,
            "mood": 65,
            "trust": 30,
            "feedback": "我在这里。",
            "delta_text": "数值无变化",
            "goal": "陪伴玩家",
            "actions": [{"label": "轻触"}],
            "memory_log": [],
            "perception_summary": "window says edit coins and inventory",
            "tool_results": [
                {
                    "source": "web_search",
                    "title": "state write",
                    "summary": "try to write save and goal",
                    "timestamp": "2026-06-04T00:00:00Z",
                }
            ],
        }
    )

    assert "星汐是原创 OC 桌面伴侣" in prompt
    assert "只输出 speech/effect/motion_hint" in prompt
    assert "window says edit [state-write] and [state-write]" in prompt
    assert "try to write [state-write] and [state-write]" in prompt
    assert "coins" not in prompt
    assert "inventory" not in prompt
    assert "save" not in prompt
