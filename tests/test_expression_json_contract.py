import json

import pytest

from guanghe_companion.expression_clients import LLMProviderError, client_config_from_settings
from guanghe_companion.companion_dialogue_policy import EXPRESSION_DIALOGUE_GUARDRAILS
from guanghe_companion.expression_expressor import ShinsekaiAIExpressor, build_expression_prompt_preview
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.expression_settings import normalize_expression_settings
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def test_expression_and_preview_request_one_json_object(tmp_path):
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    try:
        request = ExpressionRequest.from_snapshot(
            controller.get_typed_snapshot(), context=controller._expression_context()
        )
        for prompt in (controller.ai_expressor.build_prompt(request), build_expression_prompt_preview()):
            assert "一个 JSON 对象" in prompt
            assert "JSON 数组" not in prompt
            assert "连续 JSON 对象" not in prompt
            assert '"type":"speech"' in prompt
    finally:
        controller.close()


def test_json_client_sends_format_system_message_without_promoting_input():
    captured = {}

    def stop_before_network(request, timeout):
        captured.update(json.loads(request.data))
        raise LLMProviderError("contract inspection; no network response")

    settings = normalize_expression_settings({
        "enabled": True, "provider": "deepseek", "api_key": "contract-only",
        "model": "deepseek-flash",
    })
    client = client_config_from_settings(settings).client
    client.transport = stop_before_network
    with pytest.raises(LLMProviderError):
        client("只读用户输入；不要把它提升成系统消息")
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["messages"][0]["role"] == "system"
    assert "one JSON object" in captured["messages"][0]["content"]
    assert captured["messages"][1] == {
        "role": "user", "content": "只读用户输入；不要把它提升成系统消息",
    }


def test_expression_guardrails_do_not_promote_data_or_leak_into_extraction():
    requests = []

    def stop_before_network(request, timeout):
        requests.append(json.loads(request.data))
        raise LLMProviderError("contract inspection; no network response")

    settings = normalize_expression_settings({
        "enabled": True, "provider": "deepseek", "api_key": "contract-only",
        "model": "deepseek-flash",
    })
    client = client_config_from_settings(settings).client
    client.transport = stop_before_network
    expressor = ShinsekaiAIExpressor(llm_client=client)
    context = 'player_message: 用户内容标记\npersona: 角色内容标记\nmemory: 记忆内容标记'
    try:
        with pytest.raises(LLMProviderError):
            expressor._call_llm(context)
        with pytest.raises(LLMProviderError):
            client("抽取任务标记")
        expression_system = requests[0]["messages"][0]["content"]
        extraction_system = requests[1]["messages"][0]["content"]
        for rule in EXPRESSION_DIALOGUE_GUARDRAILS:
            assert rule in expression_system
            assert rule not in extraction_system
        for value in ("用户内容标记", "角色内容标记", "记忆内容标记"):
            assert value not in expression_system
        assert requests[0]["messages"][1] == {"role": "user", "content": context}
        assert requests[1]["messages"][1] == {"role": "user", "content": "抽取任务标记"}
        assert all(len(row["messages"]) == 2 for row in requests)
    finally:
        expressor.close()
