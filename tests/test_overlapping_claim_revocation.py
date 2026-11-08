from dataclasses import replace
import json
import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_index import IndexedMemoryQuery
from guanghe_companion.memory_source_spans import source_span_metadata


def create(memory, text, claim, suffix):
    return memory.remember(kind="用户自述", title="隔离来源", summary=claim, source="user_chat",
        source_ids=("utterance:split:" + suffix,), now=10,
        metadata={"message_id": "split:1", "original_quote": text,
                  **source_span_metadata(text, claim)})


def test_forget_revokes_overlapping_card_but_keeps_disjoint_fact_after_reopen(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我的邻居叫周澄，我周末喜欢陶艺。"
    target = create(memory, text, "我的邻居叫周澄", "name")
    broad = create(memory, text, text, "whole")
    kept = create(memory, text, "我周末喜欢陶艺", "hobby")
    memory.update_bond_profile(new_preference=text, source_memory_ids=(broad.memory_id,), now=10)
    memory.forget(target.memory_id, now=11)
    memory.close()
    reopened = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    try:
        rows = reopened.store.read_indexed_snapshot(IndexedMemoryQuery(limit=10), now=12).entries
        assert {row.memory_id for row in rows} == {kept.memory_id}
        assert "周澄" not in json.dumps(reopened.store.load_profile().to_dict(), ensure_ascii=False)
        assert reopened.store.upsert_memory(replace(broad, memory_id="late-replayed-card")).deleted
    finally:
        reopened.close()


def test_correction_revokes_old_overlapping_summary_without_revoking_new_source(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我的邻居叫周澄，我周末喜欢陶艺。"
    target = create(memory, text, "我的邻居叫周澄", "name")
    broad = create(memory, text, text, "whole")
    fixed = memory.correct(target.memory_id, title="邻居", summary="我的邻居叫周静", now=11,
        source_ids=("new-statement:1",), metadata={})
    rows = {row.memory_id: row for row in memory.store.load_memories()}
    assert rows[broad.memory_id].deleted
    assert not rows[fixed.memory_id].deleted
    memory.close()


def test_physical_purge_removes_overlapping_text_without_deleting_disjoint_fact(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我的邻居叫周澄，我周末喜欢陶艺。"
    target = create(memory, text, "我的邻居叫周澄", "name")
    broad = create(memory, text, text, "whole")
    kept = create(memory, text, "我周末喜欢陶艺", "hobby")
    from guanghe_companion.memory_lifecycle import purge_memory
    removed = purge_memory(memory.store, target.memory_id, now=11)
    assert set(removed) == {target.memory_id, broad.memory_id}
    with memory.store._document() as document:
        assert "周澄" not in json.dumps(document, ensure_ascii=False)
    assert next(row for row in memory.store.load_memories() if row.memory_id == kept.memory_id).is_active(now=11)
    memory.close()


def test_atomic_claim_revokes_when_its_literal_identity_support_is_withdrawn(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我的邻居叫周澄，周末一起做陶艺。"
    identity = create(memory, text, "我的邻居叫周澄", "identity")
    activity = create(memory, text, "周末一起做陶艺", "activity")
    start = text.index("周澄")
    memory.store.upsert_memory(replace(activity,
        metadata={**activity.metadata, "source_support_spans": [[start, start + 2]]}))
    memory.forget(identity.memory_id, now=11)
    assert all(entry.deleted for entry in memory.store.load_memories())
    memory.close()


def test_forgetting_atomic_activity_does_not_revoke_its_identity_support(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我的邻居叫周澄，周末一起做陶艺。"
    identity = create(memory, text, "我的邻居叫周澄", "identity")
    activity = create(memory, text, "周末一起做陶艺", "activity")
    start = text.index("周澄")
    memory.store.upsert_memory(replace(activity,
        metadata={**activity.metadata, "source_support_spans": [[start, start + 2]]}))
    memory.forget(activity.memory_id, now=11)
    assert next(entry for entry in memory.store.load_memories() if entry.memory_id == identity.memory_id).is_active(now=11)
    memory.close()


@pytest.mark.parametrize("support", [[[0, 999]], [[False, 2]], [[2, 1]]])
def test_invalid_literal_support_does_not_silently_disappear(tmp_path, support):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = create(memory, "我喜欢陶艺。", "我喜欢陶艺", "hobby")
    with pytest.raises(ValueError, match="source support spans"):
        memory.store.upsert_memory(replace(entry,
            metadata={**entry.metadata, "source_support_spans": support}))
    assert memory.store.load_memories()[0].metadata == entry.metadata
    memory.close()
