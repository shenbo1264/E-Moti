"""Frozen JSON-snapshot control path; indexed default is tested separately.

The previous performance/race contract remains available as build_legacy_context
for comparisons. New default-path invariants are in test_ondemand_retrieval and
test_memory_hierarchy_retrieval, including zero full-document warm reads.
"""
from contextlib import contextmanager
from dataclasses import replace

import pytest

from guanghe_companion.emotional_memory import CoreBondProfile, EmotionalMemoryStore
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_document import MemoryStorageError


def service(root):
    return EmotionalMemoryService(root=root, character_id="xingxi_pixel_pet")


def remember(memory, text="用户喜欢咖啡", now=10, **extra):
    return memory.remember(kind="玩家希望被记住", title="偏好", summary=text,
                           source="explicit_user_request", now=now, importance=.9, **extra)


@pytest.mark.parametrize("query,expected_hits", [("咖啡", 1), ("astronomy", 0)])
def test_stable_context_needs_only_snapshot_and_finalize_transactions(
    tmp_path, monkeypatch, query, expected_hits
):
    memory = service(tmp_path)
    entry = remember(memory)
    transactions = []
    original = EmotionalMemoryStore._document

    @contextmanager
    def counted(store):
        transactions.append(store)
        with original(store) as document:
            yield document

    monkeypatch.setattr(EmotionalMemoryStore, "_document", counted)
    bundle = memory.build_legacy_context(query, now=20)

    assert len(bundle.memories) == expected_hits
    # An explicit performance requirement: repeated full-document transactions
    # dominated the measured build_context latency even at 300 entries.
    assert len(transactions) == 2
    current = next(row for row in memory.store.load_memories() if row.memory_id == entry.memory_id)
    assert current.access_count == expected_hits


def test_expiry_updates_sources_profile_chapter_and_epoch_in_one_context(tmp_path):
    memory = service(tmp_path)
    old = remember(memory, valid_until=30)
    remember(memory, "每周练习电吉他", now=11)
    remember(memory, "喜欢安静的早晨", now=12)
    assert memory.consolidate(now=20) is not None
    memory.update_bond_profile(now=21, new_preference=old.summary,
                               source_memory_ids=(old.memory_id,))
    before_epoch = memory.store.context_epoch

    bundle = memory.build_legacy_context("咖啡", now=30)

    assert "咖啡" not in bundle.to_prompt_text()
    assert not bundle.bond_profile.stable_preferences
    assert bundle.chapter is None
    assert bundle.context_epoch == before_epoch + 1
    assert memory.build_legacy_context("咖啡", now=31).context_epoch == bundle.context_epoch


def test_untrusted_profile_fingerprint_never_becomes_context(tmp_path):
    memory = service(tmp_path)
    entry = remember(memory)
    memory.store.save_profile(CoreBondProfile(
        memory.character_id, memory.owner_id,
        stable_preferences=("错误画像标记",),
        evidence={"stable_preferences:错误画像标记": {entry.memory_id: "0" * 64}},
    ))

    bundle = memory.build_legacy_context("咖啡", now=20)

    assert bundle.memories
    assert bundle.bond_profile.stable_preferences == ()
    assert "错误画像标记" not in bundle.to_prompt_text()


def test_recall_keeps_scope_and_active_filters(tmp_path):
    memory = service(tmp_path)
    live = remember(memory, "任务紫水晶", scope="work")
    remember(memory, "任务紫水晶旧项", scope="work", valid_until=15)
    remember(memory, "任务紫水晶未生效", scope="work", valid_from=30)

    assert memory.recall("紫水晶", now=20) == ()
    assert [row.memory_id for row in memory.recall("紫水晶", now=20, scope="work")] == [live.memory_id]
    assert "紫水晶" not in memory.build_legacy_context("紫水晶", now=20).to_prompt_text()


def test_semantic_callback_runs_outside_store_transaction(tmp_path, monkeypatch):
    memory = service(tmp_path)
    remember(memory)
    depth = 0
    observed_depths = []
    original = EmotionalMemoryStore._document

    @contextmanager
    def tracked(store):
        nonlocal depth
        with original(store) as document:
            depth += 1
            try:
                yield document
            finally:
                depth -= 1

    def semantic(query, entries):
        observed_depths.append(depth)
        return {entry.memory_id: .9 for entry in entries}

    memory.semantic_retriever = semantic
    monkeypatch.setattr(EmotionalMemoryStore, "_document", tracked)

    assert memory.build_legacy_context("drink", now=20).memories
    assert observed_depths == [0]


def test_correction_during_retrieval_retries_without_touching_stale_candidate(tmp_path):
    memory, writer = service(tmp_path), service(tmp_path)
    old = remember(memory)
    calls = 0

    def semantic(query, entries):
        nonlocal calls
        calls += 1
        if calls == 1:
            writer.store.update_memory(replace(old, summary="用户喜欢绿茶"))
        return {entry.memory_id: .9 for entry in entries}

    memory.semantic_retriever = semantic
    bundle = memory.build_legacy_context("饮品", now=20)

    assert calls == 2
    assert "绿茶" in bundle.to_prompt_text()
    assert "咖啡" not in bundle.to_prompt_text()
    current = next(row for row in writer.store.load_memories() if row.memory_id == old.memory_id)
    assert current.access_count == 1
    assert bundle.context_epoch == writer.store.context_epoch


def test_profile_change_during_retrieval_is_not_mixed_with_old_snapshot(tmp_path):
    memory, writer = service(tmp_path), service(tmp_path)
    entry = remember(memory)
    calls = 0

    def semantic(query, entries):
        nonlocal calls
        calls += 1
        if calls == 1:
            writer.update_bond_profile(now=19, new_preference=entry.summary,
                                       source_memory_ids=(entry.memory_id,))
        return {row.memory_id: .9 for row in entries}

    memory.semantic_retriever = semantic
    bundle = memory.build_legacy_context("饮品", now=20)

    assert calls == 2
    assert bundle.bond_profile.stable_preferences == (entry.summary,)
    assert bundle.memories[0].access_count == 1


def test_forget_during_retrieval_cannot_return_or_touch_old_source(tmp_path):
    memory, writer = service(tmp_path), service(tmp_path)
    old = remember(memory)
    calls = 0

    def semantic(query, entries):
        nonlocal calls
        calls += 1
        if calls == 1:
            writer.forget(old.memory_id, now=19)
        return {old.memory_id: 1.0}

    memory.semantic_retriever = semantic
    bundle = memory.build_legacy_context("咖啡", now=20)

    assert calls == 2
    assert "咖啡" not in bundle.to_prompt_text()
    retired = next(row for row in writer.store.load_memories() if row.memory_id == old.memory_id)
    assert retired.deleted and retired.access_count == 0


def test_concurrent_recall_counts_are_not_overwritten_by_snapshot(tmp_path):
    memory, other = service(tmp_path), service(tmp_path)
    entry = remember(memory)

    def semantic(query, entries):
        assert other.recall("咖啡", now=19)
        return {row.memory_id: .9 for row in entries}

    memory.semantic_retriever = semantic
    bundle = memory.build_legacy_context("饮品", now=20)

    assert bundle.memories[0].memory_id == entry.memory_id
    assert bundle.memories[0].access_count == 2


def test_three_revocation_conflicts_keep_existing_empty_bundle_contract(tmp_path):
    memory, writer = service(tmp_path), service(tmp_path)
    entry = remember(memory)
    calls = 0

    def semantic(query, entries):
        nonlocal calls
        calls += 1
        current = next(row for row in writer.store.load_memories() if row.memory_id == entry.memory_id)
        writer.store.update_memory(replace(current, summary=f"用户喜欢咖啡版本{calls}"))
        return {row.memory_id: .9 for row in entries}

    memory.semantic_retriever = semantic
    bundle = memory.build_legacy_context("饮品", now=20)

    assert calls == 3
    assert bundle.memories == ()
    assert bundle.chapter is None
    assert bundle.bond_profile == CoreBondProfile(memory.character_id, memory.owner_id)
    current = next(row for row in writer.store.load_memories() if row.memory_id == entry.memory_id)
    assert current.access_count == 0


def test_store_failure_after_snapshot_is_propagated(tmp_path):
    memory = service(tmp_path)
    remember(memory)

    def semantic(query, entries):
        memory.store.state_path.write_bytes(b"broken sqlite document")
        return {row.memory_id: .9 for row in entries}

    memory.semantic_retriever = semantic

    with pytest.raises(MemoryStorageError):
        memory.build_legacy_context("饮品", now=20)


@pytest.mark.parametrize("latest_changes", [
    {"scope": "work"}, {"confidence": 0}, {"valid_from": 30}, {"valid_until": 15},
])
def test_duplicate_id_cannot_revive_an_earlier_active_revision(tmp_path, latest_changes):
    memory = service(tmp_path)
    old = remember(memory)
    latest = replace(old, summary="最新事实", **latest_changes)
    # Old migrations or manually imported documents can contain duplicate IDs.
    # Existing store writes use the last valid, same-owner row for that ID.
    with memory.store._document() as document:
        document["entries"] = [old.to_dict(), latest.to_dict()]

    bundle = memory.build_legacy_context("咖啡", now=20)

    assert bundle.memories == ()
    assert all(row.access_count == 0 for row in memory.store.load_memories())


def test_finalize_keeps_unselected_raw_rows_and_uses_last_valid_owned_row(tmp_path):
    memory = service(tmp_path)
    old = remember(memory)
    latest = replace(old, summary="用户喜欢绿茶", access_count=7)
    latest_row = {**latest.to_dict(), "memory_id": f" {latest.memory_id}\n"}
    invalid = {"memory_id": old.memory_id, "summary": "无效行"}
    foreign = replace(old, owner_id="another_owner", summary="另一个用户的咖啡").to_dict()
    unrelated = {**replace(old, memory_id="unrelated", summary="天文学").to_dict(),
                 "future_extension": {"keep": True}}
    with memory.store._document() as document:
        document["entries"] = [old.to_dict(), latest_row, invalid, foreign, unrelated]
    seen_candidates = []

    def semantic(query, entries):
        seen_candidates.extend(entries)
        return {old.memory_id: .9}

    memory.semantic_retriever = semantic
    bundle = memory.build_legacy_context("drink", now=20)

    assert [row.summary for row in seen_candidates if row.memory_id == old.memory_id] == [latest.summary]
    assert len(bundle.memories) == 1
    assert bundle.memories[0].summary == latest.summary
    assert bundle.memories[0].access_count == 8
    with memory.store._document() as document:
        assert document["entries"][0] == old.to_dict()
        assert document["entries"][1]["access_count"] == 8
        assert document["entries"][2:] == [invalid, foreign, unrelated]


def test_finalize_checks_current_fingerprint_even_without_epoch_change(tmp_path):
    memory = service(tmp_path)
    old = remember(memory)
    calls = 0

    def semantic(query, entries):
        nonlocal calls
        calls += 1
        if calls == 1:
            # Simulate an old/importing writer that did not advance the barrier.
            with memory.store._document() as document:
                document["entries"][0]["summary"] = "用户喜欢绿茶"
        return {entry.memory_id: .9 for entry in entries}

    memory.semantic_retriever = semantic
    bundle = memory.build_legacy_context("drink", now=20)

    assert calls == 2
    assert bundle.memories[0].summary == "用户喜欢绿茶"
    assert bundle.memories[0].access_count == 1
