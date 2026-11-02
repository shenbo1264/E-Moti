"""Production routing/evidence acceptance; no embedding scores masquerade as truth."""
from dataclasses import replace

import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.retrieval_router import MemoryRetrievalRouter


@pytest.mark.parametrize("query,route,subject,predicate", [
    ("今天有点无聊", "chat", "", ""),
    ("我喜欢喝什么", "fact", "user:self", "饮料偏好"),
    ("我的牙医叫什么名字", "fact", "relation:牙医", "name"),
    ("还记得我们第一次一起玩游戏吗", "episode", "", ""),
    ("上次部署为什么失败", "task", "", ""),
    ("Relay 的任务完成了吗", "live", "", ""),
])
def test_routes_without_a_model(query, route, subject, predicate):
    plan = MemoryRetrievalRouter().plan(query)
    assert plan.routes == (route,)
    if subject:
        assert subject in plan.intents[0].subjects
    if predicate:
        assert predicate in plan.intents[0].predicates


def test_mixed_intents_and_reference_inherit_only_user_question():
    router = MemoryRetrievalRouter()
    assert set(router.plan("我喜欢喝什么，另外 Relay 的任务完成了吗").routes) == {"fact", "live"}
    plan = router.plan("那他住哪里", history=(
        {"role": "user", "text": "我的牙医叫什么名字"},
        {"role": "assistant", "text": "你的老师叫小林。"},
    ))
    assert plan.intents[0].subjects == ("relation:牙医",)
    assert plan.intents[0].predicates == ("residence",)
    assert plan.inherited_context


@pytest.mark.parametrize("query,route,predicate", [
    ("我家鹦鹉叫什么", "fact", "宠物称呼:鹦鹉"),
    ("我现在做哪一行", "fact", "occupation"),
    ("聊聊我们浇花的两次经历", "episode", ""),
    ("为什么失败、后来怎么成功的", "task", ""),
    ("那次种了几盆花", "episode", ""),
])
def test_general_question_forms_are_not_general_chat(query, route, predicate):
    plan = MemoryRetrievalRouter().plan(query)
    assert plan.routes == (route,)
    if predicate:
        assert predicate in plan.intents[0].predicates


def test_subject_field_lists_are_separate_intents_with_one_subject():
    plan = MemoryRetrievalRouter().plan("我的教练住哪、叫什么")
    assert len(plan.intents) == 2
    assert all(i.subjects == ("relation:教练",) for i in plan.intents)
    assert {i.predicates[0] for i in plan.intents} == {"residence", "name"}


def make_service(path):
    return EmotionalMemoryService(root=path, character_id="xingxi_pixel_pet")


def fact(service, summary, *, subject="user:self", predicate="饮料偏好", value="绿茶", **kwargs):
    return service.remember(kind="玩家希望被记住", title=predicate, summary=summary,
        source="user_chat", now=10, source_ids=("statement:" + summary,),
        metadata={"fact_subject": subject, "fact_predicate": predicate,
                  "fact_domain": predicate, "fact_slot": predicate, "fact_value": value,
                  "speaker": "user", "scene": "companion_chat"}, **kwargs)


def test_chat_has_no_retrieval_or_semantic_call_but_keeps_profile(tmp_path):
    service = make_service(tmp_path)
    entry = fact(service, "用户喜欢绿茶")
    service.update_bond_profile(now=11, new_preference=entry.summary,
                                source_memory_ids=(entry.memory_id,))
    def forbidden(*args):
        pytest.fail("ordinary chat must not invoke semantic retrieval")
    service.semantic_retriever = forbidden
    result = service.retrieve("今天有点无聊", now=20)
    assert result.trace.status == "not_needed"
    assert result.trace.retrieval_calls == 0
    assert result.bundle.memories == ()
    assert result.bundle.bond_profile.stable_preferences == (entry.summary,)


def test_semantic_similarity_cannot_turn_teacher_into_dentist(tmp_path):
    service = make_service(tmp_path)
    fact(service, "用户的吉他老师叫林舟", subject="relation:吉他老师", predicate="name", value="林舟")
    service.semantic_retriever = lambda query, entries: {e.memory_id: .999 for e in entries}
    result = service.retrieve("我的牙医叫什么名字", now=20)
    assert result.bundle.memories == ()
    assert result.trace.status == "unknown"
    assert "林舟" not in result.bundle.to_prompt_text()


def test_structured_answer_survives_large_irrelevant_collection(tmp_path):
    service = make_service(tmp_path)
    correct = fact(service, "用户的牙医叫林舟", subject="relation:牙医", predicate="name", value="林舟")
    fact(service, "用户的牙医住在苏州", subject="relation:牙医", predicate="residence", value="苏州")
    result = service.retrieve("我的牙医叫什么名字", now=20)
    assert [e.memory_id for e in result.bundle.memories] == [correct.memory_id]
    assert result.trace.status == "sufficient"
    assert result.trace.rows_loaded <= 2


def test_repeated_equal_facts_share_context_without_deleting_sources(tmp_path):
    service = make_service(tmp_path)
    first = fact(service, "用户喜欢喝绿茶")
    second = fact(service, "用户再次确认喜欢绿茶")
    other = fact(service, "用户喜欢喝乌龙茶", value="乌龙茶")
    result = service.retrieve("我喜欢喝什么", now=20)
    assert len(result.bundle.memories) == 2
    assert other.memory_id in result.trace.selected_memory_ids
    assert len({first.memory_id, second.memory_id}.intersection(result.trace.selected_memory_ids)) == 1
    assert len([e for e in service.store.load_memories() if not e.deleted]) == 3


def test_correction_and_forget_invalidate_index_overview_and_profile(tmp_path):
    service = make_service(tmp_path)
    old = fact(service, "用户喜欢咖啡", value="咖啡")
    service.update_bond_profile(now=11, new_preference=old.summary, source_memory_ids=(old.memory_id,))
    service.retrieve("我喜欢喝什么", now=20)
    new = service.correct(old.memory_id, title="饮品", summary="用户喜欢绿茶", now=21)
    corrected = service.retrieve("我喜欢喝什么", now=22)
    assert new.memory_id in corrected.trace.selected_memory_ids
    assert "咖啡" not in corrected.bundle.to_prompt_text()
    service.forget(new.memory_id, now=23)
    forgotten = service.retrieve("我喜欢喝什么", now=24)
    assert forgotten.trace.status == "unknown"
    assert "绿茶" not in forgotten.bundle.to_prompt_text()


def test_explicit_live_query_does_not_recall_stale_task_memory(tmp_path):
    service = make_service(tmp_path)
    service.remember(kind="任务经验", title="任务", summary="Relay 的任务昨天完成了", source="executor",
                     now=10, scope="task_experience", source_ids=("run:1",))
    result = service.retrieve("Relay 的任务完成了吗", now=20)
    assert result.trace.status == "external_unavailable"
    assert result.trace.retrieval_calls == 0
    assert not result.bundle.memories


def test_plan_is_not_completed_episode(tmp_path):
    service = make_service(tmp_path)
    service.remember(kind="玩家希望被记住", title="游戏计划", summary="用户计划周末一起玩星际游戏", source="user_chat",
                     now=10, source_ids=("turn:1",), metadata={"plan_status": "planned", "fact_slot": "plan"})
    result = service.retrieve("我们上次一起玩星际游戏发生了什么", now=20)
    assert not result.bundle.memories
    assert result.trace.status == "unknown"


def test_expired_fact_can_be_historical_but_forgotten_cannot(tmp_path):
    service = make_service(tmp_path)
    old = fact(service, "用户住在杭州", predicate="居住地", value="杭州", valid_until=15)
    assert service.retrieve("我现在住在哪里", now=20).trace.status == "unknown"
    history = service.retrieve("我以前住在哪里", now=20)
    assert old.memory_id in history.trace.selected_memory_ids
    assert history.bundle.to_prompt_payload()["retrieval"]["temporal_mode"] == "history"
    service.forget(old.memory_id, now=21)
    assert service.retrieve("我以前住在哪里", now=22).trace.status == "unknown"


def test_task_context_has_explicit_scope_and_preconditions(tmp_path):
    service = make_service(tmp_path)
    task = service.remember(kind="任务经验", title="部署失败", summary="部署因端口被占用而失败", source="executor",
        now=10, scope="task_experience", source_ids=("run:2",),
        metadata={"app": "web", "version": "1.0", "outcome": "failed", "preconditions": ["端口80"]})
    assert not service.retrieve("今天有点无聊", now=20).bundle.memories
    result = service.retrieve("上次部署为什么失败", now=20)
    assert task.memory_id in result.trace.selected_memory_ids

