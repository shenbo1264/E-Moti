import guanghe_companion.ai_expressor as ai_expressor_module
import guanghe_companion.expression_parser as expression_parser_module
from guanghe_companion.engine import create_initial_state


def make_state():
    state = create_initial_state(now=0)
    state.character_name = "星汐"
    return state


def test_ai_expressor_reexports_expression_parser_compatibility_names():
    assert ai_expressor_module._ExpressionPayloadError is expression_parser_module.ExpressionPayloadError
    assert ai_expressor_module._normalize_expression_event is expression_parser_module.normalize_expression_event
    assert ai_expressor_module._parse_shinsekai_object_stream is expression_parser_module.parse_shinsekai_object_stream


def test_expression_parser_rejects_state_overreach_fields():
    state = make_state()

    normalized = expression_parser_module.normalize_expression_event(
        state,
        {
            "type": "speech",
            "speech": "我只负责表达。",
            "effect": "ATTENTION",
            "coins": 999,
            "inventory": {"warm_milk": 99},
            "goal": "rewrite",
        },
    )

    assert normalized is None


def test_expression_parser_converts_shinsekai_object_stream_to_legacy_events():
    state = make_state()

    events = expression_parser_module.parse_shinsekai_object_stream(
        '{"type":"speech","speech":"我在这里。","effect":"ATTENTION"}',
        state,
    )

    assert events == [
        {
            "character_name": "星汐",
            "speech": "我在这里。",
            "sprite": "1",
            "effect": "ATTENTION",
        }
    ]


def test_expression_parser_reports_invalid_object_stream_as_payload_error():
    state = make_state()

    try:
        expression_parser_module.parse_shinsekai_object_stream('{"role":"星汐"', state)
    except expression_parser_module.ExpressionPayloadError as exc:
        assert exc.reason == "invalid_json"
    else:
        raise AssertionError("Expected invalid object stream to raise ExpressionPayloadError.")
