import time

from guanghe_companion.ai_expressor import OpenAIResponsesClient, ShinsekaiAIExpressor, build_default_ai_expressor
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
    assert '"character_name"' in prompt


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


def test_expressor_rejects_more_than_four_llm_rows():
    snapshot = make_snapshot()
    row = '{"character_name":"%s","speech":"ok","sprite":"1","effect":"ATTENTION"}' % snapshot["character_name"]
    expressor = ShinsekaiAIExpressor(llm_client=lambda prompt: f"[{','.join([row] * 5)}]")

    events = expressor.express(snapshot)

    assert len(events) == 3
    assert events[0]["speech"] == snapshot["feedback"]


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
