from guanghe_companion.expression_diagnostic_view import (
    expression_test_action_text,
    expression_test_status_text,
    format_expression_diagnostic_target,
    format_expression_test_failure,
    format_expression_test_stage,
    model_fetch_reason,
)


def test_expression_test_status_text_formats_success_target():
    result = {
        "ok": True,
        "speech": "LLM connected",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "timeout_seconds": 0.5,
    }

    status = expression_test_status_text(result)

    assert "LLM" in status
    assert "deepseek/deepseek-v4-flash" in status
    assert "LLM connected" in status


def test_expression_test_status_text_formats_stage_reason_action_and_state_guard():
    result = {
        "ok": False,
        "stage": "state_guard",
        "reason": "state_mutated",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "timeout_seconds": 30.0,
    }

    status = expression_test_status_text(result)

    assert "LLM" in status
    assert "deepseek-v4-flash" in status
    assert "Action: review state guard" in status


def test_expression_diagnostic_target_omits_timeout_when_missing():
    assert format_expression_diagnostic_target({"provider": "openai", "model": "gpt-5.5"}) == "openai/gpt-5.5"


def test_expression_test_failure_and_stage_keep_unknown_fallbacks():
    assert format_expression_test_failure("timeout")
    assert format_expression_test_failure("unknown_reason") == "unknown_reason"
    assert format_expression_test_stage("provider_call")
    assert format_expression_test_stage("unknown_stage") == "unknown_stage"


def test_expression_diagnostic_actions_cover_common_provider_failures():
    expected = {
        "missing_api_key": "set API key",
        "http_401": "replace API key",
        "http_429": "check quota",
        "timeout": "increase timeout",
        "invalid_response_json": "change model",
        "unsafe_event": "review unsafe event",
        "state_mutated": "review state guard",
    }

    for reason, phrase in expected.items():
        assert phrase in expression_test_action_text(reason)


def test_model_fetch_reason_extracts_known_provider_reason():
    assert model_fetch_reason(RuntimeError("model list fetch failed: empty_model_list")) == "empty_model_list"
    assert model_fetch_reason(RuntimeError("model list fetch failed: http_401")) == "http_401"
    assert model_fetch_reason(RuntimeError("unexpected transport failure")) == "provider_error"
