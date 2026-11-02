from dataclasses import replace

import pytest

from guanghe_companion.emotional_memory import EmotionalMemoryEntry, EmotionalMemoryStore
from guanghe_companion.emotional_memory_service import EmotionalMemoryService


@pytest.mark.parametrize("basis,zone,occurred,recorded", [
    ("logical", "", 100, 200),
    ("unix", "Asia/Shanghai", 1791950000, 1792036400),
])
def test_service_correction_preserves_occurrence_and_records_new_submission(tmp_path, basis, zone, occurred, recorded):
    service = EmotionalMemoryService(root=tmp_path, character_id="pet", time_basis=basis, timezone_name=zone)
    original = service.remember(kind="用户事实", title="偏好", summary="喜欢青茶", source="user_chat",
                                now=occurred, occurred_at=occurred)
    corrected = service.correct(original.memory_id, title="偏好", summary="喜欢红茶", now=recorded)
    reopened = EmotionalMemoryService(root=tmp_path, character_id="pet")
    persisted = next(row for row in reopened.store.load_memories() if row.memory_id == corrected.memory_id)
    for row in (corrected, persisted):
        assert row.occurred_at == row.metadata["occurred_time"] == occurred
        assert row.metadata["recorded_time"] == row.created_at == row.updated_at == recorded
        assert row.metadata["time_basis"] == basis
        assert row.metadata["timezone"] == zone


@pytest.mark.parametrize("preserve", [True, False])
def test_store_replacement_does_not_add_missing_legacy_time_metadata(tmp_path, preserve):
    store = EmotionalMemoryStore(tmp_path, "pet")
    original = EmotionalMemoryEntry(memory_id="old", character_id="pet", owner_id=store.owner_id,
        kind="用户事实", title="偏好", summary="喜欢青茶", source="user_chat",
        occurred_at=100, created_at=100, updated_at=100, metadata={"legacy": True})
    store.upsert_memory(original)
    corrected = store.replace_memory("old", replace(original, memory_id="new", occurred_at=200),
                                      now=200, preserve_occurred_at=preserve)
    assert corrected.occurred_at == (100 if preserve else 200)
    assert corrected.metadata == {"legacy": True}


def test_explicit_replacement_occurrence_keeps_matching_metadata(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="pet")
    original = service.remember(kind="用户事实", title="偏好", summary="喜欢青茶", source="user_chat", now=100)
    replacement = service.remember(kind="用户事实", title="偏好", summary="喜欢红茶", source="user_chat",
        now=300, occurred_at=200, supersedes=original.memory_id, preserve_occurred_at=False)
    assert replacement.occurred_at == replacement.metadata["occurred_time"] == 200
    assert replacement.metadata["recorded_time"] == 300
