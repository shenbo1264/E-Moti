import json
from dataclasses import replace

from guanghe_companion.emotional_memory import EmotionalMemoryEntry
from guanghe_companion.memory_evidence_judgment import validate_judgment
from guanghe_companion.retrieval_router import MemoryRetrievalRouter


def planned_source():
    return EmotionalMemoryEntry("plan", "character", "owner", "事实", "计划",
        "用户计划和伙伴去参观展馆。", "explicit_user_request", 1, 1, 1,
        metadata={"event_status": "planned", "fact_subject": "user:self"})


def validate(query, claim_use):
    source = planned_source()
    plan = MemoryRetrievalRouter(time_basis="logical").plan(query, now=10)
    raw = json.dumps({"intents": [{"route": "fact", "question": query,
        "claim_use": claim_use, "status": "sufficient",
        "evidence": [{"id": source.memory_id, "quote": source.summary}]}]}, ensure_ascii=False)
    result = validate_judgment(raw, query=query, plan=plan, entries=(source,), now=10,
        owner_id="owner", character_id="character")
    return plan, result


def test_shared_past_event_cannot_be_reclassified_as_plan():
    plan, result = validate("我们那次一起做了什么？", "planned_event")
    assert plan.intents[0].requires_shared_event
    assert plan.intents[0].temporal_mode != "planned"
    assert not result.source_ids


def test_personal_occurrence_cannot_be_reclassified_as_current_attribute():
    _, result = validate("我去过那个展馆吗？", "current_attribute")
    assert not result.source_ids


def test_genuine_shared_plan_remains_eligible():
    plan, result = validate("我们计划一起做什么？", "planned_event")
    assert plan.intents[0].temporal_mode == "planned"
    assert result.source_ids == ("plan",)


def test_experiential_relative_clause_does_not_block_current_attribute():
    for query in ("出过差的同事现在住哪？", "出过差的同事现在住深圳吗？"):
        source = replace(planned_source(), summary="用户的同事目前住深圳，并计划去观星。")
        plan = MemoryRetrievalRouter(time_basis="logical").plan(query, now=10)
        raw = json.dumps({"intents": [{"route": "fact", "question": query,
            "claim_use": "current_attribute", "status": "sufficient",
            "evidence": [{"id": source.memory_id, "quote": "同事目前住深圳"}]}]}, ensure_ascii=False)
        result = validate_judgment(raw, query=query, plan=plan, entries=(source,), now=10,
            owner_id="owner", character_id="character")
        assert result.source_ids == ("plan",)
