import json
from dataclasses import replace

import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_evidence_judgment import MemoryEvidenceJudge, validate_judgment, resolve_judged_subjects
from guanghe_companion.retrieval_router import MemoryRetrievalRouter


def statement(service, text, subject, value, predicate="配置"):
    return service.remember(kind="用户事实", title=text, summary=text, source="explicit_user_request",
        source_ids=("statement:" + subject,), now=10,
        metadata={"fact_subject": subject, "fact_predicate": predicate, "fact_value": value})


@pytest.mark.parametrize("basis,zone", [("unix", "Asia/Shanghai"), ("logical", "")])
def test_host_query_clock_reaches_judgment_and_final_memory_prompt(tmp_path, basis, zone):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet",
        time_basis=basis, timezone_name=zone)
    statement(service, "用户的画架夹紧力度设为7档。", "object:画架", {"夹紧力度": 7})
    query = "画架夹紧力度现在是多少？"
    captured = []
    def protocol(prompt):
        captured.append(json.loads(prompt.split("\n")[-1]))
        return json.dumps({"intents": [{"route": "fact", "question": query,
            "status": "unknown", "evidence": []}]})
    service.evidence_judge = MemoryEvidenceJudge(protocol)
    try:
        service.prepare_retrieval(query, now=1800000000).result(timeout=5)
        payload = service.retrieve(query, now=1800000000).bundle.to_prompt_payload()
        clock = payload["retrieval"]["query_clock"]
        assert captured[0]["query_clock"] == clock
        assert clock["time_basis"] == basis
        assert clock["now"] == 1800000000
        from guanghe_companion.expression_request import ExpressionRequest
        from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
        request = ExpressionRequest.from_snapshot({"character_name": "星汐", "focus": 50,
            "charge": 50, "stability": 50, "mood": 50, "trust": 50},
            context={"emotional_memory": payload, "player_message": query})
        prompt = ShinsekaiAIExpressor().build_prompt(request)
        rendered = json.loads(next(line.removeprefix("emotional_memory: ") for line in prompt.splitlines()
            if line.startswith("emotional_memory: ")))
        assert rendered["retrieval"]["query_clock"] == clock
        assert service.evidence_judge.prepared(service, query, scope="companion", now=1800000000) is not None
        assert service.evidence_judge.prepared(service, query, scope="companion", now=1800000001) is None
        if basis == "unix":
            assert clock["timezone"] == zone
            assert clock["local_datetime"].endswith("+08:00")
        else:
            assert "local_datetime" not in clock
            assert "timezone" not in clock
    finally:
        service.close(wait=True)


def alias_case(tmp_path, service=None):
    service = service or EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    identity = statement(service, "用户的雕刻搭档季芹昵称栀子。", "relation:雕刻搭档",
        {"姓名": "季芹", "昵称": "栀子"}, "姓名与称呼")
    fact = statement(service, "季芹保管的刻刀放在蓝色箱子里。", "person:季芹", {"箱子": "蓝色"})
    query = "栀子保管的刻刀放在哪？"
    row = {"route": "fact", "question": query, "status": "sufficient", "claim_use": "current_attribute",
        "evidence": [{"id": fact.memory_id, "quote": fact.summary}],
        "subject_binding": {"mention": "栀子", "subject": "person:季芹", "kind": "alias", "quote": identity.summary}}
    return service, identity, fact, query, row


def test_cross_card_alias_keeps_identity_dependency_and_revokes_with_it(tmp_path):
    service, identity, fact, query, row = alias_case(tmp_path)
    service.evidence_judge = MemoryEvidenceJudge(lambda prompt: json.dumps({"intents": [row]}, ensure_ascii=False))
    try:
        service.prepare_retrieval(query, now=10).result(timeout=5)
        result = service.retrieve(query, now=10)
        assert result.trace.status == "sufficient"
        assert fact.memory_id in {entry.memory_id for entry in result.bundle.memories}
        payload = result.bundle.to_prompt_payload()
        assert identity.memory_id in {entry["memory_id"] for entry in payload["resolution_evidence"]}
        service.forget(identity.memory_id, now=11)
        result = service.retrieve(query, now=11)
        assert fact.memory_id not in {entry.memory_id for entry in result.bundle.memories}
    finally:
        service.close(wait=True)


def test_prepared_query_survives_delivery_tick_but_not_next_query_clock(tmp_path):
    service, identity, fact, query, row = alias_case(tmp_path)
    service.evidence_judge = MemoryEvidenceJudge(lambda prompt: json.dumps({"intents": [row]}, ensure_ascii=False))
    try:
        service.prepare_retrieval(query, now=10).result(timeout=5)
        result = service.retrieve(query, now=25)
        assert result.trace.status == "sufficient"
        assert result.bundle.retrieval["query_clock"]["now"] == 10
        assert service.evidence_judge.prepared(service, query, scope="companion", now=26) is None
        later = service.retrieve(query, now=26)
        assert later.bundle.retrieval["query_clock"]["now"] == 26
        service.prepare_retrieval(query, now=26).result(timeout=5)
        fresh = service.retrieve(query, now=41)
        assert fresh.trace.status == "sufficient"
        assert fresh.bundle.retrieval["query_clock"]["now"] == 26
    finally:
        service.close(wait=True)


@pytest.mark.parametrize("entry_point", ["desktop", "album"])
def test_controller_and_album_deliver_prepared_judgment_after_tick(tmp_path, entry_point):
    from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController
    from guanghe_companion.dialogue import DialogueRequest
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    controller.now = 10
    service, identity, fact, query, row = alias_case(tmp_path, controller.story_runtime.memory)
    service.evidence_judge = MemoryEvidenceJudge(lambda prompt: json.dumps({"intents": [row]}, ensure_ascii=False))
    try:
        request = DialogueRequest(query)
        controller.prepare_semantic_recall(request).result(timeout=5)
        controller.advance_tick(include_ai_expression=False)
        if entry_point == "desktop":
            ticket = controller.prepare_host_dialogue(request)
            payload = ticket.expression_request.emotional_memory
            assert payload["retrieval"]["status"] == "sufficient"
            assert payload["retrieval"]["query_clock"]["now"] == 10
            assert fact.memory_id in {item["memory_id"] for item in payload["shared_memories"]}
            again = service.retrieve(query, now=int(controller.now)).bundle
            assert again.retrieval["query_clock"]["now"] == 10
            assert again.retrieval["status"] == "sufficient"
        else:
            answer = controller.memory_album_controller.ask(query, now=int(controller.now))
            assert answer["status"] == "sufficient"
            assert fact.memory_id in {item["memory_id"] for item in answer["claims"]}
    finally:
        controller.close()


def test_prepared_query_rechecks_expiration_at_delivery(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    query = "画架夹紧力度现在是多少？"
    fact = service.remember(kind="用户事实", title="画架夹紧力度", summary="画架夹紧力度为7档。",
        source="explicit_user_request", now=10, valid_until=20,
        metadata={"fact_subject": "object:画架", "fact_predicate": "配置", "fact_value": {"力度": 7}})
    row = {"route": "fact", "question": query, "status": "sufficient", "claim_use": "current_attribute",
        "evidence": [{"id": fact.memory_id, "quote": fact.summary}]}
    service.evidence_judge = MemoryEvidenceJudge(lambda prompt: json.dumps({"intents": [row]}, ensure_ascii=False))
    try:
        service.prepare_retrieval(query, now=10).result(timeout=5)
        result = service.retrieve(query, now=25)
        assert fact.memory_id not in {entry.memory_id for entry in result.bundle.memories}
    finally:
        service.close(wait=True)


def test_alias_proof_cannot_cross_owner_or_conflicting_identity(tmp_path):
    service, identity, fact, query, row = alias_case(tmp_path)
    plan = service.retrieval_router.plan(query, now=10)
    other = replace(identity, memory_id="other", summary="用户的校稿搭档林汀昵称栀子。",
        metadata={"fact_subject": "relation:校稿搭档", "fact_value": {"姓名": "林汀", "昵称": "栀子"}})
    for entries in ((replace(identity, owner_id="someone_else"), fact), (identity, fact, other)):
        result = validate_judgment(json.dumps({"intents": [row]}, ensure_ascii=False), query=query,
            plan=plan, entries=entries, now=10, owner_id=service.owner_id, character_id=service.character_id)
        assert not result.source_ids


def test_alias_with_description_uses_only_declared_name(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    fact = statement(service, "用户给保温壶取的名字是小舟，壶盖需要拧紧。", "object:保温壶",
        {"名字": "小舟", "壶盖": "拧紧"})
    query = "小舟那只壶盖紧吗？"
    row = {"route": "fact", "question": query, "status": "sufficient", "claim_use": "current_attribute",
        "evidence": [{"id": fact.memory_id, "quote": fact.summary}],
        "subject_binding": {"mention": "小舟那只壶", "subject": "object:保温壶", "kind": "alias", "quote": fact.summary}}
    result = validate_judgment(json.dumps({"intents": [row]}, ensure_ascii=False), query=query,
        plan=service.retrieval_router.plan(query, now=10), entries=(fact,), now=10,
        owner_id=service.owner_id, character_id=service.character_id)
    assert result.statuses == ("sufficient",)
    assert not resolve_judged_subjects(service.store, result, 0, now=10)[1]


@pytest.mark.parametrize("text", [
    "截至2027年3月2日用户尚未完成这次排练。",
    "截至3月2日明确还没参加过这项彩排。",
    "用户截至2027年3月2日还没上过这门安全课。",
])
def test_dated_negative_status_with_object_remains_grounded(tmp_path, text):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    fact = statement(service, text, "user:self", {"状态": "尚未参加"})
    fact = replace(fact, metadata={**fact.metadata, "event_status": "planned"})
    query = "我已经参加过了吗？"
    row = {"route": "episode", "question": query, "status": "sufficient", "claim_use": "current_attribute",
        "evidence": [{"id": fact.memory_id, "quote": text}]}
    result = validate_judgment(json.dumps({"intents": [row]}, ensure_ascii=False), query=query,
        plan=MemoryRetrievalRouter(time_basis="logical").plan(query, now=10), entries=(fact,), now=10,
        owner_id=service.owner_id, character_id=service.character_id)
    assert result.statuses == ("sufficient",)
    assert result.plan.intents[0].route == "fact"


@pytest.mark.parametrize("text", [
    "截至2027年3月2日用户是否尚未参加这项彩排还不确定。",
    "截至3月2日用户尚未参加这项彩排吗？",
    "如果截至3月2日用户尚未参加这项彩排，就继续等待。",
    "不知道截至3月2日用户尚未参加这项彩排是否属实。",
    "不要写截至3月2日用户尚未参加这项彩排。",
])
def test_negative_status_does_not_accept_question_hypothesis_or_uncertainty(tmp_path, text):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    fact = statement(service, text, "user:self", {"状态": "未确认"})
    fact = replace(fact, metadata={**fact.metadata, "event_status": "planned"})
    query = "我已经参加过了吗？"
    row = {"route": "fact", "question": query, "status": "sufficient", "claim_use": "current_attribute",
        "evidence": [{"id": fact.memory_id, "quote": text}]}
    result = validate_judgment(json.dumps({"intents": [row]}, ensure_ascii=False), query=query,
        plan=service.retrieval_router.plan(query, now=10), entries=(fact,), now=10,
        owner_id=service.owner_id, character_id=service.character_id)
    assert not result.source_ids


def test_unknown_result_is_not_changed_by_unresolved_subject(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    statement(service, "储物箱放在西侧柜子。", "object:储物箱", {"位置": "西侧柜子"})
    query = "阿团的储物箱密码是什么？"
    service.evidence_judge = MemoryEvidenceJudge(lambda prompt: json.dumps({"intents": [
        {"route": "fact", "question": query, "status": "unknown", "evidence": []}]}, ensure_ascii=False))
    try:
        service.prepare_retrieval(query, now=10).result(timeout=5)
        result = service.retrieve(query, now=10)
        assert result.trace.status == "unknown"
        assert not result.bundle.memories
    finally:
        service.close(wait=True)


def test_prior_mistake_in_completed_episode_is_not_an_expired_fact(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    fact = statement(service, "用户和伙伴核对乐谱时发现把升号当成降号，已改回升号，用户确认正确。",
        "", {})
    fact = replace(fact, kind="共同经历", metadata={"event_status": "completed", "participants": ["user:self", "character:self"],
        "user_accepted": True})
    query = "我们上次把乐谱改成了什么，原来错在哪？"
    plan = service.retrieval_router.plan(query, now=10)
    rows = [{"route": "episode", "question": question, "status": "sufficient", "claim_use": "completed_event",
        "evidence": [{"id": fact.memory_id, "quote": fact.summary}]}
        for question in ("我们上次把乐谱改成了什么", "原来错在哪")]
    result = validate_judgment(json.dumps({"intents": rows}, ensure_ascii=False), query=query,
        plan=plan, entries=(fact,), now=10, owner_id=service.owner_id, character_id=service.character_id)
    assert result.statuses == ("sufficient", "sufficient")
    assert all(intent.requires_shared_event for intent in result.plan.intents)
    rejected = validate_judgment(json.dumps({"intents": rows}, ensure_ascii=False), query=query,
        plan=plan, entries=(replace(fact, metadata={**fact.metadata, "user_accepted": False}),), now=10,
        owner_id=service.owner_id, character_id=service.character_id)
    assert not rejected.source_ids
