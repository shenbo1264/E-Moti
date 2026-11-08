import json
from dataclasses import replace

import pytest

from guanghe_companion.chat_memory import ChatMemory
from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_album_controller import MemoryAlbumController
from guanghe_companion.memory_hierarchy import build_layers
from guanghe_companion.memory_source_spans import resolve_source_spans, source_span_metadata


def test_forgetting_one_fact_does_not_leak_from_another_facts_source(tmp_path):
    story = CompanionStoryRuntime.create(user_data_root=tmp_path, character_id="xingxi_pixel_pet")
    chat = ChatMemory(story.memory, tmp_path / "mode.json")
    text = "我的室友叫林岚，我的邻居住在苏州。"
    assert chat.process(text, now=10).status == "saved"
    rows = story.memory.store.load_memories()
    forgotten = next(row for row in rows if "林岚" in row.summary)
    kept = next(row for row in rows if "苏州" in row.summary)
    album = MemoryAlbumController(story)
    album.forget(forgotten.memory_id, now=20)
    details = album.source_details(kept.memory_id, now=20)
    assert "苏州" in json.dumps(details, ensure_ascii=False)
    assert "林岚" not in json.dumps(details, ensure_ascii=False)


def test_one_shared_event_with_distinct_receipts_counts_once(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    rows = [memory.remember(kind="玩耍", title="合作拼图", summary=summary, source="game_event",
        now=10, source_ids=(source,), metadata={"event_id": "puzzle-session-17"})
        for source, summary in (("chat:17", "我们一起完成拼图"), ("artifact:17", "拼图成果已经保存"))]
    assert build_layers(tuple(rows)).overview["catalog"]["event_count"] == 1


def test_distinct_event_ids_are_not_merged_by_a_shared_parent_source(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    rows = [memory.remember(kind="玩耍", title="合作拼图", summary=f"我们完成了第 {index} 次拼图",
        source="game_event", now=index, source_ids=("game-session:shared",), metadata={"event_id": f"puzzle:{index}"})
        for index in (10, 11)]
    assert build_layers(tuple(rows)).overview["catalog"]["event_count"] == 2


def test_executor_completion_is_not_user_accepted_shared_experience(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    row = memory.remember(kind="共同经历", title="相册整理", summary="执行器报告完成相册整理",
        source="executor", now=10, source_ids=("run:17",), user_confirmed=False,
        metadata={"run_id": "17", "event_status": "completed", "participants": ["user:self", "character:self"],
                  "user_accepted": False})
    assert not build_layers((row,)).overview


def test_album_does_not_guess_unix_from_large_logical_timestamp(tmp_path):
    story = CompanionStoryRuntime.create(user_data_root=tmp_path, character_id="xingxi_pixel_pet")
    story.memory.remember(kind="用户自述", title="偏好", summary="用户喜欢陶艺", source="user_chat",
                          now=1_100_000_000, source_ids=("chat:1",))
    assert story.memory.time_basis == "logical"
    assert MemoryAlbumController(story)._now(None) == 1_100_000_000


def sourced(memory, text, quote, *, now=10, valid_until=0):
    return memory.remember(kind="用户自述", title="原话片段", summary=quote, source="user_chat",
        now=now, valid_until=valid_until, source_ids=("chat:" + quote,),
        metadata={"message_id": "message:7", "original_quote": text, **source_span_metadata(text, quote)})


def test_overlapping_original_quote_is_withheld_after_one_claim_is_forgotten(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我的室友叫林岚，我的邻居住在苏州。"
    broad = sourced(memory, text, text)
    withdrawn = sourced(memory, text, "我的室友叫林岚")
    memory.forget(withdrawn.memory_id, now=20)
    result = resolve_source_spans(memory.store, {broad.memory_id: broad.evidence_fingerprint()},
                                 expected_epoch=memory.store.context_epoch, now=20)
    assert result["spans"] == []
    assert result["unavailable_sources"][broad.memory_id] == "invalid_or_revoked_source"
    assert next(row for row in memory.store.load_memories() if row.memory_id == broad.memory_id).deleted


def test_disjoint_source_span_survives_sibling_expiry_and_restart(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我住在青岛，我喜欢陶艺。"
    sourced(memory, text, "我住在青岛", valid_until=15)
    kept = sourced(memory, text, "我喜欢陶艺")
    memory.store.expire_memories(now=20)
    reopened = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    result = resolve_source_spans(reopened.store, {kept.memory_id: kept.evidence_fingerprint()},
                                 expected_epoch=reopened.store.context_epoch, now=20)
    assert result["status"] == "sufficient"
    assert [span["text"] for span in result["spans"]] == ["我喜欢陶艺"]
    assert "青岛" not in json.dumps(result, ensure_ascii=False)


def test_source_spans_check_epoch_fingerprint_scope_and_character(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    row = sourced(memory, "我喜欢陶艺。", "我喜欢陶艺")
    bindings = {row.memory_id: row.evidence_fingerprint()}
    epoch = memory.store.context_epoch
    assert not resolve_source_spans(memory.store, bindings, expected_epoch=epoch, now=10, scope="task_experience")["spans"]
    foreign = EmotionalMemoryService(root=tmp_path, character_id="other")
    assert not resolve_source_spans(foreign.store, bindings, expected_epoch=foreign.store.context_epoch, now=10)["spans"]
    memory.correct(row.memory_id, title="更正", summary="我喜欢木工", now=20)
    assert resolve_source_spans(memory.store, bindings, expected_epoch=epoch, now=20)["status"] == "unavailable"
    assert not resolve_source_spans(memory.store, bindings, expected_epoch=memory.store.context_epoch, now=20)["spans"]


def test_legacy_source_without_span_does_not_guess_a_safe_full_quote(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    row = memory.remember(kind="用户自述", title="偏好", summary="我喜欢陶艺", source="user_chat", now=10,
        source_ids=("legacy:1",), metadata={"message_id": "legacy:1", "original_quote": "我住在青岛，我喜欢陶艺。"})
    result = resolve_source_spans(memory.store, {row.memory_id: row.evidence_fingerprint()},
                                 expected_epoch=memory.store.context_epoch, now=10)
    assert not result["spans"]
    assert result["unavailable_sources"][row.memory_id] == "unbound_source_span"


def test_edited_source_text_does_not_keep_an_old_span_binding(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    row = sourced(memory, "我喜欢陶艺", "我喜欢陶艺")
    tampered = replace(row, metadata={**row.metadata, "original_quote": "我喜欢其他东西"})
    memory.store.upsert_memory(tampered)
    result = resolve_source_spans(memory.store, {tampered.memory_id: tampered.evidence_fingerprint()},
                                 expected_epoch=memory.store.context_epoch, now=10)
    assert not result["spans"]


def test_ambiguous_duplicate_quote_is_not_assigned_an_arbitrary_offset():
    assert not source_span_metadata("你好，你好", "你好")
    with pytest.raises(ValueError, match="span"):
        source_span_metadata("我喜欢陶艺", "陶艺", start=0)


def test_reality_change_retains_history_while_correction_revokes_it(tmp_path):
    from guanghe_companion.memory_lifecycle import change_memory
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    old = sourced(memory, "我住在青岛", "我住在青岛")
    replacement = replace(old, memory_id="move:2", title="居住地", summary="我住在大连",
                          source_ids=("move:2",), metadata={})
    changed = change_memory(memory.store, old.memory_id, replacement, now=30, effective_at=20)
    rows = {entry.memory_id: entry for entry in memory.store.load_memories()}
    assert not rows[old.memory_id].deleted
    assert rows[old.memory_id].is_active(now=19)
    assert not rows[old.memory_id].is_active(now=20)
    assert changed.is_active(now=20)
    assert changed.occurred_at == 20 and changed.created_at == 30
    assert changed.supersedes == old.memory_id
    memory.correct(changed.memory_id, title="居住地", summary="我住在烟台", now=40)
    assert next(row for row in memory.store.load_memories() if row.memory_id == changed.memory_id).deleted


def test_purge_removes_history_and_original_text_without_removing_unrelated_fact(tmp_path):
    from guanghe_companion.memory_lifecycle import change_memory, purge_memory
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我住在青岛，我喜欢陶艺。"
    old = sourced(memory, text, "我住在青岛")
    kept = sourced(memory, text, "我喜欢陶艺")
    changed = change_memory(memory.store, old.memory_id,
        replace(old, memory_id="move:2", summary="我住在大连", source_ids=("move:2",), metadata={}),
        now=20, effective_at=20)
    assert set(purge_memory(memory.store, changed.memory_id, now=30)) == {old.memory_id, changed.memory_id}
    with memory.store._document() as document:
        payload = json.dumps(document, ensure_ascii=False)
    assert "青岛" not in payload and "大连" not in payload
    assert "陶艺" in payload
    assert memory.store.upsert_memory(old).deleted
    assert memory.store.upsert_memory(replace(old, memory_id="replayed-with-new-id")).deleted
    current = next(row for row in memory.store.load_memories() if row.memory_id == kept.memory_id)
    assert current.is_active(now=30)
    assert not resolve_source_spans(memory.store, {current.memory_id: current.evidence_fingerprint()},
        expected_epoch=memory.store.context_epoch, now=30)["spans"]


def test_legacy_time_basis_is_not_guessed_and_new_unix_basis_survives_restart(tmp_path):
    from guanghe_companion.memory_time import bind_archive_time, temporal_metadata
    legacy = EmotionalMemoryService(root=tmp_path / "old", character_id="xingxi_pixel_pet")
    legacy.remember(kind="用户自述", title="偏好", summary="喜欢木工", source="user_chat", now=1_900_000_000)
    assert bind_archive_time(legacy.store) == ("logical", "")
    with pytest.raises(ValueError, match="time basis"):
        bind_archive_time(legacy.store, time_basis="unix")
    fresh = EmotionalMemoryService(root=tmp_path / "new", character_id="xingxi_pixel_pet",
                                   time_basis="unix", timezone_name="Asia/Shanghai")
    assert bind_archive_time(fresh.store, time_basis="unix", timezone_name="Asia/Shanghai") == ("unix", "Asia/Shanghai")
    assert bind_archive_time(fresh.store) == ("unix", "Asia/Shanghai")
    meta = temporal_metadata(time_basis="unix", timezone_name="Asia/Shanghai", now=100, occurred_at=80)
    assert meta["time_basis"] == "unix" and meta["recorded_time"] == 100 and meta["occurred_time"] == 80
    with pytest.raises(ValueError):
        temporal_metadata(time_basis="logical", timezone_name="Asia/Shanghai", now=100)


def test_lifecycle_rejects_stale_writes_future_changes_and_source_replay(tmp_path):
    from guanghe_companion.memory_lifecycle import change_memory, purge_memory
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    old = sourced(memory, "我住在青岛", "我住在青岛")
    replacement = replace(old, memory_id="move:2", summary="我住在大连", source_ids=("move:2",), metadata={})
    epoch = memory.store.context_epoch
    for effective_at in (0, 31):
        with pytest.raises(ValueError, match="interval"):
            change_memory(memory.store, old.memory_id, replacement, now=30, effective_at=effective_at)
    changed = change_memory(memory.store, old.memory_id, replacement, now=30, effective_at=20, expected_epoch=epoch)
    with pytest.raises(ValueError, match="stale"):
        purge_memory(memory.store, changed.memory_id, now=40, expected_epoch=epoch)
    purge_memory(memory.store, changed.memory_id, now=40, expected_epoch=memory.store.context_epoch)
    with pytest.raises(ValueError, match="source"):
        memory.store.save_pending_candidate("replayed", replace(old, memory_id="new-replay-id"),
            requires_user_confirmation=True, expected_epoch=memory.store.context_epoch)


def test_forgetting_current_fact_revokes_retained_historical_revisions(tmp_path):
    from guanghe_companion.memory_lifecycle import change_memory, forget_fact_memory
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    old = sourced(memory, "我住在青岛", "我住在青岛")
    changed = change_memory(memory.store, old.memory_id,
        replace(old, memory_id="move:2", summary="我住在大连", source_ids=("move:2",), metadata={}),
        now=20, effective_at=20)
    forget_fact_memory(memory.store, changed.memory_id, now=30)
    assert all(entry.deleted for entry in memory.store.load_memories())


@pytest.mark.parametrize("zone,query,start,end", [
    ("Asia/Shanghai", "2026年11月1日我们一起做了什么", "2026-10-31T16:00:00+00:00", "2026-11-01T16:00:00+00:00"),
    ("America/Los_Angeles", "2026年3月8日我们一起做了什么", "2026-03-08T08:00:00+00:00", "2026-03-09T07:00:00+00:00"),
    ("America/Los_Angeles", "2026年11月1日我们一起做了什么", "2026-11-01T07:00:00+00:00", "2026-11-02T08:00:00+00:00"),
])
def test_calendar_day_uses_archive_timezone_and_actual_day_length(zone, query, start, end):
    from datetime import datetime
    from guanghe_companion.retrieval_router import MemoryRetrievalRouter
    router = MemoryRetrievalRouter(time_basis="unix", timezone_name=zone)
    intent = router.plan(query, now=1_800_000_000).intents[0]
    assert intent.temporal_mode == "as_of"
    assert (intent.as_of, intent.as_of_end) == (int(datetime.fromisoformat(start).timestamp()),
                                               int(datetime.fromisoformat(end).timestamp()))


def test_relative_calendar_month_uses_local_year_boundary():
    from datetime import datetime
    from guanghe_companion.retrieval_router import MemoryRetrievalRouter
    now = int(datetime.fromisoformat("2026-12-31T17:00:00+00:00").timestamp())
    router = MemoryRetrievalRouter(time_basis="unix", timezone_name="Asia/Shanghai")
    intent = router.plan("上个月我们一起做了什么", now=now).intents[0]
    assert intent.as_of == int(datetime.fromisoformat("2026-11-30T16:00:00+00:00").timestamp())
    assert intent.as_of_end == int(datetime.fromisoformat("2026-12-31T16:00:00+00:00").timestamp())
    logical = MemoryRetrievalRouter(time_basis="logical")
    assert logical.plan("2026年11月1日我们一起做了什么", now=now).intents[0].temporal_mode == "unresolved"


@pytest.mark.parametrize("date_text", ["五月四号", "二零二六年五月四日", "二千零二十六年五月四号"])
def test_chinese_calendar_date_is_host_resolved(date_text):
    from datetime import datetime
    from guanghe_companion.retrieval_router import MemoryRetrievalRouter
    router = MemoryRetrievalRouter(time_basis="unix", timezone_name="Asia/Shanghai")
    now = int(datetime.fromisoformat("2026-05-10T00:00:00+00:00").timestamp())
    intent = router.plan(f"如果按{date_text}那会儿，我住在哪里？", now=now).intents[0]
    assert intent.temporal_mode == "as_of"
    assert intent.as_of == int(datetime.fromisoformat("2026-05-03T16:00:00+00:00").timestamp())
    assert intent.as_of_end == int(datetime.fromisoformat("2026-05-04T16:00:00+00:00").timestamp())


@pytest.mark.parametrize("date_text", ["五月四十号", "农历五月四日", "五月某号", "五月上旬", "五月初四", "十十月四号"])
def test_unsupported_explicit_calendar_date_does_not_become_current(date_text):
    from guanghe_companion.retrieval_router import MemoryRetrievalRouter
    intent = MemoryRetrievalRouter().plan(f"{date_text}我住在哪里？", now=1_800_000_000).intents[0]
    assert intent.temporal_mode == "unresolved"


def test_calendar_number_normalization_does_not_change_serial_number_or_fact_query():
    from guanghe_companion.retrieval_router import MemoryRetrievalRouter
    query = "我的设备序列号是一二三号吗"
    intent = MemoryRetrievalRouter().plan(query).intents[0]
    assert intent.temporal_mode == "current"
    assert "一二三号" in intent.query


@pytest.mark.parametrize("basis", ["logical", "unix"])
@pytest.mark.parametrize("question,previous", [
    ("那现在做这个袋子，我该留多宽来着？", "五月初做午餐袋时，我留的缝份是多少？"),
    ("那目前这个收纳架，我该留多宽来着？", "2026年5月4日做收纳架时，我留的间距是多少？"),
])
def test_explicit_current_reference_inherits_topic_without_previous_calendar_time(basis, question, previous):
    from guanghe_companion.retrieval_router import MemoryRetrievalRouter
    plan = MemoryRetrievalRouter(time_basis=basis).plan(question, now=1_800_000_000,
        history=[{"role": "user", "content": previous}])
    assert plan.inherited_context
    memory_intents = [intent for intent in plan.intents if intent.route != "chat"]
    assert memory_intents
    assert all(intent.temporal_mode == "current" for intent in memory_intents)
    assert all(intent.as_of is None and intent.as_of_end is None for intent in memory_intents)
    assert any("缝份" in intent.query or "间距" in intent.query for intent in memory_intents)
