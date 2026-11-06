import copy
import importlib.util
import json
from pathlib import Path

import pytest

from guanghe_companion.expression_request import ExpressionRequest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eval_ondemand_presentation", ROOT / "tools/eval_ondemand_presentation.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def inputs(tmp_path, *, wrong_body=False):
    memory = {"id": "m1", "story_id": "s1", "kind": "用户自述", "title": "饮品偏好",
              "summary": "用户喜欢白茶。", "source": "explicit_user_request", "source_ids": ["source:1"],
              "user_confirmed": True, "scope": "companion", "occurred_at": 1, "created_at": 1, "updated_at": 1}
    query = {"id": "q1", "story_id": "s1", "family": "drink", "text": "我喜欢什么茶？",
             "gold_ids": ["m1"], "forbidden_ids": [], "expected_routes": ["fact"],
             "expected_status": "sufficient", "should_retrieve_long_term": True, "scope": "companion"}
    dataset = {"schema_version": 1, "split": "validation", "owner_id": "owner", "character_id": "character",
               "stories": [{"id": "s1", "template_family": "drink"}], "memories": [memory], "queries": [query]}
    dataset_path = tmp_path / "ondemand_memory_validation.json"
    dataset_path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
    payload = ExpressionRequest.from_snapshot({"character_name": "旧名", "focus": 50, "charge": 50,
        "stability": 50, "mood": 50, "trust": 50, "player_message": query["text"]},
        context={"persona": {"character_name": "旧名", "description": "旧版展示"},
        "emotional_memory": {"shared_memories": [{"memory_id": "m1",
             "summary": "用户喜欢红茶。" if wrong_body else memory["summary"]}]}}).to_prompt_dict()
    raw = {"method": "lexical", "size": 300, "source_commit": "legacy-revision", "source_sha256": {"legacy.py": "old"},
        "dataset_sha256": {"validation": runner.digest(dataset_path)},
        "budget": {"expression_memory_chars": 6000, "final_provider_prompt_chars": 8192},
        "summary": {"supported_delivery": {"numerator": 99, "denominator": 99}},
        "rows": [{"query_id": "q1", "story_id": "s1", "split": "validation", "family": "drink", "query": query["text"],
             "gold_ids": ["m1"], "forbidden_ids": [], "expected_routes": ["fact"], "expected_status": "sufficient",
             "should_retrieve_long_term": True, "retrieved_ids": ["m1"], "delivered_ids": ["m1"],
             "supported_gold_delivered": True, "trace": {"router_evaluated": False, "retrieval_calls": 1},
             "actual_expression_request": payload, "actual_provider_prompt": "old presentation", "error": None}]}
    path = tmp_path / "lexical-300.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path, raw, runner.load_datasets(tmp_path, ["validation"])


def test_rebuilds_current_prompt_keeps_retrieval_and_original_evidence(tmp_path):
    path, raw, datasets = inputs(tmp_path)
    original = copy.deepcopy(raw)
    result = runner.normalize_artifact(path, datasets)
    assert raw == original
    assert json.loads(path.read_text(encoding="utf-8")) == original
    row = result["rows"][0]
    assert row["retrieved_ids"] == original["rows"][0]["retrieved_ids"]
    assert row["actual_expression_request"]["emotional_memory"] == original["rows"][0]["actual_expression_request"]["emotional_memory"]
    assert row["actual_provider_prompt"] == runner.render_prompt(row["actual_expression_request"])
    assert row["actual_expression_request"]["persona"]["character_name"] != "旧名"
    assert result["source_commit"] == "legacy-revision"
    assert result["source_sha256"] == {"legacy.py": "old"}
    assert result["original_retrieval"]["summary"] == original["summary"]
    assert result["original_retrieval"]["sha256"] == runner.digest(path)
    assert row["supported_gold_delivered"] is True
    assert result["summary"]["supported_delivery"] == {"numerator": 1, "denominator": 1, "rate": 1.0}


def test_recomputes_final_evidence_support_instead_of_trusting_old_score(tmp_path):
    path, raw, datasets = inputs(tmp_path, wrong_body=True)
    result = runner.normalize_artifact(path, datasets)
    row = result["rows"][0]
    assert row["original_delivery"]["supported_gold_delivered"] is True
    assert row["supported_gold_delivered"] is False
    assert row["verified_delivered_ids"] == []
    assert row["delivered_ids"] == ["m1"]


def test_rejects_different_dataset_without_changing_original(tmp_path):
    path, raw, datasets = inputs(tmp_path)
    datasets[0]["dataset_sha256"] = "other-data"
    with pytest.raises(ValueError, match="dataset"):
        runner.normalize_artifact(path, datasets)
    assert json.loads(path.read_text(encoding="utf-8")) == raw


def test_rejects_missing_request_and_already_normalized_input(tmp_path):
    path, raw, datasets = inputs(tmp_path)
    raw["rows"][0]["actual_expression_request"] = {}
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="ExpressionRequest"):
        runner.normalize_artifact(path, datasets)
    raw["presentation"] = {"version": "already"}
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="already"):
        runner.normalize_artifact(path, datasets)


def test_cli_writes_separate_artifact_and_rejects_existing_output(tmp_path):
    path, raw, _ = inputs(tmp_path)
    output = tmp_path / "unified"
    args = runner.parse_args(["--input", str(path), "--dataset-dir", str(tmp_path),
                             "--splits", "validation", "--output-dir", str(output)])
    written = runner.run(args)
    assert written == [output / path.name]
    assert json.loads(written[0].read_text(encoding="utf-8"))["presentation"]["version"] == runner.PRESENTATION_VERSION
    assert json.loads(path.read_text(encoding="utf-8")) == raw
    with pytest.raises(FileExistsError):
        runner.run(args)


def test_five_methods_receive_identical_presentation_for_identical_saved_evidence(tmp_path):
    path, raw, datasets = inputs(tmp_path)
    outputs = []
    for method in ("none", "lexical", "bge_rrf", "routed", "layered"):
        candidate = copy.deepcopy(raw)
        candidate["method"] = method
        candidate["source_commit"] = "old" if method in {"none", "lexical", "bge_rrf"} else "new"
        target = tmp_path / (method + ".json")
        target.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
        outputs.append(runner.normalize_artifact(target, datasets))
    assert len({item["rows"][0]["actual_provider_prompt"] for item in outputs}) == 1
    assert len({item["rows"][0]["presentation_persona_sha256"] for item in outputs}) == 1
    assert [item["source_commit"] for item in outputs] == ["old", "old", "old", "new", "new"]


def test_final_budget_loss_is_rescored_from_actual_rendered_prompt(tmp_path):
    path, raw, datasets = inputs(tmp_path)
    memory = raw["rows"][0]["actual_expression_request"]["emotional_memory"]
    original_card = memory["shared_memories"][0]
    memory["shared_memories"] = [{"memory_id": "padding-" + str(index), "summary": "这是一段普通日常记录。" * 18}
                                  for index in range(19)] + [original_card]
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    result = runner.normalize_artifact(path, datasets)
    row = result["rows"][0]
    assert len(row["actual_provider_prompt"]) <= 8192
    assert row["provider_lost_evidence_ids"]
    assert row["supported_gold_delivered"] is False
    assert "m1" in row["provider_lost_evidence_ids"]
