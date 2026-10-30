from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.emotional_memory_retrieval import lexical_similarity
from guanghe_companion.semantic_memory import SemanticMemoryRetriever


FACTS = [
    ("allergy", "饮食边界", "我对花生过敏，不能吃含有花生的食品。"),
    ("rest", "放松方式", "我喜欢在树林里慢慢走路，听鸟叫声。"),
    ("noise", "休息边界", "晚上睡觉时我需要安静，不喜欢大声的音乐。"),
    ("pet", "宠物", "我的猫叫芝麻，今年两岁。"),
]
PROBES = [
    ("点餐时应该避开什么食材？", "allergy"),
    ("心情烦躁时有什么适合我的舒缓活动？", "rest"),
    ("准备就寝了，周围环境怎样才合适？", "noise"),
    ("如何计算三角形的面积？", None),
    ("月球为什么总有一面朝向地球？", None),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "artifacts/codex_handoff/embedding-models")
    args = parser.parse_args()
    scratch = ROOT / "artifacts/codex_handoff/semantic-benchmark"
    scratch.mkdir(parents=True, exist_ok=True)
    retriever = SemanticMemoryRetriever(cache_dir=args.cache_dir, character_id="xingxi_pixel_pet", owner_id="local_user")
    started = time.perf_counter()
    retriever.warmup().result(timeout=600)
    load_ms = (time.perf_counter() - started) * 1000
    try:
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            service = EmotionalMemoryService(root=Path(folder), character_id="xingxi_pixel_pet")
            memories = {}
            for alias, title, text in FACTS:
                memories[alias] = service.remember(kind="玩家希望被记住", title=title, summary=text,
                                                   source="explicit_user_request", now=100)
            results = []
            for query, expected in PROBES:
                service.semantic_retriever = None
                lexical = service.recall(query, now=101)
                entries = tuple(service.store.load_memories())
                started = time.perf_counter()
                retriever.prepare(query, entries, now=101).result(timeout=90)
                preparation_ms = (time.perf_counter() - started) * 1000
                service.semantic_retriever = retriever
                combined = service.recall(query, now=101)
                expected_id = memories[expected].memory_id if expected else None
                results.append({"query": query, "expected": expected,
                                "lexical": [entry.title for entry in lexical],
                                "combined": [entry.title for entry in combined],
                                "cosines": retriever.last_cosines,
                                "fusion_scores_above_threshold": retriever(query, entries),
                                "target_lexical_similarity": lexical_similarity(query, memories[expected].summary) if expected else None,
                                "lexical_pass": expected_id in {entry.memory_id for entry in lexical} if expected else not lexical,
                                "combined_pass": expected_id in {entry.memory_id for entry in combined} if expected else not combined,
                                "preparation_ms": preparation_ms})
            report = {"model": retriever.status["model"], "backend": "FastEmbed 0.9.1 / ONNX Runtime CPU",
                      "minimum_cosine": retriever.minimum_cosine, "load_or_download_ms": load_ms,
                      "facts": FACTS, "results": results,
                      "lexical_pass": sum(row["lexical_pass"] for row in results),
                      "combined_pass": sum(row["combined_pass"] for row in results), "total": len(results),
                      "scope": "synthetic development probes; real local embedding, no generation model"}
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({key: report[key] for key in ("model", "lexical_pass", "combined_pass", "total")}, ensure_ascii=True))
    finally:
        retriever.close()


if __name__ == "__main__":
    main()
