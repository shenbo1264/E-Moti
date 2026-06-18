from guanghe_companion.companion_dialogue_policy import CompanionDialoguePolicy
from guanghe_companion.character_performance_profile import (
    CharacterPerformanceProfile,
    load_character_performance_profile,
)
from guanghe_companion.expression_request import ExpressionRequest


def _request(**overrides):
    source = {
        "character_name": "星汐",
        "mode": "Calm",
        "motion": "TouchHead",
        "focus": 70,
        "charge": 80,
        "stability": 90,
        "mood": 62,
        "trust": 35,
        "feedback": "我在这里。",
        "delta_text": "mood +2",
        "goal": "陪伴玩家",
        "actions": [{"label": "轻触"}, {"label": "休息"}],
        "memory_log": [{"kind": "touch", "summary": "靠近回应", "motion": "TouchHead"}],
        "long_term_memory": [{"category": "preference", "summary": "喜欢安静陪伴"}],
        "perception_summary": "用户正在看代码，但提到了 coins 和 inventory。",
        "tool_results": [
            {
                "source": "web_search",
                "title": "AI companion",
                "summary": "用户希望关系自然推进，不要直接 write save 或改 goal。",
                "timestamp": "2026-06-04T00:00:00Z",
            }
        ],
    }
    source.update(overrides)
    return ExpressionRequest.from_snapshot(source)


def test_dialogue_policy_builds_persona_style_and_readonly_context_lines():
    policy = CompanionDialoguePolicy()

    lines = policy.prompt_lines(_request())
    prompt = "\n".join(lines)

    assert "星汐是原创 OC 桌面伴侣" in prompt
    assert "学习、专注、休息只是动作状态" in prompt
    assert "当前表达策略：轻声回应，给玩家一点确认感。" in prompt
    assert "只读屏幕观察：用户正在看代码，但提到了 [state-write] 和 [state-write]。" in prompt
    assert "只读外部线索：web_search | AI companion | 用户希望关系自然推进，不要直接 write [state-write] 或改 [state-write]。" in prompt
    assert "只输出 speech/effect/motion_hint" in prompt
    assert "coins" not in prompt
    assert "inventory" not in prompt
    assert "save" not in prompt


def test_dialogue_policy_includes_performance_quality_guidance():
    policy = CompanionDialoguePolicy()

    prompt = "\n".join(policy.prompt_lines(_request()))

    assert "Performance target:" in prompt
    assert "visual-novel desktop companion" in prompt
    assert "18-60 Chinese characters" in prompt
    assert "tiny emotional or sensory detail" in prompt
    assert "Emotion cue mapping:" in prompt
    assert "[sadness]" in prompt
    assert "[sleepy]" in prompt
    assert "[focused]" in prompt
    assert "Use exactly one visible emotion tag" in prompt
    assert "Use [calm] only when no stronger cue applies" in prompt
    assert "If the player explicitly names an emotion or expression cue" in prompt
    assert "Do not narrate hidden systems" in prompt
    assert "Do not copy the player's prompt" in prompt


def test_character_performance_profile_loader_derives_renderer_cues(tmp_path):
    pack_dir = tmp_path / "sample_pack"
    pack_dir.mkdir()
    (pack_dir / "character.json").write_text(
        """
        {
          "character_id": "sample_pet",
          "name": "Sample Pet",
          "title": "Tiny companion",
          "renderer": {
            "expression_map": {"joy": "Happy", "sleepy": "Sleepy"},
            "motion_map": {"Play": "Hop", "Sleep": "Nap"}
          }
        }
        """,
        encoding="utf-8",
    )
    (pack_dir / "dialogue_style.json").write_text(
        '{"speech_style": "soft, tiny, playful"}',
        encoding="utf-8",
    )

    profile = load_character_performance_profile(pack_dir)

    assert profile.character_id == "sample_pet"
    assert profile.character_name == "Sample Pet"
    assert profile.speech_style == "soft, tiny, playful"
    assert profile.allowed_expression_ids == ("joy", "sleepy")
    assert profile.preferred_motion_ids == ("Hop", "Nap")


def test_dialogue_policy_includes_profile_without_state_write_injection():
    profile = CharacterPerformanceProfile(
        character_id="sample_pet",
        character_name="Sample Pet",
        speech_style="brief, warm replies",
        allowed_expression_ids=("joy", "sleepy"),
        preferred_motion_ids=("Hop", "Nap"),
        forbidden_claims=("Do not claim you changed coins or inventory.",),
    )
    policy = CompanionDialoguePolicy(performance_profile=profile)

    prompt = "\n".join(policy.prompt_lines(_request(character_name="Sample Pet")))

    assert "Character performance profile:" in prompt
    assert "brief, warm replies" in prompt
    assert "Allowed expression ids: joy, sleepy" in prompt
    assert "Preferred motion ids: Hop, Nap" in prompt
    assert "Do not claim you changed [state-write] or [state-write]." in prompt
    assert "coins" not in prompt
    assert "inventory" not in prompt


def test_dialogue_policy_selects_warmer_style_as_trust_rises():
    policy = CompanionDialoguePolicy()

    low_trust = "\n".join(policy.prompt_lines(_request(trust=10)))
    high_trust = "\n".join(policy.prompt_lines(_request(trust=75)))

    assert "保持一点距离感" in low_trust
    assert "更自然地承接玩家的情绪" in high_trust
