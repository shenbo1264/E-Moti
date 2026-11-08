"""Generation-runner contract tests; synthetic transports are not model results."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eval_ondemand_generation", ROOT / "tools/eval_ondemand_generation.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def source(tmp_path, method="layered", count=2):
    from guanghe_companion.expression_request import ExpressionRequest
    payload = ExpressionRequest.from_snapshot({"character_name": "星汐", "focus": 50, "charge": 50,
        "stability": 50, "mood": 50, "trust": 50, "player_message": "我喜欢什么茶"},
        context={"persona": {"character_name": "星汐", "description": "好奇，保持判断。"},
                 "emotional_memory": {"shared_memories": [{"memory_id": "tea", "summary": "用户喜欢白茶"}]}}).to_prompt_dict()
    path = tmp_path / (method + ".json")
    path.write_text(json.dumps({"method": method, "size": 300, "rows": [
        {"query_id": f"q{i}", "story_id": "s1", "split": "validation", "query": "我喜欢什么茶",
         "gold_ids": ["tea"], "expected_status": "sufficient", "actual_expression_request": payload}
        for i in range(count)]}, ensure_ascii=False))
    return path


def config(tmp_path, inputs, *extra):
    return runner.parse_args(["--input", *(str(p) for p in inputs), "--output", str(tmp_path / "results.json"),
        "--model", "configured-model", "--base-url", "https://example.invalid/v1/responses", *extra])


def test_missing_credentials_produces_not_run_without_transport(tmp_path):
    args = config(tmp_path, [source(tmp_path)])
    def forbidden(*args):
        pytest.fail("missing key must never call transport")
    result = runner.run(args, environ={}, transport=forbidden)
    assert result["status"] == "not_run"
    assert result["actual_requests"] == 0
    assert all(row["status"] == "not_run" for row in result["rows"])
    assert "AI 只能生成表达事件" in result["rows"][0]["final_prompt"]
    assert result["rows"][0]["final_prompt_evidence_ids"] == ["tea"]
    assert result["evaluation"]["answer_correctness"]["status"] == "not_run"


def test_actual_client_applies_budget_and_records_usage_without_secrets(tmp_path):
    args = config(tmp_path, [source(tmp_path)], "--max-requests", "1", "--max-output-tokens", "96")
    seen = []
    secret = "test-secret-do-not-save"
    def transport(request, timeout):
        seen.append(json.loads(request.data))
        return json.dumps({"id": "response-1", "model": "returned-model-version", "usage": {
            "input_tokens": 24, "output_tokens": 12}, "output_text": '{"type":"speech","speech":"白茶。"}',
            "diagnostic": secret}).encode()
    result = runner.run(args, environ={"EMOTI_HOLDOUT_API_KEY": secret}, transport=transport)
    assert len(seen) == result["actual_requests"] == 1
    assert seen[0]["max_output_tokens"] == 96
    assert result["rows"][0]["provider_model"] == "returned-model-version"
    assert result["rows"][0]["usage"]["output_tokens"] == 12
    assert result["rows"][0]["review"]["answer_correctness"] == "pending_review"
    assert result["rows"][1]["status"] == "not_run"
    assert result["rows"][1]["reason"] == "request_budget_exhausted"
    assert secret not in json.dumps(result, ensure_ascii=False)
    assert secret not in args.output.read_text()


def test_transport_errors_do_not_become_unknown_answers(tmp_path):
    args = config(tmp_path, [source(tmp_path, count=1)])
    secret = "secret-transport"
    def failed(request, timeout):
        raise RuntimeError("bad provider " + secret)
    result = runner.run(args, environ={"EMOTI_HOLDOUT_API_KEY": secret}, transport=failed)
    assert result["rows"][0]["status"] == "failed"
    assert result["rows"][0]["answer"] is None
    assert result["rows"][0]["review"]["answer_correctness"] == "not_run"
    assert secret not in args.output.read_text()


def test_chat_uses_existing_client_and_user_prices_only(tmp_path):
    args = config(tmp_path, [source(tmp_path, count=1)], "--api-style", "chat",
        "--input-price-per-million", "2", "--output-price-per-million", "4")
    def transport(request, timeout):
        body = json.loads(request.data)
        assert body["max_tokens"] == 512
        assert body["messages"][0]["role"] == "user"
        return json.dumps({"model": "chat-version", "choices": [{"message": {"content":
            '{"type":"speech","speech":"白茶。"}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}}).encode()
    result = runner.run(args, environ={"EMOTI_HOLDOUT_API_KEY": "test-key"}, transport=transport)
    assert result["rows"][0]["cost_usd"] == pytest.approx(.0004)
    assert result["pricing"]["source"] == "user_supplied"
    assert result["evaluation"]["persona_behavior"]["value"] is None


def test_case_order_balances_methods_before_advancing_query(tmp_path):
    first = source(tmp_path, "lexical")
    second = source(tmp_path, "layered")
    args = config(tmp_path, [first, second])
    result = runner.run(args, environ={})
    assert [row["query_id"] for row in result["rows"]] == ["q0", "q0", "q1", "q1"]
    assert len({row["review_id"] for row in result["rows"]}) == 4


def test_missing_model_does_not_silently_use_client_default(tmp_path):
    args = config(tmp_path, [source(tmp_path, count=1)])
    args.model = "   "
    def forbidden(*args):
        pytest.fail("an empty explicit model cannot silently select a paid default")
    result = runner.run(args, environ={"EMOTI_HOLDOUT_API_KEY": "test-key"}, transport=forbidden)
    assert result["status"] == "not_run"
    assert "model" in result["missing_configuration"]


def test_saved_final_prompt_is_replayed_exactly_without_rebuilding(tmp_path, monkeypatch):
    path = source(tmp_path, count=1)
    data = json.loads(path.read_text())
    data["rows"][0]["actual_provider_prompt"] = "冻结时的真实生产提示词"
    path.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(runner, "render_prompt", lambda payload: pytest.fail("saved final prompt must not be rebuilt"))
    result = runner.run(config(tmp_path, [path]), environ={})
    assert result["rows"][0]["final_prompt"] == "冻结时的真实生产提示词"
    assert result["rows"][0]["prompt_origin"] == "saved_provider_prompt"


def test_missing_usage_is_unknown_cost_not_free(tmp_path):
    args = config(tmp_path, [source(tmp_path, count=1)], "--input-price-per-million", "2",
                  "--output-price-per-million", "4")
    def transport(request, timeout):
        return json.dumps({"model": "provider-model", "output_text": '{"type":"speech","speech":"白茶。"}'}).encode()
    result = runner.run(args, environ={"EMOTI_HOLDOUT_API_KEY": "test-key"}, transport=transport)
    assert result["estimated_cost_usd"] is None
    assert result["cost_coverage"]["known_requests"] == 0


def test_production_mode_requires_matching_saved_request_before_any_call(tmp_path):
    path = source(tmp_path, count=1)
    data = json.loads(path.read_text())
    data["rows"][0]["actual_provider_prompt"] = "旧版本提示词，不能伪称当前生产调用"
    path.write_text(json.dumps(data, ensure_ascii=False))
    args = config(tmp_path, [path], "--production-expression")
    result = runner.run(args, environ={})
    assert result["actual_requests"] == 0
    assert result["rows"][0]["reason"] == "prompt_build_failed"


def test_production_mode_without_credentials_is_not_run(tmp_path):
    args = config(tmp_path, [source(tmp_path, count=1)], "--production-expression")
    result = runner.run(args, environ={})
    assert result["status"] == "not_run"
    assert result["generation_mode"] == "production_expression"
    assert result["rows"][0]["answer"] is None


@pytest.mark.parametrize("option,value", [("--max-requests", "0"), ("--max-output-tokens", "4097"), ("--timeout", "61")])
def test_budget_rejects_values_the_existing_client_cannot_honor(tmp_path, option, value):
    with pytest.raises(SystemExit):
        config(tmp_path, [source(tmp_path)], option, value)
