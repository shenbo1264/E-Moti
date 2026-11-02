import json
from dataclasses import replace

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_evidence_judgment import validate_judgment, resolve_judged_subjects
from guanghe_companion.retrieval_contract import RetrievalIntent, RetrievalPlan


def source(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = service.remember(kind="用户事实", title="器材", summary="用户计划送检望远镜，目前望远镜仍在书房。",
        source="explicit_user_request", now=10, metadata={"event_status": "planned", "fact_subject": "object:望远镜"})
    return service, entry


def validate(service, entry, query, plan, rows):
    return validate_judgment(json.dumps({"intents": rows}, ensure_ascii=False), query=query, plan=plan,
        entries=(entry,), now=10, owner_id=service.owner_id, character_id=service.character_id)


def row(entry, query, **extra):
    return {"route": "fact", "question": query, "status": "sufficient", "claim_use": "current_attribute",
        "evidence": [{"id": entry.memory_id, "quote": "目前望远镜仍在书房。"}], **extra}


def test_current_claim_on_plan_card_is_not_erased(tmp_path):
    service, entry = source(tmp_path)
    query = "望远镜现在在哪？"
    result = validate(service, entry, query, RetrievalPlan((RetrievalIntent("fact", query),)), [row(entry, query)])
    assert result.source_ids == (entry.memory_id,)


def test_colloquial_booking_claim_uses_plan_without_marking_event_complete(tmp_path):
    service, entry = source(tmp_path)
    query = "我约的是哪项检查？"
    result = validate(service, entry, query, RetrievalPlan((RetrievalIntent("bounded", query),)),
        [row(entry, query, claim_use="planned_event", evidence=[{"id": entry.memory_id, "quote": entry.summary}])])
    assert result.source_ids == (entry.memory_id,)
    assert result.plan.intents[0].temporal_mode == "planned"


def test_plan_cannot_prove_completed_or_shared_event(tmp_path):
    service, entry = source(tmp_path)
    for query in ("望远镜实际上送检完成了吗？", "我们共同完成了什么？"):
        result = validate(service, entry, query, RetrievalPlan((RetrievalIntent("episode", query, requires_shared_event=True),)),
            [row(entry, query)])
        assert not result.source_ids


def test_current_rule_and_hypothetical_setting_are_not_past_or_plan_states(tmp_path):
    service, entry = source(tmp_path)
    entry = replace(entry, metadata={"fact_subject": "object:望远镜"})
    for mode, query in (("history", "以前定的使用规则现在允许外借吗？"), ("planned", "准备观星时，原来的设置是什么？")):
        result = validate(service, entry, query, RetrievalPlan((RetrievalIntent("fact", query, temporal_mode=mode),)), [row(entry, query)])
        assert result.source_ids == (entry.memory_id,)
        assert result.plan.intents[0].temporal_mode == "current"


def test_optional_unrepresentable_alias_does_not_veto_supported_card(tmp_path):
    service, entry = source(tmp_path)
    entry = replace(entry, summary="观星组的小柳负责器材记录，小柳是柳岚的昵称。", metadata={"fact_subject": "group:观星组"})
    query = "器材记录找小柳吗？"
    result = validate(service, entry, query, RetrievalPlan((RetrievalIntent("fact", query, subjects=("器材记录",)),)),
        [row(entry, query, evidence=[{"id": entry.memory_id, "quote": entry.summary}],
            subject_binding={"mention": "小柳", "subject": "柳岚", "kind": "alias", "quote": entry.summary})])
    assert not resolve_judged_subjects(service.store, result, 0, now=10)[1]


def test_collective_original_spans_cover_question_without_appending_duplicate(tmp_path):
    service, entry = source(tmp_path)
    entry = replace(entry, metadata={"fact_subject": "object:望远镜"})
    query = "望远镜在哪里、什么颜色？"
    result = validate(service, entry, query, RetrievalPlan((RetrievalIntent("fact", query),)),
        [row(entry, "望远镜在哪里"), row(entry, "什么颜色")])
    assert len(result.plan.intents) == 2
    assert result.statuses == ("sufficient", "sufficient")


def test_current_claim_survives_final_delivery_and_is_revoked_with_source(tmp_path):
    from guanghe_companion.memory_evidence_judgment import MemoryEvidenceJudge
    service, entry = source(tmp_path)
    query = "望远镜现在在哪？"
    service.evidence_judge = MemoryEvidenceJudge(lambda prompt: json.dumps({"intents": [row(entry, query)]}, ensure_ascii=False))
    try:
        service.prepare_retrieval(query, now=10).result(timeout=5)
        assert entry.memory_id in {e.memory_id for e in service.retrieve(query, now=10).bundle.memories}
        service.forget(entry.memory_id, now=11)
        assert not service.retrieve(query, now=11).bundle.memories
    finally:
        service.evidence_judge.close()


def test_context_declaration_not_needed_is_chat_but_question_is_not(tmp_path):
    service, entry = source(tmp_path)
    declaration = "我想把望远镜带出去"
    result = validate(service, entry, declaration, RetrievalPlan((RetrievalIntent("bounded", declaration),)),
        [{"route": "task", "question": declaration, "status": "not_needed", "evidence": []}])
    assert result.plan.intents[0].route == "chat"
    assert result.statuses == ("not_needed",)
    query = "我想知道望远镜在哪？"
    result = validate(service, entry, query, RetrievalPlan((RetrievalIntent("fact", query),)),
        [{"route": "fact", "question": query, "status": "not_needed", "evidence": []}])
    assert result.statuses == ("unknown",)
