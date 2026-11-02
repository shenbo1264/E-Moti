import json

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_evidence_judgment import validate_judgment, resolve_judged_subjects
from guanghe_companion.retrieval_contract import RetrievalIntent, RetrievalPlan


def case(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = service.remember(kind="用户事实", title="人物", summary="用户的园艺搭档叫青禾。",
        source="explicit_user_request", now=10,
        metadata={"fact_subject": "relation:园艺搭档", "fact_predicate": "name", "fact_value": "青禾"})
    query = "负责园艺的那位搭档叫什么？"
    plan = RetrievalPlan((RetrievalIntent("fact", query, subjects=("负责园艺的那位搭档",)),))
    row = {"route": "fact", "question": query, "status": "sufficient",
        "subject_binding": {"mention": "负责园艺的那位搭档", "subject": "relation:园艺搭档",
            "kind": "description", "quote": entry.summary},
        "evidence": [{"id": entry.memory_id, "quote": entry.summary}]}
    return service, entry, query, plan, row


def validate(service, entry, query, plan, row):
    return validate_judgment(json.dumps({"intents": [row]}, ensure_ascii=False), query=query,
        plan=plan, entries=(entry,), now=10, owner_id=service.owner_id, character_id=service.character_id)


def test_descriptive_subject_is_bound_to_actual_selected_source(tmp_path):
    service, entry, query, plan, row = case(tmp_path)
    judged = validate(service, entry, query, plan, row)
    intent, unresolved, _ = resolve_judged_subjects(service.store, judged, 0, now=10)
    assert not unresolved
    assert intent.subjects == ("relation:园艺搭档",)


def test_unknown_name_cannot_be_bound_to_unrelated_person(tmp_path):
    service, entry, _, _, row = case(tmp_path)
    query = "阿白叫什么？"
    plan = RetrievalPlan((RetrievalIntent("fact", query, subjects=("阿白",)),))
    row.update(question=query, subject_binding={"mention": "阿白", "subject": "relation:园艺搭档",
        "kind": "alias", "quote": entry.summary})
    judged = validate(service, entry, query, plan, row)
    assert resolve_judged_subjects(service.store, judged, 0, now=10)[1]


def test_unsupported_single_field_does_not_deliver_its_premise(tmp_path):
    service, entry, query, plan, row = case(tmp_path)
    for status in ("unknown", "insufficient"):
        judged = validate(service, entry, query, plan, {**row, "status": status})
        assert not judged.source_ids


def test_punctuation_normalization_keeps_host_question(tmp_path):
    service, entry, query, plan, row = case(tmp_path)
    judged = validate(service, entry, query, plan, {**row, "question": query.replace("？", "?")})
    assert judged.plan.intents[0].query == query


def test_bound_subject_reaches_final_bundle_and_forget_revokes_it(tmp_path):
    from guanghe_companion.memory_evidence_judgment import MemoryEvidenceJudge
    service, entry, query, _, row = case(tmp_path)
    service.evidence_judge = MemoryEvidenceJudge(lambda prompt: json.dumps({"intents": [row]}, ensure_ascii=False))
    try:
        service.prepare_retrieval(query, now=10).result(timeout=5)
        result = service.retrieve(query, now=10)
        assert entry.memory_id in {e.memory_id for e in result.bundle.memories}
        service.forget(entry.memory_id, now=11)
        assert entry.memory_id not in {e.memory_id for e in service.retrieve(query, now=11).bundle.memories}
    finally:
        service.evidence_judge.close()


def test_homonym_binding_cannot_select_one_person(tmp_path):
    service, entry, _, _, row = case(tmp_path)
    service.remember(kind="用户事实", title="另一人物", summary="用户的校稿搭档也叫青禾。",
        source="explicit_user_request", now=10,
        metadata={"fact_subject": "relation:校稿搭档", "fact_predicate": "name", "fact_value": "青禾"})
    query = "青禾叫什么？"
    plan = RetrievalPlan((RetrievalIntent("fact", query, subjects=("青禾",)),))
    row.update(question=query, subject_binding={"mention": "青禾", "subject": "relation:园艺搭档",
        "kind": "description", "quote": entry.summary})
    judged = validate(service, entry, query, plan, row)
    assert resolve_judged_subjects(service.store, judged, 0, now=10)[1]


def test_host_intent_index_uses_original_question_and_constraints(tmp_path):
    from dataclasses import replace
    service, entry, query, plan, row = case(tmp_path)
    plan = replace(plan, intents=(replace(plan.intents[0], temporal_mode="unresolved"),))
    row.update(question="这个搭档的姓名是什么", intent_index=0)
    judged = validate(service, entry, query, plan, row)
    assert judged.plan.intents[0].query == query
    assert judged.plan.intents[0].temporal_mode == "unresolved"
    assert not judged.source_ids


def test_semantic_description_need_not_contain_canonical_characters(tmp_path):
    service, entry, _, _, row = case(tmp_path)
    query = "帮我照料花草的那个人叫什么？"
    plan = RetrievalPlan((RetrievalIntent("fact", query, subjects=("帮我照料花草的那个人",)),))
    row.update(question=query)
    row["subject_binding"]["mention"] = "帮我照料花草的那个人"
    judged = validate(service, entry, query, plan, row)
    intent, unresolved, _ = resolve_judged_subjects(service.store, judged, 0, now=10)
    assert not unresolved
    assert intent.subjects == ("relation:园艺搭档",)
