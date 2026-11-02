import argparse
from collections import Counter
import json
from pathlib import Path


def diagnose(row):
    gold = set(row["gold_ids"])
    delivered = set(row.get("verified_delivered_ids", ()))
    decisions = row.get("trace", {}).get("decisions", ())
    causes = []
    if set(row.get("expected_routes", ())) != set(row.get("trace", {}).get("route", ())):
        causes.append("intent_route")
    judged = {decision["memory_id"] for decision in decisions}
    if gold - judged - delivered:
        causes.append("candidate_not_recalled")
    gold_decisions = [d for d in decisions if d["memory_id"] in gold and not d["accepted"]]
    for decision in gold_decisions:
        reason = decision["reason"]
        if reason == "subject_mismatch_or_unproved":
            causes.append("subject_entity_relation_understanding")
        elif reason in {"field_mismatch_or_unproved", "bounded_literal_attribute_verification", "topic_not_supported"}:
            causes.append("recalled_but_literal_rejected")
        elif reason in {"requested_detail_not_supported", "no_resolved_topic", "missing_literal_fact_value"}:
            causes.append("evidence_insufficient_or_unparsed")
        else:
            causes.append("time_scope_source_or_revocation")
    if row.get("provider_lost_evidence_ids") or row.get("trace", {}).get("status") == "insufficient" and any(
            s.get("reason") == "budget_limited" for s in row.get("trace", {}).get("intent_status", ())):
        causes.append("final_prompt_budget")
    if gold - delivered and not causes:
        causes.append("needs_manual_source_review")
    return {"query_id": row["query_id"], "query": row["query"], "history": row.get("history", []),
        "gold_ids": sorted(gold), "delivered_ids": sorted(delivered),
        "strict_pass": row.get("supported_gold_delivered", False),
        "categories": sorted(set(causes)), "gold_rejections": gold_decisions,
        "trace": row.get("trace"), "forbidden_delivered": row.get("forbidden_delivered", [])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    rows = [diagnose(row) for row in data["rows"]]
    failures = [row for row in rows if row["gold_ids"] and not row["strict_pass"]]
    report = {"source": str(args.input), "queries": len(rows),
        "answerable": sum(bool(row["gold_ids"]) for row in rows),
        "strict_failures": len(failures),
        "category_counts_overlapping": dict(Counter(c for row in failures for c in row["categories"])),
        "interpretation": "自动分类定位失证阶段；字段未解析与真实不支持须逐题复核，不把规则拒绝直接当成事实不存在。",
        "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
