from dataclasses import replace
import json

import pytest

from guanghe_companion.emotional_memory import EmotionalMemoryStore
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_hierarchy import validate_layers
from guanghe_companion.retrieval_contract import ExternalStateEvidence


def service(root):
    return EmotionalMemoryService(root=root, character_id="xingxi_pixel_pet")


def event(memory, text="我们一起完成了星际游戏第一关", now=10, **extra):
    return memory.remember(kind="玩耍", title="星际游戏", summary=text, source="game_event",
        source_ids=("game:" + str(now),), now=now, importance=.8, **extra)


def test_overview_is_extractive_and_detail_expands_without_double_count(tmp_path):
    memory = service(tmp_path)
    rows = [event(memory, f"我们一起完成了星际游戏第{n}关", now=n) for n in (10, 11, 12)]
    memory.consolidate(now=15, shared_only=True)
    overview = memory.retrieve("还记得我们一起玩的星际游戏吗", now=20)
    payload = overview.bundle.to_prompt_payload()
    assert overview.trace.evidence_level == "L1"
    assert "shared_memories" not in payload
    assert validate_layers(payload["memory_overview"], overview.bundle.memories)
    assert len({c["source_memory_id"] for c in payload["memory_overview"]["claims"]}) == 3
    details = memory.retrieve("详细讲讲那次", now=21,
        history=({"role": "user", "text": "还记得我们一起玩的星际游戏吗"},))
    assert details.plan.inherited_context
    assert details.trace.evidence_level == "L2"
    assert "memory_overview" not in details.bundle.to_prompt_payload()
    assert {r["memory_id"] for r in details.bundle.to_prompt_payload()["shared_memories"]} == {r.memory_id for r in rows}


def test_chapter_free_prose_cannot_create_a_new_claim(tmp_path):
    memory = service(tmp_path)
    for n in (10, 11, 12):
        event(memory, now=n)
    chapter = memory.consolidate(now=15, shared_only=True)
    memory.store.upsert_chapter(replace(chapter, summary="虚构我们一起赢得世界冠军"))
    result = memory.retrieve("还记得我们一起玩的星际游戏吗", now=20)
    assert "世界冠军" not in result.bundle.to_prompt_text()
    assert validate_layers(result.bundle.overview, result.bundle.memories)


def test_explicit_source_expansion_authenticates_overview_version(tmp_path):
    memory = service(tmp_path)
    original = event(memory)
    overview = memory.retrieve("还记得我们一起玩的星际游戏吗", now=20)
    claims = overview.bundle.overview["claims"]
    bindings = {c["source_memory_id"]: c["source_fingerprint"] for c in claims}
    detail = memory.expand_sources(bindings, expected_epoch=overview.bundle.context_epoch, now=21)
    assert detail.trace.status == "sufficient"
    assert detail.trace.evidence_level == "L2"
    assert detail.bundle.memories[0].memory_id == original.memory_id
    assert not detail.bundle.overview
    memory.forget(original.memory_id, now=22)
    stale = memory.expand_sources(bindings, expected_epoch=overview.bundle.context_epoch, now=23)
    assert stale.trace.status == "unavailable"
    assert not stale.bundle.memories
    assert original.summary not in stale.bundle.to_prompt_text()


def test_source_expansion_checks_fingerprint_and_role_without_search(tmp_path):
    memory = service(tmp_path)
    original = event(memory)
    foreign = EmotionalMemoryService(root=tmp_path, character_id="other")
    other = event(foreign, "我们一起去了花园", now=12)
    result = memory.expand_sources({original.memory_id: "obsolete", other.memory_id: other.evidence_fingerprint()},
                                   expected_epoch=memory.store.context_epoch, now=20)
    assert result.trace.status == "unknown"
    assert not result.bundle.memories
    assert result.trace.rows_loaded <= 1


def test_source_expansion_respects_an_explicit_task_scope(tmp_path):
    memory = service(tmp_path)
    row = memory.remember(kind="任务经验", title="导出", summary="将采样率统一为44kHz后导出成功",
        source="executor", source_ids=("run:1",), scope="task_experience", now=10,
        metadata={"outcome": "succeeded", "app": "audio-editor"})
    result = memory.expand_sources({row.memory_id: row.evidence_fingerprint()},
        expected_epoch=memory.store.context_epoch, now=20, scope="task_experience")
    assert result.trace.status == "sufficient"
    assert result.bundle.memories == (memory.store.load_memories()[0],)


def test_multiple_sources_of_one_event_do_not_create_a_longer_relationship(tmp_path):
    from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
    runtime = CompanionStoryRuntime.create(user_data_root=tmp_path, character_id="xingxi_pixel_pet")
    memory = runtime.memory
    memory.remember(kind="玩耍", title="共同画画", summary="我们一起完成了一幅画", source="game_event",
                    source_ids=("session:1", "artifact:1", "event:1"), now=10)
    state = runtime.relationship_development(now=20)
    assert state["shared_moment_count"] == 1
    assert state["expression_stage"] == "first_shared_moments"


def test_overlapping_event_origins_are_one_event_with_multiple_claims(tmp_path):
    from guanghe_companion.memory_hierarchy import build_layers
    memory = service(tmp_path)
    a = memory.remember(kind="玩耍", title="画画", summary="我们一起画了背景", source="game_event",
                        source_ids=("session:1", "step:1"), now=10)
    b = memory.remember(kind="玩耍", title="画画", summary="我们一起画了人物", source="game_event",
                        source_ids=("session:1", "step:2"), now=11)
    layer = build_layers((a, b))
    assert len(layer.overview["claims"]) == 2
    assert layer.overview["catalog"]["event_count"] == 1


@pytest.mark.parametrize("status", ["pending", "queued", "running", "in_progress", "cancelled"])
def test_unfinished_event_never_counts_as_shared_past_or_relationship(tmp_path, status):
    from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
    runtime = CompanionStoryRuntime.create(user_data_root=tmp_path, character_id="xingxi_pixel_pet")
    row = runtime.memory.remember(kind="玩耍", title="种花", summary="我们一起种花，准备种下三盆向日葵",
        source="game_event", source_ids=("game:queued:1",), now=10, metadata={"event_status": status})
    result = runtime.memory.retrieve("还记得我们一起种花吗", now=20)
    assert row.memory_id not in result.trace.selected_memory_ids
    assert not result.bundle.overview
    assert runtime.relationship_development(now=20)["shared_moment_count"] == 0


def test_forget_during_ranking_fences_all_levels_and_keeps_other_evidence(tmp_path):
    memory, other = service(tmp_path), service(tmp_path)
    old = event(memory, "我们一起完成了星际游戏第一关", now=10)
    kept = event(memory, "我们一起完成了星际游戏第二关", now=11)
    calls = []
    def rank(query, entries):
        calls.append(entries)
        if len(calls) == 1:
            other.forget(old.memory_id, now=19)
        return {e.memory_id: .99 for e in entries}
    memory.semantic_retriever = rank
    result = memory.retrieve("还记得我们一起玩的星际游戏吗", now=20)
    assert result.trace.retries == 1
    assert "第一关" not in result.bundle.to_prompt_text()
    assert kept.memory_id in result.trace.selected_memory_ids
    assert validate_layers(result.bundle.overview, result.bundle.memories)


def test_raw_legacy_writer_cannot_hide_changed_fingerprint(tmp_path):
    memory = service(tmp_path)
    old = event(memory)
    calls = 0
    def rank(query, entries):
        nonlocal calls
        calls += 1
        if calls == 1:
            with memory.store._document() as doc:
                doc["entries"][0]["summary"] = "我们一起完成了星际游戏第三关"
        return {e.memory_id: .99 for e in entries}
    memory.semantic_retriever = rank
    result = memory.retrieve("我们一起玩的星际游戏还记得吗", now=20)
    assert result.trace.retries == 1
    assert "第一关" not in result.bundle.to_prompt_text()
    assert "第三关" in result.bundle.to_prompt_text()


def test_indexed_chat_never_calls_full_document_reader(tmp_path, monkeypatch):
    memory = service(tmp_path)
    event(memory)
    memory.retrieve("你好", now=20)  # finish any initial projection migration
    def fail(*args):
        pytest.fail("a warm read should not open the full JSON document")
    monkeypatch.setattr(EmotionalMemoryStore, "_document", fail)
    result = memory.retrieve("今天有点无聊", now=21)
    assert result.trace.retrieval_calls == 0
    assert result.trace.rows_loaded == 0


def test_live_state_is_scoped_current_and_never_persisted(tmp_path):
    memory = service(tmp_path)
    memory.external_state_readers["relay"] = lambda intent, now: ExternalStateEvidence(
        "relay", "本轮任务正在执行第2步", now-1, now+30, "relay:run-42", memory.character_id)
    result = memory.retrieve("Relay 的任务完成了吗", now=20)
    assert result.trace.status == "sufficient"
    assert result.bundle.external_state[0].source_id == "relay:run-42"
    assert memory.store.load_memories() == ()
    memory.external_state_readers["relay"] = lambda intent, now: ExternalStateEvidence(
        "relay", "其他用户的状态", now-1, now+30, "relay:run-99", memory.character_id, owner_id="other")
    result = memory.retrieve("Relay 的任务完成了吗", now=21)
    assert result.trace.status == "external_unavailable"
    assert not result.bundle.external_state


def test_persona_configuration_is_unmodified_by_retrieval_lifecycle(tmp_path):
    from guanghe_companion.character_pack import load_default_character_pack
    from guanghe_companion.persona import build_persona_payload
    before = build_persona_payload(load_default_character_pack())
    memory = service(tmp_path)
    row = event(memory)
    memory.retrieve("我们一起玩的星际游戏还记得吗", now=20)
    memory.correct(row.memory_id, title="游戏", summary="我们一起完成了星际游戏第三关", now=21)
    memory.forget(row.memory_id, now=22)
    memory.retrieve("我们一起玩的星际游戏还记得吗", now=23)
    after = build_persona_payload(load_default_character_pack())
    assert before == after
    assert len(after["config_hash"]) == 64


def test_chapter_does_not_repeat_same_event_source(tmp_path):
    memory = service(tmp_path)
    first = event(memory, now=10)
    memory.store.upsert_memory(replace(first, memory_id="second-card", title="同一事件的另一张卡"))
    result = memory.retrieve("还记得我们一起玩的星际游戏吗", now=20)
    assert result.bundle.overview["catalog"]["event_count"] == 1
    assert len(result.bundle.overview["claims"]) == 1


def test_chat_write_parser_skips_full_archive_when_no_write_intent(tmp_path, monkeypatch):
    from guanghe_companion.chat_memory import ChatMemory
    memory = service(tmp_path)
    event(memory)
    chat = ChatMemory(memory, tmp_path / "settings.json")
    def fail(*args):
        pytest.fail("chat without a fact/forget must not read the whole archive")
    monkeypatch.setattr(EmotionalMemoryStore, "load_memories", fail)
    for text in ("今天有点无聊", "我的牙医叫什么名字", "帮我写一个笑话"):
        assert chat.process(text, now=20).status == "ignored"


def test_zero_hit_profile_also_has_final_fingerprint_fence(tmp_path, monkeypatch):
    memory, writer = service(tmp_path), service(tmp_path)
    row = memory.remember(kind="用户自述", title="偏好", summary="用户喜欢咖啡",
        source="explicit_user_request", now=10, source_ids=("statement:1",))
    memory.update_bond_profile(now=11, new_preference=row.summary, source_memory_ids=(row.memory_id,))
    original = EmotionalMemoryStore.finalize_indexed_recall
    calls = 0
    def intercept(store, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            with writer.store._document() as document:
                document["entries"][0]["summary"] = "用户喜欢绿茶"
        return original(store, *args, **kwargs)
    monkeypatch.setattr(EmotionalMemoryStore, "finalize_indexed_recall", intercept)
    result = memory.retrieve("今天有点无聊", now=20)
    assert result.trace.retries == 1
    assert "咖啡" not in result.bundle.to_prompt_text()


def test_entity_resolution_proof_is_validated_and_delivered(tmp_path):
    memory = service(tmp_path)
    name = memory.remember(kind="用户事实", title="姓名", summary="用户的教练叫沈原", source="user_chat",
        now=10, source_ids=("statement:name",), metadata={"fact_subject": "relation:教练", "fact_predicate": "name",
        "fact_slot": "relation:教练:name", "fact_value": "沈原", "subject_aliases": ["沈原"]})
    job = memory.remember(kind="用户事实", title="职业", summary="用户的教练从事游泳教学", source="user_chat",
        now=11, source_ids=("statement:job",), metadata={"fact_subject": "relation:教练", "fact_predicate": "occupation",
        "fact_slot": "relation:教练:occupation", "fact_value": "游泳教学"})
    result = memory.retrieve("沈原的职业是什么", now=20)
    assert job.memory_id in result.trace.selected_memory_ids
    assert result.bundle.resolution_evidence[0]["memory_id"] == name.memory_id
    assert name.memory_id not in result.trace.selected_memory_ids
    memory.forget(name.memory_id, now=21)
    result = memory.retrieve("沈原的职业是什么", now=22)
    assert not result.bundle.resolution_evidence
    assert not result.bundle.memories

