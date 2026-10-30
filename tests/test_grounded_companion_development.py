from dataclasses import replace

from guanghe_companion.capability_settings import ProactiveCompanionSettings
from guanghe_companion.chat_memory import ChatMemory
from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
from guanghe_companion.engine import create_initial_state
from guanghe_companion.proactive_companion import ProactiveCompanionService, proactive_rejection_cooldown_updates


def gift(index):
    return {"event_type": "inventory", "event_id": f"gift:{index}",
            "payload": {"action": "gift", "item_id": f"gift-{index}",
                        "item_name": f"纪念礼物{index}", "first_time": True}}


def story(tmp_path):
    return CompanionStoryRuntime.create(user_data_root=tmp_path, character_id="xingxi_pixel_pet")


def test_settled_experiences_automatically_consolidate_with_sources(tmp_path):
    runtime = story(tmp_path)
    for index in range(3):
        runtime.record_settled_events([gift(index)], now=100 + index)
    chapters = runtime.memory.valid_chapters(now=200)
    assert len(chapters) == 1
    assert len(chapters[0].source_fingerprints) == 3
    runtime.record_settled_events([gift(2)], now=102)
    assert len(runtime.memory.valid_chapters(now=200)) == 1


def test_chapter_keeps_chronological_event_bodies_and_evidence(tmp_path):
    from guanghe_companion.emotional_memory_reflection import MemoryReflectionService
    runtime = story(tmp_path)
    for index in range(3):
        runtime.record_settled_events([gift(index)], now=100 + index)
    entries = sorted(runtime.memory.store.load_memories(), key=lambda item: item.occurred_at)
    chapter = MemoryReflectionService().build_chapter(reversed(entries), character_id="xingxi_pixel_pet", now=200)
    assert chapter is not None
    positions = [chapter.summary.index(entry.summary) for entry in entries]
    assert positions == sorted(positions)
    assert "逻辑时间100—102秒" in chapter.summary
    assert "1970" not in chapter.summary
    assert "UTC" not in chapter.summary
    assert "赠礼记录3次" in chapter.summary
    assert "习惯" not in chapter.summary
    assert chapter.source_fingerprints == {entry.memory_id: entry.evidence_fingerprint() for entry in entries}


def test_chapter_budget_keeps_complete_events_and_matching_sources(tmp_path):
    from guanghe_companion.emotional_memory_reflection import MemoryReflectionService
    runtime = story(tmp_path)
    for index in range(3):
        runtime.record_settled_events([gift(index)], now=100 + index)
    entries = sorted(runtime.memory.store.load_memories(), key=lambda item: item.occurred_at)
    entries = [replace(entry, summary=f"事件{index}：" + "完整内容" * 25) for index, entry in enumerate(entries)]
    chapter = MemoryReflectionService().build_chapter(entries, character_id="xingxi_pixel_pet", now=200)
    assert chapter is not None and len(chapter.summary) <= 320
    assert len(chapter.source_memory_ids) == 2
    for entry in entries:
        assert (entry.summary in chapter.summary) == (entry.memory_id in chapter.source_memory_ids)
    assert set(chapter.source_fingerprints) == set(chapter.source_memory_ids)


def test_user_facts_do_not_become_shared_chapter_or_relationship(tmp_path):
    runtime = story(tmp_path)
    for index in range(3):
        pending = runtime.memory.propose_explicit_user_memory(f"请记住：我喜欢颜色{index}", now=100 + index)
        runtime.memory.confirm_candidate(pending, now=100 + index)
    runtime.record_settled_events([gift(1)], now=200)
    assert runtime.memory.valid_chapters(now=300) == ()
    assert runtime.relationship_development(now=300)["shared_moment_count"] == 1


def test_generic_proactive_memory_cannot_bypass_completion_gate(tmp_path):
    runtime = story(tmp_path)
    ids = runtime.record_settled_events([{
        "event_type": "memory", "event_id": "unaccepted:1",
        "payload": {"kind": "主动陪伴", "summary": "模型说一起完成了任务", "first_time": True},
    }], now=100)
    assert ids == []
    assert runtime.memory.store.load_memories() == ()


def test_recollection_and_development_disappear_when_evidence_is_forgotten(tmp_path):
    runtime = story(tmp_path)
    ids = runtime.record_settled_events([gift(1)], now=100)
    candidate = runtime.memory_recollection(now=1000)
    assert candidate is not None
    assert runtime.is_recollection_current(candidate, now=1000)
    assert runtime.relationship_development(now=1000)["source_memory_ids"] == ids
    runtime.memory.forget(ids[0], now=1001)
    assert not runtime.is_recollection_current(candidate, now=1002)
    assert runtime.memory_recollection(now=1002) is None
    assert runtime.relationship_development(now=1002)["shared_moment_count"] == 0


def test_recollection_requires_idle_and_existing_permission_gates(tmp_path):
    runtime = story(tmp_path)
    runtime.record_settled_events([gift(1)], now=100)
    candidate = runtime.memory_recollection(now=50000)
    state = replace(create_initial_state(now=49000), character_id="xingxi_pixel_pet")
    settings = ProactiveCompanionSettings(enabled=True)

    def decide(config=settings, last=None, current_state=state):
        return ProactiveCompanionService(state=current_state, previous_state=current_state, now=50000,
            settings=config, last_proactive_at=last or {}, daily_counts={},
            memory_candidate=candidate).select_decision("Default")

    decision = decide()
    assert decision.feedback.kind == "memory_recollection"
    assert decision.feedback.memory_source == candidate
    assert decision.memory_drafts() == []
    assert decide(replace(settings, enabled=False)).feedback is None
    assert decide(replace(settings, quiet_hours_enabled=True, quiet_start="00:00", quiet_end="23:59")).feedback is None
    assert decide(last=proactive_rejection_cooldown_updates(kind="memory_recollection", now=49999)).feedback is None
    assert decide(current_state=replace(state, last_interaction_at=49990)).feedback is None


def test_same_memory_is_not_repeated_during_daily_recollection_cooldown(tmp_path):
    runtime = story(tmp_path)
    runtime.record_settled_events([gift(1)], now=100)
    candidate = runtime.memory_recollection(now=1000)
    assert candidate is not None
    assert runtime.memory_recollection(now=2000, last_proactive_at={candidate.cooldown_key: 1000}) is None
    assert runtime.memory_recollection(now=90000, last_proactive_at={candidate.cooldown_key: 1000}) is not None


def test_recent_dialogue_suppresses_memory_even_when_game_state_is_idle(tmp_path):
    runtime = story(tmp_path)
    runtime.record_settled_events([gift(1)], now=100)
    candidate = runtime.memory_recollection(now=1000)
    state = replace(create_initial_state(now=100), character_id="xingxi_pixel_pet")

    def decide(last_dialogue_at, cooldown=60):
        return ProactiveCompanionService(
            state=state, previous_state=state, now=1000,
            settings=ProactiveCompanionSettings(enabled=True, global_cooldown_seconds=cooldown),
            last_proactive_at={}, daily_counts={}, memory_candidate=candidate,
            forced_kind="memory_recollection", last_dialogue_at=last_dialogue_at,
        ).select_feedback()

    assert decide(None).kind == "memory_recollection"
    assert decide(999) is None
    assert decide(701) is None
    assert decide(700).kind == "memory_recollection"
    assert decide(700, cooldown=600) is None
    assert decide(400, cooldown=600).kind == "memory_recollection"


def test_corrected_or_expired_source_cannot_replay_recollection(tmp_path):
    runtime = story(tmp_path)
    memory_id = runtime.record_settled_events([gift(1)], now=100)[0]
    entry = runtime.memory.store.load_memories()[0]
    runtime.memory.store.upsert_memory(replace(entry, valid_until=1200))
    candidate = runtime.memory_recollection(now=1000)
    assert candidate is not None
    assert not runtime.is_recollection_current(candidate, now=1200)
    assert runtime.relationship_development(now=1200)["shared_moment_count"] == 0
    runtime.memory.correct(memory_id, title="纠正", summary="原记录有误", now=1100)
    assert not runtime.is_recollection_current(candidate, now=1101)


def test_development_is_bounded_and_never_includes_model_or_observation(tmp_path):
    runtime = story(tmp_path)
    for index in range(8):
        runtime.record_settled_events([gift(index)], now=100 + index)
    for source in ("model", "observation", "explicit_user_request"):
        runtime.memory.remember(kind="共同学习", title="假设", summary="没有发生的经历", source=source,
                                now=200, source_ids=(source,), user_confirmed=True)
    development = runtime.relationship_development(now=1000)
    assert len(development["source_memory_ids"]) <= 6
    entries = {entry.memory_id: entry for entry in runtime.memory.store.load_memories()}
    assert all(entries[key].source == "game_event" for key in development["source_memory_ids"])
    assert "persona" not in development


def test_three_completed_user_confirmed_breaks_form_shared_chapter(tmp_path):
    runtime = story(tmp_path)
    for index in range(3):
        now = 10000 + index * 4000
        runtime.focus.inject_demo_focus(now=now, focused_minutes=52)
        runtime.focus.confirm_break(now=now + 1, duration_seconds_override=1)
        completed = runtime.focus.tick(now=now + 3)[0]
        runtime.record_focus_completion(completed, now=now + 3, event_id=f"completed:{index}")
    assert len(runtime.memory.valid_chapters(now=20000)) == 1


def test_approved_chat_interest_can_start_a_grounded_topic_without_shared_history(tmp_path):
    runtime = story(tmp_path)
    chat = ChatMemory(runtime.memory, tmp_path / "chat-settings.json")
    result = chat.process("我喜欢爬山", now=100)
    assert result.status == "saved"
    candidate = runtime.memory_recollection(now=50000)
    assert candidate is not None
    state = replace(create_initial_state(now=49000), character_id="xingxi_pixel_pet")
    decision = ProactiveCompanionService(state=state, previous_state=state, now=50000,
        settings=ProactiveCompanionSettings(enabled=True), last_proactive_at={}, daily_counts={},
        memory_candidate=candidate).select_decision("Default")
    assert "你之前提过" in decision.feedback.speech
    assert "爬山" in decision.feedback.speech
    assert "一起" not in decision.feedback.speech
    assert len(decision.feedback.speech) < 80
    assert runtime.relationship_development(now=50000)["shared_moment_count"] == 0
    runtime.memory.forget(result.memory_ids[0], now=50001)
    assert not runtime.is_recollection_current(candidate, now=50002)


def test_review_pending_and_dislikes_do_not_start_interest_topics(tmp_path):
    runtime = story(tmp_path)
    chat = ChatMemory(runtime.memory, tmp_path / "chat-settings.json")
    chat.set_mode("review")
    chat.process("我喜欢爬山", now=100)
    assert runtime.memory_recollection(now=1000) is None
    chat.set_mode("auto")
    chat.process("我不喜欢咖啡", now=101)
    assert runtime.memory_recollection(now=1000) is None
