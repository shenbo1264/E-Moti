import json
from dataclasses import replace

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_evidence_judgment import validate_judgment, resolve_judged_subjects, MemoryEvidenceJudge
from guanghe_companion.retrieval_contract import RetrievalIntent, RetrievalPlan


def fixture(tmp_path, subject="project:陶艺", summary="用户陶艺作品的底座为榆木。"):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = service.remember(kind="用户事实", title="作品", summary=summary,
        source="explicit_user_request", now=10,
        metadata={"fact_subject": subject, "fact_predicate": "构造", "fact_value": "榆木"})
    return service, entry


def judged(service, entry, query, intent, route="fact"):
    raw = json.dumps({"intents": [{"route": route, "question": query, "status": "sufficient",
        "evidence": [{"id": entry.memory_id, "quote": entry.summary}]}]}, ensure_ascii=False)
    return validate_judgment(raw, query=query, plan=RetrievalPlan((intent,)), entries=(entry,), now=10,
        owner_id=service.owner_id, character_id=service.character_id)


def test_optional_binding_absence_does_not_veto_source_supported_topic(tmp_path):
    service, entry = fixture(tmp_path)
    query = "底座是用什么做的？"
    result = judged(service, entry, query, RetrievalIntent("fact", query, subjects=("底座",)))
    intent, unresolved, _ = resolve_judged_subjects(service.store, result, 0, now=10)
    assert not unresolved
    assert intent.subjects == ("project:陶艺",)


def test_personal_episode_does_not_invent_shared_participation(tmp_path):
    service, entry = fixture(tmp_path, summary="用户昨天独自参观了陶艺展。")
    query = "我昨天参观了什么？"
    result = judged(service, entry, query, RetrievalIntent("bounded", query), route="episode")
    assert not result.plan.intents[0].requires_shared_event
    assert result.source_ids == (entry.memory_id,)


def test_explicit_shared_question_still_requires_shared_evidence(tmp_path):
    service, entry = fixture(tmp_path)
    query = "我们一起做了什么？"
    result = judged(service, entry, query, RetrievalIntent("episode", query, requires_shared_event=True), route="episode")
    assert not result.source_ids


def test_route_hint_does_not_hide_callers_companion_scope(tmp_path):
    service, entry = fixture(tmp_path, summary="用户说明陶艺架安装者完成安装，但用户尚未验收。")
    query = "上次安装者说完工了，这就算我验收了吗？"
    def reply(prompt):
        payload = json.loads(prompt.split("\n")[-1])
        assert entry.memory_id in {row["id"] for row in payload["candidates"]}
        return json.dumps({"intents": [{"route": "fact", "question": query, "status": "sufficient",
            "evidence": [{"id": entry.memory_id, "quote": entry.summary}]}]}, ensure_ascii=False)
    service.evidence_judge = MemoryEvidenceJudge(reply)
    try:
        service.prepare_retrieval(query, now=10).result(timeout=5)
        assert service.evidence_judge.status == "completed"
        assert entry.memory_id in {e.memory_id for e in service.retrieve(query, now=10).bundle.memories}
    finally:
        service.evidence_judge.close()


def test_known_person_conflict_is_not_overridden_by_source_selection(tmp_path):
    service, entry = fixture(tmp_path, subject="relation:室友")
    service.remember(kind="用户事实", title="名字", summary="用户的邻居叫小枝。",
        source="explicit_user_request", now=10,
        metadata={"fact_subject": "relation:邻居", "fact_predicate": "name", "fact_value": "小枝"})
    query = "小枝的作品是什么材料？"
    result = judged(service, entry, query, RetrievalIntent("fact", query, subjects=("小枝",)))
    assert resolve_judged_subjects(service.store, result, 0, now=10)[1]


def test_unallowed_observation_scope_stays_excluded(tmp_path):
    service, entry = fixture(tmp_path)
    query = "底座用什么？"
    result = judged(service, replace(entry, scope="observation"), query, RetrievalIntent("fact", query))
    assert not result.source_ids


def test_explicit_calendar_search_supplies_time_valid_history_without_lexical_hit(tmp_path):
    from datetime import datetime, timezone
    stamp = lambda day: int(datetime(2026, 2, day, tzinfo=timezone.utc).timestamp())
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet", time_basis="unix")
    old = service.remember(kind="用户事实", title="座位", summary="用户分到东侧长凳。",
        source="explicit_user_request", now=stamp(1), valid_from=stamp(1), valid_until=stamp(10),
        metadata={"fact_subject": "user:self", "fact_predicate": "seat", "fact_value": "东侧长凳"})
    query = "2026年2月3日我坐在哪里？"
    def reply(prompt):
        payload = json.loads(prompt.split("\n")[-1])
        assert old.memory_id in {row["id"] for row in payload["candidates"]}
        return json.dumps({"intents": [{"route": "fact", "question": query, "status": "sufficient",
            "evidence": [{"id": old.memory_id, "quote": old.summary}]}]}, ensure_ascii=False)
    service.evidence_judge = MemoryEvidenceJudge(reply)
    try:
        service.prepare_retrieval(query, now=stamp(20)).result(timeout=5)
        assert service.evidence_judge.status == "completed"
        assert old.memory_id in {e.memory_id for e in service.retrieve(query, now=stamp(20)).bundle.memories}
    finally:
        service.evidence_judge.close()


def test_booking_attribute_is_plan_but_actual_attendance_is_not():
    from guanghe_companion.retrieval_router import MemoryRetrievalRouter
    router = MemoryRetrievalRouter(time_basis="unix")
    planned = router.plan("2026年12月8日我预约的是什么？", now=1793620800).intents[0]
    assert planned.temporal_mode == "planned"
    assert planned.as_of is not None
    for query in ("我预约的课程后来参加过了吗？", "我实际完成了预约的什么活动？"):
        assert router.plan(query, now=1793620800).intents[0].temporal_mode != "planned"
    logical = MemoryRetrievalRouter(time_basis="logical")
    assert logical.plan("2026年12月8日我预约的是什么？", now=10).intents[0].temporal_mode == "unresolved"
