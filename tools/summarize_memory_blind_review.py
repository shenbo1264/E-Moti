import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics


METHODS = ("none", "lexical", "bge_rrf", "routed", "layered")
GRADES = ("pass", "partial", "fail", "not_run")
DIMENSIONS = ("accuracy", "persona", "natural_unknown")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)


def source(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def grades(rows, dimension):
    counts = Counter(row[dimension] for row in rows)
    allowed = (*GRADES, "not_applicable") if dimension == "natural_unknown" else GRADES
    return {"denominator": len(rows), **{grade: counts[grade] for grade in allowed}}


def unsupported(rows):
    return {"denominator": len(rows),
            "empty_list_or_text": sum(not row["unsupported_claims"] for row in rows),
            "nonempty_claims_or_notes": sum(bool(row["unsupported_claims"]) for row in rows),
            "interpretation": "Raw reviewer lists/text are preserved. Nonempty notes are not automatically classified as hallucinations."}


def distribution(values):
    values = sorted(values)
    if not values:
        return {"denominator": 0, "p50": None, "p95": None, "total": None}
    position = (len(values) - 1) * .95
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return {"denominator": len(values), "p50": statistics.median(values),
            "p95": values[low] + (values[high] - values[low]) * (position - low), "total": sum(values)}


def provider_measurements(rows):
    usages = [row["usage"] for row in rows if isinstance(row.get("usage"), dict)]
    def tokens(primary, alternate):
        values = [usage.get(primary, usage.get(alternate)) for usage in usages]
        values = [value for value in values if type(value) is int]
        return {"coverage": len(values), "total": sum(values) if values else None}
    return {"requests": len(rows), "usage_coverage": len(usages),
            "input_tokens": tokens("input_tokens", "prompt_tokens"),
            "output_tokens": tokens("output_tokens", "completion_tokens"),
            "provider_models": dict(Counter(row.get("provider_model", "not_reported") for row in rows)),
            "transport_latency_ms": distribution([row["transport_latency_ms"] for row in rows if isinstance(row.get("transport_latency_ms"), (float, int))]),
            "client_latency_ms": distribution([row["client_latency_ms"] for row in rows if isinstance(row.get("client_latency_ms"), (float, int))])}


def summarize(generation, mapping, reviews):
    generated = generation["rows"]
    by_id = {}
    pairs = set()
    for row in generated:
        review_id = row["review_id"]
        pair = (row["method"], row["query_id"])
        if review_id in by_id or pair in pairs:
            raise ValueError("duplicate generation review_id or method/query")
        if row["method"] not in METHODS:
            raise ValueError("unknown generation method")
        by_id[review_id] = row
        pairs.add(pair)
    if len(generated) != 320 or any(sum(row["method"] == method for row in generated) != 64 for method in METHODS):
        raise ValueError("expected 320 generation rows and 64 per method")
    query_sets = [{row["query_id"] for row in generated if row["method"] == method} for method in METHODS]
    if any(group != query_sets[0] for group in query_sets[1:]):
        raise ValueError("methods do not contain identical question sets")
    mapped_ids = set()
    for blind_id, target in mapping.items():
        if target["review_id"] in mapped_ids:
            raise ValueError("multiple blind IDs map to the same generation")
        original = by_id.get(target["review_id"])
        if original is None or any(target[key] != original[key] for key in ("method", "query_id")):
            raise ValueError(f"mapping disagrees with generation: {blind_id}")
        mapped_ids.add(target["review_id"])
    if mapped_ids != set(by_id):
        raise ValueError("mapping does not cover every generation")
    seen, joined, assignments = set(), [], Counter()
    for reviewer_file, document in reviews:
        if not isinstance(document, dict) or not isinstance(document.get("rows"), list):
            raise ValueError("review must contain top-level rows")
        for review in document["rows"]:
            blind_id = review["blind_id"]
            if blind_id not in mapping:
                raise ValueError(f"unknown blind_id: {blind_id}")
            if blind_id in seen:
                raise ValueError(f"duplicate blind_id: {blind_id}")
            for dimension in DIMENSIONS:
                allowed = (*GRADES, "not_applicable") if dimension == "natural_unknown" else GRADES
                if review.get(dimension) not in allowed:
                    raise ValueError(f"invalid or missing {dimension}: {blind_id}")
            if not isinstance(review.get("unsupported_claims"), (list, str)):
                raise ValueError(f"missing or invalid unsupported_claims: {blind_id}")
            if not isinstance(review.get("reason"), str) or not review["reason"].strip():
                raise ValueError(f"missing reason: {blind_id}")
            seen.add(blind_id)
            assignments[reviewer_file] += 1
            target = mapping[blind_id]
            original = by_id[target["review_id"]]
            joined.append({**review, **target, "review_source": reviewer_file,
                "schema_status": original.get("schema_status"), "generation_status": original["status"],
                "answerable": bool(original["gold_ids"]),
                "unknown": not original["gold_ids"] and original["expected_status"] == "unknown"})
    if seen != set(mapping):
        raise ValueError(f"missing reviews: {len(set(mapping) - seen)}")
    result = {"schema_version": 1, "status": "ai_review_aggregated", "reviewed_outputs": len(joined),
        "independent_questions": len(query_sets[0]), "review_assignments": dict(assignments),
        "review_design": "Each output received one independent AI review with method labels hidden. Reviewers cover different rows, not duplicate ratings.",
        "human_persona_acceptance": "not_run", "inter_rater_agreement": "not_run",
        "limitations": ["AI judgments have not been calibrated by human reviewers.",
                        "Method repetitions and story turns are not independent population samples.",
                        "Provider costs and latency are measurements separate from answer quality; quality grades do not change recorded usage."],
        "methods": {}, "provider_measurements": provider_measurements(generated), "rows": joined}
    for method in METHODS:
        rows = [row for row in joined if row["method"] == method]
        answerable = [row for row in rows if row["answerable"]]
        unknown = [row for row in rows if row["unknown"]]
        if len(answerable) != 38 or len(unknown) != 14:
            raise ValueError("expected 38 answerable and 14 unknown queries per method")
        result["methods"][method] = {"denominator": 64,
            **{dimension: grades(rows, dimension) for dimension in DIMENSIONS},
            "unsupported_claims": unsupported(rows),
            "answerable_accuracy": grades(answerable, "accuracy"),
            "unknown_accuracy": grades(unknown, "accuracy"),
            "unknown_natural_unknown": grades(unknown, "natural_unknown"),
            "deliverable_accuracy_pass": {"numerator": sum(row["accuracy"] == "pass" and row["schema_status"] == "valid" and row["generation_status"] == "completed" for row in rows), "denominator": 64},
            "answerable_deliverable_accuracy_pass": {"numerator": sum(row["accuracy"] == "pass" and row["schema_status"] == "valid" and row["generation_status"] == "completed" for row in answerable), "denominator": 38},
            "provider_measurements": provider_measurements([row for row in generated if row["method"] == method])}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generation", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; preserve the earlier review summary")
    result = summarize(load(args.generation), load(args.mapping), [(str(path), load(path)) for path in args.reviews])
    result["sources"] = {"generation": source(args.generation), "mapping": source(args.mapping),
                         "reviews": [source(path) for path in args.reviews]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "reviewed_outputs": result["reviewed_outputs"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
