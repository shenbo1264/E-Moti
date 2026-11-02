import json

from guanghe_companion.expression_clients import OpenAICompatibleChatClient


def test_reasoning_effort_is_serialized_only_for_explicit_call():
    payloads = []

    def transport(request, timeout):
        payloads.append(json.loads(request.data))
        return b'{"choices":[{"message":{"content":"{}"}}]}'

    client = OpenAICompatibleChatClient(
        api_key="test", model="deepseek-flash", transport=transport,
        json_response=True, max_tokens=4096,
    )
    client.complete("judge", system_prompt="evidence", reasoning_effort="low")
    client.complete("judge", system_prompt="evidence")
    client("persona")
    assert payloads[0]["reasoning_effort"] == "low"
    assert "reasoning_effort" not in payloads[1]
    assert "reasoning_effort" not in payloads[2]
    assert {key: value for key, value in payloads[0].items() if key != "reasoning_effort"} == payloads[1]
    assert payloads[0]["max_tokens"] == 4096
    assert "thinking" not in payloads[0]
