#!/usr/bin/env python3
"""Five-path on-demand memory benchmark using real temporary SQLite stores.

Every method/size runs in its own process. Each story is an independent archive
containing the same deterministic distractor pool at the requested size. The
legacy methods import a separately frozen source tree and scan its full
snapshot, never the new system's shortlisted candidates. BGE runs are real CPU
inference; unavailable generation/device experiments remain ``not_run``.

Example:
  python tools/eval_ondemand_memory.py --baseline-root /path/to/frozen/baseline \
    --model-cache /path/to/bge/cache --local-files-only --sizes 300 3000 10000 \
    --splits development validation --output-dir artifacts/ondemand

Freeze production before adding ``holdout`` to --splits. Do not adjust the
implementation using holdout errors while continuing to call it sealed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, is_dataclass, replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import random
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any


METHODS = ("none", "lexical", "bge_rrf", "routed", "layered")
SPLITS = ("development", "validation", "holdout")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.memory_profile_metrics import peak_rss_bytes
BASELINE_COMMIT = "299a0aa568c90525e6a6a90ce01dbbf80bfaefcb"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_atomic(path: Path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def timed(call):
    start = time.perf_counter_ns()
    value = call()
    return value, (time.perf_counter_ns() - start) / 1_000_000


def distribution(values):
    values = sorted(float(v) for v in values if v is not None)
    if not values:
        return {"n": 0}
    def quantile(p):
        position = p * (len(values) - 1)
        lo, hi = math.floor(position), math.ceil(position)
        return values[lo] + (values[hi] - values[lo]) * (position - lo)
    return {"n": len(values), "p50": statistics.median(values), "p95": quantile(.95),
            "p99": quantile(.99), "min": values[0], "max": values[-1]}


def rate(count, denominator):
    return {"numerator": count, "denominator": denominator,
            "rate": count / denominator if denominator else None}


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], text=True,
                            capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def source_hashes(root):
    return {str(p.relative_to(root)): digest(p)
            for p in sorted((root / "src/guanghe_companion").glob("*.py"))}


def validate_baseline(root, expected_commit):
    actual = git(root, "rev-parse", "HEAD")
    if actual != expected_commit:
        raise ValueError("Legacy source revision differs from --baseline-commit")
    if git(root, "status", "--porcelain", "--", "src/guanghe_companion"):
        raise ValueError("Frozen baseline production sources must be clean")
    return actual


def expression_history(history, character_name):
    return [{"role": row.get("role", "user"),
             "speaker": row.get("speaker") or (character_name if row.get("role") == "assistant" else "玩家"),
             "text": row.get("text", row.get("content", ""))} for row in history]


def story_clock(data, story):
    basis = story.get("time_basis", data.get("time_basis", "unix"))
    if basis not in {"logical", "unix"}:
        raise ValueError("time_basis must be logical or unix")
    return story.get("now", data.get("now", 0)), basis


def rss_mib():
    try:
        return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2**20
    except (OSError, AttributeError, ValueError):
        return None


def peak_rss_mib():
    return peak_rss_bytes() / 2**20


def environment():
    deps = {}
    for name in ("fastembed", "numpy", "onnxruntime", "tokenizers", "huggingface-hub"):
        try:
            deps[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            deps[name] = None
    cpu = platform.processor()
    try:
        cpu = next(x.split(":", 1)[1].strip() for x in Path("/proc/cpuinfo").read_text().splitlines()
                   if x.startswith("model name"))
    except (OSError, StopIteration):
        pass
    return {"python": platform.python_version(), "platform": platform.platform(),
            "sqlite": sqlite3.sqlite_version, "cpu": cpu, "logical_cpu_count": os.cpu_count(),
            "dependencies": deps}


def load_datasets(directory, splits):
    result, seen_stories, seen_memories, seen_queries, seen_families = [], set(), set(), set(), {}
    manifest_path = directory / "ondemand_memory_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": {}}
    for split in splits:
        path = directory / f"ondemand_memory_{split}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["split"] != split:
            raise ValueError(f"Incorrect split in {path.name}")
        frozen = manifest.get("files", {}).get(path.name)
        if frozen and frozen != digest(path):
            raise ValueError(f"Dataset changed after freeze: {path.name}; record a new dataset version")
        local_stories = {s["id"] for s in data["stories"]}
        local_memories = {m["id"] for m in data["memories"]}
        memory_story = {m["id"]: m["story_id"] for m in data["memories"]}
        if len(local_stories) != len(data["stories"]) or local_stories & seen_stories:
            raise ValueError("Story IDs must be unique and must not cross splits")
        if len(local_memories) != len(data["memories"]) or local_memories & seen_memories:
            raise ValueError("Memory IDs must be unique")
        for story in data["stories"]:
            family = story["template_family"]
            if family in seen_families and seen_families[family] != split:
                raise ValueError("A template family crosses dataset splits")
            seen_families[family] = split
        for q in data["queries"]:
            if q["id"] in seen_queries or q["story_id"] not in local_stories:
                raise ValueError("Duplicate query or missing story")
            story = next(s for s in data["stories"] if s["id"] == q["story_id"])
            clock_now = story.get("now", data.get("now", 0))
            if "now" in q and q["now"] != clock_now:
                raise ValueError(f"Inconsistent query clock for {q['id']}: query.now={q['now']} "
                                 f"but story/archive now={clock_now}; declare the intended archive clock")
            if set(q["gold_ids"]) & set(q["forbidden_ids"]):
                raise ValueError("Gold and forbidden evidence overlap")
            for mid in q["gold_ids"] + q["forbidden_ids"]:
                if mid not in local_memories or memory_story[mid] != q["story_id"]:
                    raise ValueError("A query refers to evidence outside its story")
            seen_queries.add(q["id"])
        seen_stories.update(local_stories)
        seen_memories.update(local_memories)
        result.append({**data, "dataset_sha256": digest(path), "dataset_path": str(path),
                       "split_usage": manifest.get("split_usage", {}).get(split, "unspecified_no_blind_claim")})
    return result


def make_input_rows(data, story_id, size):
    """Freeze authored input plus deterministic noise before any Entry sanitizer."""
    raw_rows = [dict(m) for m in data["memories"] if m["story_id"] == story_id]
    story = next((s for s in data.get("stories", ()) if s["id"] == story_id), {})
    now, time_basis = story_clock(data, story)
    if size < len(raw_rows):
        raise ValueError("Corpus size is smaller than its source story")
    # Stable IDs/content let each method reuse its own BGE passage vectors
    # between independent stories. No vectors or shortlisted IDs cross methods.
    topics = ("散步", "整理书架", "画速写", "烤饼干", "练习口琴", "晾衣服", "拼图", "收纳", "看纪录片", "听广播")
    places = ("北窗", "客厅", "阳台", "小书桌", "公园", "厨房", "湖边", "阅览室", "旧街", "工作室", "院子", "门廊")
    objects = ("树叶", "纸盒", "玻璃杯", "水彩笔", "小石头", "帆布袋", "纸灯", "木架", "地图", "布偶", "明信片", "纸船", "铅笔", "围巾", "折扇")
    moods = ("平静", "轻松", "专注", "好奇", "慢悠悠", "惬意", "有精神", "安静")
    for n in range(size - len(raw_rows)):
        timestamp = min(n, now) if time_basis == "logical" else 1_600_000_000 + n
        topic, place = topics[n % len(topics)], places[(n // len(topics)) % len(places)]
        obj, mood = objects[(n // 120) % len(objects)], moods[(n // 1800) % len(moods)]
        summary = (f"日常记录第{n}项：在{place}{topic}，注意到{obj}的形状和颜色。"
                   f"这是一段{mood}的普通片段，原始记录未提供人物姓名、联系方式、职业或执行任务结果。")
        raw_rows.append(dict(id=f"noise_{n:05d}", story_id=story_id, character_id=data["character_id"], owner_id=data["owner_id"],
                      kind="日常片段", title=f"{place}的{topic}片段{n}", summary=summary,
                      source="synthetic_distractor", source_ids=[f"noise:{n}"],
                      occurred_at=timestamp, created_at=timestamp,
                      updated_at=timestamp, valid_from=0, importance=.3, scope="companion"))
    return raw_rows


def make_entries(data, story_id, size, Entry, *, input_rows=None):
    raw_rows = make_input_rows(data, story_id, size) if input_rows is None else input_rows
    entries = []
    for raw in raw_rows:
        fields = {k: v for k, v in raw.items() if k not in {"id", "story_id", "state"}}
        fields.update(memory_id=raw["id"])
        fields.setdefault("owner_id", data["owner_id"])
        fields.setdefault("character_id", data["character_id"])
        entry = Entry(**fields).normalized()
        entry.validate()
        entries.append(entry)
    random.Random(42601).shuffle(entries)
    return tuple(entries)


def _json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def corpus_provenance(input_rows, entries):
    """Distinguish identical inputs from an intentional typed-value bug fix.

    No scoring or gold changes occur here. All non-metadata canonical fields
    must remain identical. A narrower checksum additionally prevents unrelated
    metadata changes from being hidden by the source-text checksum.
    """
    canonical = [m.to_dict() for m in sorted(entries, key=lambda m: m.memory_id)]
    by_id = {m["memory_id"]: m for m in canonical}
    changes = []
    for raw in sorted(input_rows, key=lambda m: m["id"]):
        actual = by_id[raw["id"]]
        for key, before in raw.items():
            if key in {"id", "story_id", "state"}:
                continue
            if key == "metadata":
                after_metadata = actual.get("metadata", {})
                for name in sorted(set(before) | set(after_metadata)):
                    if ((name in before) != (name in after_metadata)
                            or _json_hash(before.get(name)) != _json_hash(after_metadata.get(name))):
                        changes.append({"memory_id": raw["id"], "field": "metadata." + name,
                                        "before_present": name in before, "after_present": name in after_metadata,
                                        "before": before.get(name), "after": after_metadata.get(name)})
            elif key not in actual or _json_hash(before) != _json_hash(actual[key]):
                changes.append({"memory_id": raw["id"], "field": key,
                                "before_present": True, "after_present": key in actual,
                                "before": before, "after": actual.get(key)})
    source_text = [{k: v for k, v in row.items() if k != "metadata"} for row in canonical]
    without_value = [{**row, "metadata": {k: v for k, v in row.get("metadata", {}).items() if k != "fact_value"}}
                     for row in canonical]
    return {"corpus_sha256": _json_hash(canonical),
            "input_corpus_sha256": _json_hash(sorted(input_rows, key=lambda m: m["id"])),
            "source_text_corpus_sha256": _json_hash(source_text),
            "canonical_without_fact_value_sha256": _json_hash(without_value),
            "normalization_changes": changes}


def evidence_representations(prompt):
    """Count content cards/claims, never IDs merely mentioned in route traces."""
    memory = prompt.get("emotional_memory", {})
    representations = []
    for row in memory.get("shared_memories", []):
        if isinstance(row, dict) and row.get("memory_id") and row.get("summary"):
            representations.append({"ids": [row["memory_id"]], "text": row["summary"], "level": "raw"})
    overview = memory.get("memory_overview", {})
    for claim in overview.get("claims", []) if isinstance(overview, dict) else []:
        if not isinstance(claim, dict):
            continue
        ids = claim.get("source_memory_ids", claim.get("memory_ids", []))
        if isinstance(ids, str):
            ids = [ids]
        if claim.get("memory_id"):
            ids = [*ids, claim["memory_id"]]
        if claim.get("source_memory_id"):
            ids = [*ids, claim["source_memory_id"]]
        text = claim.get("text", claim.get("summary", claim.get("claim", "")))
        if text:
            representations.append({"ids": list(dict.fromkeys(ids)), "text": text, "level": "overview",
                                    "source_fingerprint": claim.get("source_fingerprint")})
    return representations


def provider_evidence_payload(prompt_text):
    """Read evidence that survived the real provider builder's final budget.

    Production renders these JSON values on single labelled lines. We parse
    the rendered string; taking the pre-fit request's IDs would overcount.
    """
    result = {}
    for line in prompt_text.splitlines():
        for key in ("persona", "emotional_memory"):
            prefix = key + ": "
            if line.startswith(prefix):
                value = json.loads(line[len(prefix):])
                if not isinstance(value, dict):
                    raise ValueError(f"Provider {key} section is not an object")
                result[key] = value
    return result


def score_query(query, prompt, selected_ids, trace, source_rows, *, error=None):
    representations = evidence_representations(prompt)
    delivered = list(dict.fromkeys(mid for row in representations for mid in row["ids"]))
    resolution = [r for r in prompt.get("emotional_memory", {}).get("resolution_evidence", [])
                  if isinstance(r, dict) and r.get("memory_id") and (r.get("summary") or r.get("bindings"))]
    all_context_ids = set(delivered) | {r["memory_id"] for r in resolution}
    resolution_sources = []
    for item in resolution:
        source = source_rows.get(item["memory_id"])
        meta = source.get("metadata", {}) if source else {}
        aliases = set(meta.get("subject_aliases", [])) | set(meta.get("entity_aliases", [])) | set(meta.get("fact_aliases", []))
        if meta.get("fact_predicate") in {"name", "姓名", "称呼"} and isinstance(meta.get("fact_value"), str):
            aliases.add(meta["fact_value"])
        source_subjects = {v for v in (meta.get("fact_subject"), meta.get("entity_id")) if v}
        binding_supported = (all(b.get("alias") in aliases and set(b.get("subjects", [])) <= source_subjects
                                 and bool(b.get("subjects")) for b in item["bindings"])
                             if item.get("bindings") else None)
        resolution_sources.append({"memory_id": item["memory_id"], "source_present": source is not None,
            "literal_binding_supported": binding_supported,
            "source_fingerprint_matches": (item.get("source_fingerprint") == source["_expected_fingerprint"]
                if source is not None and "_expected_fingerprint" in source else None)})
    gold, selected, delivered_set = set(query["gold_ids"]), set(selected_ids), set(delivered)
    forbidden = set(query["forbidden_ids"])
    # An ID paired with the wrong body must not pass the stricter supported
    # delivery metric. The shipped L1 contract is extractive; full gold source
    # text is available here, without a model judge or inferred facts.
    verified_delivered = {mid for rep in representations for mid in rep["ids"]
                          if mid in source_rows and rep["text"] == source_rows[mid]["summary"]
                          and (rep["level"] != "overview" or
                               "_expected_fingerprint" not in source_rows[mid] or
                               rep.get("source_fingerprint") == source_rows[mid]["_expected_fingerprint"])}
    routes = trace.get("route", [])
    if isinstance(routes, str):
        routes = [routes]
    status = trace.get("status", "unreported")
    rank = next((index + 1 for index, mid in enumerate(selected_ids) if mid in gold), None)
    graded = sum(1 / math.log2(index + 2) for index, mid in enumerate(selected_ids[:4]) if mid in gold)
    ideal = sum(1 / math.log2(index + 2) for index in range(min(4, len(gold))))
    provenance = []
    for rep in representations:
        if rep["level"] != "overview":
            continue
        rows = [source_rows.get(mid) for mid in rep["ids"]]
        present = bool(rows) and all(rows)
        # This tests the shipped extractive contract, not arbitrary semantic
        # entailment by an uncalibrated judge model.
        entailed = present and any(rep["text"] in (row["summary"], row["title"]) or
                                   rep["text"] in row["summary"] for row in rows)
        provenance.append({"source_ids": rep["ids"], "source_present": present,
                           "extractively_entailed": bool(entailed),
                           "source_fingerprint_matches": (bool(present and len(rows) == 1
                               and rep.get("source_fingerprint") == rows[0]["_expected_fingerprint"])
                               if present and any("_expected_fingerprint" in row for row in rows) else None)})
    structured_wrong = [mid for mid in delivered if mid not in gold and mid in source_rows
                        and source_rows[mid].get("metadata", {}).get("fact_predicate")
                        and "fact" in query["expected_routes"]]
    retired = [mid for mid in all_context_ids if source_rows.get(mid, {}).get("state") == "forgotten"]
    historical_wrong = [mid for mid in delivered if mid not in gold
                        and source_rows.get(mid, {}).get("state") == "historical"]
    planned_wrong = [mid for mid in delivered if mid not in gold
                     and source_rows.get(mid, {}).get("state") == "planned"]
    source_occurrences = Counter(mid for row in representations for mid in row["ids"])
    return {"query_id": query["id"], "story_id": query["story_id"], "family": query["family"],
            "query": query["text"], "history": query.get("history", []),
            "expected_routes": query["expected_routes"], "expected_status": query["expected_status"],
            "should_retrieve_long_term": query["should_retrieve_long_term"],
            "gold_ids": query["gold_ids"], "forbidden_ids": query["forbidden_ids"],
            "retrieved_ids": list(selected_ids), "delivered_ids": delivered,
            "verified_delivered_ids": sorted(verified_delivered),
            "all_context_evidence_ids": sorted(all_context_ids), "resolution_sources": resolution_sources,
            "recall_at_4": len(gold & selected) / len(gold) if gold else None,
            "delivered_recall": len(gold & delivered_set) / len(gold) if gold else None,
            "precision_returned": len(gold & selected) / len(selected) if selected else (0.0 if gold else None),
            "ndcg_at_4_binary": graded / ideal if ideal else None,
            "mrr": 1 / rank if rank else (0.0 if gold else None),
            "all_gold_delivered": gold <= delivered_set if gold else None,
            "supported_gold_delivered": (gold <= verified_delivered and not forbidden & all_context_ids) if gold else None,
            "forbidden_delivered": sorted(forbidden & all_context_ids),
            "no_answer_injection": bool(all_context_ids) if not gold else None,
            "structured_wrong_ids": structured_wrong, "forgotten_ids": retired,
            "historical_wrong_ids": historical_wrong, "planned_wrong_ids": planned_wrong,
            "route_exact": set(routes) == set(query["expected_routes"]) if trace.get("router_evaluated") else None,
            "status_exact": status == query["expected_status"] if trace.get("router_evaluated") else None,
            "trace": trace, "overview_claims": provenance,
            "duplicate_evidence_ids": sorted(mid for mid, count in source_occurrences.items() if count > 1),
            "prompt_chars": len(json.dumps(prompt, ensure_ascii=False, separators=(",", ":"))),
            "memory_context_chars": len(json.dumps(prompt.get("emotional_memory", {}), ensure_ascii=False, separators=(",", ":"))),
            "prompt_tokens": None, "provider_generation": "not_run",
            "actual_expression_request": prompt, "error": error}


def retrieval_performed(row):
    return bool(row["trace"].get("retrieval_calls", 0) or row.get("prepare_rows_loaded", 0)
                or row.get("prepare_retrieval_calls", 0)
                or row.get("embedding_query_calls", 0) or row.get("evidence_judgment", {}).get("requests"))


def summarize_evidence(rows):
    judgments = [r["evidence_judgment"] for r in rows if "evidence_judgment" in r]
    requests = [request for judgment in judgments for request in judgment.get("requests", [])]
    usages = [request.get("provider_response", {}).get("usage") for request in requests
              if isinstance(request.get("provider_response"), dict)]
    usages = [usage for usage in usages if isinstance(usage, dict)]
    def tokens(key, alternative):
        values = [usage.get(key, usage.get(alternative)) for usage in usages]
        values = [value for value in values if type(value) is int]
        return sum(values) if values else None
    reasoning = [usage.get("completion_tokens_details", {}).get("reasoning_tokens") for usage in usages]
    reasoning = [value for value in reasoning if type(value) is int]
    return {"status": "run" if requests else "not_run", "actual_requests": len(requests),
            "judgment_status_counts": dict(Counter(j.get("status", "not_run") for j in judgments)),
            "completed_judgments": sum(j.get("status") == "completed" and bool(j.get("requests")) for j in judgments),
            "failed_judgments": sum(bool(j.get("requests")) and j.get("status") != "completed" for j in judgments),
            "usage_coverage": rate(len(usages), len(requests)),
            "input_tokens": tokens("input_tokens", "prompt_tokens"),
            "output_tokens": tokens("output_tokens", "completion_tokens"),
            "reasoning_tokens": sum(reasoning) if reasoning else None}


def summarize(rows):
    answerable = [r for r in rows if r["gold_ids"]]
    absent = [r for r in rows if not r["gold_ids"] and r["expected_status"] == "unknown"]
    no_retrieval = [r for r in rows if not r["should_retrieve_long_term"]]
    route_rows = [r for r in rows if r["route_exact"] is not None]
    claims = [c for r in rows for c in r["overview_claims"]]
    resolution_sources = [c for r in rows for c in r.get("resolution_sources", [])]
    # Legacy methods have no evidence-status contract. Their lack of a status
    # must not be misreported as failed generated unknown answers.
    unknown = [r for r in route_rows if r["expected_status"] == "unknown"]
    token_rows = [r for r in rows if r.get("bge_tokenizer_prompt_tokens") is not None]
    persona_rows = [r for r in rows if "persona_config_unchanged" in r]
    provider_rows = [r for r in rows if "provider_lost_evidence_ids" in r]
    multi_evidence = [r for r in answerable if len(r["gold_ids"]) > 1]
    followups = [r for r in answerable if r.get("history")]
    mixed = [r for r in rows if len(set(r["expected_routes"])) > 1]
    unknown_episodes = [r for r in absent if "episode" in r["expected_routes"]]
    def mean(key, group=answerable):
        values = [r[key] for r in group if r[key] is not None]
        return statistics.mean(values) if values else None
    stages = sorted({key for r in rows for key in r.get("timings_ms", {})})
    return {"queries": len(rows), "stories": len({r["story_id"] for r in rows}),
            "answerable_queries": len(answerable), "no_answer_queries": len(absent),
            "macro_recall_at_4": mean("recall_at_4"), "delivered_recall": mean("delivered_recall"),
            "precision_returned": mean("precision_returned"), "ndcg_at_4_binary": mean("ndcg_at_4_binary"),
            "mrr": mean("mrr"), "all_gold_delivered": rate(sum(r["all_gold_delivered"] for r in answerable), len(answerable)),
            "supported_delivery": rate(sum(r["supported_gold_delivered"] for r in answerable), len(answerable)),
            "multi_evidence_complete_delivery": rate(sum(r["supported_gold_delivered"] for r in multi_evidence), len(multi_evidence)),
            "followup_complete_delivery": rate(sum(r["supported_gold_delivered"] for r in followups), len(followups)),
            "mixed_request_source_delivery": rate(sum(r["supported_gold_delivered"] for r in mixed if r["gold_ids"]), sum(bool(r["gold_ids"]) for r in mixed)),
            "unrecorded_episode_injection": rate(sum(r["no_answer_injection"] for r in unknown_episodes), len(unknown_episodes)),
            "no_answer_injection": rate(sum(r["no_answer_injection"] for r in absent), len(absent)),
            "unnecessary_retrieval": rate(sum(retrieval_performed(r) for r in no_retrieval), len(no_retrieval)),
            "route_exact": rate(sum(r["route_exact"] for r in route_rows), len(route_rows)),
            "status_exact": rate(sum(r["status_exact"] for r in route_rows), len(route_rows)),
            "correct_unknown_with_no_injection": rate(sum(r["trace"].get("status") == "unknown" and not r["all_context_evidence_ids"] for r in unknown), len(unknown)),
            "answerable_zero_evidence": rate(sum(not r["delivered_ids"] for r in answerable), len(answerable)),
            "forbidden_injection": rate(sum(bool(r["forbidden_delivered"]) for r in rows), len(rows)),
            "structured_wrong_injection": rate(sum(bool(r["structured_wrong_ids"]) for r in rows), len(rows)),
            "historical_wrong_injection": rate(sum(bool(r["historical_wrong_ids"]) for r in rows), len(rows)),
            "planned_wrong_injection": rate(sum(bool(r["planned_wrong_ids"]) for r in rows), len(rows)),
            "forgotten_injection": rate(sum(bool(r["forgotten_ids"]) for r in rows), len(rows)),
            "isolation_injection": rate(sum(bool(r.get("scope_or_owner_ineligible_ids")) for r in rows), len(rows)),
            "persona_config_unchanged": rate(sum(r["persona_config_unchanged"] for r in persona_rows), len(persona_rows)),
            "persona_config_delivered": rate(sum(r["persona_config_delivered"] for r in persona_rows), len(persona_rows)),
            "provider_context_lost_evidence": rate(sum(bool(r["provider_lost_evidence_ids"]) for r in provider_rows), len(provider_rows)),
            "overview_source_coverage": rate(sum(c["source_present"] for c in claims), len(claims)),
            "overview_extractive_entailment": rate(sum(c["extractively_entailed"] for c in claims), len(claims)),
            "overview_source_fingerprint": rate(sum(c.get("source_fingerprint_matches") is True for c in claims),
                                                 sum(c.get("source_fingerprint_matches") is not None for c in claims)),
            "resolution_source_coverage": rate(sum(c["source_present"] for c in resolution_sources), len(resolution_sources)),
            "resolution_literal_binding": rate(sum(c.get("literal_binding_supported") is True for c in resolution_sources),
                                                sum(c.get("literal_binding_supported") is not None for c in resolution_sources)),
            "resolution_source_fingerprint": rate(sum(c.get("source_fingerprint_matches") is True for c in resolution_sources),
                                                    sum(c.get("source_fingerprint_matches") is not None for c in resolution_sources)),
            "duplicate_evidence_queries": rate(sum(bool(r["duplicate_evidence_ids"]) for r in rows), len(rows)),
            "errors": rate(sum(bool(r["error"]) for r in rows), len(rows)),
            "stages_ms": {key: distribution(r.get("timings_ms", {}).get(key) for r in rows) for key in stages},
            "warm_total_ms": distribution(r.get("timings_ms", {}).get("total") for r in rows if r.get("index_warm")),
            "cold_query_total_ms": distribution(r.get("timings_ms", {}).get("total") for r in rows if r.get("index_warm") is False),
            "embedding_query_calls": sum(r.get("embedding_query_calls", 0) for r in rows),
            "passage_encoded_entries": sum(r.get("encoded_entries", 0) for r in rows),
            "rows_loaded": distribution(r["trace"].get("rows_loaded", 0) for r in rows),
            "prepare_rows_loaded": distribution(r.get("prepare_rows_loaded", 0) for r in rows),
            "prepare_retrieval_calls": sum(r.get("prepare_retrieval_calls", 0) for r in rows),
            "context_chars": distribution(r["memory_context_chars"] for r in rows),
            "bge_tokenizer_prompt_tokens": distribution(r["bge_tokenizer_prompt_tokens"] for r in token_rows),
            "provider_tokens": {"evidence_judgment": summarize_evidence(rows), "answer_generation": "not_run"},
            "actual_answer_accuracy": "not_run", "persona_behavior": "not_run"}


def _serializable(value):
    if is_dataclass(value):
        return asdict(value)
    return value.to_dict() if hasattr(value, "to_dict") else dict(value)


def paired_story_bootstrap(baseline, candidate, repetitions=1000):
    """Descriptive story-cluster stability, not a real-population guarantee."""
    left, right = {r["query_id"]: r for r in baseline}, {r["query_id"]: r for r in candidate}
    if set(left) != set(right):
        raise ValueError("Paired comparison requires identical query IDs")
    stories = defaultdict(list)
    for key, row in left.items():
        stories[row["story_id"]].append(key)
    story_ids = sorted(stories)
    rng = random.Random(73529)
    metrics = {
        "delivered_recall_delta": (lambda r: bool(r["gold_ids"]), lambda r: r["delivered_recall"]),
        "no_answer_injection_delta": (lambda r: not r["gold_ids"] and r["expected_status"] == "unknown",
                                      lambda r: float(r["no_answer_injection"])),
    }
    result = {}
    for name, (eligible, value) in metrics.items():
        def delta(keys):
            keys = [k for k in keys if eligible(left[k])]
            return statistics.mean(value(right[k]) - value(left[k]) for k in keys) if keys else None
        observed = delta(left)
        draws = []
        for _ in range(repetitions):
            sampled = [key for story in rng.choices(story_ids, k=len(story_ids)) for key in stories[story]]
            effect = delta(sampled)
            if effect is not None:
                draws.append(effect)
        draws.sort()
        result[name] = {"observed": observed, "cluster_count": len(story_ids), "repetitions": len(draws),
                        "descriptive_95_percentile_interval": [draws[int(.025 * (len(draws) - 1))],
                                                               draws[int(.975 * (len(draws) - 1))]] if draws else None}
    result["interpretation"] = "Paired synthetic-story cluster bootstrap; no sampling claim about real users"
    return result


def worker(args):
    source_root = args.baseline_root if args.worker in {"none", "lexical", "bge_rrf"} else args.source_root
    if args.worker in {"none", "lexical", "bge_rrf"}:
        validate_baseline(source_root, args.baseline_commit)
    sys.path.insert(0, str(source_root / "src"))
    from guanghe_companion.emotional_memory import EmotionalMemoryEntry, MemoryContextBundle, CoreBondProfile
    from guanghe_companion.emotional_memory_service import EmotionalMemoryService
    from guanghe_companion.emotional_memory_retrieval import rank_memories
    from guanghe_companion.expression_request import ExpressionRequest
    from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
    from guanghe_companion.character_pack import load_default_character_pack
    from guanghe_companion.persona import build_persona_payload
    from guanghe_companion.semantic_memory import SemanticMemoryRetriever, MODEL_NAME, MODEL_REVISION
    datasets = load_datasets(args.dataset_dir, args.splits)
    if args.story_ids:
        wanted = set(args.story_ids)
        known = {s["id"] for d in datasets for s in d["stories"]}
        if not wanted <= known:
            raise ValueError("Unknown requested story ID")
        datasets = [{**d, "stories": [s for s in d["stories"] if s["id"] in wanted]}
                    for d in datasets]
    hashes = source_hashes(source_root)
    # Use the real authored default persona in the isolated synthetic memory
    # namespace; no existing character save or selected pack is touched.
    persona = build_persona_payload(replace(load_default_character_pack(), character_id=datasets[0]["character_id"]))
    persona_hash = hashlib.sha256(json.dumps(persona, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    expressor = ShinsekaiAIExpressor()
    result = {"schema_version": 1, "method": args.worker, "size": args.size,
              "status": "running", "source_root": str(source_root),
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "source_commit": git(source_root, "rev-parse", "HEAD"), "source_sha256": hashes,
              "script_sha256": digest(Path(__file__)), "dataset_sha256": {d["split"]: d["dataset_sha256"] for d in datasets},
              "environment": environment(), "stories": [], "rows": [],
              "semantic": {"model": MODEL_NAME, "revision": MODEL_REVISION, "threads": 2,
                           "provider": "CPUExecutionProvider", "enabled": args.worker in {"bge_rrf", "routed", "layered"} and not args.no_semantic},
              "budget": {"top_k": 4, "expression_memory_chars": 6000, "requested_new_context_chars": 6000,
                         "final_provider_prompt_chars": 8192},
              "story_filter": args.story_ids,
              "split_roles": {d["split"]: d["split_usage"] for d in datasets},
              "measurement_scope": "real temporary SQLite + retrieval + ExpressionRequest + final production provider prompt, no generation",
              "not_run": ["generative answer accuracy", "model persona behavior", "desktop real-user interaction", "phone device validation", "provider token billing"]}
    args.worker_output.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = ROOT / "artifacts/codex_handoff/ondemand-evaluation-temp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    result["temporary_root"] = str(temporary_root)
    result["baseline_expected_commit"] = args.baseline_commit
    judge, judge_client, judge_meter, judge_secret = None, None, None, ""
    if args.evidence_settings and args.worker in {"routed", "layered"}:
        from tools.eval_ondemand_generation import recorded_app_client, redact
        from guanghe_companion.memory_evidence_judgment import MemoryEvidenceJudge
        judge_client, judge_meter, metadata, judge_secret = recorded_app_client(
            args.evidence_settings, max_requests=args.max_evidence_requests,
            max_output_tokens=args.max_evidence_output_tokens)
        judge = MemoryEvidenceJudge(judge_client)
        result["evidence_provider"] = metadata
        result["not_run"] = [item for item in result["not_run"] if item != "provider token billing"]
        result["not_run"].append("answer-generation provider token billing")
    def checkpoint():
        write_json_atomic(args.worker_output, result)
    semantic, tokenizer = None, None
    if result["semantic"]["enabled"]:
        semantic = SemanticMemoryRetriever(cache_dir=args.model_cache, character_id=datasets[0]["character_id"],
                                           owner_id=datasets[0]["owner_id"], local_files_only=args.local_files_only)
        _, result["model_load_ms"] = timed(lambda: semantic.warmup().result(timeout=600))
    if args.model_cache:
        tokenizer_paths = sorted(args.model_cache.glob("models--Qdrant--bge-small-zh-v1.5/snapshots/*/tokenizer.json"))
        if tokenizer_paths:
            try:
                from tokenizers import Tokenizer
                tokenizer = Tokenizer.from_file(str(tokenizer_paths[-1]))
                tokenizer.no_truncation()
                result["token_measurement"] = {"tokenizer": str(tokenizer_paths[-1]), "sha256": digest(tokenizer_paths[-1]),
                                               "note": "Common BGE tokenizer proxy, not answer-provider billable tokens"}
            except ImportError:
                pass
    query_counter = 0
    try:
        for data in datasets:
            for story in data["stories"]:
                now, time_basis = story_clock(data, story)
                input_rows = make_input_rows(data, story["id"], args.size)
                entries = make_entries(data, story["id"], args.size, EmotionalMemoryEntry, input_rows=input_rows)
                source_rows = {m["id"]: m for m in data["memories"] if m["story_id"] == story["id"]}
                normalized_by_id = {m.memory_id: m for m in entries}
                source_rows = {key: {**row, "_expected_fingerprint": normalized_by_id[key].evidence_fingerprint()}
                               for key, row in source_rows.items()}
                own = [m for m in entries if m.owner_id == data["owner_id"] and m.character_id == data["character_id"]]
                story_result = {"story_id": story["id"], "split": data["split"], "source_count": len(source_rows),
                                "now": now, "time_basis": time_basis,
                                "archive_entries": len(entries), "main_namespace_entries": len(own),
                                **corpus_provenance(input_rows, entries),
                                "summary_chars": distribution(len(m.summary) for m in entries), "rss_before_mib": rss_mib()}
                with tempfile.TemporaryDirectory(prefix="emoti-ondemand-", dir=temporary_root) as directory:
                    kwargs = {}
                    if args.worker in {"routed", "layered"}:
                        from guanghe_companion.retrieval_contract import RetrievalBudget
                        kwargs["retrieval_budget"] = RetrievalBudget(max_context_chars=6000)
                        kwargs["time_basis"] = time_basis
                        if judge is not None:
                            kwargs["evidence_judge"] = judge
                    service = EmotionalMemoryService(root=directory, character_id=data["character_id"],
                                                     owner_id=data["owner_id"], semantic_retriever=semantic, **kwargs)
                    _, story_result["seed_ms"] = timed(lambda: service.store.save_memories(own))
                    for owner, character in {(m.owner_id, m.character_id) for m in entries} - {(data["owner_id"], data["character_id"])}:
                        other = EmotionalMemoryService(root=directory, character_id=character, owner_id=owner)
                        other.store.save_memories(m for m in entries if m.owner_id == owner and m.character_id == character)
                    if semantic and args.worker == "bge_rrf":
                        _, story_result["initial_index_prepare_ms"] = timed(lambda: semantic.prepare(
                            "初始化检索索引", own, now=now, scope="companion").result(timeout=600))
                        story_result["initial_index_entries"] = semantic.status.get("indexed_entries")
                    result["stories"].append(story_result)
                    queries = [q for q in data["queries"] if q["story_id"] == story["id"]]
                    for q in queries:
                        judge_start = len(judge_meter.records) if judge_meter else 0
                        timing, error, selected_ids = {}, None, []
                        prompt, expression_payload, provider_prompt = {}, {}, ""
                        semantic_before = dict(semantic.status) if semantic else {}
                        trace = {"router_evaluated": args.worker in {"routed", "layered"}, "route": [],
                                 "status": "not_needed" if args.worker == "none" else "legacy_ungated",
                                 "retrieval_calls": 0 if args.worker == "none" else 1, "rows_loaded": 0}
                        start = time.perf_counter_ns()
                        bundle = MemoryContextBundle(CoreBondProfile(data["character_id"], data["owner_id"]))
                        try:
                            if args.worker in {"routed", "layered"}:
                                def prepare_new():
                                    pending = service.prepare_retrieval(q["text"], now=now, history=q.get("history", ()), scope=q["scope"])
                                    if pending is not None:
                                        pending.result(timeout=600)
                                _, timing["index_and_query_prepare"] = timed(prepare_new)
                                retrieved, timing["retrieve"] = timed(lambda: service.retrieve(
                                    q["text"], now=now, history=q.get("history", ()), scope=q["scope"],
                                    top_k=4, layered=args.worker == "layered"))
                                bundle = retrieved.bundle
                                trace = {**_serializable(retrieved.trace), "router_evaluated": True}
                                selected_ids = list(trace.get("selected_memory_ids", [m.memory_id for m in bundle.memories]))
                                timing.update({"retrieval_" + k: v for k, v in trace.get("stage_ms", {}).items()})
                            elif args.worker != "none":
                                snapshot, timing["database_read"] = timed(lambda: service.store.read_context_snapshot(now=now))
                                active, timing["qualification"] = timed(lambda: tuple(m for m in snapshot.entries
                                    if m.owner_id == data["owner_id"] and m.character_id == data["character_id"]
                                    and m.is_active(now=now, scope=q["scope"])))
                                scores = {}
                                if semantic:
                                    _, timing["index_and_query_prepare"] = timed(lambda: semantic.prepare(
                                        q["text"], active, now=now, scope=q["scope"]).result(timeout=600))
                                    scores, timing["semantic_scores"] = timed(lambda: semantic(q["text"], active))
                                ranked, timing["lexical_and_fusion"] = timed(lambda: rank_memories(
                                    active, q["text"], now=now, top_k=4, scope=q["scope"], semantic_scores=scores))
                                selected = tuple(m for m, _ in ranked)
                                selected, timing["finalize_recall"] = timed(lambda: service.store.finalize_recall(
                                    selected, expected_epoch=snapshot.context_epoch, now=now, scope=q["scope"]))
                                selected = selected or ()
                                bundle = MemoryContextBundle(snapshot.profile, selected, context_epoch=snapshot.context_epoch)
                                selected_ids = [m.memory_id for m in selected]
                                trace.update(rows_loaded=len(snapshot.entries), candidate_count=len(active),
                                             selected_memory_ids=selected_ids)
                            context = {"memory_v2_authoritative": True, "emotional_memory": bundle.to_prompt_payload(), "persona": persona}
                            recent = expression_history(q.get("history", []), persona["character_name"])
                            request, timing["context_assembly"] = timed(lambda: ExpressionRequest.from_snapshot(
                                {"character_name": persona["character_name"], "focus": 50, "charge": 50,
                                 "stability": 50, "mood": 50, "trust": 50, "player_message": q["text"],
                                 "recent_dialogue": recent}, context=context))
                            expression_payload = request.to_prompt_dict()
                            provider_prompt, timing["provider_prompt_assembly"] = timed(lambda: expressor.build_prompt(request))
                            prompt = provider_evidence_payload(provider_prompt)
                        except Exception as exc:
                            error = f"{type(exc).__name__}: {exc}"
                            trace["status"] = "error"
                            prompt = {}
                        timing["total"] = (time.perf_counter_ns() - start) / 1_000_000
                        row = score_query(q, prompt, selected_ids, trace, source_rows, error=error)
                        before_provider = evidence_representations(expression_payload)
                        before_ids = list(dict.fromkeys(mid for rep in before_provider for mid in rep["ids"]))
                        row.update(actual_expression_request=expression_payload, actual_provider_prompt=provider_prompt,
                                   actual_provider_payload=prompt, provider_prompt_sha256=hashlib.sha256(provider_prompt.encode()).hexdigest(),
                                   provider_prompt_chars=len(provider_prompt), expression_request_delivered_ids=before_ids,
                                   provider_lost_evidence_ids=sorted(set(before_ids) - set(row["delivered_ids"])),
                                   provider_retrieval_status=prompt.get("emotional_memory", {}).get("retrieval", {}).get("status"))
                        row.update(split=data["split"], timings_ms=timing, rss_mib=rss_mib())
                        allowed_scopes = {"task_experience" if route == "task" else "companion" for route in q["expected_routes"]}
                        row["scope_or_owner_ineligible_ids"] = [mid for mid in row["all_context_evidence_ids"]
                            if mid in normalized_by_id and (normalized_by_id[mid].owner_id != data["owner_id"]
                            or normalized_by_id[mid].character_id != data["character_id"]
                            or normalized_by_id[mid].scope not in allowed_scopes)]
                        if semantic:
                            after = dict(semantic.status)
                            row["embedding_query_calls"] = (after.get("query_embed_count", 0) - semantic_before.get("query_embed_count", 0)
                                if "query_embed_count" in after else int(args.worker == "bge_rrf"))
                            row["encoded_entries"] = after.get("encoded_entries_total", 0) - semantic_before.get("encoded_entries_total", 0)
                            row["semantic_stage_status"] = {key: value for key, value in after.items()
                                if key.endswith("_ms") or key in {"manifest_pages", "payload_rows_loaded", "prepare_retries", "indexed_entries"}}
                        else:
                            row.update(embedding_query_calls=0, encoded_entries=0)
                        row["index_warm"] = row["encoded_entries"] == 0
                        actual_persona = prompt.get("persona", {})
                        row["persona_config_delivered"] = actual_persona.get("config_hash") == persona.get("config_hash")
                        row["persona_config_unchanged"] = hashlib.sha256(json.dumps(persona, sort_keys=True, ensure_ascii=False).encode()).hexdigest() == persona_hash
                        if tokenizer is not None:
                            row["bge_tokenizer_prompt_tokens"] = len(tokenizer.encode(provider_prompt).ids)
                        if judge_meter is not None:
                            row["prepare_rows_loaded"] = judge.prepare_rows_loaded
                            row["prepare_retrieval_calls"] = judge.prepare_retrieval_calls
                            row["evidence_judgment"] = {"status": judge.status,
                                "requests": redact(judge_meter.records[judge_start:], judge_secret)}
                        result["rows"].append(row)
                        query_counter += 1
                        if query_counter % 24 == 0:
                            print(json.dumps({"event": "queries", "method": args.worker, "size": args.size,
                                              "done": query_counter, "errors": sum(bool(r["error"]) for r in result["rows"])}), flush=True)
                    story_result["database_bytes"] = service.store.state_path.stat().st_size
                    story_result["rss_after_mib"] = rss_mib()
                    checkpoint()
    finally:
        expressor.close()
        if judge is not None:
            judge.close()
        if judge_client is not None:
            judge_client.close()
        if semantic is not None:
            semantic.close()
    result["summary"] = summarize(result["rows"])
    result["by_split"] = {split: summarize([r for r in result["rows"] if r["split"] == split]) for split in args.splits}
    result["by_family"] = {family: summarize([r for r in result["rows"] if r["family"] == family])
                           for family in sorted({r["family"] for r in result["rows"]})}
    result["peak_rss_mib"] = peak_rss_mib()
    result["source_unchanged_during_run"] = hashes == source_hashes(source_root)
    result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["status"] = ("measured_synthetic_retrieval" if result["source_unchanged_during_run"]
                        else "source_changed_during_run_do_not_compare_as_frozen_revision")
    checkpoint()
    print(json.dumps({"event": "worker_complete", "method": args.worker, "size": args.size,
                      "status": result["status"], "output": str(args.worker_output)}), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, default=ROOT)
    p.add_argument("--baseline-root", type=Path, default=ROOT)
    p.add_argument("--baseline-commit", default=BASELINE_COMMIT)
    p.add_argument("--evidence-settings", type=Path)
    p.add_argument("--max-evidence-requests", type=int, default=10000)
    p.add_argument("--max-evidence-output-tokens", type=int, default=4096)
    p.add_argument("--dataset-dir", type=Path, default=ROOT / "tests/fixtures")
    p.add_argument("--splits", nargs="+", choices=SPLITS, default=["development", "validation"])
    p.add_argument("--story-ids", nargs="+", help="Predeclared scale subset; saved explicitly in the manifest")
    p.add_argument("--sizes", type=int, nargs="+", default=[300, 3000, 10000])
    p.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    p.add_argument("--model-cache", type=Path)
    p.add_argument("--local-files-only", action="store_true")
    p.add_argument("--no-semantic", action="store_true", help="Explicit lexical-only development diagnostic, never labelled BGE results")
    p.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/ondemand-memory")
    p.add_argument("--worker", choices=METHODS)
    p.add_argument("--size", type=int)
    p.add_argument("--worker-output", type=Path)
    args = p.parse_args()
    if not 1 <= args.max_evidence_requests <= 10000:
        p.error("--max-evidence-requests must be between 1 and 10000 per worker")
    if not 1 <= args.max_evidence_output_tokens <= 4096:
        p.error("--max-evidence-output-tokens must be between 1 and 4096")
    if args.worker:
        worker(args)
        return
    datasets = load_datasets(args.dataset_dir, args.splits)
    if any(size < max(sum(m["story_id"] == s["id"] for m in d["memories"]) for d in datasets for s in d["stories"])
           for size in args.sizes):
        p.error("A requested size is smaller than a source story")
    if args.no_semantic and "bge_rrf" in args.methods:
        p.error("--no-semantic cannot be used to label a run bge_rrf")
    if any(method in {"none", "lexical", "bge_rrf"} for method in args.methods):
        validate_baseline(args.baseline_root, args.baseline_commit)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "status": "running", "methods": args.methods, "sizes": args.sizes,
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "splits": args.splits, "dataset_sha256": {d["split"]: d["dataset_sha256"] for d in datasets},
                "split_roles": {d["split"]: d["split_usage"] for d in datasets},
                "story_filter": args.story_ids,
                "script_sha256": digest(Path(__file__)), "baseline_expected_commit": args.baseline_commit,
                "baseline_actual_commit": git(args.baseline_root, "rev-parse", "HEAD"),
                "new_source_start_sha256": source_hashes(args.source_root), "runs": [],
                "data_policy": "Independent story archives; synthetic stress tests, no population inference; fixed order; no generative LLM"}
    path = args.output_dir / "run-manifest.json"
    def checkpoint():
        write_json_atomic(path, manifest)
    checkpoint()
    for size in args.sizes:
        for method in args.methods:
            output = args.output_dir / f"{method}-{size}.json"
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", method, "--size", str(size),
                       "--worker-output", str(output), "--source-root", str(args.source_root),
                       "--baseline-root", str(args.baseline_root), "--dataset-dir", str(args.dataset_dir),
                       "--baseline-commit", args.baseline_commit,
                       "--splits", *args.splits]
            if args.model_cache:
                command += ["--model-cache", str(args.model_cache)]
            if args.evidence_settings:
                command += ["--evidence-settings", str(args.evidence_settings),
                            "--max-evidence-requests", str(args.max_evidence_requests),
                            "--max-evidence-output-tokens", str(args.max_evidence_output_tokens)]
            if args.story_ids:
                command += ["--story-ids", *args.story_ids]
            if args.local_files_only:
                command.append("--local-files-only")
            if args.no_semantic:
                command.append("--no-semantic")
            start = time.perf_counter_ns()
            log_path = args.output_dir / f"{method}-{size}.log"
            with log_path.open("w", encoding="utf-8") as log:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           text=True, encoding="utf-8")
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    print(line, end="", flush=True)
                returncode = process.wait()
            elapsed = (time.perf_counter_ns() - start) / 1_000_000
            record = {"method": method, "size": size, "output": str(output),
                      "command": command, "console_log": str(log_path),
                      "returncode": returncode, "elapsed_ms": elapsed}
            if output.exists():
                raw = json.loads(output.read_text())
                record.update(status=raw["status"], summary=raw.get("summary"), sha256=digest(output))
            manifest["runs"].append(record)
            checkpoint()
    manifest["paired_comparisons"] = {}
    for size in args.sizes:
        for baseline_method in ("lexical", "bge_rrf"):
            for candidate_method in ("routed", "layered"):
                baseline_path = args.output_dir / f"{baseline_method}-{size}.json"
                candidate_path = args.output_dir / f"{candidate_method}-{size}.json"
                if baseline_method not in args.methods or candidate_method not in args.methods:
                    continue
                if baseline_path.exists() and candidate_path.exists():
                    baseline = json.loads(baseline_path.read_text())
                    candidate = json.loads(candidate_path.read_text())
                    if baseline.get("summary") and candidate.get("summary"):
                        manifest["paired_comparisons"][f"{candidate_method}_vs_{baseline_method}_{size}"] = paired_story_bootstrap(
                            baseline["rows"], candidate["rows"])
    manifest["new_source_unchanged_during_campaign"] = manifest["new_source_start_sha256"] == source_hashes(args.source_root)
    manifest["status"] = ("completed" if all(r["returncode"] == 0 for r in manifest["runs"])
                          else "completed_with_failed_workers")
    manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    checkpoint()
    print(json.dumps({"manifest": str(path), "status": manifest["status"]}), flush=True)


if __name__ == "__main__":
    main()
