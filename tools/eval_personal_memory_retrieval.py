#!/usr/bin/env python3
"""Reproducible CPU retrieval diagnostic for E-Moti, without a generative LLM.

Uses production eligibility, ranking, semantic retriever and ExpressionRequest.
The committed corpus is synthetic development data, not a sealed benchmark.
Examples (run from repository root):
  python tools/eval_personal_memory_retrieval.py --lexical-only --sizes 300 \
      --output artifacts/retrieval-lexical.json
  python tools/eval_personal_memory_retrieval.py --sizes 300 3000 \
      --model-cache /path/to/model-cache --store-queries 8 \
      --output artifacts/retrieval.json

For storage alone, pass --store-only --sizes 300 3000 --output PATH.
Install the project's semantic extra to run real BGE. This script creates only
temporary SQLite stores and the requested output/cache; no provider keys or API
calls are used. A model download can occur unless --local-files-only is passed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timed(function):
    start = time.perf_counter_ns()
    result = function()
    return result, (time.perf_counter_ns() - start) / 1_000_000


def distribution(values):
    values = sorted(float(value) for value in values)
    if not values:
        return {"n": 0}
    def percentile(p):
        position = (len(values) - 1) * p
        lower = math.floor(position)
        upper = math.ceil(position)
        return values[lower] + (values[upper] - values[lower]) * (position - lower)
    return {"n": len(values), "p50": statistics.median(values),
            "p95": percentile(.95), "p99": percentile(.99),
            "min": values[0], "max": values[-1]}


def rss_mib():
    try:
        pages = int(Path("/proc/self/statm").read_text().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") / 1024**2
    except (OSError, ValueError, AttributeError):
        return None


def cpu_model():
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unavailable"


def git_value(source_root, *arguments):
    result = subprocess.run(["git", "-C", str(source_root), *arguments],
                            capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def validate_dataset(data):
    ids = [row["id"] for row in data["memories"]]
    query_ids = [row["id"] for row in data["queries"]]
    if len(ids) != len(set(ids)) or len(query_ids) != len(set(query_ids)):
        raise ValueError("Dataset IDs must be unique")
    if any(not query["text"].strip() for query in data["queries"]):
        raise ValueError("Empty queries have different production semantics")
    for query in data["queries"]:
        if not set(query["gold_ids"]) <= set(ids):
            raise ValueError(f"Unknown gold ID in {query['id']}")


def make_entries(data, size, Entry):
    rows = []
    defaults = data["defaults"]
    for raw in data["memories"]:
        fields = {**defaults, **raw}
        fields["memory_id"] = fields.pop("id")
        fields.setdefault("character_id", data["character_id"])
        fields.setdefault("owner_id", data["owner_id"])
        fields["source_ids"] = (f"synthetic:{fields['memory_id']}",)
        row = Entry(**fields).normalized()
        row.validate()
        rows.append(row)
    if size < len(rows):
        raise ValueError(f"size must be at least {len(rows)}")
    fillers = list(range(size - len(rows)))
    random.Random(data["filler_seed"]).shuffle(fillers)
    for index in fillers:
        text = data["filler_templates"][index % len(data["filler_templates"])].format(n=index)
        row = Entry(memory_id=f"filler_{index:06d}",
                    character_id=data["character_id"], owner_id=data["owner_id"],
                    title=f"日常资料{index}", summary=text,
                    source_ids=(f"synthetic:filler:{index}",), **defaults)
        row.validate()
        rows.append(row)
    return tuple(rows)


def eligible(entries, data, query):
    # Same owner/character ownership gate as EmotionalMemoryStore._entries,
    # plus the production Entry.is_active gate. Do not compare routes on
    # differently scoped corpora.
    return tuple(entry for entry in entries
                 if entry.owner_id == data["owner_id"]
                 and entry.character_id == data["character_id"]
                 and entry.is_active(now=data["now"], scope=query.get("scope", "companion")))


def prompt_for(entries, data, query, Bundle, Profile, Request):
    bundle = Bundle(Profile(data["character_id"], data["owner_id"]),
                    memories=tuple(entries), context_epoch=1)
    request = Request.from_snapshot(
        {"character_name": "合成测试角色", "focus": 50, "charge": 50,
         "stability": 50, "mood": 50, "trust": 50,
         "player_message": query["text"]},
        context={"memory_v2_authoritative": True,
                 "emotional_memory": bundle.to_prompt_payload()})
    return request.to_prompt_dict()


def score_row(route, query, rows, eligible_ids, data, prepare_ms, rank_ms,
              index_warm, Bundle, Profile, Request):
    selected = tuple(row[0] for row in rows)
    ids = [entry.memory_id for entry in selected]
    gold = set(query["gold_ids"])
    hits = gold & set(ids)
    prompt, context_ms = timed(lambda: prompt_for(selected, data, query, Bundle, Profile, Request))
    delivered = [row["memory_id"] for row in prompt.get("emotional_memory", {}).get("shared_memories", [])]
    position = next((i + 1 for i, value in enumerate(ids) if value in gold), None)
    return {
        "query_id": query["id"], "family": query["family"], "query": query["text"],
        "scope": query.get("scope", "companion"), "route": route,
        "gold_ids": query["gold_ids"], "retrieved_ids": ids, "delivered_ids": delivered,
        "recall_at_4": len(hits) / len(gold) if gold else None,
        "precision_at_4": len(hits) / len(ids) if gold and ids else (0.0 if gold else None),
        "mrr": 1 / position if position else (0.0 if gold else None),
        "all_gold_delivered": gold <= set(delivered) if gold else None,
        "no_answer_injection": bool(ids) if not gold else None,
        "ineligible_ids": sorted(set(ids) - eligible_ids),
        "prepare_ms": prepare_ms, "rank_ms": rank_ms, "context_ms": context_ms,
        "retrieval_and_context_ms": prepare_ms + rank_ms + context_ms,
        "index_warm": index_warm,
        "prompt_chars": len(json.dumps(prompt, ensure_ascii=False, separators=(",", ":"))),
        "prompt_tokens": None,
        "prompt_tokens_note": "Not measured with the answer-provider tokenizer",
        "scores": [{"memory_id": entry.memory_id, "summary": entry.summary, **score}
                   for entry, score in rows],
        "actual_expression_request": prompt,
    }


def summarize(rows):
    answerable = [row for row in rows if row["gold_ids"]]
    negatives = [row for row in rows if not row["gold_ids"]]
    return {
        "queries": len(rows), "answerable_queries": len(answerable),
        "no_personal_evidence_queries": len(negatives),
        "macro_recall_at_4": statistics.mean(row["recall_at_4"] for row in answerable) if answerable else None,
        "macro_precision_at_4": statistics.mean(row["precision_at_4"] for row in answerable) if answerable else None,
        "mrr": statistics.mean(row["mrr"] for row in answerable) if answerable else None,
        "all_gold_delivered_rate": sum(row["all_gold_delivered"] for row in answerable) / len(answerable) if answerable else None,
        "no_answer_injection_count": sum(row["no_answer_injection"] for row in negatives),
        "no_answer_injection_rate": sum(row["no_answer_injection"] for row in negatives) / len(negatives) if negatives else None,
        "ineligible_result_count": sum(len(row["ineligible_ids"]) for row in rows),
        "warm_prepare_ms": distribution(row["prepare_ms"] for row in rows if row["index_warm"]),
        "rank_ms": distribution(row["rank_ms"] for row in rows),
        "warm_retrieval_and_context_ms": distribution(row["retrieval_and_context_ms"] for row in rows if row["index_warm"]),
        "context_chars": distribution(row["prompt_chars"] for row in rows),
    }


def store_probe(entries, data, args, semantic, EntryStore, Service, Request):
    """Real SQLite/context microbenchmark, not the desktop event loop."""
    if args.store_queries == 0:
        return None
    sample = [query for query in data["queries"] if query.get("scope", "companion") == "companion"][:args.store_queries]
    rows = []
    with tempfile.TemporaryDirectory(prefix="emoti-retrieval-store-") as temporary:
        service = Service(root=temporary, character_id=data["character_id"],
                          owner_id=data["owner_id"], semantic_retriever=semantic)
        # Explicitly raise the old configurable 300-row cap for scale testing.
        # This does not prove the project's default retention policy is fixed.
        service.store = EntryStore(root=temporary, character_id=data["character_id"],
                                   owner_id=data["owner_id"], max_entries=len(entries))
        owned = tuple(entry for entry in entries if entry.owner_id == data["owner_id"]
                      and entry.character_id == data["character_id"])
        _, seed_ms = timed(lambda: service.store.save_memories(owned))
        loaded = service.store.load_memories()
        for query in sample:
            latest, load_ms = timed(service.store.load_memories)
            prepare_ms = 0.0
            if semantic is not None:
                _, prepare_ms = timed(lambda: semantic.prepare(query["text"], latest, now=data["now"]).result(timeout=600))
            bundle, context_ms = timed(lambda: service.build_context(query["text"], now=data["now"]))
            request = Request.from_snapshot(
                {"character_name": "合成测试角色", "focus": 50, "charge": 50,
                 "stability": 50, "mood": 50, "trust": 50, "player_message": query["text"]},
                context={"memory_v2_authoritative": True, "emotional_memory": bundle.to_prompt_payload()})
            rows.append({"query_id": query["id"], "load_memories_ms": load_ms, "prepare_ms": prepare_ms,
                         "sqlite_build_context_ms": context_ms,
                         "delivered_ids": [item["memory_id"] for item in request.emotional_memory.get("shared_memories", [])]})
        corrected, correct_ms = timed(lambda: service.correct(
            "nickname", title="称呼", summary="用户希望被称为小禾。", now=data["now"] + 1,
            source_ids=("synthetic:timed-correction",)))
        forgotten, forget_ms = timed(lambda: service.forget(corrected.memory_id, now=data["now"] + 2))
        final = service.store.load_memories()
        if forgotten is None or any(entry.memory_id == corrected.memory_id and not entry.deleted for entry in final):
            raise AssertionError("Timed forget did not actually retire the corrected memory")
        return {"note": "Real public bulk seed, SQLite reads/expiry/touch/profile/chapter and context. Explicit max_entries=size. No desktop event loop or generative LLM.",
                "seed_ms": seed_ms, "owned_seed_rows": len(owned), "stored_rows": len(loaded),
                "load_memories_ms": distribution(row["load_memories_ms"] for row in rows),
                "build_context_ms": distribution(row["sqlite_build_context_ms"] for row in rows),
                "single_correct_ms": correct_ms, "single_forget_ms": forget_ms,
                "mutation_samples": 1, "forget_verified": True,
                "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    repo_default = Path(__file__).resolve().parents[1]
    parser.add_argument("--source-root", type=Path, default=repo_default,
                        help="Repository whose production code is evaluated (may be a frozen baseline checkout)")
    parser.add_argument("--dataset", type=Path, default=repo_default / "tests/fixtures/personal_memory_retrieval_cases.json")
    parser.add_argument("--sizes", nargs="+", type=int, default=[300, 3000])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-cache", type=Path, default=Path(tempfile.gettempdir()) / "emoti-bge-model-cache")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--lexical-only", action="store_true")
    parser.add_argument("--store-only", action="store_true",
                        help="Skip quality and embeddings; profile real SQLite + lexical context and mutations")
    parser.add_argument("--store-queries", type=int, default=0)
    args = parser.parse_args()
    args.source_root = args.source_root.resolve()
    if args.store_queries < 0:
        parser.error("--store-queries must be nonnegative")
    if args.store_only and not args.store_queries:
        args.store_queries = 8
    sys.path.insert(0, str(args.source_root / "src"))
    from guanghe_companion.emotional_memory import (
        EmotionalMemoryEntry, EmotionalMemoryStore, MemoryContextBundle, CoreBondProfile)
    from guanghe_companion.emotional_memory_retrieval import rank_memories
    from guanghe_companion.emotional_memory_service import EmotionalMemoryService
    from guanghe_companion.expression_request import ExpressionRequest
    from guanghe_companion.semantic_memory import SemanticMemoryRetriever, MODEL_NAME, MODEL_REVISION
    data = json.loads(args.dataset.read_text(encoding="utf-8"))
    validate_dataset(data)
    source_files = ["emotional_memory.py", "emotional_memory_service.py",
                    "emotional_memory_retrieval.py", "memory_fusion.py",
                    "semantic_memory.py", "expression_request.py"]
    hashes = {name: digest(args.source_root / "src/guanghe_companion" / name) for name in source_files}
    dependencies = {}
    for package in ("fastembed", "numpy", "onnxruntime", "tokenizers", "huggingface-hub"):
        try:
            dependencies[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            dependencies[package] = None
    result: dict[str, Any] = {
        "benchmark": data["name"], "status": "measured_synthetic_development_diagnostic",
        "dataset_sha256": digest(args.dataset), "script_sha256": digest(Path(__file__)),
        "source_commit": git_value(args.source_root, "rev-parse", "HEAD"),
        "source_dirty": git_value(args.source_root, "status", "--porcelain"),
        "source_sha256": hashes,
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "cpu": cpu_model(), "logical_cpu_count": os.cpu_count(),
                        "dependencies": dependencies},
        "semantic": {"enabled": not args.lexical_only and not args.store_only, "model": MODEL_NAME,
                     "revision": MODEL_REVISION, "minimum_cosine": 0.45,
                     "threads": 2, "provider": "CPUExecutionProvider"},
        "methods": {"lexical": "production rank_memories without semantic scores",
                    "semantic": "production SemanticMemoryRetriever threshold and cosine order",
                    "rrf": "production rank_memories with the same prepared semantic scores"},
        "scope": "retrieval + actual ExpressionRequest; optional separate real SQLite context microbenchmark",
        "not_measured": ["generative answer accuracy", "provider tokens", "API response latency",
                         "real user distribution", "phone or Windows device performance"],
        "filler_note": data["filler_note"], "runs": []
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def checkpoint():
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for size in args.sizes:
        entries = make_entries(data, size, EmotionalMemoryEntry)
        for query in data["queries"]:
            allowed = eligible(entries, data, query)
            if not set(query["gold_ids"]) <= {item.memory_id for item in allowed}:
                raise ValueError(f"Ineligible gold in {query['id']}")
        texts = [entry.title + " " + entry.summary for entry in entries]
        run = {"size": size, "unique_texts": len(set(texts)),
               "summary_chars": distribution(len(entry.summary) for entry in entries),
               "filler_count": size - len(data["memories"]), "filler_template_count": len(data["filler_templates"]),
               "rss_before_mib": rss_mib(), "rows": []}
        result["runs"].append(run)
        for query in ([] if args.store_only else data["queries"]):
            current = eligible(entries, data, query)
            ranked, rank_ms = timed(lambda: rank_memories(current, query["text"], now=data["now"],
                                                         scope=query.get("scope", "companion")))
            scored = [(entry, {"relevance": score.relevance, "semantic": score.semantic,
                               "total": score.total, "fusion": score.fusion}) for entry, score in ranked]
            run["rows"].append(score_row("lexical", query, scored, {entry.memory_id for entry in current},
                                         data, 0.0, rank_ms, True,
                                         MemoryContextBundle, CoreBondProfile, ExpressionRequest))
        semantic = None
        if not args.lexical_only and not args.store_only:
            semantic = SemanticMemoryRetriever(cache_dir=args.model_cache,
                                                character_id=data["character_id"], owner_id=data["owner_id"],
                                                local_files_only=args.local_files_only)
            _, run["model_load_ms"] = timed(lambda: semantic.warmup().result(timeout=600))
            bootstrap = {"text": "初始化本地检索", "scope": "companion"}
            initial = eligible(entries, data, bootstrap)
            _, run["initial_index_prepare_ms"] = timed(lambda: semantic.prepare(bootstrap["text"], entries, now=data["now"]).result(timeout=600))
            previous_ids = {entry.memory_id for entry in initial}
            run["initial_index_entries"] = semantic.status["indexed_entries"]
            run["rss_after_index_mib"] = rss_mib()
            print(json.dumps({"event": "indexed", "size": size, "index_ms": run["initial_index_prepare_ms"],
                              "entries": run["initial_index_entries"]}), flush=True)
            for index, query in enumerate(data["queries"]):
                current = eligible(entries, data, query)
                current_ids = {entry.memory_id for entry in current}
                warm = current_ids <= previous_ids
                _, prepare_ms = timed(lambda: semantic.prepare(query["text"], entries, now=data["now"],
                                                               scope=query.get("scope", "companion")).result(timeout=600))
                scores = semantic(query["text"], current)
                by_id = {entry.memory_id: entry for entry in current}
                def semantic_rank():
                    return [(by_id[key], {"semantic": value}) for key, value in
                            sorted(scores.items(), key=lambda item: item[1], reverse=True)[:4]]
                ranked, rank_ms = timed(semantic_rank)
                run["rows"].append(score_row("semantic", query, ranked, current_ids, data, prepare_ms,
                                             rank_ms, warm, MemoryContextBundle, CoreBondProfile, ExpressionRequest))
                ranked, rank_ms = timed(lambda: rank_memories(current, query["text"], now=data["now"],
                                                             scope=query.get("scope", "companion"), semantic_scores=scores))
                scored = [(entry, {"relevance": score.relevance, "semantic": score.semantic,
                                   "total": score.total, "fusion": score.fusion}) for entry, score in ranked]
                run["rows"].append(score_row("rrf", query, scored, current_ids, data, prepare_ms,
                                             rank_ms, warm, MemoryContextBundle, CoreBondProfile, ExpressionRequest))
                previous_ids = current_ids
                if (index + 1) % 10 == 0:
                    print(json.dumps({"event": "queries", "size": size, "done": index + 1}), flush=True)
            # Scope-switch rebuild time belongs to its own category, not warm p95.
            run["scope_rebuild_queries"] = [{"id": row["query_id"], "prepare_ms": row["prepare_ms"]}
                                            for row in run["rows"] if row["route"] == "rrf" and not row["index_warm"]]
        try:
            run["store_probe"] = store_probe(entries, data, args, semantic,
                                             EmotionalMemoryStore, EmotionalMemoryService, ExpressionRequest)
        finally:
            if semantic is not None:
                semantic.close()
        routes = sorted({row["route"] for row in run["rows"]})
        run["summary"] = {route: summarize([row for row in run["rows"] if row["route"] == route])
                          for route in routes}
        run["by_family"] = {route: {
            family: summarize([row for row in run["rows"] if row["route"] == route and row["family"] == family])
            for family in sorted({row["family"] for row in run["rows"]})} for route in routes}
        run["bad_cases"] = [{"query_id": row["query_id"], "family": row["family"], "route": row["route"],
                             "gold_ids": row["gold_ids"], "retrieved_ids": row["retrieved_ids"]}
                            for row in run["rows"] if row["ineligible_ids"] or row["no_answer_injection"]
                            or (row["gold_ids"] and row["recall_at_4"] < 1)]
        run["rss_after_mib"] = rss_mib()
        checkpoint()
        print(json.dumps({"event": "complete_size", "size": size, "summary": run["summary"]}), flush=True)
    final_hashes = {name: digest(args.source_root / "src/guanghe_companion" / name) for name in source_files}
    result["source_unchanged_during_run"] = hashes == final_hashes
    if hashes != final_hashes:
        result["source_sha256_after"] = final_hashes
        result["status"] = "source_changed_during_run_do_not_compare_as_frozen_revision"
    checkpoint()
    print(json.dumps({"output": str(args.output), "status": result["status"]}), flush=True)


if __name__ == "__main__":
    main()
