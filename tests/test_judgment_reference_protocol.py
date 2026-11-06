import json
from dataclasses import replace

import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_evidence_judgment import validate_judgment
from guanghe_companion.retrieval_contract import RetrievalIntent, RetrievalPlan


def validate(service, entries, query, rows, plan=None, history=()):
    return validate_judgment(json.dumps({"intents": rows}, ensure_ascii=False), query=query,
        plan=plan or RetrievalPlan((RetrievalIntent("episode", query),)), entries=entries, now=10,
        owner_id=service.owner_id, character_id=service.character_id, history=history)


def source(service, summary, **metadata):
    return service.remember(kind="用户事实", title="隔离协议案例", summary=summary,
        source="explicit_user_request", now=10, metadata=metadata)


def test_question_reference_uses_host_text_instead_of_generated_paraphrase(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = source(service, "橘色滑轮盒放在门边的木柜。")
    query = "滑轮盒是什么颜色，要去什么位置找？"
    result = validate(service, (entry,), query, [{"route": "fact", "question_ref": 0,
        "question": "滑轮盒的颜色和存放位置", "status": "sufficient",
        "evidence": [{"id": entry.memory_id, "quote": entry.summary}]}])
    assert result.plan.intents[0].query == query
    assert result.statuses == ("sufficient",)
    assert result.source_ids == (entry.memory_id,)


def test_references_preserve_independent_questions_and_unanswered_fields(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = source(service, "滑轮盒是橘色的。")
    query = "滑轮盒是什么颜色？我把它放在哪里？"
    parts = ("滑轮盒是什么颜色？", "我把它放在哪里？")
    plan = RetrievalPlan(tuple(RetrievalIntent("fact", text) for text in parts))
    result = validate(service, (entry,), query, [
        {"route": "fact", "question_ref": 1, "status": "sufficient",
         "evidence": [{"id": entry.memory_id, "quote": entry.summary}]},
        {"route": "fact", "question_ref": 2, "status": "unknown", "evidence": []},
    ], plan)
    assert tuple(intent.query for intent in result.plan.intents) == parts
    assert result.statuses == ("sufficient", "unknown")


@pytest.mark.parametrize("reference", [-1, 9, True, "0", None])
def test_invalid_reference_does_not_fall_back_to_free_text(tmp_path, reference):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    query = "盒子在哪？"
    with pytest.raises(ValueError, match="question reference"):
        validate(service, (), query, [{"route": "fact", "question_ref": reference,
            "question": query, "status": "unknown", "evidence": []}])


@pytest.mark.parametrize("summary,accepted", [
    ("瓷板耐温测试至今一次也没有进行过；下周预约检查。", True),
    ("那批仪器的校准工作从未实际完成；已经预约下周。", True),
    ("粉色编钟至今尚未调音。", True),
    ("如果瓷板耐温测试没有进行过，就预约检查。", False),
    ("瓷板耐温测试是否没有进行过尚不清楚。", False),
    ("瓷板耐温测试不是没有进行过。", False),
    ("瓷板耐温测试没有进行过吗？", False),
    ("瓷板耐温测试已预约下周进行。", False),
])
def test_explicit_negative_claim_can_be_separate_from_card_plan(tmp_path, summary, accepted):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = source(service, summary, event_status="planned")
    query = "这项工作已经完成了吗？"
    result = validate(service, (entry,), query, [{"route": "episode", "question_ref": 0,
        "claim_use": "current_attribute", "status": "sufficient",
        "evidence": [{"id": entry.memory_id, "quote": summary,
                      "occurrence": "explicitly_not_occurred"}]}])
    assert bool(result.source_ids) is accepted


def test_negative_claim_cannot_quote_only_negated_words_out_of_condition(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = source(service, "用户想问：如果仪器没有校准，就不能使用。", event_status="planned")
    query = "仪器已经完成校准了吗？"
    result = validate(service, (entry,), query, [{"route": "episode", "question_ref": 0,
        "claim_use": "current_attribute", "status": "sufficient",
        "evidence": [{"id": entry.memory_id, "quote": "仪器没有校准",
                      "occurrence": "explicitly_not_occurred"}]}])
    assert not result.source_ids


def test_recent_user_alias_adds_identity_source_without_trusting_history(tmp_path):
    from guanghe_companion.memory_evidence_judgment import _history_identity_sources
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    identity = source(service, "旧书修复搭档邹然的昵称是木舟。", fact_subject="relation:旧书修复搭档",
        fact_predicate="姓名与昵称", fact_value={"姓名": "邹然", "昵称": "木舟"})
    ordinary = source(service, "木舟是修复桌的地址。", fact_subject="object:修复桌",
        fact_predicate="地址", fact_value="木舟")
    history = ("我说的是木舟，一起修复书籍的搭档。",)
    entries, loaded = _history_identity_sources(service, history, now=10, scopes=("companion",))
    assert loaded > 0
    assert {entry.memory_id for entry in entries} == {identity.memory_id}
    assert ordinary.memory_id not in {entry.memory_id for entry in entries}
    service.forget(identity.memory_id, now=11)
    entries, _ = _history_identity_sources(service, history, now=11, scopes=("companion",))
    assert not entries


def test_history_identity_does_not_cross_expiry_or_allowed_scope(tmp_path):
    from guanghe_companion.memory_evidence_judgment import _history_identity_sources
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    service.remember(kind="用户事实", title="过期别名", summary="邻居乐衡的昵称是木舟。",
        source="explicit_user_request", now=5, valid_until=9,
        metadata={"fact_subject": "relation:邻居", "fact_predicate": "昵称", "fact_value": "木舟"})
    identity = source(service, "同事段遥的昵称是木舟。", fact_subject="relation:同事",
        fact_predicate="昵称", fact_value="木舟")
    entries, _ = _history_identity_sources(service, ("木舟",), now=10, scopes=("companion",))
    assert {entry.memory_id for entry in entries} == {identity.memory_id}
    entries, _ = _history_identity_sources(service, ("木舟",), now=10, scopes=("task_experience",))
    assert not entries


def test_history_identity_budget_preserves_ambiguity(tmp_path):
    from guanghe_companion.memory_evidence_judgment import _history_identity_sources
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    ids = {source(service, f"第{number}位同伴的昵称是木舟。", fact_subject=f"person:同伴{number}",
        fact_predicate="昵称", fact_value="木舟").memory_id for number in range(2)}
    entries, _ = _history_identity_sources(service, ("木舟",), now=10, scopes=("companion",))
    assert {entry.memory_id for entry in entries} == ids
    for number in range(2, 6):
        source(service, f"第{number}位同伴的昵称是木舟。", fact_subject=f"person:同伴{number}",
            fact_predicate="昵称", fact_value="木舟")
    entries, _ = _history_identity_sources(service, ("木舟",), now=10, scopes=("companion",))
    assert not entries


@pytest.mark.parametrize("history_role,antecedent,accepted", [
    ("user", "木舟", True), ("assistant", "木舟", False), ("user", "青叶", False),
])
def test_alias_pronoun_requires_user_antecedent_and_identity_source(tmp_path, history_role, antecedent, accepted):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    identity = source(service, "修复搭档邹然的昵称是木舟。", fact_subject="relation:修复搭档",
        fact_predicate="姓名与昵称", fact_value={"姓名": "邹然", "昵称": "木舟"})
    fact = source(service, "邹然把纸样夹放在灰布袋。", fact_subject="person:邹然")
    query = "她把纸样夹放哪里？"
    row = {"route": "fact", "question_ref": 0, "status": "sufficient",
        "evidence": [{"id": fact.memory_id, "quote": fact.summary}],
        "subject_binding": {"mention": "她", "antecedent": antecedent, "subject": "person:邹然",
            "kind": "alias", "quote": identity.summary}}
    history = ({"role": history_role, "text": "我说的是木舟。"},)
    result = validate(service, (identity, fact), query, [row], history=history)
    assert bool(result.source_ids) is accepted
    if accepted:
        assert identity.memory_id in result.source_ids
        assert result.binding_sources == ((identity.memory_id,),)
    missing = validate(service, (fact,), query, [row], history=history)
    assert not missing.source_ids


@pytest.mark.parametrize("different", [
    {"temporal_mode": "as_of", "as_of": 20, "as_of_end": 30},
    {"scopes": ("task_experience",)},
    {"requires_shared_event": True},
    {"authority": "executor"},
])
def test_whole_query_reference_cannot_merge_different_host_constraints(tmp_path, different):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    first = RetrievalIntent("fact", "第一天位置是什么？", temporal_mode="as_of", as_of=5, as_of_end=10)
    second = replace(first, query="第二天位置是什么？", **different)
    query = first.query + second.query
    plan = RetrievalPlan((first, second))
    with pytest.raises(ValueError, match="incompatible host constraints"):
        validate(service, (), query, [{"route": "fact", "question_ref": 0, "status": "unknown", "evidence": []}], plan)
    result = validate(service, (), query, [
        {"route": "fact", "question_ref": 1, "status": "unknown", "evidence": []},
        {"route": "fact", "question_ref": 2, "status": "unknown", "evidence": []},
    ], plan)
    assert result.plan.intents[1].as_of == second.as_of
    assert result.plan.intents[1].requires_shared_event == second.requires_shared_event
    assert result.plan.intents[1].authority == second.authority


def test_context_prefix_does_not_erase_shared_participation_constraint(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = source(service, "用户独自完成了书架搭建。")
    prefix, question = "说起书架，", "我们一起完成了吗？"
    query = prefix + question
    plan = RetrievalPlan((RetrievalIntent("chat", prefix),
        RetrievalIntent("episode", question, requires_shared_event=True)))
    result = validate(service, (entry,), query, [{"route": "episode", "question_ref": 0,
        "status": "sufficient", "claim_use": "completed_event",
        "evidence": [{"id": entry.memory_id, "quote": entry.summary}]}], plan)
    assert result.plan.intents[0].requires_shared_event
    assert not result.source_ids
