import argparse
import cProfile
import json
from pathlib import Path
import pstats
import tempfile
from time import perf_counter

from benchmark_memory_index import records, source_hashes
from guanghe_companion.emotional_memory_service import EmotionalMemoryService


def measure(call):
    profile = cProfile.Profile()
    started = perf_counter()
    result = profile.runcall(call)
    elapsed_ms = (perf_counter() - started) * 1000
    stats = pstats.Stats(profile)
    rows = [{"file": filename, "line": line, "function": function, "calls": values[1],
             "self_ms": values[2] * 1000, "cumulative_ms": values[3] * 1000}
            for (filename, line, function), values in stats.stats.items()]
    rows.sort(key=lambda row: row["cumulative_ms"], reverse=True)
    return result, {"elapsed_ms_with_profiling": elapsed_ms, "functions": rows}


def main():
    parser = argparse.ArgumentParser(description="定位真实记忆更正/遗忘的CPU成本；profile开销不作为用户时延")
    parser.add_argument("--size", type=int, default=3000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.size < 50:
        parser.error("size must be at least 50")
    temporary_root = Path(__file__).resolve().parents[1] / "artifacts/codex_handoff/storage-profile-temp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    report = {"size": args.size, "corpus_profile": "long-source", "source_hashes": source_hashes(),
              "measurement": "real SQLite and service methods under cProfile; synthetic data only"}
    with tempfile.TemporaryDirectory(prefix="emoti-write-profile-", dir=temporary_root) as directory:
        memory = EmotionalMemoryService(root=directory, character_id="xingxi_pixel_pet")
        memory.store.save_memories(records(args.size, corpus_profile="long-source"))
        corrected, report["correction"] = measure(lambda: memory.correct(
            "record-00020", title="人物姓名", summary="用户的联系人00020叫更正联系人。", now=100000))
        _, report["forget"] = measure(lambda: memory.forget(corrected.memory_id, now=100001))
    report["source_unchanged"] = report["source_hashes"] == source_hashes()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
