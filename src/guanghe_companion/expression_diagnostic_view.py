from __future__ import annotations

from collections.abc import Mapping

FAILURE_LABELS = {
    "disabled": "未启用或缺少 API Key",
    "missing_api_key": "缺少 API Key",
    "local_fallback": "已回退到本地表达",
    "timeout": "请求超时",
    "provider_error": "Provider 调用失败",
    "http_401": "Provider 认证失败",
    "http_403": "Provider 拒绝访问",
    "http_429": "Provider 额度或速率限制",
    "network_error": "Provider 网络不可达",
    "invalid_json": "返回不是合法 JSON",
    "invalid_response_text": "返回文本为空或过长",
    "invalid_response_json": "返回不是合法 JSON",
    "invalid_response_shape": "返回结构不符合模型列表格式",
    "invalid_response_encoding": "返回编码不合法",
    "invalid_response_bytes": "返回字节不合法",
    "invalid_response_size": "返回内容过大",
    "invalid_payload": "返回内容为空或格式不符合规则",
    "empty_model_list": "模型列表为空",
    "unsafe_event": "返回包含不允许的字段",
    "invalid_event": "返回事件未通过本地校验",
    "too_many_events": "返回事件过多",
    "closed": "表达器已关闭",
    "state_mutated": "Provider 修改了本地状态",
}

ACTION_HINTS = {
    "disabled": "Action: enable LLM expression and save settings",
    "missing_api_key": "Action: set API key in local settings",
    "http_401": "Action: replace API key and rerun provider matrix",
    "http_403": "Action: check provider account access",
    "http_429": "Action: check quota or switch provider",
    "network_error": "Action: check network or start local provider",
    "timeout": "Action: increase timeout or use a local provider",
    "provider_error": "Action: run provider matrix and inspect provider status",
    "invalid_response_json": "Action: change model or disable JSON mode for this provider",
    "invalid_response_shape": "Action: change model or review provider compatibility",
    "invalid_response_encoding": "Action: change model or review provider compatibility",
    "invalid_response_bytes": "Action: change model or review provider compatibility",
    "invalid_response_size": "Action: reduce prompt size or response token limit",
    "invalid_response_text": "Action: change model or reduce prompt size",
    "invalid_payload": "Action: review returned event payload",
    "empty_model_list": "Action: check base URL or provider model access",
    "unsafe_event": "Action: review unsafe event output and typed event schema",
    "invalid_event": "Action: review event validation errors",
    "state_mutated": "Action: review state guard and reject this provider output",
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
    "http_401",
    "http_403",
    "http_429",
    "network_error",
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
    reason_key = str(result.get("reason", result.get("fallback_reason", "")))
    reason = format_expression_test_failure(reason_key)
    action = expression_test_action_text(reason_key)
    suffix = f"；{action}" if action else ""
    return f"LLM 测试失败：{stage} / {reason}（{target}）{suffix}"


def format_expression_test_failure(reason: str) -> str:
    return FAILURE_LABELS.get(reason, reason or "未知错误")


def format_expression_test_stage(stage: str) -> str:
    return STAGE_LABELS.get(stage, stage or "未知阶段")


def expression_test_action_text(reason: str) -> str:
    return ACTION_HINTS.get(reason, "")


def format_expression_diagnostic_target(result: Mapping[str, object]) -> str:
    provider = str(result.get("provider", "") or "unknown")
    model = str(result.get("model", "") or "unknown")
    timeout = result.get("timeout_seconds", "")
    if timeout == "":
        return f"{provider}/{model}"
    return f"{provider}/{model}，超时 {timeout}s"


def model_fetch_reason(exc: Exception) -> str:
    message = str(exc)
    public_reason = getattr(exc, "public_reason", "")
    if public_reason in MODEL_FETCH_REASONS:
        return public_reason
    for reason in MODEL_FETCH_REASONS:
        if reason in message:
            return reason
    return "provider_error"
