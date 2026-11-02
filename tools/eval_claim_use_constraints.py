import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_evidence_judgment import MemoryEvidenceJudge
from tools.eval_ondemand_generation import recorded_app_client, redact


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/codex_handoff/memory-upgrade/claim-use-constraints-flash"
CASES = (
    ("personal_occurrence", "我去过那个水族馆吗？", "用户计划去参观水族馆，尚未确认成行。", False),
    ("shared_past", "我们那次一起做了什么？", "用户计划和伙伴一起拼大型拼图。", False),
    ("shared_plan", "我们计划一起做什么？", "用户计划和伙伴一起练习陶艺。", True),
    ("independent_current_attribute", "摄像机目前放在哪里？", "用户计划送摄像机去保养，目前摄像机仍放在书房抽屉。", True),
)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=False)
    client, meter, metadata, secret = recorded_app_client(
        Path("C:/Users/19970/AppData/Local/E-Moti/expression_settings.json"), max_requests=8, max_output_tokens=4096)
    report = {"evaluation_kind": "targeted_development_regression_not_sealed",
        "measurement_scope": "真实Flash判据及最终来源交付；卡片标题保留原查询以控制候选可达性，不测候选召回泛化。不是最终角色生成评测。",
        "provider": metadata, "rows": []}
    for key, query, summary, expected in CASES:
        service = EmotionalMemoryService(root=OUTPUT / "archives" / key, character_id="xingxi_pixel_pet")
        entry = service.remember(kind="用户事实", title=query, summary=summary,
            source="explicit_user_request", source_ids=("development:" + key,), now=10,
            metadata={"event_status": "planned", "fact_subject": "user:self", "fact_predicate": "活动或设备状态"})
        judge = MemoryEvidenceJudge(client)
        service.evidence_judge = judge
        start_record = len(meter.records)
        started = perf_counter()
        try:
            service.prepare_retrieval(query, now=10).result(timeout=65)
            result = service.retrieve(query, now=10)
            ids = [item.memory_id for item in result.bundle.memories]
            report["rows"].append({"case": key, "query": query, "source": entry.to_dict(),
                "host_plan": asdict(service.retrieval_router.plan(query, now=10)),
                "expected_source_delivery": expected, "actual_delivered_ids": ids,
                "passed": (entry.memory_id in ids) is expected, "judge_status": judge.status,
                "trace": asdict(result.trace), "elapsed_ms": (perf_counter() - started) * 1000,
                "requests": redact(meter.records[start_record:], secret)})
            (OUTPUT / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(key, judge.status, report["rows"][-1]["passed"], flush=True)
        finally:
            judge.close()
    report["summary"] = {"passed": sum(row["passed"] for row in report["rows"]), "total": len(CASES)}
    (OUTPUT / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
