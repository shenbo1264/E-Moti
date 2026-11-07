"""Evaluation integrity: grade delivered evidence, never the expected answer."""
import importlib.util
import json
import pytest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ondemand_eval", ROOT / "tools/eval_ondemand_memory.py")
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def query():
    return {"id": "q", "story_id": "s", "family": "f", "text": "我的名字是什么？",
            "history": [], "gold_ids": ["name"], "forbidden_ids": [],
            "expected_routes": ["fact"], "expected_status": "sufficient",
            "should_retrieve_long_term": True}


@pytest.mark.parametrize("archive_now,story_now", [(None, None), (10, None), (20, 10)])
def test_query_clock_cannot_be_silently_ignored(tmp_path, archive_now, story_now):
    data = {"split": "holdout", "stories": [{"id": "s", "template_family": "clock"}],
            "memories": [{"id": "name", "story_id": "s"}], "queries": [{**query(), "now": 20}]}
    if archive_now is not None:
        data['now'] = archive_now
    if story_now is not None:
        data['stories'][0]['now'] = story_now
    (tmp_path / 'ondemand_memory_holdout.json').write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='query clock'):
        evaluation.load_datasets(tmp_path, ['holdout'])


def test_matching_query_clock_preserves_authored_time(tmp_path):
    data = {"split": "holdout", "now": 20, "stories": [{"id": "s", "template_family": "clock"}],
            "memories": [{"id": "name", "story_id": "s"}], "queries": [{**query(), "now": 20}]}
    (tmp_path / 'ondemand_memory_holdout.json').write_text(json.dumps(data), encoding='utf-8')
    assert evaluation.load_datasets(tmp_path, ['holdout'])[0]['now'] == 20


def test_frozen_datasets_keep_stories_and_gold_in_their_split():
    datasets = evaluation.load_datasets(ROOT / "tests/fixtures", evaluation.SPLITS)
    assert [len(d["queries"]) for d in datasets] == [108, 36, 48]
    assert sum(len(d["stories"]) for d in datasets) == 32
    assert all(any(q["gold_ids"] for q in d["queries"]) and
               any(not q["gold_ids"] for q in d["queries"]) for d in datasets)


def test_selected_id_without_source_content_does_not_receive_delivery_credit():
    prompt = {"emotional_memory": {"retrieval": {"selected_memory_ids": ["name"]}}}
    row = evaluation.score_query(query(), prompt, ["name"], {}, {})
    assert row["recall_at_4"] == 1
    assert row["delivered_recall"] == 0
    assert not row["all_gold_delivered"]


def test_provider_budget_is_scored_from_rendered_json_not_prefit_ids():
    text = 'instructions\npersona: {"config_hash":"abc"}\nemotional_memory: {"retrieval":{"status":"insufficient"}}\n'
    payload = evaluation.provider_evidence_payload(text)
    row = evaluation.score_query(query(), payload, ["name"], {}, {})
    assert row["recall_at_4"] == 1
    assert row["delivered_recall"] == 0
    assert payload["persona"]["config_hash"] == "abc"


def test_extractive_overview_gets_evidence_credit_and_source_check():
    prompt = {"emotional_memory": {"memory_overview": {"claims": [
        {"text": "我的名字是阿青。", "source_memory_id": "name"}]}}}
    row = evaluation.score_query(query(), prompt, ["name"], {},
                                 {"name": {"title": "名字", "summary": "我的名字是阿青。"}})
    assert row["all_gold_delivered"]
    assert row["overview_claims"][0]["extractively_entailed"]


def test_unrelated_overview_claim_cannot_pass_extractive_entailment():
    prompt = {"emotional_memory": {"memory_overview": {"claims": [
        {"text": "用户很信任我。", "source_memory_id": "name"}]}}}
    row = evaluation.score_query(query(), prompt, ["name"], {},
                                 {"name": {"title": "名字", "summary": "我的名字是阿青。"}})
    assert not row["overview_claims"][0]["extractively_entailed"]
    assert not row["supported_gold_delivered"]


def test_source_id_with_wrong_raw_body_cannot_pass_supported_delivery():
    prompt = {"emotional_memory": {"shared_memories": [
        {"memory_id": "name", "summary": "用户很信任我。"}]}}
    row = evaluation.score_query(query(), prompt, ["name"], {},
                                 {"name": {"title": "名字", "summary": "我的名字是阿青。"}})
    assert row["all_gold_delivered"]
    assert not row["supported_gold_delivered"]


def test_unsourced_overview_claim_remains_in_the_coverage_denominator():
    prompt = {"emotional_memory": {"memory_overview": {"claims": [{"text": "用户很信任我。"}]}}}
    row = evaluation.score_query(query(), prompt, [], {}, {})
    assert row["delivered_ids"] == []
    assert len(row["overview_claims"]) == 1
    assert not row["overview_claims"][0]["source_present"]
    assert evaluation.summarize([row])["overview_source_coverage"]["denominator"] == 1


def test_alias_source_is_not_answer_credit_but_is_a_forgetting_channel():
    q = {**query(), "forbidden_ids": ["alias"]}
    prompt = {"emotional_memory": {"resolution_evidence": [
        {"memory_id": "alias", "summary": "阿青就是用户。", "purpose": "entity_resolution"}]}}
    row = evaluation.score_query(q, prompt, [], {}, {"alias": {"state": "forgotten"}})
    assert row["delivered_ids"] == []
    assert row["delivered_recall"] == 0
    assert row["forbidden_delivered"] == ["alias"]
    assert row["forgotten_ids"] == ["alias"]


def test_empty_gold_does_not_count_as_perfect_recall():
    q = {**query(), "gold_ids": [], "expected_status": "unknown"}
    row = evaluation.score_query(q, {"emotional_memory": {}}, [], {"status": "unknown"}, {})
    result = evaluation.summarize([row])
    assert result["macro_recall_at_4"] is None
    assert result["no_answer_injection"] == {"numerator": 0, "denominator": 1, "rate": 0}
    assert result["answerable_zero_evidence"]["denominator"] == 0


def test_manifest_usage_is_loaded_instead_of_inferred_from_split_name(tmp_path):
    data = {"split": "holdout", "stories": [{"id": "s", "template_family": "family"}],
            "memories": [{"id": "name", "story_id": "s"}], "queries": [query()]}
    path = tmp_path / "ondemand_memory_holdout.json"
    path.write_text(json.dumps(data))
    (tmp_path / "ondemand_memory_manifest.json").write_text(json.dumps({
        "files": {path.name: evaluation.digest(path)}, "split_usage": {"holdout": "seen_regression"}}))
    assert evaluation.load_datasets(tmp_path, ["holdout"])[0]["split_usage"] == "seen_regression"


def typed_corpus():
    return {"owner_id": "owner", "character_id": "character", "memories": [{
        "id": "typed", "story_id": "s", "kind": "用户事实", "title": "设置",
        "summary": "用户设置为 grid，边距为 0。", "source": "user_chat", "source_ids": ["statement"],
        "occurred_at": 1, "created_at": 1, "updated_at": 1,
        "metadata": {"fact_subject": "user:self", "fact_value": {"layout": "grid", "margin": 0}}}]}


def test_input_and_text_hashes_do_not_hide_typed_value_normalization():
    from guanghe_companion.emotional_memory import EmotionalMemoryEntry
    data = typed_corpus()
    inputs = evaluation.make_input_rows(data, "s", 3)
    entries = evaluation.make_entries(data, "s", 3, EmotionalMemoryEntry, input_rows=inputs)
    corrected = evaluation.corpus_provenance(inputs, entries)
    old = tuple(replace(e, metadata={k: v for k, v in e.metadata.items() if k != "fact_value"})
                if e.memory_id == "typed" else e for e in entries)
    legacy = evaluation.corpus_provenance(inputs, old)
    assert corrected["input_corpus_sha256"] == legacy["input_corpus_sha256"]
    assert corrected["source_text_corpus_sha256"] == legacy["source_text_corpus_sha256"]
    assert corrected["canonical_without_fact_value_sha256"] == legacy["canonical_without_fact_value_sha256"]
    assert corrected["corpus_sha256"] != legacy["corpus_sha256"]
    assert not corrected["normalization_changes"]
    assert legacy["normalization_changes"][0]["field"] == "metadata.fact_value"
    assert legacy["normalization_changes"][0]["after_present"] is False


def test_canonical_source_text_hash_changes_when_the_body_changes():
    from guanghe_companion.emotional_memory import EmotionalMemoryEntry
    data = typed_corpus(); inputs = evaluation.make_input_rows(data, "s", 1)
    entries = evaluation.make_entries(data, "s", 1, EmotionalMemoryEntry, input_rows=inputs)
    original = evaluation.corpus_provenance(inputs, entries)
    changed = evaluation.corpus_provenance(inputs, [replace(entries[0], summary="另一份正文")])
    assert original["input_corpus_sha256"] == changed["input_corpus_sha256"]
    assert original["source_text_corpus_sha256"] != changed["source_text_corpus_sha256"]


def test_minimal_alias_binding_still_counts_forbidden_and_retired_source():
    q = {**query(), "forbidden_ids": ["alias"]}
    prompt = {"emotional_memory": {"resolution_evidence": [
        {"memory_id": "alias", "bindings": [{"alias": "阿青", "subjects": ["user:self"]}]}]}}
    source = {"state": "forgotten", "metadata": {"fact_subject": "user:self", "subject_aliases": ["阿青"]}}
    row = evaluation.score_query(q, prompt, [], {}, {"alias": source})
    assert row["forbidden_delivered"] == ["alias"]
    assert row["forgotten_ids"] == ["alias"]
    assert row["delivered_ids"] == []
    assert row["resolution_sources"][0]["literal_binding_supported"]
    prompt["emotional_memory"]["resolution_evidence"][0]["bindings"][0]["subjects"] = ["relation:同事"]
    row = evaluation.score_query(q, prompt, [], {}, {"alias": source})
    assert not row["resolution_sources"][0]["literal_binding_supported"]
