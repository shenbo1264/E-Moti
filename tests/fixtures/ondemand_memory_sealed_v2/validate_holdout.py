#!/usr/bin/env python3
"""Independent interface, temporal, reference, and literal-evidence checks.

Reads only the two explicitly supplied artifacts in this script's own directory.
It never imports or executes application code and never runs retrieval evaluation.
"""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
DATA_PATH = HERE / "ondemand_memory_holdout.json"
MANIFEST_PATH = HERE / "manifest.json"


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tally(values):
    return dict(sorted(Counter(values).items()))


def literal_values(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from literal_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from literal_values(child)
    elif isinstance(value, bool):
        yield "true" if value else "false"
    else:
        yield str(value)


def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    check(data["schema_version"] == 1, "schema_version")
    check(data["split"] == "holdout", "split")
    check(data["status"] == "independently_authored_frozen", "status")
    check(data["character_id"] == "eval_companion", "character_id")
    check(data["owner_id"] == "eval_user", "owner_id")
    check(data["now"] == 1781496000, "now")
    now = data["now"]

    stories = data["stories"]
    memories = data["memories"]
    queries = data["queries"]
    story_map = {item["id"]: item for item in stories}
    memory_map = {item["id"]: item for item in memories}
    query_map = {item["id"]: item for item in queries}
    check(len(story_map) == len(stories) == 8, "story uniqueness/count")
    check(len(memory_map) == len(memories) == 48, "memory uniqueness/count")
    check(len(query_map) == len(queries) == 48, "query uniqueness/count")
    check(not (set(story_map) & set(memory_map) or set(story_map) & set(query_map) or set(memory_map) & set(query_map)), "global id uniqueness")
    check(all(4 <= count <= 6 for count in Counter(item["story_id"] for item in memories).values()), "memory count per story")
    check(Counter(item["story_id"] for item in queries) == {sid: 6 for sid in story_map}, "query count per story")

    source_ids = []
    for item in stories:
        check(all(isinstance(item[key], str) and item[key] for key in ("id", "template_family", "description")), "story fields")

    required_memory = {
        "id", "story_id", "title", "summary", "kind", "source", "source_ids",
        "valid_from", "valid_until", "occurred_at", "created_at", "updated_at",
        "scope", "deleted", "confidence", "metadata",
    }
    for item in memories:
        ident = item["id"]
        check(required_memory <= item.keys(), f"memory schema {ident}")
        check(item["story_id"] in story_map, f"memory story {ident}")
        check(all(isinstance(item[key], str) and item[key] for key in ("title", "summary", "kind")), f"memory text {ident}")
        check(item["source"] in {"synthetic_user_statement", "synthetic_execution_log"}, f"source {ident}")
        check(isinstance(item["source_ids"], list) and len(item["source_ids"]) == 1, f"source ids {ident}")
        check(isinstance(item["source_ids"][0], str) and item["source_ids"][0], f"source id type {ident}")
        source_ids.extend(item["source_ids"])
        check(item["scope"] in {"companion", "task_experience"}, f"scope {ident}")
        check(isinstance(item["deleted"], bool), f"deleted type {ident}")
        check(item["confidence"] == 1.0, f"confidence {ident}")
        for key in ("valid_from", "valid_until", "occurred_at", "created_at", "updated_at"):
            check(type(item[key]) is int, f"time type {ident}")
        check(0 < item["valid_from"] < now, f"valid_from {ident}")
        check(item["valid_until"] == 0 or item["valid_from"] < item["valid_until"] < now, f"half-open interval {ident}")
        check(0 < item["occurred_at"] <= item["created_at"] <= item["updated_at"] < now, f"event times {ident}")
        metadata = item["metadata"]
        check(isinstance(metadata, dict) and metadata.get("synthetic") is True, f"synthetic marker {ident}")
        if "fact_subject" in metadata:
            for key in ("fact_subject", "fact_predicate", "fact_slot", "fact_domain", "fact_value", "subject_aliases", "speaker"):
                check(key in metadata, f"fact schema {ident}")
            check(metadata["fact_subject"] == "user:self" or metadata["fact_subject"].startswith(("relation:", "entity:")), f"fact subject {ident}")
            check(re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", metadata["fact_predicate"]) is not None, f"predicate {ident}")
            check(metadata["fact_slot"] == metadata["fact_subject"] + ":" + metadata["fact_predicate"], f"fact slot {ident}")
            check(metadata["fact_domain"] == metadata["fact_predicate"], f"fact domain {ident}")
            check(metadata["speaker"] == "user", f"fact speaker {ident}")
            check(item["scope"] == "companion", f"fact scope {ident}")
            aliases = metadata["subject_aliases"]
            check(isinstance(aliases, list) and aliases, f"aliases {ident}")
            check(all(isinstance(alias, str) and alias and alias in item["summary"] for alias in aliases), f"alias evidence {ident}")
            check(all(value in item["summary"] for value in literal_values(metadata["fact_value"])), f"literal fact evidence {ident}")
        if item["kind"] == "共同经历":
            check(item["scope"] == "companion", f"episode scope {ident}")
            check(metadata.get("event_status") in {"completed", "planned"}, f"episode status {ident}")
            check(metadata.get("participants") == ["user:self", "character:self"], f"episode participants {ident}")
            if metadata["event_status"] == "planned":
                check(metadata.get("plan_status") == "planned", f"plan status {ident}")
        if item["scope"] == "task_experience":
            check(item["kind"] == "任务经验", f"task kind {ident}")
            check(metadata.get("outcome") in {"completed", "succeeded", "failed"}, f"task outcome {ident}")
            check(metadata.get("version") == "1.2", f"task version {ident}")
            check(all(isinstance(metadata.get(key), str) and metadata[key] for key in ("app", "preconditions", "procedure")), f"task schema {ident}")
            if metadata["outcome"] == "failed":
                check(isinstance(metadata.get("cause"), str) and metadata["cause"], f"task cause {ident}")
    check(len(source_ids) == len(set(source_ids)), "source id uniqueness")

    # Time-varying fact slots use non-overlapping half-open intervals.
    slots = {}
    for item in memories:
        if "fact_slot" in item["metadata"] and not item["deleted"]:
            key = (item["story_id"], item["metadata"]["fact_slot"])
            slots.setdefault(key, []).append(item)
    for group in slots.values():
        group.sort(key=lambda item: item["valid_from"])
        for first, second in zip(group, group[1:]):
            check(first["valid_until"] != 0 and first["valid_until"] <= second["valid_from"], "fact slot interval overlap")

    check(set(manifest["query_audit"]) == set(query_map), "audit query coverage")
    allowed_routes = {"chat", "fact", "episode", "task", "live", "bounded"}
    allowed_statuses = {"sufficient", "unknown", "not_needed", "partial", "insufficient"}
    required_query = {
        "id", "story_id", "text", "history", "expected_routes", "gold_ids",
        "forbidden_ids", "expected_status", "family", "scope", "should_retrieve_long_term",
    }
    support_span_count = 0
    for item in queries:
        ident = item["id"]
        check(required_query <= item.keys(), f"query schema {ident}")
        check(item["story_id"] in story_map, f"query story {ident}")
        check(isinstance(item["text"], str) and item["text"], f"query text {ident}")
        check(item["family"] == story_map[item["story_id"]]["template_family"], f"query family {ident}")
        check(item["scope"] == "companion", f"query scope {ident}")
        check(isinstance(item["should_retrieve_long_term"], bool), f"retrieval flag {ident}")
        check(isinstance(item["history"], list), f"history type {ident}")
        for turn in item["history"]:
            check(set(turn) == {"role", "content"} and turn["role"] in {"user", "assistant"}, f"history schema {ident}")
            check(isinstance(turn["content"], str) and turn["content"], f"history content {ident}")
        check(isinstance(item["expected_routes"], list) and item["expected_routes"], f"routes type {ident}")
        check(set(item["expected_routes"]) <= allowed_routes, f"routes enum {ident}")
        check(len(item["expected_routes"]) == len(set(item["expected_routes"])), f"routes uniqueness {ident}")
        check(item["expected_status"] in allowed_statuses, f"status enum {ident}")
        for key in ("gold_ids", "forbidden_ids"):
            check(isinstance(item[key], list), f"reference list {ident}")
            check(len(item[key]) == len(set(item[key])), f"reference uniqueness {ident}")
            for ref in item[key]:
                check(ref in memory_map, f"reference existence {ident}")
                check(memory_map[ref]["story_id"] == item["story_id"], f"cross-story reference {ident}")
        check(not (set(item["gold_ids"]) & set(item["forbidden_ids"])), f"gold/forbidden overlap {ident}")
        if item["expected_status"] == "not_needed":
            check(not item["should_retrieve_long_term"] and not item["gold_ids"] and not item["forbidden_ids"], f"chat retrieval {ident}")
            check(item["expected_routes"] == ["chat"], f"chat route {ident}")
        elif item["expected_status"] == "unknown":
            check(item["should_retrieve_long_term"] and not item["gold_ids"] and item["forbidden_ids"], f"unknown evidence {ident}")
        elif item["expected_status"] in {"sufficient", "partial"}:
            check(item["should_retrieve_long_term"] and item["gold_ids"], f"answerable evidence {ident}")

        case = manifest["query_audit"][ident]
        check(set(case["support_spans"]) == set(item["gold_ids"]), f"support coverage {ident}")
        as_of = case["historical_as_of"] or now
        for ref in item["gold_ids"]:
            source = memory_map[ref]
            check(not source["deleted"], f"deleted gold {ident}")
            check(source["valid_from"] <= as_of and (source["valid_until"] == 0 or as_of < source["valid_until"]), f"gold interval {ident}")
            check(source["metadata"].get("event_status") != "planned", f"planned event gold {ident}")
            for span in case["support_spans"][ref]:
                check(isinstance(span, str) and span and span in source["summary"], f"literal support span {ident}")
                support_span_count += 1

    counts = manifest["counts"]
    check(counts["stories"] == len(stories) and counts["memories"] == len(memories) and counts["queries"] == len(queries), "manifest totals")
    check(counts["memories_per_story"] == tally(item["story_id"] for item in memories), "manifest memory strata")
    check(counts["queries_per_story"] == tally(item["story_id"] for item in queries), "manifest query strata")
    check(counts["status_denominators"] == tally(item["expected_status"] for item in queries), "manifest status strata")
    check(counts["primary_stratum_denominators"] == tally(item["primary_stratum"] for item in manifest["query_audit"].values()), "manifest primary strata")
    check(sum(counts["primary_stratum_denominators"].values()) == len(queries), "primary strata total")
    check(counts["overlapping_tag_denominators"] == tally(tag for item in manifest["query_audit"].values() for tag in item["tags"]), "manifest tags")
    check(counts["route_membership_denominators"] == tally(route for item in queries for route in item["expected_routes"]), "manifest routes")
    check(counts["retrieval_required"] == sum(item["should_retrieve_long_term"] for item in queries), "manifest retrieval count")
    check(counts["no_retrieval_required"] == sum(not item["should_retrieve_long_term"] for item in queries), "manifest non-retrieval count")
    check(counts["with_gold_evidence"] == sum(bool(item["gold_ids"]) for item in queries), "manifest gold count")
    check(counts["with_forbidden_sources"] == sum(bool(item["forbidden_ids"]) for item in queries), "manifest forbidden count")
    check(counts["multiple_gold_sources"] == sum(len(item["gold_ids"]) > 1 for item in queries), "manifest multi-source count")
    check(counts["with_history"] == sum(bool(item["history"]) for item in queries), "manifest history count")
    check(counts["memory_scopes"] == tally(item["scope"] for item in memories), "manifest scope count")
    check(counts["memory_kinds"] == tally(item["kind"] for item in memories), "manifest kind count")
    check(counts["memory_sources"] == tally(item["source"] for item in memories), "manifest source count")
    check(counts["deleted_memories"] == sum(item["deleted"] for item in memories), "manifest deleted count")
    check(counts["expired_memories"] == sum(0 < item["valid_until"] <= now for item in memories), "manifest expired count")
    check(counts["completed_shared_events"] == sum(item["metadata"].get("event_status") == "completed" for item in memories), "manifest completed count")
    check(counts["planned_shared_events"] == sum(item["metadata"].get("event_status") == "planned" for item in memories), "manifest planned count")
    check(counts["task_outcomes"] == tally(item["metadata"]["outcome"] for item in memories if item["scope"] == "task_experience"), "manifest task outcomes")
    check(counts["distinct_fact_predicates"] == len({item["metadata"]["fact_predicate"] for item in memories if "fact_predicate" in item["metadata"]}), "manifest predicate count")
    check(counts["distinct_fact_subjects"] == len({item["metadata"]["fact_subject"] for item in memories if "fact_subject" in item["metadata"]}), "manifest subject count")
    check(manifest["data_sha256"] == digest(DATA_PATH), "data hash")
    for record in manifest["files"].values():
        path = Path(record["path"])
        check(path.parent == HERE, "artifact-only validation boundary")
        check(record["sha256"] == digest(path), "artifact hash")

    result = {
        "valid": True,
        "checks": [
            "json_schema_and_enums", "source_id_uniqueness", "timestamps_before_now",
            "half_open_nonoverlapping_fact_intervals", "same_story_reference_integrity",
            "gold_forbidden_disjointness", "literal_fact_values_in_source_summaries",
            "literal_gold_support_spans", "gold_temporal_validity", "no_deleted_or_planned_gold",
            "manifest_counts", "artifact_sha256_integrity",
        ],
        "counts": counts,
        "support_span_checks": support_span_count,
        "data_path": str(DATA_PATH),
        "data_sha256": digest(DATA_PATH),
        "manifest_path": str(MANIFEST_PATH),
        "manifest_sha256": digest(MANIFEST_PATH),
        "validator_path": str(Path(__file__).resolve()),
        "validator_sha256": digest(Path(__file__).resolve()),
        "retrieval_evaluation_run": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"valid": False, "error_type": type(exc).__name__, "error": str(exc)}, ensure_ascii=False))
        sys.exit(1)
