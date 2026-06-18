from io import BytesIO
from urllib.error import HTTPError

import pytest

import guanghe_companion.ai_expressor as ai_expressor_module
import guanghe_companion.expression_clients as expression_clients_module
import guanghe_companion.expression_diagnostics as diagnostics_module


def test_ai_expressor_reexports_expression_client_provider_names():
    assert ai_expressor_module.LLMProviderError is expression_clients_module.LLMProviderError
    assert ai_expressor_module.OpenAIResponsesClient is expression_clients_module.OpenAIResponsesClient
    assert ai_expressor_module.OpenAICompatibleChatClient is expression_clients_module.OpenAICompatibleChatClient
    assert ai_expressor_module.fetch_provider_model_ids is expression_clients_module.fetch_provider_model_ids


def test_expression_diagnostics_reexports_default_model_fetcher_from_clients():
    assert diagnostics_module.fetch_provider_model_ids is expression_clients_module.fetch_provider_model_ids


def test_expression_clients_openai_compatible_chat_contract():
    captured = {}

    def transport(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = request.data.decode("utf-8")
        captured["timeout"] = timeout
        return b'{"choices":[{"message":{"content":"[{\\"type\\":\\"speech\\",\\"speech\\":\\"ok\\"}]"}}]}'

    client = expression_clients_module.OpenAICompatibleChatClient(
        api_key=" test-key ",
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        timeout_seconds=0.5,
        transport=transport,
    )

    assert client("prompt text") == '[{"type":"speech","speech":"ok"}]'
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert '"model": "deepseek-chat"' in captured["payload"]
    assert '"content": "prompt text"' in captured["payload"]
    assert captured["timeout"] == 0.5


def test_expression_clients_model_fetch_allows_local_provider_without_auth_header():
    captured = {}

    def transport(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return b'{"data":[{"id":"llama3.2"},{"id":"qwen2.5:7b"}]}'

    models = expression_clients_module.fetch_provider_model_ids(
        provider="ollama",
        base_url="http://127.0.0.1:11434/v1",
        api_key="",
        timeout_seconds=1.5,
        transport=transport,
    )

    assert models == ("llama3.2", "qwen2.5:7b")
    assert captured["url"] == "http://127.0.0.1:11434/v1/models"
    assert "Authorization" not in captured["headers"]
    assert captured["timeout"] == 1.5


def test_expression_clients_openai_compatible_chat_classifies_http_401_without_secret():
    def transport(request, timeout):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=BytesIO(b'{"error":{"message":"Authentication Fails, Your api key: sk-secret is invalid"}}'),
        )

    client = expression_clients_module.OpenAICompatibleChatClient(
        api_key="sk-secret",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        timeout_seconds=0.5,
        transport=transport,
    )

    with pytest.raises(expression_clients_module.LLMProviderError) as captured:
        client("prompt text")

    assert captured.value.public_reason == "http_401"
    assert "sk-secret" not in str(captured.value)
    assert "Authentication Fails" not in str(captured.value)
