"""Typed literal facts remain exact data through storage and revocation."""
from copy import deepcopy
from dataclasses import replace
import json
import sqlite3

import pytest

from guanghe_companion.emotional_memory import (
    CoreBondProfile, EmotionalMemoryEntry, EmotionalMemoryStore, MemoryChapter,
)
from guanghe_companion.memory_index import IndexedMemoryQuery


def fact(value, *, key="settings"):
    return EmotionalMemoryEntry(memory_id=key, character_id="test_character", owner_id="local_user",
        kind="用户事实", title="设备设置", summary="用户确认了设备设置", source="user_chat",
        source_ids=("statement:" + key,), occurred_at=10, created_at=10, updated_at=10,
        metadata={"speaker": "user", "fact_subject": "user:self", "fact_predicate": "settings",
            "fact_slot": "settings", "fact_value": value})


@pytest.mark.parametrize("value", [
    {"mode": "静音", "thresholds": {"low": 0, "high": 7.5},
     "targets": ["桌面", {"device": "测试设备", "enabled": False}]},
    [{"option": "A"}, [0, False, None]],
    0, False, 7.5, "字面字符串", ["旧扁平列表", 0, False, None], {}, [],
])
def test_literal_value_roundtrip_preserves_structure_and_scalar_types(value):
    original = fact(value).normalized()
    restored = EmotionalMemoryEntry.from_dict(original.to_dict())
    assert "fact_value" in original.metadata
    assert original.metadata["fact_value"] == value
    assert type(original.metadata["fact_value"]) is type(value)
    assert restored.metadata["fact_value"] == value
    assert type(restored.metadata["fact_value"]) is type(value)


def test_structured_fact_is_owned_copy_and_other_metadata_mappings_stay_unsupported():
    value = {"configuration": {"levels": [1, 2]}}
    entry = replace(fact(value), metadata={**fact(value).metadata,
        "arbitrary_debug_tree": {"claims": ["不能扩大 metadata 契约"]}}).normalized()
    value["configuration"]["levels"][0] = 99
    assert entry.metadata["fact_value"] == {"configuration": {"levels": [1, 2]}}
    assert "arbitrary_debug_tree" not in entry.metadata


def test_fingerprint_covers_nested_values_but_not_mapping_insertion_order():
    first = fact({"limits": {"low": 0, "high": 7}, "enabled": False}).normalized()
    reordered = fact({"enabled": False, "limits": {"high": 7, "low": 0}}).normalized()
    revised = fact({"limits": {"low": 0, "high": 8}, "enabled": False}).normalized()
    assert first.evidence_fingerprint() == reordered.evidence_fingerprint()
    assert first.evidence_fingerprint() != revised.evidence_fingerprint()


def test_existing_scalar_and_flat_values_remain_compatible(tmp_path):
    store = EmotionalMemoryStore(tmp_path, "test_character")
    values = ["旧标量" * 2000, ["旧列表值" * 400, 0, False, None], 0, False]
    originals = [fact(value, key=str(i)) for i, value in enumerate(values)]
    store.save_memories(originals)
    before = store.current_context_epoch(now=20)
    reopened = EmotionalMemoryStore(tmp_path, "test_character")
    actual = {m.memory_id: m for m in reopened.load_memories()}
    for original in originals:
        assert actual[original.memory_id].metadata["fact_value"] == original.metadata["fact_value"]
        assert actual[original.memory_id].evidence_fingerprint() == original.evidence_fingerprint()
    assert reopened.current_context_epoch(now=20) == before


def _nested_too_deep():
    value = "leaf"
    for _ in range(5):
        value = {"child": value}
    return value


@pytest.mark.parametrize("value", [
    _nested_too_deep(), {str(i): i for i in range(33)},
    {"x" * 81: 1}, {"value": "x" * 1025},
    {str(i): "界" * 1024 for i in range(20)},
    {"sets": [{"values": [0] * 32} for _ in range(4)]},
    {1: "不能隐式改为字符串键"}, {"bad": {1, 2}},
    {"bad": float("inf")}, {"bad": float("nan")},
])
def test_unsupported_or_over_budget_structure_rejects_the_whole_write(tmp_path, value):
    store = EmotionalMemoryStore(tmp_path, "test_character")
    original = fact("现有合法值")
    store.save_memories([original])
    before = store.current_index_state(now=20)
    with pytest.raises(ValueError, match="fact_value"):
        store.update_memory(replace(original, metadata={**original.metadata, "fact_value": value}))
    assert store.current_index_state(now=20) == before
    assert store.load_memories()[0].metadata["fact_value"] == "现有合法值"


def test_read_correct_forget_manifest_and_derived_invalidation(tmp_path):
    store = EmotionalMemoryStore(tmp_path, "test_character")
    value = {"mode": "晨雾计时模式", "limits": {"low": 0, "high": 7}, "enabled": False}
    original = fact(value)
    stored = store.upsert_memory(original)
    assert stored.metadata["fact_value"] == value
    store.save_profile(CoreBondProfile(store.character_id, stable_preferences=("设备设置",),
        evidence={"stable_preferences:设备设置": {stored.memory_id: stored.evidence_fingerprint()}}))
    store.save_chapters([MemoryChapter("chapter", store.character_id, "阶段概览", stored.summary,
        (stored.memory_id,), 12, source_fingerprints={stored.memory_id: stored.evidence_fingerprint()})])
    before = store.read_indexed_snapshot(IndexedMemoryQuery(subjects=("user:self",), predicates=("settings",)), now=20)
    assert before.entries[0].metadata["fact_value"] == value
    assert before.chapters and before.profile.stable_preferences
    manifest = store.index_manifest(now=20)
    changed_value = deepcopy(value)
    changed_value["mode"] = "晚霞计时模式"
    changed = store.update_memory(replace(stored, metadata={**stored.metadata, "fact_value": changed_value}))
    assert changed.version == stored.version + 1
    assert store.current_context_epoch(now=21) == before.context_epoch + 1
    assert store.finalize_indexed_recall(before.entries, expected_epoch=before.context_epoch, now=21) is None
    current = store.read_indexed_snapshot(now=21)
    assert current.entries[0].metadata["fact_value"] == changed_value
    assert not current.chapters and not current.profile.stable_preferences
    assert not store.read_indexed_snapshot(IndexedMemoryQuery(query="晨雾"), now=21).entries
    assert [m.memory_id for m in store.read_indexed_snapshot(IndexedMemoryQuery(query="晚霞"), now=21).entries] == [changed.memory_id]
    delta = store.index_manifest(now=21, after_revision=manifest.revision)
    assert delta.records[0].fingerprint == changed.evidence_fingerprint()
    store.forget_memory(changed.memory_id, now=22)
    assert not store.read_indexed_snapshot(IndexedMemoryQuery(query="晚霞"), now=23).entries
    assert changed.memory_id in store.index_manifest(now=23, after_revision=delta.revision).removed_ids


@pytest.mark.parametrize("value, serialized", [(0, "0"), (False, "false"), ({"b": 2, "a": 1}, '{"a":1,"b":2}')])
def test_index_value_is_stable_text_while_payload_retains_type(tmp_path, value, serialized):
    store = EmotionalMemoryStore(tmp_path, "test_character")
    store.save_memories([fact(value)])
    with sqlite3.connect(store.state_path) as db:
        literal = db.execute("SELECT fact_value FROM memory_index_entries WHERE memory_id='settings'").fetchone()[0]
    assert literal == serialized
    row = store.read_indexed_snapshot(now=20).entries[0]
    assert row.metadata["fact_value"] == value
    assert type(row.metadata["fact_value"]) is type(value)


def test_old_projection_algorithm_rebuilds_value_view_without_changing_authority(tmp_path):
    store = EmotionalMemoryStore(tmp_path, "test_character")
    store.save_memories([fact(0)])
    before = store.current_index_state(now=20)
    with sqlite3.connect(store.state_path) as db:
        db.execute("UPDATE memory_index_meta SET algorithm_version=? WHERE id=1",
            ("typed-literal-v2:cn-grams-v1:fts-rowid-v1:structured-pk-v1:raw-diff-v1",))
        db.execute("UPDATE memory_index_entries SET fact_value='' WHERE memory_id='settings'")
    snapshot = store.read_indexed_snapshot(now=20)
    assert snapshot.index_generation != before[0]
    assert snapshot.context_epoch == before[2]
    assert snapshot.entries[0].metadata["fact_value"] == 0
    with sqlite3.connect(store.state_path) as db:
        assert db.execute("SELECT fact_value FROM memory_index_entries WHERE memory_id='settings'").fetchone()[0] == "0"
        payload = json.loads(db.execute("SELECT payload FROM memory_state WHERE id=1").fetchone()[0])
    assert payload["entries"][0]["metadata"]["fact_value"] == 0
