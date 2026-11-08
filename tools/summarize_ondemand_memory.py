#!/usr/bin/env python3
"""Audit and summarize frozen five-path artifacts without rerunning retrieval.

Example:
  python tools/summarize_ondemand_memory.py \
    --input-dir artifacts/final-300 artifacts/final-scale \
    --output artifacts/final-summary.json

This consumes recorded provider prompts and scores; it never makes an LLM
request. Incomplete workers, changed production, missing queries, or different
story corpora fail the audit rather than silently becoming a favorable table.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


METHODS = ("none", "lexical", "bge_rrf", "routed", "layered")


def _legacy_structured_value_loss(change):
    """Only the documented old sanitizer loss may explain a corpus difference."""
    if change.get("field") != "metadata.fact_value" or not change.get("before_present"):
        return False
    before, after = change.get("before"), change.get("after")
    if isinstance(before, dict):
        return not change.get("after_present")
    if isinstance(before, list) and any(isinstance(v, (dict, list)) for v in before):
        expected = [v for v in before[:16] if isinstance(v, (str, int, float, bool)) or v is None]
        return bool(change.get("after_present")) and json.dumps(after, sort_keys=True) == json.dumps(expected, sort_keys=True)
    return False


def audit_group(artifacts):
    """Validate one size/campaign; keep runtime-error rows in its denominator."""
    methods = {a["method"]: a for a in artifacts}
    if len(artifacts) != len(METHODS) or set(methods) != set(METHODS):
        raise ValueError("A frozen comparison requires exactly the five declared methods")
    if len({a["size"] for a in artifacts}) != 1:
        raise ValueError("Compare one archive size at a time")
    query_ids, corpora, datasets, budget = None, None, None, None
    input_corpora, text_corpora, compatible_corpora, roles = None, None, None, None
    corpus_fields = ("input_corpus_sha256", "source_text_corpus_sha256", "canonical_without_fact_value_sha256")
    has_new_provenance = [all(story.get(key) for key in corpus_fields)
                          for artifact in artifacts for story in artifact["stories"]]
    modern = bool(has_new_provenance) and all(has_new_provenance)
    if any(has_new_provenance) and not modern:
        raise ValueError("Mixed or incomplete input/source-text corpus provenance")
    canonical_identical = True
    normalization_differences = []
    for method in METHODS:
        artifact = methods[method]
        if artifact.get("status") != "measured_synthetic_retrieval" or not artifact.get("source_unchanged_during_run"):
            raise ValueError(f"{method}: incomplete or changed-source worker")
        rows = artifact["rows"]
        ids = {r["query_id"] for r in rows}
        if len(rows) != len(ids) or artifact["summary"]["queries"] != len(rows):
            raise ValueError(f"{method}: duplicate query or lost denominator")
        actual_corpora = {(s["split"], s["story_id"]): s.get("corpus_sha256") for s in artifact["stories"]}
        if not actual_corpora or not all(actual_corpora.values()):
            raise ValueError(f"{method}: missing actual corpus hashes")
        if modern:
            actual_inputs, actual_texts, actual_compatible = (
                {(s["split"], s["story_id"]): s[key] for s in artifact["stories"]}
                for key in corpus_fields)
            for story in artifact["stories"]:
                if not isinstance(story.get("normalization_changes"), list):
                    raise ValueError(f"{method}: missing normalization changes")
                changed_values = [change for change in story["normalization_changes"]
                                  if change.get("field") == "metadata.fact_value"]
                if any(not _legacy_structured_value_loss(change) for change in changed_values):
                    raise ValueError(f"{method}: unapproved fact-value normalization")
                if changed_values:
                    normalization_differences.append({"method": method, "split": story["split"],
                        "story_id": story["story_id"], "changes": changed_values})
        if query_ids is None:
            query_ids, corpora = ids, actual_corpora
            datasets, budget = artifact["dataset_sha256"], artifact["budget"]
            roles = artifact.get("split_roles")
            if modern:
                input_corpora, text_corpora, compatible_corpora = actual_inputs, actual_texts, actual_compatible
        else:
            if ids != query_ids:
                raise ValueError(f"{method}: different query set")
            if actual_corpora != corpora:
                canonical_identical = False
                if not modern:
                    raise ValueError(f"{method}: different story corpus without input provenance")
            if modern and (actual_inputs != input_corpora or actual_texts != text_corpora):
                raise ValueError(f"{method}: different input corpus or source text")
            if modern and actual_compatible != compatible_corpora:
                raise ValueError(f"{method}: canonical difference extends beyond typed fact_value normalization")
            if artifact["dataset_sha256"] != datasets or artifact["budget"] != budget:
                raise ValueError(f"{method}: different dataset or context budget")
            if artifact.get("split_roles") != roles:
                raise ValueError(f"{method}: different dataset usage roles")
        if any(not row.get("error") and not row.get("actual_provider_prompt") for row in rows):
            raise ValueError(f"{method}: successful row has no actual provider prompt")
    if methods["routed"]["source_sha256"] != methods["layered"]["source_sha256"]:
        raise ValueError("Routed and layered production revisions differ")
    if not canonical_identical and not normalization_differences:
        raise ValueError("Canonical corpus changed without a recorded normalization explanation")
    return {"query_count_per_method": len(query_ids), "story_count": len(corpora),
            "actual_corpora_identical": canonical_identical, "canonical_corpora_identical": canonical_identical,
            "input_corpora_identical": True if modern else None,
            "source_text_corpora_identical": True if modern else None,
            "comparison_basis": "same_input_and_source_text_with_typed_value_fix" if modern else "legacy_strict_canonical",
            "normalization_differences": normalization_differences,
            "datasets_identical": True, "budget_identical": True, "source_unchanged": True}


def bad_case(row):
    reasons = []
    if row.get("error"):
        reasons.append("runtime_error")
    if row["gold_ids"] and not row["supported_gold_delivered"]:
        reasons.append("required_evidence_not_fully_supported")
    if not row["gold_ids"] and row["expected_status"] == "unknown" and row["no_answer_injection"]:
        reasons.append("unknown_query_received_evidence")
    if row["forbidden_delivered"]:
        reasons.append("forbidden_evidence")
    if row["route_exact"] is False:
        reasons.append("route_mismatch")
    if row["status_exact"] is False:
        reasons.append("status_mismatch")
    if not row["should_retrieve_long_term"] and row["trace"].get("retrieval_calls", 0):
        reasons.append("unnecessary_retrieval")
    if row.get("provider_lost_evidence_ids"):
        reasons.append("provider_budget_removed_evidence")
    if not reasons:
        return None
    keys = ("query_id", "story_id", "split", "query", "history", "gold_ids", "forbidden_ids",
            "delivered_ids", "verified_delivered_ids", "forbidden_delivered",
            "expected_routes", "expected_status", "provider_prompt_sha256", "error")
    case = {key: row.get(key) for key in keys}
    case.update(reasons=reasons, actual_routes=row["trace"].get("route"),
                actual_status=row["trace"].get("status"),
                source_decisions=[d for d in row["trace"].get("decisions", [])
                                  if not d.get("memory_id", "").startswith("noise_")])
    return case


def ratio(value):
    if not value or not value.get("denominator"):
        return "—"
    return f"{value['numerator']}/{value['denominator']}"


def delivery_transitions(baseline, candidate):
    """A positive mean change must not hide individual false rejections."""
    old = {row["query_id"]: row for row in baseline}
    result = {}
    for split in sorted({row["split"] for row in candidate}):
        rows = [row for row in candidate if row["split"] == split and row["gold_ids"]]
        gained, lost, both, neither = [], [], 0, 0
        for row in rows:
            before = old[row["query_id"]]["supported_gold_delivered"]
            after = row["supported_gold_delivered"]
            if after and not before:
                gained.append(row["query_id"])
            elif before and not after:
                lost.append(row["query_id"])
            elif before and after:
                both += 1
            else:
                neither += 1
        result[split] = {"answerable_denominator": len(rows), "gained_ids": gained,
                         "lost_ids": lost, "both_supported": both, "neither_supported": neither}
    return result


def render_markdown(report):
    lines = ["# 冻结五路线结果（由原始 JSON 汇总）", "",
             "实际 SQLite、CPU embedding 和最终 provider prompt；未发送生成请求。"
             "下表不表示实际模型答案、人格行为或真实用户成功率。", "",
             "| 规模 / split | 方法 | 问题数 | 交付 Recall | 严格支持交付 | 未知误注入 | 路由一致 | 多余检索 | 错误 |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for group in report["groups"]:
        for split in group["splits"]:
            for method in METHODS:
                s = group["methods"][method]["by_split"][split]
                recall = "—" if s["delivered_recall"] is None else f"{s['delivered_recall']:.4f}"
                lines.append(f"| {group['size']} / {split} | {method} | {s['queries']} | {recall} | "
                             f"{ratio(s['supported_delivery'])} | {ratio(s['no_answer_injection'])} | "
                             f"{ratio(s['route_exact'])} | {ratio(s['unnecessary_retrieval'])} | {ratio(s['errors'])} |")
    for group in report["groups"]:
        if not group["audit"]["canonical_corpora_identical"]:
            lines += ["", f"{group['size']} 条组：原输入与来源正文相同，但规范化后的结构化值不同。"
                      "旧版本会丢失嵌套 fact_value，新版本保留；全部逐字段变化已记录，结果包含这项输入规范化修复的收益，不能只归因于检索算法。"]
        if group.get("split_roles"):
            lines += ["", "数据用途：" + "；".join(f"{k}={v}" for k, v in group["split_roles"].items()) + "。"]
    lines += ["", "所有分母、阶段耗时、每类失败与原始 artifact SHA 均保存在同名 JSON。",
              "这是合成故事的经验测量；独立故事是聚类单位，同一句换措辞不是新增独立用户。", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"schema_version": 1, "status": "frozen_artifacts_audited", "groups": [],
              "not_run": ["generative answer accuracy", "model persona behavior", "real-user desktop interaction"]}
    production_hashes = None
    for directory in args.input_dir:
        manifest_path = directory / "run-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("status") != "completed" or not manifest.get("new_source_unchanged_during_campaign"):
            raise ValueError(f"{directory}: campaign did not finish with frozen production")
        if production_hashes is None:
            production_hashes = manifest["new_source_start_sha256"]
        elif production_hashes != manifest["new_source_start_sha256"]:
            raise ValueError("Production changed between quality and scaling campaigns")
        for size in manifest["sizes"]:
            paths = {m: directory / f"{m}-{size}.json" for m in METHODS}
            artifacts = {m: json.loads(path.read_text()) for m, path in paths.items()}
            audit = audit_group(list(artifacts.values()))
            group = {"directory": str(directory), "size": size, "splits": manifest["splits"],
                     "split_roles": manifest.get("split_roles", artifacts["routed"].get("split_roles", {})),
                     "story_filter": manifest.get("story_filter"), "audit": audit, "methods": {},
                     "paired_delivery_transitions": {
                         f"{candidate}_vs_{baseline}": delivery_transitions(artifacts[baseline]["rows"], artifacts[candidate]["rows"])
                         for baseline in ("lexical", "bge_rrf") for candidate in ("routed", "layered")},
                     "paired_comparisons": {k: v for k, v in manifest.get("paired_comparisons", {}).items()
                                            if k.endswith("_" + str(size))}}
            for method, artifact in artifacts.items():
                cases = [case for row in artifact["rows"] if (case := bad_case(row))]
                group["methods"][method] = {"artifact": str(paths[method]),
                    "sha256": hashlib.sha256(paths[method].read_bytes()).hexdigest(),
                    "summary": artifact["summary"], "by_split": artifact["by_split"],
                    "peak_rss_mib": artifact.get("peak_rss_mib"),
                    "model_load_ms": artifact.get("model_load_ms"),
                    "stories": artifact["stories"], "bad_cases": cases}
            report["groups"].append(group)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"status": report["status"], "groups": len(report["groups"]),
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
