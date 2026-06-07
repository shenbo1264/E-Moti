from guanghe_companion.expression_diagnostic_view import (
    expression_test_status_text,
    format_expression_diagnostic_target,
    format_expression_test_failure,
    format_expression_test_stage,
    model_fetch_reason,
)


def test_expression_test_status_text_formats_success_target():
    result = {
        "ok": True,
        "speech": "我在这里。",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "timeout_seconds": 0.5,
    }

    assert expression_test_status_text(result) == "LLM 测试通过：我在这里。（deepseek/deepseek-v4-flash，超时 0.5s）"


def test_expression_test_status_text_formats_stage_reason_and_state_guard():
    result = {
        "ok": False,
        "stage": "state_guard",
        "reason": "state_mutated",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "timeout_seconds": 30.0,
    }

    assert expression_test_status_text(result) == (
        "LLM 测试失败：状态守卫 / Provider 修改了本地状态（deepseek/deepseek-v4-flash，超时 30.0s）"
    )


def test_expression_diagnostic_target_omits_timeout_when_missing():
    assert format_expression_diagnostic_target({"provider": "openai", "model": "gpt-5.5"}) == "openai/gpt-5.5"


def test_expression_test_failure_and_stage_keep_unknown_fallbacks():
    assert format_expression_test_failure("timeout") == "请求超时"
    assert format_expression_test_failure("unknown_reason") == "unknown_reason"
    assert format_expression_test_stage("provider_call") == "调用服务"
    assert format_expression_test_stage("unknown_stage") == "unknown_stage"


def test_model_fetch_reason_extracts_known_provider_reason():
    assert model_fetch_reason(RuntimeError("model list fetch failed: empty_model_list")) == "empty_model_list"
    assert model_fetch_reason(RuntimeError("unexpected transport failure")) == "provider_error"
