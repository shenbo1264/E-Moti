"""Pinned real-BGE restart/mutation benchmark with independent processes.

Synthetic text only. This measures indexing and cache maintenance, not answer
quality, persona behavior or a production service-level objective. A parent
retains one temporary SQLite database across three fresh child processes per
scale, then removes that synthetic database after saving all measurements.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import sqlite3
import statistics
import subprocess
import sys
import tempfile
from time import perf_counter


TEMPLATES = (
    "用户在周末练习摄影，记录公园里的飞鸟、花朵与光线变化。这条记录来自用户明确分享的日常兴趣，描述一次已完成的活动。",
    "我们一起整理了书桌上的书籍与便签，给常用工具安排了固定位置。桌面互动事件已完成，来源记录保留了发生时间。",
    "用户喜欢清淡口味，平时会选择不加糖的茶饮。偏好来源是用户的直接陈述，没有推断健康状况或未说过的饮食禁忌。",
    "一次共同学习结束后，我们回顾了三个问题的解决过程，记录了检查条件和验证结果。这段经历来自已完成的互动事件。",
    "用户分享了喜欢的音乐类型和练习乐器的习惯，明确说这些是休息时的兴趣。这里没有记录任何外部软件的临时执行状态。",
    "共同游戏的一局顺利结束，我们记下了合作时发现的小技巧和使用道具的时机。该结果有真实的本地事件标识作为来源。",
)
SOURCE_FILES = (
    "semantic_memory.py", "memory_vector_cache.py", "memory_index.py", "memory_index_schema.py",
    "memory_document.py", "emotional_memory.py", "emotional_memory_service.py",
)
QUERY = "我们上次共同游戏留下什么经验"
WARM_QUERIES = ("周末喜欢做什么活动", "一起学习时解决了哪些问题", "有哪些日常饮品偏好")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_result(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def cache_size(store):
    with sqlite3.connect(store.state_path) as connection:
        rows, blob_bytes = connection.execute("SELECT COUNT(*),COALESCE(SUM(length(vector)),0) FROM memory_vector_cache").fetchone()
        page_size = connection.execute("PRAGMA page_size").fetchone()[0]
        pages = connection.execute("PRAGMA page_count").fetchone()[0]
        free = connection.execute("PRAGMA freelist_count").fetchone()[0]
    return {"rows": rows, "vector_blob_bytes": blob_bytes, "database_bytes": store.state_path.stat().st_size,
            "sqlite_page_size": page_size, "sqlite_pages": pages, "sqlite_freelist_pages": free}


def child(args):
    sys.path.insert(0, str(args.source_root / "src"))
    from guanghe_companion.emotional_memory import EmotionalMemoryEntry
    from guanghe_companion.emotional_memory_service import EmotionalMemoryService
    from guanghe_companion.semantic_memory import SemanticMemoryRetriever, MODEL_NAME, MODEL_REVISION, MODEL_DIMENSIONS
    hashes = {name: digest(args.source_root / "src/guanghe_companion" / name) for name in SOURCE_FILES}
    memory = EmotionalMemoryService(root=args.state_root, character_id="xingxi_pixel_pet")
    now = args.size + 100
    result = {"phase": args.phase, "size": args.size, "pid": os.getpid(), "source_sha256": hashes,
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "script_sha256": digest(Path(__file__)),
        "model": {"name": MODEL_NAME, "revision": MODEL_REVISION, "dimensions": MODEL_DIMENSIONS,
                  "provider": "CPUExecutionProvider", "inference_threads": 2},
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
            "logical_cpus": os.cpu_count(), "openblas_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
            "omp_threads": os.environ.get("OMP_NUM_THREADS"), "packages": {name: importlib.metadata.version(name)
                for name in ("fastembed", "numpy", "onnxruntime", "huggingface-hub")}}}
    if args.phase == "cold":
        entries = [EmotionalMemoryEntry(memory_id=f"synthetic-{i:06d}", character_id=memory.character_id,
            owner_id=memory.owner_id, kind="玩家希望被记住", title=f"合成记忆{i}",
            summary=TEMPLATES[i % len(TEMPLATES)] + f" 记录编号{i}。", source="explicit_user_request",
            occurred_at=i + 1, created_at=i + 1, updated_at=i + 1, source_ids=(f"synthetic:{i}",))
            for i in range(args.size)]
        entries[0] = replace(entries[0], summary="用户喜欢绿茶", metadata={"speaker": "user",
            "fact_slot": "preference:饮料偏好:like", "fact_domain": "饮料偏好", "fact_value": "绿茶"})
        started = perf_counter()
        memory.store.save_memories(entries)
        result["seed_sqlite_ms"] = (perf_counter() - started) * 1000
        result["corpus"] = {"source": "synthetic six-template Chinese text; no private data",
            "min_chars": min(len(e.summary) for e in entries), "median_chars": statistics.median(len(e.summary) for e in entries),
            "max_chars": max(len(e.summary) for e in entries), "all_current_companion": True,
            "current_entries": args.size, "vector_distance": "normalized float32 exact cosine"}
    else:
        now += 5 if args.phase == "reopen_verify" else 0
    retriever = SemanticMemoryRetriever(cache_dir=args.model_cache, character_id=memory.character_id,
        owner_id=memory.owner_id, local_files_only=True)
    try:
        started = perf_counter()
        retriever.warmup().result(timeout=120)
        result["model_load_ms"] = (perf_counter() - started) * 1000
        if args.phase == "reopen_verify":
            def reject_passages(*unused, **kwargs):
                raise AssertionError("a restart must not reencode current persisted passages")
            retriever._model.passage_embed = reject_passages
            result["passage_encoder_guard"] = "raises_if_called"
        def run(query, instant):
            started = perf_counter()
            retriever.prepare_indexed(query, memory.store, now=instant).result(timeout=360)
            return {"wall_ms": (perf_counter() - started) * 1000, "status": retriever.status,
                    "top_ids": list(retriever.candidate_ids(query, limit=4))}
        result["first_query"] = run(QUERY, now)
        result["model_load_plus_first_query_ms"] = result["model_load_ms"] + result["first_query"]["wall_ms"]
        result["cache_after_first"] = cache_size(memory.store)
        result["warm_queries"] = [run(query, now) for query in WARM_QUERIES]
        result["warm_wall_p50_ms"] = statistics.median(row["wall_ms"] for row in result["warm_queries"])
        result["warm_wall_max_ms"] = max(row["wall_ms"] for row in result["warm_queries"])
        expected = args.size - int(args.phase == "reopen_verify")
        first = result["first_query"]["status"]
        assert first["last_encoded_entries"] == (args.size if args.phase == "cold" else 0)
        assert first["persistent_cache_hits"] == (0 if args.phase == "cold" else expected)
        assert first["persistent_cache_writes"] == (args.size if args.phase == "cold" else 0)
        assert first["persistent_cache_errors"] == 0 and first["persistent_cache_pending"] == 0
        assert first["indexed_entries"] == expected
        assert all(row["status"]["last_encoded_entries"] == 0 for row in result["warm_queries"])
        if args.phase == "reopen_mutate":
            started = perf_counter()
            corrected = memory.correct("synthetic-000000", title="饮品偏好更正", summary="用户喜欢白茶", now=now + 1)
            result["correction_write_ms"] = (perf_counter() - started) * 1000
            result["cache_immediately_after_correction"] = cache_size(memory.store)
            assert result["cache_immediately_after_correction"]["rows"] == args.size - 1
            retriever.invalidate()
            result["correction"] = run("用户喜欢什么茶", now + 2)
            assert result["correction"]["status"]["last_encoded_entries"] == 1
            assert result["correction"]["status"]["persistent_cache_writes"] == 1
            assert "synthetic-000000" not in retriever.last_cosines
            started = perf_counter()
            memory.forget(corrected.memory_id, now=now + 3)
            result["forget_write_ms"] = (perf_counter() - started) * 1000
            result["cache_immediately_after_forget"] = cache_size(memory.store)
            assert result["cache_immediately_after_forget"]["rows"] == args.size - 1
            retriever.invalidate()
            result["forgotten"] = run("用户喜欢什么茶", now + 4)
            assert result["forgotten"]["status"]["last_encoded_entries"] == 0
            assert result["forgotten"]["status"]["persistent_cache_writes"] == 0
            assert "synthetic-000000" not in retriever.last_cosines and corrected.memory_id not in retriever.last_cosines
        result["cache_final"] = cache_size(memory.store)
        result["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        result["final_vector_bytes"] = sum(value.nbytes for value in retriever._vectors.values())
        result["final_matrix_cache_bytes"] = sum(value.nbytes for value in retriever._matrix_cache.values())
        result["assertions"] = "cold N / restart 0 / correction 1 / forget 0 passage encodes; transactionally revoked cache rows absent"
        result["source_unchanged_during_run"] = all(digest(args.source_root / "src/guanghe_companion" / name) == value
                                                   for name, value in hashes.items())
    finally:
        retriever.close()
    write_result(args.output, result)
    print(json.dumps({"size": args.size, "phase": args.phase, "first_ms": result["first_query"]["wall_ms"],
        "passage_encodes": result["first_query"]["status"]["last_encoded_entries"],
        "cache_hits": result["first_query"]["status"]["persistent_cache_hits"], "rss_mib": result["peak_rss_mib"]}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--model-cache", type=Path, required=True)
    parser.add_argument("--size", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--phase", choices=("cold", "reopen_mutate", "reopen_verify"))
    args = parser.parse_args()
    if args.phase:
        if args.size is None or args.state_root is None:
            parser.error("child phase requires --size and --state-root")
        return child(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    summaries = []
    for size in (args.size,) if args.size else (300, 3000, 10000):
        phases = {}
        with tempfile.TemporaryDirectory(prefix=f"emoti-persistent-bge-{size}-") as temporary:
            for phase in ("cold", "reopen_mutate", "reopen_verify"):
                path = args.output.with_name(f"{args.output.stem}-{size}-{phase}.json")
                command = [sys.executable, str(Path(__file__).resolve()), "--source-root", str(args.source_root),
                    "--model-cache", str(args.model_cache), "--size", str(size), "--output", str(path),
                    "--state-root", temporary, "--phase", phase]
                started = perf_counter()
                completed = subprocess.run(command, text=True, capture_output=True, timeout=420)
                process_wall_ms = (perf_counter() - started) * 1000
                path.with_suffix(".log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
                if completed.returncode:
                    raise RuntimeError(f"benchmark phase failed: {path.with_suffix('.log')}")
                data = json.loads(path.read_text(encoding="utf-8"))
                data["subprocess_wall_ms"] = process_wall_ms
                write_result(path, data)
                phases[phase] = data
                print(completed.stdout.strip(), flush=True)
            assert len({data["pid"] for data in phases.values()}) == 3
            assert len({json.dumps(data["source_sha256"], sort_keys=True) for data in phases.values()}) == 1
            assert all(data["source_unchanged_during_run"] for data in phases.values())
        summaries.append({"size": size, "phases": phases})
        write_result(args.output, {"status": "measured_real_sqlite_and_pinned_bge_synthetic_text",
            "runs": summaries, "independent_processes_per_scale": 3,
            "conditions": "coordinated absence of heavy parallel benchmarks; not exclusive CPU; 3 warm queries per phase, one correction/forget",
            "not_measured": ["LLM answer correctness", "persona behavior", "desktop user interaction", "production p95 SLO"]})


if __name__ == "__main__":
    main()
