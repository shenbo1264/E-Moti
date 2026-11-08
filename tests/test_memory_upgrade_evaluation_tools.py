import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from guanghe_companion.expression_settings import ExpressionSettings, ExpressionSettingsStore


ROOT = Path(__file__).resolve().parents[1]


def load_tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generation_input(tmp_path):
    path = tmp_path / "retrieval.json"
    path.write_text(json.dumps({"method": "layered", "size": 1, "rows": [
        {"query_id": "q", "story_id": "s", "split": "development", "query": "你好",
         "gold_ids": [], "forbidden_ids": [], "actual_provider_prompt": "冻结的测试提示词"}]}), encoding="utf-8")
    return path


def test_app_settings_keep_actual_model_protocol_and_ignore_environment_credentials(tmp_path):
    runner = load_tool("eval_ondemand_generation")
    path = tmp_path / "expression_settings.json"
    secret = "local-protocol-test-secret"
    ExpressionSettingsStore(path).save(ExpressionSettings(enabled=True, provider="deepseek", model="deepseek-flash",
        base_url="https://example.invalid/v1", api_key=secret, timeout_seconds=17))
    args = runner.parse_args(["--input", str(generation_input(tmp_path)), "--output", str(tmp_path / "out.json"),
        "--app-settings", str(path), "--max-output-tokens", "1024"])
    sent = []

    def transport(request, timeout):
        sent.append((json.loads(request.data), timeout, request.get_header("Authorization")))
        return json.dumps({"model": "returned-flash-version", "choices": [{"message": {"content":
            '{"type":"speech","speech":"你好。"}'}}], "usage": {"prompt_tokens": 12, "completion_tokens": 6}}).encode()

    result = runner.run(args, environ={"EMOTI_HOLDOUT_API_KEY": "wrong-environment-key", "EMOTI_LLM_MODEL": "wrong-model"}, transport=transport)
    body, timeout, header = sent[0]
    assert body["model"] == "deepseek-flash"
    assert body["max_tokens"] == 1024
    assert body["response_format"] == {"type": "json_object"}
    assert timeout == 17 and header == "Bearer " + secret
    assert result["provider"]["api_style"] == "chat"
    assert result["provider"]["credential_source"] == "app_settings"
    assert result["rows"][0]["provider_model"] == "returned-flash-version"
    assert result["rows"][0]["raw_response_text"]
    assert secret not in args.output.read_text(encoding="utf-8")
    assert "wrong-environment-key" not in args.output.read_text(encoding="utf-8")
    assert result["provider"]["transport"] == "injected_test"


def test_disabled_app_settings_do_not_fall_back_to_environment(tmp_path):
    runner = load_tool("eval_ondemand_generation")
    path = tmp_path / "expression_settings.json"
    ExpressionSettingsStore(path).save(ExpressionSettings(enabled=False, provider="deepseek", model="deepseek-flash", api_key="disabled-test-key"))
    args = runner.parse_args(["--input", str(generation_input(tmp_path)), "--output", str(tmp_path / "out.json"), "--app-settings", str(path)])
    result = runner.run(args, environ={"EMOTI_HOLDOUT_API_KEY": "other-key", "EMOTI_LLM_MODEL": "other", "EMOTI_LLM_BASE_URL": "https://example.invalid"})
    assert result["actual_requests"] == 0
    assert result["status"] == "not_run"
    assert "enabled" in result["missing_configuration"]


def test_explicit_app_settings_cannot_be_silently_overridden(tmp_path):
    runner = load_tool("eval_ondemand_generation")
    with pytest.raises(SystemExit):
        runner.parse_args(["--input", str(generation_input(tmp_path)), "--app-settings", "settings.json", "--model", "other"])


def test_story_clock_precedes_dataset_clock():
    runner = load_tool("eval_ondemand_memory")
    assert runner.story_clock({"now": 1793534400, "time_basis": "unix"}, {"now": 500, "time_basis": "logical"}) == (500, "logical")
    assert runner.story_clock({"now": 23, "time_basis": "logical"}, {}) == (23, "logical")
    assert runner.story_clock({"now": 1793534400}, {}) == (1793534400, "unix")
    with pytest.raises(ValueError):
        runner.story_clock({"now": 0}, {"time_basis": "guess"})


def test_logical_stress_entries_do_not_use_unix_timestamps():
    runner = load_tool("eval_ondemand_memory")
    data = {"owner_id": "owner", "character_id": "character", "now": 500, "time_basis": "logical",
            "stories": [{"id": "s"}], "memories": []}
    rows = runner.make_input_rows(data, "s", 300)
    assert all(0 <= row["occurred_at"] <= 500 for row in rows)


def test_explicit_legacy_revision_checks_real_repository(tmp_path):
    runner = load_tool("eval_ondemand_memory")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    source = tmp_path / "src/guanghe_companion/probe.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Protocol Test", "-c", "user.email=protocol@example.invalid",
                    "commit", "-qm", "fixture"], check=True)
    commit = subprocess.check_output(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True).strip()
    assert runner.validate_baseline(tmp_path, commit) == commit
    with pytest.raises(ValueError):
        runner.validate_baseline(tmp_path, "0" * 40)
    source.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        runner.validate_baseline(tmp_path, commit)


def test_peak_memory_is_measured_on_current_platform():
    runner = load_tool("eval_ondemand_memory")
    assert runner.peak_rss_mib() > 0


def test_recording_transport_keeps_invalid_response_and_request_budget():
    from urllib.request import Request
    runner = load_tool("eval_ondemand_generation")
    meter = runner.RecordingTransport(delegate=lambda request, timeout: b"invalid-provider-json", api_style="chat", max_output_tokens=128, max_requests=1)
    request = Request("https://example.invalid", data=b'{"model":"protocol-only"}')
    assert meter(request, 5) == b"invalid-provider-json"
    assert meter.records[0]["raw_response_text"] == "invalid-provider-json"
    with pytest.raises(RuntimeError, match="request budget"):
        meter(request, 5)
    assert meter.calls == 1


def test_judge_usage_counts_failed_outputs_and_prepare_only_retrieval():
    runner = load_tool("eval_ondemand_memory")
    rows = [{"trace": {"retrieval_calls": 0}, "prepare_rows_loaded": 3,
             "evidence_judgment": {"status": "unavailable:LLMProviderError", "requests": [
                 {"provider_response": {"usage": {"prompt_tokens": 577, "completion_tokens": 1024,
                    "completion_tokens_details": {"reasoning_tokens": 1024}},
                    "choices": [{"finish_reason": "length", "message": {"content": ""}}]}}]}}]
    summary = runner.summarize_evidence(rows)
    assert summary["actual_requests"] == 1
    assert summary["failed_judgments"] == 1
    assert summary["output_tokens"] == 1024
    assert summary["reasoning_tokens"] == 1024
    assert summary["input_tokens"] == 577
    assert runner.retrieval_performed(rows[0])
    assert runner.retrieval_performed({"trace": {"retrieval_calls": 0}, "prepare_rows_loaded": 2})
    assert not runner.retrieval_performed({"trace": {"retrieval_calls": 0}})


def test_app_evidence_budget_preserves_existing_provider_default(tmp_path):
    runner = load_tool("eval_ondemand_generation")
    path = tmp_path / "settings.json"
    ExpressionSettingsStore(path).save(ExpressionSettings(enabled=True, provider="deepseek", model="deepseek-flash", api_key="test-key"))
    client, meter, metadata, secret = runner.recorded_app_client(path)
    try:
        assert client.max_tokens == 4096
        assert meter.max_output_tokens == 4096
        assert metadata["max_output_tokens"] == 4096
    finally:
        client.close()


def test_logical_story_worker_keeps_declared_time_basis(tmp_path):
    dataset = {"split": "development", "owner_id": "protocol-owner", "character_id": "protocol_character",
        "now": 1793534400, "time_basis": "unix", "stories": [{"id": "s", "template_family": "clock", "now": 500, "time_basis": "logical"}],
        "memories": [{"id": "m", "story_id": "s", "kind": "用户自述", "title": "职业", "summary": "用户的职业是木工。",
                      "source": "explicit_user_request", "source_ids": ["statement"], "user_confirmed": True,
                      "occurred_at": 10, "created_at": 11, "updated_at": 11}],
        "queries": [{"id": "q", "story_id": "s", "family": "clock", "text": "2026年10月20日我的职业是什么？", "gold_ids": [],
                     "forbidden_ids": ["m"], "scope": "companion", "expected_routes": ["fact"], "expected_status": "insufficient", "should_retrieve_long_term": True}]}
    (tmp_path / "ondemand_memory_development.json").write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "result.json"
    result = subprocess.run([sys.executable, str(ROOT / "tools/eval_ondemand_memory.py"), "--worker", "routed", "--size", "1",
        "--dataset-dir", str(tmp_path), "--splits", "development", "--source-root", str(ROOT), "--no-semantic", "--worker-output", str(output)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 0, result.stderr
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["stories"][0]["now"] == 500
    assert artifact["stories"][0]["time_basis"] == "logical"
    assert artifact["rows"][0]["trace"]["status"] == "insufficient"
    assert Path(artifact["temporary_root"]).is_relative_to(ROOT / "artifacts/codex_handoff")
