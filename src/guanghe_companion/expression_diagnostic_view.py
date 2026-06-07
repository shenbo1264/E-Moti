from __future__ import annotations

from collections.abc import Mapping

FAILURE_LABELS = {
    "disabled": "未启用或缺少 API Key",
    "missing_api_key": "缺少 API Key",
    "local_fallback": "已回退到本地表达",
    "timeout": "请求超时",
    "provider_error": "Provider 调用失败",
    "invalid_json": "返回不是合法 JSON",
    "invalid_response_text": "返回文本为空或过长",
    "invalid_response_json": "返回不是合法 JSON",
    "invalid_response_shape": "返回结构不符合模型列表格式",
    "invalid_payload": "返回内容为空或格式不符合规则",
    "empty_model_list": "模型列表为空",
    "unsafe_event": "返回包含不允许的字段",
    "invalid_event": "返回事件未通过本地校验",
    "too_many_events": "返回事件过多",
    "closed": "表达器已关闭",
    "state_mutated": "Provider 修改了本地状态",
}

STAGE_LABELS = {
    "settings": "设置检查",
    "model_list": "模型列表",
    "prompt": "构造提示",
    "provider_call": "调用服务",
    "provider_parse": "解析响应",
    "event_validation": "事件校验",
    "state_guard": "状态守卫",
}

MODEL_FETCH_REASONS = (
    "missing_api_key",
    "timeout",
    "invalid_response_json",
    "invalid_response_shape",
    "empty_model_list",
    "invalid_response_encoding",
    "invalid_response_bytes",
    "invalid_response_size",
)


def expression_test_status_text(result: Mapping[str, object]) -> str:
    target = format_expression_diagnostic_target(result)
    if result.get("ok"):
        speech = str(result.get("speech", ""))
        return f"LLM 测试通过：{speech}（{target}）"
    stage = format_expression_test_stage(str(result.get("stage", "")))
    reason = format_expression_test_failure(str(result.get("reason", result.get("fallback_reason", ""))))
    return f"LLM 测试失败：{stage} / {reason}（{target}）"


def format_expression_test_failure(reason: str) -> str:
    return FAILURE_LABELS.get(reason, reason or "未知错误")


def format_expression_test_stage(stage: str) -> str:
    return STAGE_LABELS.get(stage, stage or "未知阶段")


def format_expression_diagnostic_target(result: Mapping[str, object]) -> str:
    provider = str(result.get("provider", "") or "unknown")
    model = str(result.get("model", "") or "unknown")
    timeout = result.get("timeout_seconds", "")
    if timeout == "":
        return f"{provider}/{model}"
    return f"{provider}/{model}，超时 {timeout}s"


def model_fetch_reason(exc: Exception) -> str:
    message = str(exc)
    for reason in MODEL_FETCH_REASONS:
        if reason in message:
            return reason
    return "provider_error"
