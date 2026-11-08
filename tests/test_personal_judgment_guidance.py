from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.expression_refinement import review_rules
from guanghe_companion.expression_request import ExpressionRequest
from tools.eval_ondemand_generation import production_policy
from tools.eval_ondemand_presentation import common_persona


def test_final_draft_and_review_keep_person_judgment_boundary_and_character_views():
    persona = common_persona('xingxi_pixel_pet')
    request = ExpressionRequest.from_snapshot({'character_name': persona['character_name'],
        'player_message': '我喜欢浅绿色的杯子，你呢？', 'focus': 50, 'charge': 50,
        'stability': 50, 'mood': 50, 'trust': 50}, context={'persona': persona})
    with ShinsekaiAIExpressor(enabled=False, dialogue_policy=production_policy()) as expressor:
        draft_prompt = expressor.build_prompt(request)
    for delivered in (draft_prompt, review_rules()):
        assert '不从普通偏好或一次选择推断用户的性格、品味、能力或成熟程度' in delivered
        assert '保留角色对事物本身的喜恶、联想和轻巧玩笑' in delivered
        assert '用户明确请求评价或夸奖' in delivered
    assert request.persona == persona
    assert request.player_message in draft_prompt


def test_temporal_presupposition_boundary_preserves_explicit_repetition_and_personification():
    persona = common_persona('xingxi_pixel_pet')
    request = ExpressionRequest.from_snapshot({'character_name': persona['character_name'],
        'player_message': '我又给阳台的薄荷浇水了。', 'focus': 50, 'charge': 50,
        'stability': 50, 'mood': 50, 'trust': 50}, context={'persona': persona})
    with ShinsekaiAIExpressor(enabled=False, dialogue_policy=production_policy()) as expressor:
        prompt = expressor.build_prompt(request)
    for delivered in (prompt, review_rules()):
        assert '重复、持续、变化、等待和习惯也属于事实预设' in delivered
        assert '保留拟人和玩笑本身' in delivered
        assert '原话明确提供的重复或延续信息应保留' in delivered
    assert request.player_message in prompt
    assert request.persona == persona
