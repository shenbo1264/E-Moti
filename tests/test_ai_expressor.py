from dataclasses import FrozenInstanceError
import time

from guanghe_companion.ai_expressor import (
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_OPENAI_MODEL,
    ExpressionRequest,
    LLMProviderError,
    OpenAIResponsesClient,
    ShinsekaiAIExpressor,
    build_default_ai_expressor,
)
from guanghe_companion.controller import CompanionController


def make_snapshot() -> dict[str, object]:
    controller = CompanionController(auto_load=False)
    return controller.perform_action("touch")


def test_prompt_builder_includes_state_action_and_ai_boundaries():
    snapshot = make_snapshot()
    expressor = ShinsekaiAIExpressor()

    prompt = expressor.build_prompt(snapshot)

    assert "星汐" in prompt
    assert "motion: TouchHead" in prompt
    assert "focus: 70" in prompt
    assert "mood: 62" in prompt
    assert "AI 只能生成表达事件" in prompt
    assert "不能修改状态数值" in prompt
    assert '"type":"speech"' in prompt
    assert '"speech"' in prompt
    assert '"effect"' in prompt
    assert '"motion_hint"' in prompt
    assert '"character_name"' not in prompt
    assert '"sprite"' not in prompt


def test_expression_request_from_snapshot_keeps_only_readonly_summary_fields():
    snapshot = make_snapshot()
    original_action_label = snapshot["actions"][0]["label"]
    original_memory_kind = snapshot["memory_log"][0]["kind"]
    snapshot["inventory"]["warm_milk"] = 99
    snapshot["shop_items"][0]["price"] = 0
    snapshot["unlocks"].append("injected_unlock")
    snapshot["perception_summary"] = "current window: draft note"
    snapshot["tool_results"] = [
        {
            "source": "local_profile",
            "title": "expression style",
            "summary": "keep the reply gentle",
            "coins": "999",
            "inventory": "warm_milk",
        }
    ]

    request = ExpressionRequest.from_snapshot(snapshot)
    prompt_payload = request.to_prompt_dict()

    assert set(prompt_payload) == {
        "character_name",
        "mode",
        "motion",
        "focus",
        "charge",
        "stability",
        "mood",
        "trust",
        "feedback",
        "delta_text",
        "goal",
        "actions",
        "recent_memory",
        "perception_summary",
        "tool_results",
    }
    assert "inventory" not in prompt_payload
    assert "shop_items" not in prompt_payload
    assert "unlocks" not in prompt_payload
    assert "coins" not in prompt_payload
    assert prompt_payload["actions"][0] == {"label": original_action_label}
    assert prompt_payload["recent_memory"][0]["kind"] == original_memory_kind
    assert prompt_payload["perception_summary"] == "current window: draft note"
    assert prompt_payload["tool_results"] == [
        {
            "source": "local_profile",
            "title": "expression style",
            "summary": "keep the reply gentle",
        }
    ]


def test_expression_request_sanitizes_perception_and_tool_result_anchors():
    snapshot = make_snapshot()
    snapshot["perception_summary"] = "x" * 320
    snapshot["tool_results"] = [
        {"source": "local_doc", "title": "one", "summary": "first"},
        {"source": "search", "title": "two", "summary": "second", "goal": "rewrite"},
        {"source": "tool", "title": "three", "summary": "third"},
        {"source": "overflow", "title": "four", "summary": "ignored"},
        {"source": "bad", "title": {"nested": "bad"}, "summary": "ignored"},
    ]

    request = ExpressionRequest.from_snapshot(snapshot)
    prompt_payload = request.to_prompt_dict()

    assert prompt_payload["perception_summary"] == "x" * 240
    assert prompt_payload["tool_results"] == [
        {"source": "local_doc", "title": "one", "summary": "first"},
        {"source": "search", "title": "two", "summary": "second"},
        {"source": "tool", "title": "three", "summary": "third"},
    ]


def test_expression_request_is_immutable_and_copies_mutable_snapshot_values():
    snapshot = make_snapshot()
    original_action_label = snapshot["actions"][0]["label"]
    original_memory_summary = snapshot["memory_log"][0]["summary"]
    request = ExpressionRequest.from_snapshot(snapshot)
    snapshot["actions"][0]["label"] = "mutated"
    snapshot["memory_log"][0]["summary"] = "mutated"

    assert request.actions[0]["label"] == original_action_label
    assert request.recent_memory[0]["summary"] == original_memory_summary
    try:
        request.feedback = "mutated"
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("ExpressionRequest should be immutable.")


def test_prompt_builder_filters_state_write_surfaces_from_raw_snapshot():
    snapshot = make_snapshot()

    prompt = ShinsekaiAIExpressor().build_prompt(snapshot)

    assert "inventory" not in prompt
    assert "shop_items" not in prompt
    assert "unlocks" not in prompt
    assert "coins:" not in prompt
    assert "recent_memory:" in prompt


def test_expressor_uses_valid_llm_json_events_without_changing_snapshot():
    snapshot = make_snapshot()
    original_focus = snapshot["focus"]
    payload = (
        '[{"character_name":"星汐","speech":"我听见你靠近了。",'
        '"sprite":"1","effect":"ATTENTION"}]'
    )
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: payload)

    events = expressor.express(snapshot)

    assert events == [
        {"character_name": "星汐", "speech": "我听见你靠近了。", "sprite": "1", "effect": "ATTENTION"}
    ]
    assert snapshot["focus"] == original_focus


def test_expressor_accepts_limited_speech_event_schema_without_applying_motion_hint():
    snapshot = make_snapshot()
    payload = (
        '[{"type":"speech","speech":"我会轻一点回应。",'
        '"effect":"ATTENTION","motion_hint":"Raised"}]'
    )
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: payload)

    events = expressor.express(snapshot)

    assert events == [
        {
            "character_name": snapshot["character_name"],
            "speech": "我会轻一点回应。",
            "sprite": "1",
            "effect": "ATTENTION",
        }
    ]
    assert snapshot["motion"] == "TouchHead"


def test_expressor_trims_speech_schema_text_before_returning_expression():
    snapshot = make_snapshot()
    payload = '[{"type":"speech","speech":"\\n  Back online.  \\t","effect":"ATTENTION"}]'
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: payload)

    events = expressor.express(snapshot)

    assert events == [
        {
            "character_name": snapshot["character_name"],
            "speech": "Back online.",
            "sprite": "1",
            "effect": "ATTENTION",
        }
    ]
    assert expressor.last_fallback_reason is None


def test_expressor_trims_speech_schema_effect_before_validating_expression():
    snapshot = make_snapshot()
    payload = '[{"type":"speech","speech":"Back online.","effect":"  ATTENTION  "}]'
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: payload)

    events = expressor.express(snapshot)

    assert events == [
        {
            "character_name": snapshot["character_name"],
            "speech": "Back online.",
            "sprite": "1",
            "effect": "ATTENTION",
        }
    ]
    assert expressor.last_fallback_reason is None


def test_expressor_trims_legacy_speech_text_before_returning_expression():
    snapshot = make_snapshot()
    payload = (
        '[{"character_name":"%s","speech":"  Back online.  ","sprite":"1","effect":"ATTENTION"}]'
        % snapshot["character_name"]
    )
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: payload)

    events = expressor.express(snapshot)

    assert events == [
        {
            "character_name": snapshot["character_name"],
            "speech": "Back online.",
            "sprite": "1",
            "effect": "ATTENTION",
        }
    ]
    assert expressor.last_fallback_reason is None


def test_expressor_trims_legacy_fields_before_validating_expression():
    snapshot = make_snapshot()
    payload = (
        '[{"character_name":"  %s  ","speech":"  Back online.  ","sprite":" 1 ","effect":" ATTENTION "}]'
        % snapshot["character_name"]
    )
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: payload)

    events = expressor.express(snapshot)

    assert events == [
        {
            "character_name": snapshot["character_name"],
            "speech": "Back online.",
            "sprite": "1",
            "effect": "ATTENTION",
        }
    ]
    assert expressor.last_fallback_reason is None


def test_expressor_rejects_blank_speech_schema_text():
    snapshot = make_snapshot()
    payload = '[{"type":"speech","speech":"   ","effect":"ATTENTION","motion_hint":"Raised"}]'
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: payload)

    events = expressor.express(snapshot)

    assert len(events) == 3
    assert events[0]["character_name"] == snapshot["character_name"]
    assert events[0]["speech"] == snapshot["feedback"]
    assert events[0]["effect"] == "DISAPPOINTED"
    assert events[1]["character_name"] == "STAT"
    assert events[2]["character_name"] == "CHOICE"
    assert expressor.last_fallback_reason == "unsafe_event"


def test_expressor_rejects_blank_legacy_speech_text():
    snapshot = make_snapshot()
    payload = (
        '[{"character_name":"%s","speech":"   ","sprite":"1","effect":"ATTENTION"}]'
        % snapshot["character_name"]
    )
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: payload)

    events = expressor.express(snapshot)

    assert len(events) == 3
    assert events[0]["character_name"] == snapshot["character_name"]
    assert events[0]["speech"] == snapshot["feedback"]
    assert events[0]["effect"] == "DISAPPOINTED"
    assert events[1]["character_name"] == "STAT"
    assert events[2]["character_name"] == "CHOICE"
    assert expressor.last_fallback_reason == "unsafe_event"


def test_expressor_falls_back_when_llm_json_is_invalid():
    snapshot = make_snapshot()
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: "not json")

    events = expressor.express(snapshot)

    assert len(events) == 3
    assert events[0]["character_name"] == "星汐"
    assert events[0]["speech"] == snapshot["feedback"]
    assert events[0]["effect"] == "DISAPPOINTED"
    assert events[1]["character_name"] == "STAT"
    assert events[2]["character_name"] == "CHOICE"
    assert expressor.last_fallback_reason == "invalid_json"


def test_expressor_marks_empty_llm_event_list_as_invalid_payload():
    snapshot = make_snapshot()
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: "[]")

    events = expressor.express(snapshot)

    assert len(events) == 3
    assert events[0]["character_name"] == snapshot["character_name"]
    assert events[0]["speech"] == snapshot["feedback"]
    assert events[0]["effect"] == "DISAPPOINTED"
    assert events[1]["character_name"] == "STAT"
    assert events[2]["character_name"] == "CHOICE"
    assert expressor.last_fallback_reason == "invalid_payload"


def test_expressor_clears_fallback_reason_after_next_valid_llm_expression():
    snapshot = make_snapshot()
    responses = iter(
        [
            "not json",
            '[{"type":"speech","speech":"Back online.","effect":"ATTENTION","motion_hint":"TouchHead"}]',
        ]
    )
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: next(responses))

    fallback_events = expressor.express(snapshot)
    valid_events = expressor.express(snapshot)

    assert fallback_events[0]["speech"] == snapshot["feedback"]
    assert expressor.last_fallback_reason is None
    assert valid_events == [
        {
            "character_name": snapshot["character_name"],
            "speech": "Back online.",
            "sprite": "1",
            "effect": "ATTENTION",
        }
    ]


def test_expressor_replaces_previous_reason_when_client_raises_unwrapped_error():
    snapshot = make_snapshot()
    calls = 0

    def flaky_client(prompt: str) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            return "not json"
        raise RuntimeError("network down")

    expressor = ShinsekaiAIExpressor(llm_client=flaky_client)

    first_events = expressor.express(snapshot)
    second_events = expressor.express(snapshot)

    assert first_events[0]["speech"] == snapshot["feedback"]
    assert len(second_events) == 3
    assert second_events[0]["speech"] == snapshot["feedback"]
    assert second_events[0]["effect"] == "DISAPPOINTED"
    assert expressor.last_fallback_reason == "provider_error"


def test_expressor_falls_back_when_mock_client_raises_custom_exception():
    class MockProviderError(Exception):
        pass

    snapshot = make_snapshot()

    def broken_client(prompt: str) -> str:
        raise MockProviderError("mock provider unavailable")

    expressor = ShinsekaiAIExpressor(llm_client=broken_client)

    events = expressor.express(snapshot)

    assert len(events) == 3
    assert events[0]["speech"] == snapshot["feedback"]
    assert events[0]["effect"] == "DISAPPOINTED"
    assert events[1]["character_name"] == "STAT"
    assert events[2]["character_name"] == "CHOICE"
    assert expressor.last_fallback_reason == "provider_error"


def test_expressor_falls_back_quickly_when_llm_times_out():
    snapshot = make_snapshot()

    def slow_client(prompt: str) -> str:
        time.sleep(0.2)
        return '[{"character_name":"ignored","speech":"late","sprite":"1","effect":"ATTENTION"}]'

    expressor = ShinsekaiAIExpressor(llm_client=slow_client, timeout_seconds=0.01)

    started_at = time.monotonic()
    events = expressor.express(snapshot)

    assert time.monotonic() - started_at < 0.15
    assert len(events) == 3
    assert events[0]["speech"] == snapshot["feedback"]
    assert events[0]["effect"] == "DISAPPOINTED"
    assert expressor.last_fallback_reason == "timeout"


def test_expressor_rejects_non_finite_direct_timeout():
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: "[]", timeout_seconds=float("inf"))

    assert expressor.timeout_seconds == DEFAULT_TIMEOUT_SECONDS


def test_expressor_rejects_non_numeric_direct_timeout():
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: "[]", timeout_seconds="bad")

    assert expressor.timeout_seconds == DEFAULT_TIMEOUT_SECONDS


def test_expressor_rejects_llm_owned_stat_or_choice_rows():
    snapshot = make_snapshot()
    payload = '[{"character_name":"STAT","speech":"coins 999","sprite":"-1","effect":""}]'
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: payload)

    events = expressor.express(snapshot)

    assert len(events) == 3
    assert events[0]["character_name"] == snapshot["character_name"]
    assert events[0]["speech"] == snapshot["feedback"]
    assert events[1]["character_name"] == "STAT"
    assert events[1]["speech"] != "coins 999"


def test_expressor_rejects_overreach_fields_and_preserves_snapshot_values():
    snapshot = make_snapshot()
    original_coins = snapshot["coins"]
    payload = (
        '[{"character_name":"%s","speech":"try write","sprite":"1","effect":"ATTENTION",'
        '"coins":999,"inventory":{"warm_milk":99}}]'
    ) % snapshot["character_name"]
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: payload)

    events = expressor.express(snapshot)

    assert len(events) == 3
    assert events[0]["speech"] == snapshot["feedback"]
    assert snapshot["coins"] == original_coins
    assert expressor.last_fallback_reason == "unsafe_event"


def test_expressor_rejects_non_string_expression_fields():
    snapshot = make_snapshot()
    payload = (
        '[{"character_name":"%s","speech":{"text":"nested"},"sprite":"1","effect":"ATTENTION"}]'
    ) % snapshot["character_name"]
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: payload)

    events = expressor.express(snapshot)

    assert len(events) == 3
    assert events[0]["character_name"] == snapshot["character_name"]
    assert events[0]["speech"] == snapshot["feedback"]
    assert events[0]["effect"] == "DISAPPOINTED"


def test_expressor_rejects_more_than_four_llm_rows():
    snapshot = make_snapshot()
    row = '{"character_name":"%s","speech":"ok","sprite":"1","effect":"ATTENTION"}' % snapshot["character_name"]
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: f"[{','.join([row] * 5)}]")

    events = expressor.express(snapshot)

    assert len(events) == 3
    assert events[0]["speech"] == snapshot["feedback"]
    assert expressor.last_fallback_reason == "too_many_events"


def test_expressor_prioritizes_event_limit_before_unsafe_row_details():
    snapshot = make_snapshot()
    safe_row = '{"type":"speech","speech":"ok","effect":"ATTENTION"}'
    unsafe_row = '{"type":"speech","speech":"try write","effect":"ATTENTION","coins":999}'
    expressor = ShinsekaiAIExpressor(
        llm_client=lambda prompt: f"[{','.join([safe_row] * 4 + [unsafe_row])}]"
    )

    events = expressor.express(snapshot)

    assert len(events) == 3
    assert events[0]["speech"] == snapshot["feedback"]
    assert events[0]["effect"] == "DISAPPOINTED"
    assert events[1]["character_name"] == "STAT"
    assert events[2]["character_name"] == "CHOICE"
    assert expressor.last_fallback_reason == "too_many_events"


def test_default_expressor_stays_disabled_without_explicit_env(monkeypatch):
    monkeypatch.delenv("GUANGHE_LLM_ENABLED", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    expressor = build_default_ai_expressor()

    assert expressor.enabled is False
    assert expressor.llm_client is None


def test_default_expressor_requires_api_key_even_when_enabled(monkeypatch):
    monkeypatch.setenv("GUANGHE_LLM_ENABLED", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    expressor = build_default_ai_expressor()

    assert expressor.enabled is False
    assert expressor.llm_client is None


def test_default_expressor_trims_enabled_env_before_checking_flag(monkeypatch):
    monkeypatch.setenv("GUANGHE_LLM_ENABLED", " 1 ")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    expressor = build_default_ai_expressor()

    assert expressor.enabled is True
    assert isinstance(expressor.llm_client, OpenAIResponsesClient)


def test_default_expressor_treats_non_string_enabled_env_as_disabled():
    expressor = build_default_ai_expressor(
        {
            "GUANGHE_LLM_ENABLED": object(),
            "OPENAI_API_KEY": "test-key",
        }
    )

    assert expressor.enabled is False
    assert expressor.llm_client is None


def test_default_expressor_treats_blank_api_key_as_disabled(monkeypatch):
    monkeypatch.setenv("GUANGHE_LLM_ENABLED", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "   ")

    expressor = build_default_ai_expressor()

    assert expressor.enabled is False
    assert expressor.llm_client is None


def test_default_expressor_treats_non_string_api_key_env_as_disabled():
    expressor = build_default_ai_expressor(
        {
            "GUANGHE_LLM_ENABLED": "1",
            "OPENAI_API_KEY": object(),
        }
    )

    assert expressor.enabled is False
    assert expressor.llm_client is None


def test_default_expressor_uses_openai_provider_when_env_is_enabled(monkeypatch):
    monkeypatch.setenv("GUANGHE_LLM_ENABLED", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("GUANGHE_LLM_MODEL", "gpt-test")
    monkeypatch.setenv("GUANGHE_LLM_TIMEOUT_SECONDS", "0.5")

    expressor = build_default_ai_expressor()

    assert expressor.enabled is True
    assert isinstance(expressor.llm_client, OpenAIResponsesClient)
    assert expressor.llm_client.model == "gpt-test"
    assert expressor.timeout_seconds == 0.5


def test_default_expressor_uses_default_model_for_blank_model_env(monkeypatch):
    monkeypatch.setenv("GUANGHE_LLM_ENABLED", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("GUANGHE_LLM_MODEL", "   ")

    expressor = build_default_ai_expressor()

    assert isinstance(expressor.llm_client, OpenAIResponsesClient)
    assert expressor.llm_client.model == DEFAULT_OPENAI_MODEL


def test_default_expressor_rejects_non_finite_timeout_env(monkeypatch):
    monkeypatch.setenv("GUANGHE_LLM_ENABLED", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("GUANGHE_LLM_TIMEOUT_SECONDS", "inf")

    expressor = build_default_ai_expressor()

    assert expressor.timeout_seconds == 2.0
    assert isinstance(expressor.llm_client, OpenAIResponsesClient)
    assert expressor.llm_client.timeout_seconds == 2.0


def test_default_expressor_rejects_non_numeric_timeout_env_value():
    expressor = build_default_ai_expressor(
        {
            "GUANGHE_LLM_ENABLED": "1",
            "OPENAI_API_KEY": "test-key",
            "GUANGHE_LLM_TIMEOUT_SECONDS": object(),
        }
    )

    assert expressor.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
    assert isinstance(expressor.llm_client, OpenAIResponsesClient)
    assert expressor.llm_client.timeout_seconds == DEFAULT_TIMEOUT_SECONDS


def test_openai_responses_client_posts_prompt_and_extracts_output_text():
    captured = {}

    def transport(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = request.data.decode("utf-8")
        captured["timeout"] = timeout
        return (
            '{"output":[{"content":[{"type":"output_text","text":"'
            '[{\\"character_name\\":\\"星汐\\",\\"speech\\":\\"hi\\",\\"sprite\\":\\"1\\",\\"effect\\":\\"ATTENTION\\"}]'
            '"}]}]}'
        ).encode("utf-8")

    client = OpenAIResponsesClient(api_key="test-key", model="gpt-test", timeout_seconds=0.5, transport=transport)

    result = client("prompt text")

    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["timeout"] == 0.5
    assert '"model": "gpt-test"' in captured["payload"]
    assert '"input": "prompt text"' in captured["payload"]
    assert result.startswith('[{"character_name"')


def test_openai_responses_client_trims_api_key_for_authorization_header():
    captured = {}

    def transport(request, timeout):
        captured["headers"] = dict(request.header_items())
        return b'{"output_text":"[{\\"type\\":\\"speech\\",\\"speech\\":\\"hi\\"}]"}'

    client = OpenAIResponsesClient(api_key="  test-key  ", transport=transport)

    client("prompt text")

    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_openai_responses_client_rejects_blank_direct_api_key_without_transport():
    called = False

    def transport(request, timeout):
        nonlocal called
        called = True
        return b'{"output_text":"[{\\"type\\":\\"speech\\",\\"speech\\":\\"hi\\"}]"}'

    client = OpenAIResponsesClient(api_key="   ", transport=transport)

    try:
        client("prompt text")
    except LLMProviderError as exc:
        assert "OpenAI expression provider failed" in str(exc)
    else:
        raise AssertionError("blank api key should fail before transport.")
    assert called is False


def test_openai_responses_client_rejects_non_string_direct_api_key_without_transport():
    called = False

    def transport(request, timeout):
        nonlocal called
        called = True
        return b'{"output_text":"[{\\"type\\":\\"speech\\",\\"speech\\":\\"hi\\"}]"}'

    client = OpenAIResponsesClient(api_key=object(), transport=transport)

    try:
        client("prompt text")
    except LLMProviderError as exc:
        assert "OpenAI expression provider failed" in str(exc)
    else:
        raise AssertionError("non-string api key should fail before transport.")
    assert called is False


def test_openai_responses_client_trims_model_for_request_payload():
    captured = {}

    def transport(request, timeout):
        captured["payload"] = request.data.decode("utf-8")
        return b'{"output_text":"[{\\"type\\":\\"speech\\",\\"speech\\":\\"hi\\"}]"}'

    client = OpenAIResponsesClient(api_key="test-key", model="  gpt-test  ", transport=transport)

    client("prompt text")

    assert '"model": "gpt-test"' in captured["payload"]


def test_openai_responses_client_uses_default_model_for_blank_direct_model():
    captured = {}

    def transport(request, timeout):
        captured["payload"] = request.data.decode("utf-8")
        return b'{"output_text":"[{\\"type\\":\\"speech\\",\\"speech\\":\\"hi\\"}]"}'

    client = OpenAIResponsesClient(api_key="test-key", model="   ", transport=transport)

    client("prompt text")

    assert f'"model": "{DEFAULT_OPENAI_MODEL}"' in captured["payload"]


def test_openai_responses_client_uses_default_model_for_non_string_direct_model():
    captured = {}

    def transport(request, timeout):
        captured["payload"] = request.data.decode("utf-8")
        return b'{"output_text":"[{\\"type\\":\\"speech\\",\\"speech\\":\\"hi\\"}]"}'

    client = OpenAIResponsesClient(api_key="test-key", model=object(), transport=transport)

    client("prompt text")

    assert f'"model": "{DEFAULT_OPENAI_MODEL}"' in captured["payload"]


def test_openai_responses_client_rejects_non_finite_timeout_for_transport():
    captured = {}

    def transport(request, timeout):
        captured["timeout"] = timeout
        return b'{"output_text":"[{\\"type\\":\\"speech\\",\\"speech\\":\\"hi\\"}]"}'

    client = OpenAIResponsesClient(api_key="test-key", timeout_seconds=float("inf"), transport=transport)

    client("prompt text")

    assert captured["timeout"] == DEFAULT_TIMEOUT_SECONDS


def test_openai_responses_client_skips_blank_output_text_for_nested_text():
    client = OpenAIResponsesClient(
        api_key="test-key",
        transport=lambda request, timeout: (
            '{"output_text":"   ","output":[{"content":['
            '{"type":"output_text","text":"\\n"},'
            '{"type":"output_text","text":"[{\\"type\\":\\"speech\\",\\"speech\\":\\"hi\\"}]"}'
            "]}]}"
        ).encode("utf-8"),
    )

    result = client("prompt text")

    assert result == '[{"type":"speech","speech":"hi"}]'


def test_openai_responses_client_trims_response_output_text():
    client = OpenAIResponsesClient(
        api_key="test-key",
        transport=lambda request, timeout: (
            '  {"output_text":"  [{\\"type\\":\\"speech\\",\\"speech\\":\\"hi\\"}]  "}  '
        ).encode("utf-8"),
    )

    result = client("prompt text")

    assert result == '[{"type":"speech","speech":"hi"}]'


def test_openai_responses_client_trims_nested_output_text():
    client = OpenAIResponsesClient(
        api_key="test-key",
        transport=lambda request, timeout: (
            '{"output":[{"content":[{"type":"output_text","text":"\\n  '
            '[{\\"type\\":\\"speech\\",\\"speech\\":\\"hi\\"}]  \\t"}]}]}'
        ).encode("utf-8"),
    )

    result = client("prompt text")

    assert result == '[{"type":"speech","speech":"hi"}]'


def test_openai_responses_client_wraps_transport_errors_without_leaking_key():
    def transport(request, timeout):
        raise OSError("boom test-key")

    client = OpenAIResponsesClient(api_key="test-key", model="gpt-test", transport=transport)

    try:
        client("prompt text")
    except LLMProviderError as exc:
        assert "test-key" not in str(exc)
    else:
        raise AssertionError("provider transport errors should be wrapped.")


def test_openai_responses_client_wraps_empty_or_non_text_responses():
    empty_client = OpenAIResponsesClient(
        api_key="test-key",
        transport=lambda request, timeout: b'{"output":[]}',
    )
    non_text_client = OpenAIResponsesClient(
        api_key="test-key",
        transport=lambda request, timeout: b'{"output":[{"content":[{"type":"input_text","text":"ignored"}]}]}',
    )

    for client in (empty_client, non_text_client):
        try:
            client("prompt text")
        except LLMProviderError:
            pass
        else:
            raise AssertionError("missing output_text should be wrapped.")


def test_expressor_falls_back_when_provider_returns_non_json_text():
    snapshot = make_snapshot()
    client = OpenAIResponsesClient(
        api_key="test-key",
        transport=lambda request, timeout: b'{"output_text":"not json"}',
    )
    expressor = ShinsekaiAIExpressor(llm_client=client)

    events = expressor.express(snapshot)

    assert len(events) == 3
    assert events[0]["speech"] == snapshot["feedback"]
    assert events[0]["effect"] == "DISAPPOINTED"


def test_expressor_falls_back_when_provider_raises_wrapped_error():
    snapshot = make_snapshot()

    def transport(request, timeout):
        raise OSError("network down")

    expressor = ShinsekaiAIExpressor(
        llm_client=OpenAIResponsesClient(api_key="test-key", transport=transport)
    )

    events = expressor.express(snapshot)

    assert len(events) == 3
    assert events[0]["speech"] == snapshot["feedback"]
    assert events[0]["effect"] == "DISAPPOINTED"
