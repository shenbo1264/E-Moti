import json
from datetime import datetime, timezone

import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_evidence_judgment import MemoryEvidenceJudge, validate_judgment
from guanghe_companion.memory_index import IndexedMemoryQuery


def stamp(day):
    return int(datetime(2027, 3, day, tzinfo=timezone.utc).timestamp())


def test_future_effective_rule_uses_query_date_without_advancing_archive_clock(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet", time_basis="unix", timezone_name="UTC")
    now = stamp(4)
    sentinel = service.remember(kind="用户事实", title="临时有效记录", summary="工具寄存在柜子。",
        source="explicit_user_request", now=now, valid_until=stamp(8))
    fact = service.remember(kind="用户事实", title="剪辑工作台规则", summary="从2027年3月12日起，剪辑工作台使用灰色垫板。",
        source="explicit_user_request", now=now, valid_from=stamp(12),
        metadata={"fact_subject": "project:剪辑工作台", "fact_predicate": "垫板", "fact_value": "灰色", "event_status": "planned"})
    query = "按照已经定好的规则，到了3月12日剪辑工作台用什么垫板？"
    seen = []
    def protocol(prompt):
        payload = json.loads(prompt.split("\n")[-1])
        seen.extend(row["id"] for row in payload["candidates"])
        return json.dumps({"intents": [{"route": "fact", "question": query, "claim_use": "planned_event",
            "status": "sufficient", "evidence": [{"id": fact.memory_id, "quote": fact.summary}]}]})
    service.evidence_judge = MemoryEvidenceJudge(protocol)
    try:
        epoch = service.store.current_context_epoch(now=now)
        service.prepare_retrieval(query, now=now).result(timeout=5)
        assert fact.memory_id in seen
        result = service.retrieve(query, now=now)
        assert result.trace.status == "sufficient"
        assert fact.memory_id in {e.memory_id for e in result.bundle.memories}
        assert result.bundle.retrieval["query_clock"]["now"] == now
        assert service.store.current_context_epoch(now=now) == epoch
        assert service.store.read_indexed_snapshot(IndexedMemoryQuery(memory_ids=(sentinel.memory_id,)), now=now).entries
        current = service.retrieve("剪辑工作台现在用什么垫板？", now=now)
        assert fact.memory_id not in {e.memory_id for e in current.bundle.memories}
        service.forget(fact.memory_id, now=now)
        assert fact.memory_id not in {e.memory_id for e in service.retrieve(query, now=now).bundle.memories}
    finally:
        service.close(wait=True)


@pytest.mark.parametrize("entry_point", ["desktop", "album"])
def test_future_rule_keeps_calendar_query_across_desktop_and_album(tmp_path, entry_point):
    from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController
    from guanghe_companion.dialogue import DialogueRequest
    seed = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet", time_basis="unix", timezone_name="UTC")
    seed.close(wait=True)
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    controller.now = stamp(4)
    memory = controller.story_runtime.memory
    fact = memory.remember(kind="用户事实", title="收音规则", summary="从2027年3月15日起，录音间使用短支架。",
        source="explicit_user_request", now=stamp(4), valid_from=stamp(15),
        metadata={"fact_subject": "project:录音间", "fact_predicate": "支架", "fact_value": "短支架", "event_status": "planned"})
    query = "到了3月15日录音间用什么支架？"
    row = {"route": "fact", "question": query, "claim_use": "planned_event", "status": "sufficient",
           "evidence": [{"id": fact.memory_id, "quote": fact.summary}]}
    memory.evidence_judge = MemoryEvidenceJudge(lambda prompt: json.dumps({"intents": [row]}))
    try:
        controller.prepare_semantic_recall(DialogueRequest(query)).result(timeout=5)
        controller.advance_tick(include_ai_expression=False)
        if entry_point == "desktop":
            request = controller.prepare_host_dialogue(DialogueRequest(query)).expression_request
            assert request.emotional_memory["retrieval"]["status"] == "sufficient"
            assert request.emotional_memory["retrieval"]["query_clock"]["now"] == stamp(4)
            assert fact.memory_id in {row["memory_id"] for row in request.emotional_memory["shared_memories"]}
        else:
            answer = controller.memory_album_controller.ask(query, now=int(controller.now))
            assert answer["status"] == "sufficient"
            assert fact.memory_id in {row["memory_id"] for row in answer["claims"]}
    finally:
        controller.close()


@pytest.mark.parametrize("text,accepted", [
    ("截至东京时间2027年3月4日18点，用户尚未录制安全培训短片；录制预约在3月16日。", True),
    ("用户还没有归还借来的示波器。", True),
    ("用户是否还没有归还借来的示波器不清楚。", False),
    ("用户还没有归还借来的示波器吗？", False),
    ("如果用户还没有归还借来的示波器，就再等等。", False),
    ("用户计划3月16日归还借来的示波器。", False),
])
def test_semantic_negative_status_has_no_activity_or_object_vocabulary(tmp_path, text, accepted):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = service.remember(kind="用户事实", title="进展", summary=text, source="explicit_user_request", now=10,
        metadata={"fact_subject": "user:self", "fact_predicate": "进展", "event_status": "planned"})
    query = "我现在已经做过了吗？"
    row = {"route": "fact", "question": query, "claim_use": "current_attribute", "status": "sufficient",
           "evidence": [{"id": entry.memory_id, "quote": text}]}
    judgment = validate_judgment(json.dumps({"intents": [row]}), query=query,
        plan=service.retrieval_router.plan(query, now=10), entries=(entry,), now=10,
        owner_id=service.owner_id, character_id=service.character_id)
    assert bool(judgment.source_ids) is accepted


@pytest.mark.parametrize("field,summary,accepted", [
    ("社团代号", "陶艺搭档桑乔在社团的代号是山岚。", True),
    ("住址", "陶艺搭档桑乔的住址是山岚。", False),
    ("职业", "陶艺搭档桑乔的职业是山岚。", False),
    ("编号", "陶艺搭档桑乔的编号是山岚。", False),
])
def test_alias_binding_requires_identity_declaration_not_arbitrary_fact_value(tmp_path, field, summary, accepted):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    identity = service.remember(kind="用户事实", title=summary, summary=summary, source="explicit_user_request", now=10,
        metadata={"fact_subject": "relation:陶艺搭档", "fact_predicate": "姓名与" + field,
                  "fact_value": {"姓名": "桑乔", field: "山岚"}})
    fact = service.remember(kind="用户事实", title="工具", summary="桑乔的修坯刀放在紫色布包。", source="explicit_user_request", now=10,
        metadata={"fact_subject": "person:桑乔", "fact_predicate": "工具位置", "fact_value": "紫色布包"})
    query = "山岚的修坯刀放哪？"
    row = {"route": "fact", "question": query, "status": "sufficient", "evidence": [{"id": fact.memory_id, "quote": fact.summary}],
        "subject_binding": {"mention": "山岚", "subject": "person:桑乔", "kind": "alias", "quote": identity.summary}}
    result = validate_judgment(json.dumps({"intents": [row]}), query=query,
        plan=service.retrieval_router.plan(query, now=10), entries=(identity, fact), now=10,
        owner_id=service.owner_id, character_id=service.character_id)
    assert bool(result.source_ids) is accepted
