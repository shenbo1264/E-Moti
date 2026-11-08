from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import replace
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sqlite3
import statistics
import sys
import tempfile
import time
import tracemalloc

from guanghe_companion.emotional_memory import EmotionalMemoryEntry, EmotionalMemoryStore


def records(size, *, corpus_profile="short"):
    topics = ("散步看落日", "一起做晚饭", "修复部署错误", "阅读天文学", "游玩合作游戏", "练习电吉他")
    rows = []
    for index in range(size):
        name = f"联系人{index:05d}"
        summary = (f"用户的联系人{index:05d}叫{name}。那天我们讨论{topics[index % len(topics)]}，"
                   "用户明确说明这段经历和自己的习惯有关。记录保留原始来源、发生时间以及独立的角色命名空间。"
                   + "后续根据真实反馈继续调整。" * (index % 4))
        metadata = {"speaker": "user", "fact_subject": f"relation:联系人{index:05d}",
                    "fact_predicate": "name", "fact_value": name,
                    "fact_slot": f"relation:联系人{index:05d}:name"}
        if corpus_profile == "long-source":
            details = ("讨论时我们把各自的想法分开记录，对不确定的地方没有作出结论。"
                       "我希望以后能找到这段交流的原文，尤其是提到具体条件和个人选择的部分。"
                       "这次只描述当时的经历，没有把建议或计划当成已经完成的事情。")
            summary = (summary + details)[:180 + index % 61]
            target_length = (512, 1024, 2048)[index % 3]
            metadata["original_quote"] = (summary + details * (target_length // len(details) + 1))[:target_length]
        rows.append(EmotionalMemoryEntry(
            memory_id=f"record-{index:05d}", character_id="xingxi_pixel_pet", owner_id="local_user",
            kind="用户自述", title=f"人物姓名 {index:05d}", summary=summary, source="user_chat",
            occurred_at=1000 + index, created_at=1000 + index, updated_at=1000 + index,
            source_ids=(f"chat:{index:05d}",), tags=(topics[index % len(topics)], "真实数据库基准"),
            metadata=metadata))
    return rows


def distribution(values):
    ordered = sorted(values)
    return {"n": len(values), "p50_ms": statistics.median(values),
            "p95_ms": ordered[max(0, math.ceil(len(values) * .95) - 1)],
            "minimum_ms": ordered[0], "maximum_ms": ordered[-1], "samples_ms": values}


def measure(fn, count):
    values = []
    for _ in range(count):
        started = time.perf_counter_ns()
        fn()
        values.append((time.perf_counter_ns() - started) / 1_000_000)
    return distribution(values)


def peak_memory(fn):
    gc.collect()
    tracemalloc.start()
    fn()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


def source_hashes():
    root = Path(sys.modules[EmotionalMemoryStore.__module__].__file__).resolve().parent
    names = ("emotional_memory.py", "memory_document.py", "memory_index.py", "memory_index_schema.py",
             "retrieval_fact_schema.py", "chat_memory.py", "grounded_facts.py", "memory_correction.py")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in names if (root / name).exists()}


def benchmark_size(size, *, backend, repeats, writes, corpus_profile="short"):
    if backend == "index":
        from guanghe_companion.memory_index import IndexedMemoryQuery
    corpus = records(size, corpus_profile=corpus_profile)
    canonical = json.dumps([row.to_dict() for row in corpus], ensure_ascii=False, sort_keys=True)
    now = 100_000
    ids = tuple(f"record-{index:05d}" for index in (5, 42, size // 2, size - 1))
    temporary_root = Path(__file__).resolve().parents[1] / "artifacts/codex_handoff/storage-profile-temp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="emoti-index-bench-", dir=temporary_root) as directory:
        store = EmotionalMemoryStore(directory, "xingxi_pixel_pet")
        started = time.perf_counter_ns()
        store.save_memories(corpus)
        initial_write = (time.perf_counter_ns() - started) / 1_000_000

        def snapshot():
            if backend == "index":
                return store.read_indexed_snapshot(IndexedMemoryQuery(memory_ids=ids, limit=4),
                    now=now, include_chapters=False, include_profile_sources=False)
            return store.read_context_snapshot(now=now)

        def selected(value):
            return tuple(entry for entry in value.entries if entry.memory_id in ids)

        def finalize(value):
            method = store.finalize_indexed_recall if backend == "index" else store.finalize_recall
            result = method(selected(value), expected_epoch=value.context_epoch, now=now)
            assert result is not None and {entry.memory_id for entry in result} == set(ids)
            return result

        def context():
            return finalize(snapshot())

        value = snapshot()
        assert {entry.memory_id for entry in selected(value)} == set(ids)
        before_size = store.state_path.stat().st_size
        result = {
            "count": size, "backend": backend, "corpus_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "summary_chars": {"min": min(len(r.summary) for r in corpus),
                "median": statistics.median(len(r.summary) for r in corpus), "max": max(len(r.summary) for r in corpus)},
            "corpus_profile": corpus_profile,
            "source_chars": {"min": min(len(r.metadata.get("original_quote", "")) for r in corpus),
                "median": statistics.median(len(r.metadata.get("original_quote", "")) for r in corpus),
                "max": max(len(r.metadata.get("original_quote", "")) for r in corpus)},
            "serialized_corpus_bytes": len(canonical.encode()), "initial_save_ms": initial_write,
            "db_bytes": before_size, "selected_evidence_count": len(ids),
            "warm_snapshot": measure(snapshot, repeats),
            "warm_finalize_four": measure(lambda: finalize(value), repeats),
            "warm_snapshot_and_finalize": measure(context, repeats),
            "snapshot_python_tracemalloc_peak_bytes": peak_memory(snapshot),
        }
        if backend == "index":
            exact_query = IndexedMemoryQuery(subjects=("relation:联系人00042",), predicates=("name",), limit=4)
            lexical_query = IndexedMemoryQuery(query="联系人00042", limit=4)
            empty_query = IndexedMemoryQuery(memory_ids=())

            def exact():
                value = store.read_indexed_snapshot(exact_query, now=now, include_chapters=False,
                    include_profile_sources=False)
                assert [row.memory_id for row in value.entries] == ["record-00042"]
                return value

            result["structured_exact"] = measure(exact, repeats)
            result["structured_stage_timings_one_sample_ms"] = exact().timings
            result["lexical_fts"] = measure(lambda: store.read_indexed_snapshot(lexical_query, now=now,
                include_chapters=False, include_profile_sources=False), repeats)
            result["empty_lookup"] = measure(lambda: store.read_indexed_snapshot(empty_query, now=now,
                include_chapters=False, include_profile_sources=False), repeats)
            result["context_epoch_only"] = measure(lambda: store.current_context_epoch(now=now), repeats)
            manifest = store.index_manifest(now=now, limit=10000)
            result["manifest_full"] = measure(lambda: store.index_manifest(now=now, limit=10000), repeats)
            result["manifest_unchanged_delta"] = measure(lambda: store.index_manifest(now=now,
                after_revision=manifest.revision), repeats)
            result["rows_decoded_for_four"] = snapshot().rows_loaded
            with closing(sqlite3.connect(store.state_path)) as connection:
                connection.execute("DROP TABLE memory_index_entries")
            started = time.perf_counter_ns()
            snapshot()
            result["cold_projection_rebuild_ms"] = (time.perf_counter_ns() - started) / 1_000_000

        corrected = []
        correction_times, forget_times = [], []
        for index in range(writes):
            original = corpus[20 + index]
            replacement = replace(original, memory_id=f"corrected-{index}",
                summary=f"用户的联系人{20 + index:05d}叫更正联系人{index}。",
                metadata={**original.metadata, "fact_value": f"更正联系人{index}"})
            started = time.perf_counter_ns()
            corrected.append(store.replace_memory(original.memory_id, replacement, now=now + 1))
            correction_times.append((time.perf_counter_ns() - started) / 1_000_000)
        for row in corrected:
            started = time.perf_counter_ns()
            store.forget_memory(row.memory_id, now=now + 2)
            forget_times.append((time.perf_counter_ns() - started) / 1_000_000)
        result["correction"] = distribution(correction_times)
        result["forget"] = distribution(forget_times)
        result["expiry_not_due"] = measure(
            (lambda: store.expire_memories_indexed(now=now)) if backend == "index" else
            (lambda: store.expire_memories(now=now)), repeats)
        result["final_db_bytes"] = store.state_path.stat().st_size
        return result


def main():
    parser = argparse.ArgumentParser(description="同语料真实 SQLite 读取与写入测量，不接触用户存档")
    parser.add_argument("--backend", choices=("index", "document"), default="index")
    parser.add_argument("--sizes", default="300,3000,10000")
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--writes", type=int, default=3)
    parser.add_argument("--corpus-profile", choices=("short", "long-source"), default="short")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1 or args.writes < 1:
        parser.error("repeats and writes must be positive")
    cpu = ""
    if Path("/proc/cpuinfo").exists():
        cpu = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                    if line.startswith("model name")), "")
    report = {
        "schema": "emoti.memory.sqlite.performance.v1", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backend": args.backend, "environment": {"python": sys.version, "sqlite": sqlite3.sqlite_version,
            "platform": platform.platform(), "cpu": cpu, "logical_cpus": os.cpu_count(),
            "module_path": str(Path(sys.modules[EmotionalMemoryStore.__module__].__file__).resolve()),
            "timing_clock": "perf_counter_ns", "shared_runner": True},
        "method": "Same synthetic corpus, four evidence IDs, no LLM/embedding; document baseline must use prerequisite PYTHONPATH. Warm OS cache, tracemalloc measured separately, no user saves.",
        "not_run": ["real_model_request", "desktop_interaction", "embedding_quality", "physical_forget_erasure"],
        "source_hashes_start": source_hashes(),
        "results": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for size in map(int, args.sizes.split(",")):
        if size < 50:
            parser.error("sizes must be at least 50")
        report["results"].append(benchmark_size(size, backend=args.backend, repeats=args.repeats,
                                               writes=args.writes, corpus_profile=args.corpus_profile))
        report["source_hashes_end"] = source_hashes()
        report["storage_source_unchanged"] = report["source_hashes_start"] == report["source_hashes_end"]
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        row = report["results"][-1]
        print(json.dumps({"count": size, "backend": args.backend,
            "snapshot_p50_ms": row["warm_snapshot"]["p50_ms"],
            "context_p50_ms": row["warm_snapshot_and_finalize"]["p50_ms"],
            "correction_p50_ms": row["correction"]["p50_ms"], "output": str(args.output)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
