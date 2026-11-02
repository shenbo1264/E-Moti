import json
from datetime import datetime, timezone

import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_evidence_judgment import MemoryEvidenceJudge


def stamp(day):
    return int(datetime(2026, 3, day, tzinfo=timezone.utc).timestamp())


@pytest.mark.parametrize("source_day,expected", [(12, True), (13, False)])
def test_dated_plan_delivery_checks_actual_source_date(tmp_path, source_day, expected):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet", time_basis="unix")
    entry = service.remember(kind="用户事实", title="2026年3月12日我预约的是什么", summary=f"用户预约2026年3月{source_day}日参加陶印课程。",
        source="explicit_user_request", now=stamp(1), metadata={"event_status": "planned",
        "fact_subject": "user:self", "fact_predicate": "预约项目", "fact_value": "陶印课程"})
    query = "2026年3月12日我预约的是什么？"
    service.evidence_judge = MemoryEvidenceJudge(lambda prompt: json.dumps({"intents": [{"route": "fact",
        "question": query, "status": "sufficient", "evidence": [{"id": entry.memory_id, "quote": entry.summary}]}]}, ensure_ascii=False))
    try:
        service.prepare_retrieval(query, now=stamp(5)).result(timeout=5)
        result = service.retrieve(query, now=stamp(5))
        ids = {row.memory_id for row in result.bundle.memories}
        assert (entry.memory_id in ids) is expected, (service.evidence_judge.status, result.trace)
    finally:
        service.evidence_judge.close()


def test_expired_plan_can_only_answer_its_historical_date(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet", time_basis="unix")
    entry = service.remember(kind="用户事实", title="2026年3月12日我预约的是什么", summary="用户预约2026年3月12日参加陶印课程。",
        source="explicit_user_request", now=stamp(1), valid_from=stamp(1), valid_until=stamp(14),
        metadata={"event_status": "planned", "fact_subject": "user:self", "fact_predicate": "预约项目", "fact_value": "陶印课程"})
    state = {"query": "2026年3月12日我预约的是什么？"}
    service.evidence_judge = MemoryEvidenceJudge(lambda prompt: json.dumps({"intents": [{"route": "fact",
        "question": state["query"], "status": "sufficient", "evidence": [{"id": entry.memory_id, "quote": entry.summary}]}]}, ensure_ascii=False))
    try:
        service.prepare_retrieval(state["query"], now=stamp(20)).result(timeout=5)
        assert entry.memory_id in {row.memory_id for row in service.retrieve(state["query"], now=stamp(20)).bundle.memories}
        state["query"] = "我现在预约的是什么？"
        service.prepare_retrieval(state["query"], now=stamp(20)).result(timeout=5)
        assert entry.memory_id not in {row.memory_id for row in service.retrieve(state["query"], now=stamp(20)).bundle.memories}
    finally:
        service.evidence_judge.close()


def test_recording_date_does_not_prove_scheduled_date(tmp_path):
    from guanghe_companion.retrieval_evidence import check_eligibility
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet", time_basis="unix")
    entry = service.remember(kind="用户事实", title="预约",
        summary="用户2026年3月12日登记，预约2026年3月13日参加陶印课程。",
        source="explicit_user_request", now=stamp(1), metadata={"event_status": "planned"})
    intent = service.retrieval_router.plan("2026年3月12日我预约的是什么？", now=stamp(5)).intents[0]
    decision = check_eligibility(entry, intent, now=stamp(5), owner_id=service.owner_id, character_id=service.character_id)
    assert decision is not None and not decision.accepted


def test_undated_historical_booking_does_not_turn_into_current_plan():
    from guanghe_companion.retrieval_router import MemoryRetrievalRouter
    intent = MemoryRetrievalRouter().plan("我以前预约的是什么？", now=stamp(20)).intents[0]
    assert intent.temporal_mode == "history"
