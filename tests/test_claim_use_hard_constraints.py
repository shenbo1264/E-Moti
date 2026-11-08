import json
from dataclasses import replace
import pytest

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


@pytest.mark.parametrize("route", ["fact", "episode"])
def test_explicit_negative_occurrence_on_plan_is_current_status_not_completed_event(route):
    query = "我现在算参加过了吗？"
    source = replace(planned_source(), summary="预约已确认，用户尚未参加。")
    plan = MemoryRetrievalRouter(time_basis="logical").plan(query, now=10)
    raw = json.dumps({"intents": [{"route": route, "question": query,
        "claim_use": "current_attribute", "status": "sufficient",
        "evidence": [{"id": "plan", "quote": "用户尚未参加。"}]}]}, ensure_ascii=False)
    result = validate_judgment(raw, query=query, plan=plan, entries=(source,), now=10,
        owner_id="owner", character_id="character")
    assert result.source_ids == ("plan",)
    assert result.statuses == ("sufficient",)
    assert result.plan.intents[0].temporal_mode == "current"
    assert result.plan.intents[0].route == "fact"


def test_context_declaration_does_not_downgrade_complete_subquestions():
    query = "我要中途离开，按约定找谁说，必须说明理由吗？"
    source = replace(planned_source(), summary="用户离开前告知队长，无需说明理由。", metadata={})
    plan = MemoryRetrievalRouter(time_basis="logical").plan(query, now=10)
    raw = json.dumps({"intents": [{"route": "fact", "question": question,
        "claim_use": "current_attribute", "status": "sufficient",
        "evidence": [{"id": "plan", "quote": source.summary}]}
        for question in ("中途离开，按约定找谁说", "必须说明理由吗")]}, ensure_ascii=False)
    result = validate_judgment(raw, query=query, plan=plan, entries=(source,), now=10,
        owner_id="owner", character_id="character")
    assert result.statuses == ("sufficient", "sufficient")


def test_information_request_is_not_discarded_as_context_declaration():
    query = "我要了解预约结果，我的活动在哪？"
    source = replace(planned_source(), summary="用户的活动在展馆。", metadata={})
    plan = MemoryRetrievalRouter(time_basis="logical").plan(query, now=10)
    raw = json.dumps({"intents": [{"route": "fact", "question": "我的活动在哪",
        "claim_use": "current_attribute", "status": "sufficient",
        "evidence": [{"id": "plan", "quote": source.summary}]}]}, ensure_ascii=False)
    result = validate_judgment(raw, query=query, plan=plan, entries=(source,), now=10,
        owner_id="owner", character_id="character")
    assert "insufficient" in result.statuses


def test_uncertainty_or_instruction_on_plan_does_not_prove_nonoccurrence():
    query = "我现在算参加过了吗？"
    plan = MemoryRetrievalRouter(time_basis="logical").plan(query, now=10)
    for text in ("预约已确认。", "用户尚未确认是否参加。", "不能记为已经参加。",
                 "如果用户尚未参加，就保留预约。", "不要写用户尚未参加。",
                 "用户有没有参加还不确定。", "不知道用户有没有参加。", "用户没有参加吗？",
                 "用户尚未参加这件事还不确定。"):
        source = replace(planned_source(), summary=text)
        raw = json.dumps({"intents": [{"route": "fact", "question": query,
            "claim_use": "current_attribute", "status": "sufficient",
            "evidence": [{"id": "plan", "quote": text}]}]}, ensure_ascii=False)
        result = validate_judgment(raw, query=query, plan=plan, entries=(source,), now=10,
            owner_id="owner", character_id="character")
        assert not result.source_ids, text
