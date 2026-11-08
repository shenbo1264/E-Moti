"""Regressions for semantic correction, lineage and authoritative retention.

All stores and candidates are synthetic; no model or network call is involved.
"""
from dataclasses import replace
import hashlib
import json
import sqlite3

import pytest

from guanghe_companion.capability_settings import ProactiveCompanionSettings
from guanghe_companion.chat_memory import ChatMemory
from guanghe_companion.chat_memory_extraction import ChatMemoryExtraction, MemoryProposal
from guanghe_companion.chat_memory_plans import correct_plan, prepare_plan, record_plan
from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
from guanghe_companion.emotional_memory import EmotionalMemoryEntry, EmotionalMemoryStore, MAX_SOURCE_IDS
from guanghe_companion.emotional_memory import MemoryChapter
from guanghe_companion.emotional_memory_policy import MemoryCandidate
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.engine import create_initial_state
from guanghe_companion.memory_album_controller import MemoryAlbumController
from guanghe_companion.proactive_companion import ProactiveCompanionService


def service(root):
    return EmotionalMemoryService(root=root, character_id="xingxi_pixel_pet")


def active(memory, now=1000):
    return [row for row in memory.store.load_memories() if row.is_active(now=now)]


def propose(text, value, predicate, domain, *, action="remember", targets=()):
    return MemoryProposal(action, text, value, predicate, domain, targets, "explicit", "personal")


def test_album_correction_updates_structured_value_and_actual_proactive_speech(tmp_path):
    story = CompanionStoryRuntime.create(user_data_root=tmp_path, character_id="xingxi_pixel_pet")
    memory = story.memory
    ChatMemory(memory, tmp_path / "settings.json").process("我喜欢咖啡", now=10)
    old = active(memory)[0]
    old_candidate = story.memory_recollection(now=400)
    MemoryAlbumController(story).correct(old.memory_id, title="饮料偏好", summary="用户喜欢绿茶", now=20)
    new = active(memory)[0]
    assert new.metadata["fact_value"] == "绿茶"
    assert new.metadata["fact_slot"] == "preference:饮料偏好:like"
    assert "咖啡" not in json.dumps(new.metadata, ensure_ascii=False)
    assert new.supersedes == old.memory_id
    assert not story.is_recollection_current(old_candidate, now=400)
    candidate = story.memory_recollection(now=400)
    assert candidate.interest_topic == "绿茶"
    state = replace(create_initial_state(now=0), character_id="xingxi_pixel_pet")
    feedback = ProactiveCompanionService(
        state=state, previous_state=state, now=400,
        settings=ProactiveCompanionSettings(enabled=True), last_proactive_at={},
        daily_counts={}, forced_kind="memory_recollection", memory_candidate=candidate,
    ).select_feedback()
    assert "绿茶" in feedback.speech and "咖啡" not in feedback.speech
    restarted = service(tmp_path)
    assert active(restarted)[0].metadata["fact_value"] == "绿茶"
    restarted.forget(new.memory_id, now=500)
    assert not restarted.recall("饮料偏好", now=501)


def test_unstructured_album_correction_does_not_keep_old_fact_atoms(tmp_path):
    story = CompanionStoryRuntime.create(user_data_root=tmp_path, character_id="xingxi_pixel_pet")
    ChatMemory(story.memory, tmp_path / "settings.json").process("我喜欢咖啡", now=10)
    old = active(story.memory)[0]
    text = "这一条改为旅行后的随手笔记"
    MemoryAlbumController(story).correct(old.memory_id, title="旅行笔记", summary=text, now=20)
    revised = active(story.memory)[0]
    assert revised.summary == text
    assert not any(key.startswith("fact_") for key in revised.metadata)
    assert "咖啡" not in json.dumps(revised.metadata, ensure_ascii=False)
    assert story.memory_recollection(now=400) is None
    assert any(row.memory_id == old.memory_id and row.deleted for row in story.memory.store.load_memories())


def test_semantic_metadata_mutation_revokes_derived_and_candidate_but_audit_time_does_not(tmp_path):
    story = CompanionStoryRuntime.create(user_data_root=tmp_path, character_id="xingxi_pixel_pet")
    memory = story.memory
    ChatMemory(memory, tmp_path / "settings.json").process("我喜欢咖啡", now=10)
    old = active(memory)[0]
    candidate = story.memory_recollection(now=400)
    epoch = memory.store.context_epoch
    updated = memory.store.upsert_memory(replace(old, metadata={**old.metadata, "fact_value": "绿茶"}))
    assert updated.evidence_fingerprint() != old.evidence_fingerprint()
    assert updated.version == old.version + 1
    assert memory.store.context_epoch == epoch + 1
    assert not memory.valid_profile(now=400).stable_preferences
    assert not story.is_recollection_current(candidate, now=400)
    epoch = memory.store.context_epoch
    audit = memory.store.upsert_memory(replace(updated, metadata={**updated.metadata, "recorded_at": "later"}))
    assert audit.evidence_fingerprint() == updated.evidence_fingerprint()
    assert audit.version == updated.version and memory.store.context_epoch == epoch


def test_wrong_self_field_correction_is_rejected_without_writes(tmp_path):
    memory = service(tmp_path)
    ChatMemory(memory, tmp_path / "settings.json").process("我住在成都", now=10)
    old = active(memory)[0]
    extractor = ChatMemoryExtraction(memory)
    text = "更正一下，我对花生是过敏的"
    envelope = extractor.prepare(text, now=20, mode="auto", generation=0)
    result = extractor.apply(envelope, (
        propose(text, "花生", "allergy", "过敏", action="correct", targets=(old.memory_id,)),
    ), now=20, mode="auto", generation=0)
    assert result.status == "clarify"
    assert [m.memory_id for m in active(memory)] == [old.memory_id]
    assert not memory.pending_candidates


@pytest.mark.parametrize("known_first_value", [False, True])
def test_conflicting_single_value_batch_is_rejected_before_any_write(tmp_path, known_first_value):
    memory = service(tmp_path)
    if known_first_value:
        ChatMemory(memory, tmp_path / "settings.json").process("我住在成都", now=10)
    before = memory.store.load_memories()
    extractor = ChatMemoryExtraction(memory)
    text = "我的常用称呼是小叶，我住在成都，我住在青岛"
    envelope = extractor.prepare(text, now=20, mode="auto", generation=0)
    result = extractor.apply(envelope, (
        propose("我的常用称呼是小叶", "小叶", "name", "称呼"),
        propose("我住在成都", "成都", "residence", "居住地"),
        propose("我住在青岛", "青岛", "residence", "居住地"),
    ), now=20, mode="auto", generation=0)
    assert result.status == "clarify"
    assert memory.store.load_memories() == before
    assert not memory.pending_candidates


def test_multi_value_preferences_in_same_batch_remain_available(tmp_path):
    memory = service(tmp_path)
    extractor = ChatMemoryExtraction(memory)
    text = "我喜欢爵士乐，我喜欢古典音乐"
    envelope = extractor.prepare(text, now=20, mode="auto", generation=0)
    result = extractor.apply(envelope, (
        propose("我喜欢爵士乐", "爵士乐", "like", "个人偏好"),
        propose("我喜欢古典音乐", "古典音乐", "like", "个人偏好"),
    ), now=20, mode="auto", generation=0)
    assert result.status == "saved"
    assert {m.metadata["fact_value"] for m in active(memory)} == {"爵士乐", "古典音乐"}


@pytest.mark.parametrize("mode", ["auto", "review"])
def test_many_corrections_keep_direct_sources_and_complete_revision_chain(tmp_path, mode):
    memory = service(tmp_path)
    chat = ChatMemory(memory, tmp_path / "settings.json")
    chat.process("我住在城市零", now=1)
    original = active(memory)[0]
    chat.set_mode(mode)
    count = 260
    for index in range(1, count + 1):
        result = chat.process(f"更正一下，我住在城市{index}", now=index + 1)
        if mode == "review":
            assert result.status == "pending"
            memory.confirm_candidate(next(iter(memory.pending_candidates)), now=index + 1)
        else:
            assert result.status == "saved"
        latest = active(memory)[0]
        assert len(latest.source_ids) == 1
    stored = {m.memory_id: m for m in service(tmp_path).store.load_memories()}
    cursor = latest
    traversed = []
    while cursor.supersedes:
        traversed.append(cursor.memory_id)
        cursor = stored[cursor.supersedes]
    assert cursor.memory_id == original.memory_id and len(traversed) == count
    assert len(stored) == count + 1
    memory.forget(original.memory_id, now=count + 100)
    assert not active(memory)


@pytest.mark.parametrize("mode", ["auto", "review"])
def test_plan_corrections_do_not_accumulate_source_limit(tmp_path, mode):
    memory = service(tmp_path)
    record_plan(memory, prepare_plan("我下周要去成都参加课程"), now=1, mode="auto")
    old = active(memory)[0]
    first_id = old.memory_id
    for index in range(1, 12):
        text = f"更正一下，我要去城市{index}"
        result = correct_plan(memory, old, summary=f"用户计划去城市{index}", value=f"城市{index}",
                              text=text, now=index + 2, mode=mode)
        if mode == "review":
            assert result.status == "pending"
            old = memory.confirm_candidate(next(iter(memory.pending_candidates)), now=index + 2)
        else:
            assert result.status == "saved"
            old = active(memory)[0]
        assert len(old.source_ids) == 1
        assert old.metadata["plan_status"] == "planned"
    memory.forget(first_id, now=100)
    assert not active(memory)


def test_more_than_300_memories_keep_pinned_fact_and_oldest_forget_target(tmp_path):
    memory = service(tmp_path)
    first = memory.remember(kind="用户事实", title="置顶", summary="不可被容量截断的重要记录",
                            source="user_chat", now=1, pinned=True, source_ids=("first-source",))
    for index in range(300):
        memory.remember(kind="事件", title=f"事件{index}", summary=f"事件内容{index}",
                        source="game_event", now=index + 2, source_ids=(f"event-{index}",))
    restarted = service(tmp_path)
    assert len(restarted.store.load_memories()) == 301
    assert next(m for m in restarted.store.load_memories() if m.memory_id == first.memory_id).pinned
    assert restarted.forget(first.memory_id, now=500) is not None
    assert not next(m for m in restarted.store.load_memories() if m.memory_id == first.memory_id).is_active(now=501)


def test_small_legacy_max_entries_does_not_truncate_batch_or_replacements(tmp_path):
    memory = service(tmp_path)
    memory.store = replace(memory.store, max_entries=2)
    entries = [EmotionalMemoryEntry(
        memory_id=f"memory-{index}", character_id="xingxi_pixel_pet", owner_id="local_user",
        kind="事件", title=f"事件{index}", summary=f"事件内容{index}", source="user_chat",
        occurred_at=index, created_at=index, updated_at=index,
    ) for index in range(6)]
    memory.store.save_memories(entries)
    assert len(memory.store.load_memories()) == 6
    revised = memory.correct(entries[0].memory_id, title="修订", summary="用户喜欢绿茶", now=10)
    pending_id = memory.propose_explicit_user_memory("请记住：新的独立记录", now=11)
    memory.confirm_candidate(pending_id, now=12)
    assert len(memory.store.load_memories()) == 8
    memory.forget(entries[0].memory_id, now=13)
    assert next(m for m in memory.store.load_memories() if m.memory_id == revised.memory_id).deleted


def test_oversized_direct_source_batch_still_fails_without_changing_old_fact(tmp_path):
    memory = service(tmp_path)
    old = memory.remember(kind="事实", title="旧事实", summary="用户住在成都", source="user_chat",
                          now=1, source_ids=("original",))
    with pytest.raises(ValueError, match="source"):
        memory.correct(old.memory_id, title="住处", summary="用户住在青岛", now=2,
                       source_ids=tuple(f"new-{n}" for n in range(MAX_SOURCE_IDS + 1)))
    assert active(memory)[0].memory_id == old.memory_id


def legacy_fingerprint(entry):
    fields = (entry.memory_id, entry.character_id, entry.owner_id, entry.kind, entry.title,
              entry.summary, entry.source, entry.source_ids, entry.tags, entry.occurred_at,
              entry.scope, entry.confidence, entry.valid_from, entry.valid_until, entry.version)
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False).encode("utf-8")).hexdigest()


def test_legacy_fingerprint_upgrade_rebases_valid_derived_once_and_preserves_facts(tmp_path):
    memory = service(tmp_path)
    ChatMemory(memory, tmp_path / "settings.json").process("我喜欢咖啡", now=10)
    entry = active(memory)[0]
    old_epoch = memory.store.context_epoch
    pending = MemoryCandidate(character_id=memory.character_id, owner_id=memory.owner_id,
        kind="待确认备注", title="当前偏好备注", summary="用户补充的备注", source="user_statement",
        occurred_at=12, source_ids=("legacy-pending",), requires_user_confirmation=True,
        metadata={"source_memory_ids": [entry.memory_id]})
    memory.propose_candidate(pending, pending_id="valid-pending", expected_epoch=old_epoch)
    with sqlite3.connect(memory.store.state_path) as db:
        document = json.loads(db.execute("SELECT payload FROM memory_state").fetchone()[0])
        document.setdefault("migrations", {}).pop("semantic_metadata_fingerprint_v1", None)
        document["profile"]["evidence"] = {f"stable_preferences:{entry.summary}":
                                          {entry.memory_id: legacy_fingerprint(entry)}}
        document["chapters"] = [MemoryChapter(chapter_id="valid-legacy-chapter",
            character_id=memory.character_id, title="阶段回忆", summary=entry.summary,
            source_memory_ids=(entry.memory_id,), created_at=12,
            source_fingerprints={entry.memory_id: legacy_fingerprint(entry)}).to_dict()]
        document["pending_candidates"]["valid-pending"]["source_fingerprints"] = {
            entry.memory_id: legacy_fingerprint(entry)}
        db.execute("UPDATE memory_state SET payload=?", (json.dumps(document, ensure_ascii=False),))
    reopened = service(tmp_path)
    assert reopened.store.context_epoch == old_epoch + 1
    assert active(reopened)[0].memory_id == entry.memory_id
    assert reopened.valid_profile(now=20).stable_preferences == (entry.summary,)
    assert reopened.valid_chapters(now=20)[0].summary == entry.summary
    assert reopened.confirm_candidate("valid-pending", now=20).summary == pending.summary
    assert reopened.store.context_epoch == old_epoch + 1
    assert service(tmp_path).store.context_epoch == old_epoch + 1
    reopened.forget(entry.memory_id, now=21)
    assert not reopened.valid_profile(now=22).stable_preferences
    assert not reopened.valid_chapters(now=22)


@pytest.mark.parametrize("summary, expected_value", [
    ("用户喜欢绿茶", "绿茶"),
    ("这一条改为旅行后的随手笔记", None),
])
def test_legacy_corrupted_album_edit_is_repaired_without_certifying_stale_profile(
        tmp_path, summary, expected_value):
    memory = service(tmp_path)
    chat = ChatMemory(memory, tmp_path / "settings.json")
    chat.process("我喜欢咖啡", now=10)
    old = active(memory)[0]
    chat.process("我喜欢爵士乐", now=11)
    unrelated = next(row for row in active(memory) if row.memory_id != old.memory_id)
    # Reproduce a pre-upgrade UI edit: new summary and old semantic atoms.
    broken = replace(old, memory_id="legacy-album-correction", summary=summary,
                     source="user_correction", version=old.version + 1, supersedes=old.memory_id,
                     created_at=20, updated_at=20,
                     metadata={**old.metadata, "corrected_by_user": True})
    old_epoch = memory.store.context_epoch
    pending = MemoryCandidate(character_id=memory.character_id, owner_id=memory.owner_id,
        kind="待确认备注", title="旧偏好备注", summary="旧偏好生成的备注", source="user_statement",
        occurred_at=12, source_ids=("stale-pending",), requires_user_confirmation=True,
        metadata={"source_memory_ids": [old.memory_id]})
    memory.propose_candidate(pending, pending_id="stale-pending", expected_epoch=old_epoch)
    with sqlite3.connect(memory.store.state_path) as db:
        document = json.loads(db.execute("SELECT payload FROM memory_state").fetchone()[0])
        document.setdefault("migrations", {}).pop("semantic_metadata_fingerprint_v1", None)
        document["entries"] = [replace(old, deleted=True).to_dict(), unrelated.to_dict(), broken.to_dict()]
        document["retired_ids"] = [old.memory_id]
        document["retired_origins"] = ["source:" + source for source in old.source_ids]
        document["profile"]["stable_preferences"] = [old.summary, unrelated.summary]
        document["profile"]["evidence"] = {
            f"stable_preferences:{old.summary}": {broken.memory_id: legacy_fingerprint(broken)},
            f"stable_preferences:{unrelated.summary}": {unrelated.memory_id: legacy_fingerprint(unrelated)},
        }
        document["chapters"] = [MemoryChapter(chapter_id="stale-legacy-chapter",
            character_id=memory.character_id, title="旧阶段回忆", summary=old.summary,
            source_memory_ids=(broken.memory_id,), created_at=21,
            source_fingerprints={broken.memory_id: legacy_fingerprint(broken)}).to_dict()]
        proposal = document["pending_candidates"]["stale-pending"]
        proposal["entry"]["metadata"]["source_memory_ids"] = [broken.memory_id]
        proposal["source_fingerprints"] = {broken.memory_id: legacy_fingerprint(broken)}
        db.execute("UPDATE memory_state SET payload=?", (json.dumps(document, ensure_ascii=False),))
    # Indexed readiness first fences the raw writer and then repairs the old
    # semantic metadata via _document(). Both updates revoke older contexts;
    # a later reopen must not keep incrementing either barrier.
    assert memory.store.current_context_epoch(now=20) == old_epoch + 2
    reopened = service(tmp_path)
    entries = {row.memory_id: row for row in reopened.store.load_memories()}
    repaired = entries[broken.memory_id]
    assert repaired.summary == summary and repaired.version == broken.version + 1
    assert repaired.metadata.get("fact_value") == expected_value
    assert "咖啡" not in json.dumps(repaired.metadata, ensure_ascii=False)
    assert repaired.supersedes == old.memory_id and repaired.source_ids == broken.source_ids
    assert entries[old.memory_id].deleted and entries[old.memory_id].summary == old.summary
    assert entries[unrelated.memory_id] == unrelated
    assert reopened.valid_profile(now=30).stable_preferences == (unrelated.summary,)
    assert not reopened.valid_chapters(now=30)
    with pytest.raises(ValueError, match="stale"):
        reopened.confirm_candidate("stale-pending", now=30)
    assert not reopened.pending_candidates
    assert reopened.store.context_epoch == old_epoch + 2
    assert service(tmp_path).store.context_epoch == old_epoch + 2


def test_legacy_upgrade_does_not_certify_a_mismatched_stored_fingerprint(tmp_path):
    memory = service(tmp_path)
    ChatMemory(memory, tmp_path / "settings.json").process("我喜欢咖啡", now=10)
    entry = active(memory)[0]
    with sqlite3.connect(memory.store.state_path) as db:
        document = json.loads(db.execute("SELECT payload FROM memory_state").fetchone()[0])
        document.setdefault("migrations", {}).pop("semantic_metadata_fingerprint_v1", None)
        document["profile"]["evidence"] = {f"stable_preferences:{entry.summary}":
                                          {entry.memory_id: "not-a-matching-old-fingerprint"}}
        db.execute("UPDATE memory_state SET payload=?", (json.dumps(document, ensure_ascii=False),))
    assert not service(tmp_path).valid_profile(now=20).stable_preferences
