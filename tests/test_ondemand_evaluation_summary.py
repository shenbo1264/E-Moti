"""A comparative report must reject mismatched denominators and sources."""
import copy
import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("summary_eval", Path(__file__).resolve().parents[1] / "tools/summarize_ondemand_memory.py")
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def artifacts():
    return [{"method": method, "size": 300, "status": "measured_synthetic_retrieval",
             "source_unchanged_during_run": True, "source_sha256": {"module": "same"},
             "dataset_sha256": {"development": "frozen"}, "budget": {"top_k": 4},
             "stories": [{"split": "development", "story_id": "s", "corpus_sha256": "same"}],
             "rows": [{"query_id": "q", "actual_provider_prompt": "actual prompt", "error": None}],
             "summary": {"queries": 1}} for method in summary.METHODS]


def test_five_same_queries_and_corpora_are_auditable():
    assert summary.audit_group(artifacts())["query_count_per_method"] == 1


@pytest.mark.parametrize("fault", ["source_changed", "query_missing", "corpus_changed", "budget_changed", "prompt_missing"])
def test_invalid_comparison_is_not_silently_reported(fault):
    data = copy.deepcopy(artifacts())
    last = data[-1]
    if fault == "source_changed":
        last["source_unchanged_during_run"] = False
    elif fault == "query_missing":
        last["rows"] = []
    elif fault == "corpus_changed":
        last["stories"][0]["corpus_sha256"] = "different"
    elif fault == "budget_changed":
        last["budget"]["top_k"] = 1
    else:
        last["rows"][0]["actual_provider_prompt"] = ""
    with pytest.raises(ValueError):
        summary.audit_group(data)


def test_recorded_runtime_failure_stays_in_denominator():
    data = artifacts()
    data[-1]["rows"][0].update(error="TimeoutError", actual_provider_prompt="")
    assert summary.audit_group(data)["query_count_per_method"] == 1


def test_positive_net_gain_preserves_lost_correct_queries():
    old = [{"query_id": f"q{n}", "split": "validation", "gold_ids": ["source"],
            "supported_gold_delivered": n == 0} for n in range(3)]
    new = [{**r, "supported_gold_delivered": not r["supported_gold_delivered"]} for r in old]
    result = summary.delivery_transitions(old, new)["validation"]
    assert result["answerable_denominator"] == 3
    assert result["gained_ids"] == ["q1", "q2"]
    assert result["lost_ids"] == ["q0"]


def typed_artifacts():
    data = artifacts()
    for item in data:
        item["split_roles"] = {"development": "seen_regression"}
        story = item["stories"][0]
        story.update(input_corpus_sha256="same_input", source_text_corpus_sha256="same_text",
                     canonical_without_fact_value_sha256="same_other_fields", normalization_changes=[])
        if item["method"] in {"none", "lexical", "bge_rrf"}:
            story["corpus_sha256"] = "legacy_drops_dict"
            story["normalization_changes"] = [{"memory_id": "m", "field": "metadata.fact_value",
                "before_present": True, "after_present": False, "before": {"count": 0}, "after": None}]
    return data


def test_same_input_comparison_reports_documented_canonical_difference():
    audit = summary.audit_group(typed_artifacts())
    assert audit["input_corpora_identical"] and audit["source_text_corpora_identical"]
    assert audit["canonical_corpora_identical"] is False
    assert len(audit["normalization_differences"]) == 3


@pytest.mark.parametrize("field", ["input_corpus_sha256", "source_text_corpus_sha256", "canonical_without_fact_value_sha256"])
def test_normalization_fix_does_not_allow_other_input_or_text_changes(field):
    data = typed_artifacts(); data[-1]["stories"][0][field] = "changed"
    with pytest.raises(ValueError):
        summary.audit_group(data)


def test_arbitrary_replacement_of_fact_value_is_not_an_allowed_fix():
    data = typed_artifacts()
    data[-1]["stories"][0]["normalization_changes"] = [{"memory_id": "m", "field": "metadata.fact_value",
        "before_present": True, "after_present": True, "before": {"count": 0}, "after": {"count": 1}}]
    with pytest.raises(ValueError, match="unapproved"):
        summary.audit_group(data)


def test_usage_roles_must_match_across_methods():
    data = typed_artifacts(); data[-1]["split_roles"]["development"] = "independent_holdout"
    with pytest.raises(ValueError, match="usage roles"):
        summary.audit_group(data)
