from guanghe_companion.expression_expressor import ShinsekaiAIExpressor, build_expression_prompt_preview
from guanghe_companion.expression_parser import MAX_SPEECH_LENGTH
from guanghe_companion.expression_request import ExpressionRequest


def test_provider_and_preview_explain_the_actual_speech_limit():
    request = ExpressionRequest.from_snapshot({"character_name": "星汐", "focus": 50,
        "charge": 50, "stability": 50, "mood": 50, "trust": 50})
    instruction = f"speech 去掉表情标签后最多 {MAX_SPEECH_LENGTH} 个字符"
    assert instruction in ShinsekaiAIExpressor().build_prompt(request)
    assert instruction in build_expression_prompt_preview()
