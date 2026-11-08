import json
from dataclasses import replace

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.retrieval_contract import RetrievalIntent, RetrievalPlan
from guanghe_companion.memory_evidence_judgment import validate_judgment


def source(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = service.remember(kind="用户事实", title="配置", summary="用户的刻印机进给速度为17毫米每秒",
        source="explicit_user_request", source_ids=("utterance:1",), now=10,
        metadata={"fact_subject": "user:self", "fact_predicate": "feed_rate", "fact_value": 17})
    return service, entry


def response(entry, **extra):
    return json.dumps({"intents": [{"route": "fact", "question": "进给速度多少？", "status": "sufficient",
        "evidence": [{"id": entry.memory_id, "quote": "进给速度为17毫米每秒"}], **extra}]}, ensure_ascii=False)


def test_open_attribute_selection_requires_exact_source_and_host_eligibility(tmp_path):
    service, entry = source(tmp_path)
    plan = RetrievalPlan((RetrievalIntent("bounded", "进给速度多少？"),))
    selected = validate_judgment(response(entry), query="进给速度多少？", plan=plan,
        entries=(entry,), now=10, owner_id=service.owner_id, character_id=service.character_id)
    assert selected.source_ids == (entry.memory_id,)
    for invalid in (replace(entry, deleted=True), replace(entry, owner_id="other"),
                    replace(entry, valid_until=9), replace(entry, scope="observation")):
        checked = validate_judgment(response(invalid), query="进给速度多少？", plan=plan,
            entries=(invalid,), now=10, owner_id=service.owner_id, character_id=service.character_id)
        assert not checked.source_ids


def test_model_cannot_invent_quote_or_expand_authorized_scope(tmp_path):
    service, entry = source(tmp_path)
    plan = RetrievalPlan((RetrievalIntent("bounded", "进给速度多少？"),))
    for raw in (response(entry).replace("进给速度为17毫米每秒", "进给速度为99毫米每秒"),
                response(entry, route="task")):
        selected = validate_judgment(raw, query="进给速度多少？", plan=plan,
            entries=(entry,), now=10, owner_id=service.owner_id, character_id=service.character_id)
        assert not selected.source_ids


def test_logical_calendar_query_cannot_be_resolved_by_model(tmp_path):
    service, entry = source(tmp_path)
    plan = RetrievalPlan((RetrievalIntent("bounded", "进给速度多少？", temporal_mode="unresolved"),))
    selected = validate_judgment(response(entry), query="进给速度多少？", plan=plan,
        entries=(entry,), now=10, owner_id=service.owner_id, character_id=service.character_id)
    assert not selected.source_ids


def test_prepared_selection_rechecks_forgetting_before_delivery(tmp_path):
    service, entry = source(tmp_path)
    from guanghe_companion.memory_evidence_judgment import MemoryEvidenceJudge
    # 协议测试只验证真实存储与发布屏障，答案质量另跑真实模型。
    service.evidence_judge = MemoryEvidenceJudge(lambda prompt: response(entry))
    try:
        service.prepare_retrieval("进给速度多少？", now=10).result(timeout=5)
        result = service.retrieve("进给速度多少？", now=10)
        assert entry.memory_id in [e.memory_id for e in result.bundle.memories]
        service.forget(entry.memory_id, now=11)
        result = service.retrieve("进给速度多少？", now=11)
        assert not result.bundle.memories
    finally:
        service.evidence_judge.close()


def test_subject_soft_miss_never_skips_task_constraints(tmp_path):
    service, entry = source(tmp_path)
    from guanghe_companion.memory_evidence_judgment import hard_eligibility
    task = replace(entry, scope="task_experience", metadata={**entry.metadata, "outcome": "planned", "app": "Other"})
    intent = RetrievalIntent("task", "导出结果", subjects=("relation:同事",), scopes=("task_experience",), app="Editor")
    assert not hard_eligibility(task, intent, now=10, owner_id=service.owner_id, character_id=service.character_id)


def test_judge_cannot_omit_question_or_remove_shared_event_requirement(tmp_path):
    service, entry = source(tmp_path)
    plan = RetrievalPlan((RetrievalIntent("bounded", "进给速度多少？"), RetrievalIntent("fact", "谁推荐的？")))
    selected = validate_judgment(response(entry), query="进给速度多少？谁推荐的？", plan=plan,
        entries=(entry,), now=10, owner_id=service.owner_id, character_id=service.character_id)
    assert selected.statuses == ("insufficient", "insufficient")
    shared = RetrievalPlan((RetrievalIntent("episode", "进给速度多少？", requires_shared_event=True),))
    selected = validate_judgment(response(entry), query="进给速度多少？", plan=shared,
        entries=(entry,), now=10, owner_id=service.owner_id, character_id=service.character_id)
    assert not selected.source_ids


def test_history_change_invalidates_prepared_judgment(tmp_path):
    service, entry = source(tmp_path)
    from guanghe_companion.memory_evidence_judgment import MemoryEvidenceJudge
    judge = MemoryEvidenceJudge(lambda prompt: response(entry))
    service.evidence_judge = judge
    try:
        old = ({"role": "user", "text": "刚才聊的是我的刻印机"},)
        service.prepare_retrieval("进给速度多少？", now=10, history=old).result(timeout=5)
        assert judge.prepared(service, "进给速度多少？", scope="companion", now=10, history=old)
        assert judge.prepared(service, "进给速度多少？", scope="companion", now=10,
            history=({"role": "user", "text": "现在改问同事的机器"},)) is None
    finally:
        judge.close()
