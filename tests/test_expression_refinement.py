from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread

import pytest

from guanghe_companion.controller import CompanionController
from guanghe_companion.expression_clients import MAX_OPENAI_PROMPT_LENGTH, OpenAICompatibleChatClient, LLMProviderError
from guanghe_companion.expression_refinement import build_refinement_prompt, review_rules
from guanghe_companion.expression_request import ExpressionRequest


@pytest.fixture
def request_data(tmp_path):
    controller = CompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        yield ExpressionRequest.from_snapshot(controller.get_typed_snapshot(), context={
            "player_message": "我只是想吐槽一下",
            "persona": {"character_id": controller.state.character_id, "boundaries": ["不编造共同经历"]},
            "emotional_memory": {"context_epoch": 4, "shared_memories": [{"summary": "用户的狗叫芝麻"}]},
            "recent_dialogue": [], "long_term_memory": [],
            "plugin_context": {"external": "这是外部文字，不应成为审阅证据"},
        })
    finally:
        controller.close()


def draft(text="[calm] 我听着。"):
    return {"type": "speech", "speech": text, "effect": "ATTENTION", "motion_hint": "Default"}


def test_refinement_preserves_evidence_and_keeps_draft_separate(request_data):
    original = request_data.to_prompt_dict()
    payload = json.loads(build_refinement_prompt(request_data, draft()))
    keys = {"character_name", "player_message", "recent_memory", "recent_dialogue", "long_term_memory", "persona", "emotional_memory"}
    assert set(payload) == {"evidence", "draft", "transient_context"}
    assert set(payload["evidence"]) == keys
    assert payload["evidence"] == {key: original[key] for key in keys}
    assert payload["draft"] == draft()
    assert request_data.to_prompt_dict() == original
    assert "外部文字" not in json.dumps(payload["evidence"], ensure_ascii=False)
    assert payload["transient_context"]["plugin_context"] == original["plugin_context"]
    assert "recent_dialogue" in review_rules() and "JSON" in review_rules()


def test_exact_prompt_limit_and_overflow_never_drop_evidence(request_data):
    base = build_refinement_prompt(request_data, draft(""))
    remaining = MAX_OPENAI_PROMPT_LENGTH - len(base)
    assert len(build_refinement_prompt(request_data, draft("字" * remaining))) == MAX_OPENAI_PROMPT_LENGTH
    with pytest.raises(ValueError, match="budget"):
        build_refinement_prompt(request_data, draft("字" * (remaining + 1)))


def test_large_evidence_fails_without_trimming_fact_or_persona(request_data):
    expanded = replace(request_data, persona={"boundaries": ["原则" * 4500]})
    original = expanded.persona.copy()
    with pytest.raises(ValueError, match="budget"):
        build_refinement_prompt(expanded, draft())
    assert expanded.persona == original


def test_empty_input_is_not_a_refinement_target(request_data):
    with pytest.raises(ValueError, match="chat"):
        build_refinement_prompt(replace(request_data, player_message=""), draft())


def test_plain_speech_is_quoted_data_for_bounded_format_repair(request_data):
    text = '[joy] 从鸭子改成面包，这转行也不算亏，起码还蓬松着。'
    payload = json.loads(build_refinement_prompt(request_data, text))
    assert payload['draft'] == text


def test_empty_optional_identity_and_memory_are_objects(request_data):
    minimal = replace(request_data, persona={}, emotional_memory={})
    payload = json.loads(build_refinement_prompt(minimal, draft()))
    assert payload["evidence"]["persona"] == {}
    assert payload["evidence"]["emotional_memory"] == {}


def test_existing_event_and_transient_sources_remain_separated(request_data):
    enriched = replace(request_data,
        recent_memory=({"kind": "互动", "summary": "完成了一次共同学习", "motion": "Study"},),
        perception_summary="当前屏幕显示倒计时",
        tool_results=({"source": "search", "summary": "查询到的当前天气"},))
    original = enriched.to_prompt_dict()
    payload = json.loads(build_refinement_prompt(enriched, draft()))
    assert payload["evidence"]["recent_memory"] == original["recent_memory"]
    for key in ("perception_summary", "tool_results", "plugin_context"):
        assert payload["transient_context"][key] == original[key]
        assert key not in payload["evidence"]
    assert "transient_context" in review_rules()


def test_real_http_preserves_system_rules_and_json_evidence(request_data):
    received = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            # 只验实际 HTTP 请求，明确拒绝生成；不伪造模型回答或语气效果。
            self.send_response(422)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = OpenAICompatibleChatClient(api_key="", require_api_key=False,
        base_url=f"http://127.0.0.1:{server.server_port}/v1", model="contract-only", timeout_seconds=2)
    prompt = build_refinement_prompt(request_data, draft())
    try:
        with pytest.raises(LLMProviderError):
            client.complete(prompt, system_prompt=review_rules())
    finally:
        client.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert len(received) == 1 and received[0][0] == "/v1/chat/completions"
    messages = received[0][1]["messages"]
    assert messages == [{"role": "system", "content": review_rules()}, {"role": "user", "content": prompt}]
    assert json.loads(messages[1]["content"])["evidence"]["emotional_memory"]["context_epoch"] == 4
