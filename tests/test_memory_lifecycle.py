"""Lifecycle regressions target model-visible state, not just deleted flags."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from guanghe_companion.emotional_memory import (
    CoreBondProfile, EmotionalMemoryEntry, EmotionalMemoryStore, MemoryChapter,
)
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.legacy_memory_migration import migrate_legacy_entries


def service(root, character="xingxi_pixel_pet", owner="local_user"):
    return EmotionalMemoryService(root=root, character_id=character, owner_id=owner)


@pytest.mark.parametrize("argument,field,limit", [
    ("player_alias", "player_alias", 20),
    ("new_preference", "stable_preferences", 80),
    ("new_boundary", "boundaries", 100),
    ("new_ritual", "shared_rituals", 100),
    ("active_story_thread", "active_story_threads", 120),
])
def test_profile_bindings_use_the_same_canonical_text_as_saved_fields(tmp_path, argument, field, limit):
    s = service(tmp_path)
    value = "咖啡" * 80
    s.update_bond_profile(now=10, **{argument: value})
    visible = s.valid_profile(now=11)
    expected = value[:limit]
    assert getattr(visible, field) == (expected if field == "player_alias" else (expected,))
    source = next(entry for entry in s.store.load_memories() if entry.source == "profile_edit")
    assert s.store.load_profile().evidence[f"{field}:{expected}"]
    s.forget(source.memory_id, now=12)
    assert not getattr(s.valid_profile(now=13), field)


def remember(s, text="我喜欢咖啡", now=10, **kwargs):
    return s.remember(kind="玩家希望被记住", title=text, summary=text,
                      source="explicit_user_request", now=now,
                      importance=.9, tags=("关于你",), **kwargs)


def with_chapter(s):
    first = remember(s)
    remember(s, "每周练习电吉他", 20)
    remember(s, "喜欢安静的早晨", 30)
    assert s.consolidate(now=40) is not None
    return first


def test_forget_invalidates_chapter_and_profile_after_restart(tmp_path):
    s = service(tmp_path)
    first = with_chapter(s)
    s.update_bond_profile(now=45, new_preference=first.summary,
                          source_memory_ids=(first.memory_id,))
    s.forget(first.memory_id, now=50)
    restarted = service(tmp_path)
    payload = restarted.build_context("咖啡", now=60).to_prompt_text()
    assert "咖啡" not in payload
    assert not restarted.valid_chapters(now=60)
    assert restarted.store.context_epoch > 0


def test_correction_invalidates_old_derivations_without_changing_other_facts(tmp_path):
    s = service(tmp_path)
    old = with_chapter(s)
    s.update_bond_profile(now=45, new_preference=old.summary,
                          source_memory_ids=(old.memory_id,))
    new = s.correct(old.memory_id, title="饮品偏好", summary="我喜欢热牛奶", now=50)
    payload = s.build_context("热牛奶", now=60).to_prompt_text()
    assert "咖啡" not in payload and "热牛奶" in payload
    assert new.supersedes == old.memory_id and new.version == old.version + 1
    assert new.occurred_at == old.occurred_at
    assert s.recall("电吉他", now=60)


def test_same_id_content_update_invalidates_chapter(tmp_path):
    s = service(tmp_path)
    old = with_chapter(s)
    epoch = s.store.context_epoch
    s.store.update_memory(replace(old, summary="我喜欢红茶"))
    assert s.latest_chapter(now=50) is None
    assert s.store.context_epoch > epoch


def test_touch_does_not_invalidate_chapter_or_bump_epoch(tmp_path):
    s = service(tmp_path)
    with_chapter(s)
    before = s.latest_chapter(now=41)
    epoch = s.store.context_epoch
    s.recall("咖啡", now=50)
    assert s.latest_chapter(now=51) == before
    assert s.store.context_epoch == epoch


def test_cross_owner_store_and_profile_isolation(tmp_path):
    alice, bob = service(tmp_path, owner="alice"), service(tmp_path, owner="bob")
    remember(alice)
    alice.update_bond_profile(now=20, player_alias="Alice")
    assert not bob.recall("咖啡", now=30)
    assert bob.build_context("你好", now=30).bond_profile.player_alias == ""
    with pytest.raises(ValueError):
        bob.store.upsert_memory(alice.store.load_memories()[0])


@pytest.mark.parametrize("character", ["../escape", "/tmp/escape", "a/b", "a\\b", ".."])
def test_store_rejects_path_escape(tmp_path, character):
    with pytest.raises(ValueError):
        EmotionalMemoryStore(tmp_path, character).load_memories()


def test_expiry_is_a_hard_gate_even_for_pinned_memory_and_derived_data(tmp_path):
    s = service(tmp_path)
    old = remember(s, pinned=True, valid_until=25)
    remember(s, "电吉他", 12)
    remember(s, "早晨", 15)
    s.consolidate(now=20)
    s.update_bond_profile(now=21, new_preference=old.summary,
                          source_memory_ids=(old.memory_id,))
    assert s.recall("咖啡", now=24)
    assert "咖啡" not in s.build_context("咖啡", now=25).to_prompt_text()


def test_non_companion_scope_is_not_implicitly_recalled_or_consolidated(tmp_path):
    s = service(tmp_path)
    remember(s, "Relay任务标记紫水晶", scope="work", now=10)
    assert not s.recall("紫水晶", now=11)
    assert s.recall("紫水晶", now=11, scope="work")
    assert "紫水晶" not in s.build_context("任务", now=11).to_prompt_text()


def test_unattributed_legacy_profile_is_retained_but_not_in_prompt(tmp_path):
    s = service(tmp_path)
    profile = CoreBondProfile(character_id=s.character_id, stable_preferences=("旧咖啡偏好",))
    s.store.save_profile(profile)
    assert s.store.load_profile().stable_preferences == ("旧咖啡偏好",)
    assert "旧咖啡偏好" not in s.build_context("咖啡", now=10).to_prompt_text()


def test_v1_migration_preserves_source_files_and_does_not_reimport(tmp_path):
    store = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    store.character_root.mkdir(parents=True)
    row = EmotionalMemoryEntry(memory_id="legacy-1", character_id=store.character_id,
        owner_id="local_user", kind="玩家希望被记住", title="咖啡", summary="咖啡",
        source="explicit_user_request", occurred_at=1, created_at=1, updated_at=1)
    original = json.dumps({"schema_version": 1, "entries": [row.to_dict()]})
    store.memories_path.write_text(original, encoding="utf-8")
    s = service(tmp_path)
    assert s.store.load_memories()[0].memory_id == "legacy-1"
    s.forget("legacy-1", now=20)
    assert store.memories_path.read_text(encoding="utf-8") == original
    assert not service(tmp_path).recall("咖啡", now=30)
    assert store.state_path.is_file()


def test_legacy_key_tombstone_prevents_changed_timestamp_reimport(tmp_path):
    s = service(tmp_path)
    row = {"key":"preference:drink", "category":"preference", "summary":"咖啡", "updated_at":1}
    first = migrate_legacy_entries(s, [row], now=10)
    s.forget(first.migrated_ids[0], now=11)
    migrate_legacy_entries(s, [{**row, "updated_at":100}], now=101)
    assert not s.recall("咖啡", now=102)


def test_replaying_settled_event_after_forget_is_suppressed(tmp_path):
    s = service(tmp_path)
    event = {"event_type":"inventory", "event_id":"event-milk", "payload":{
        "action":"gift", "item_id":"milk", "item_name":"热牛奶", "first_time":True}}
    first = s.record_event(event, now=10)
    s.forget(first.memory_id, now=20)
    assert s.record_event(event, now=30) is None
    assert not service(tmp_path).recall("热牛奶", now=40)


def test_epoch_fences_pending_proposals_across_other_service_instance(tmp_path):
    s = service(tmp_path)
    first = remember(s)
    pending = s.propose_explicit_user_memory("请记住：咖啡", now=20)
    service(tmp_path).forget(first.memory_id, now=21)
    with pytest.raises(ValueError, match="stale"):
        s.confirm_candidate(pending, now=22)
    assert not service(tmp_path).recall("咖啡", now=23)


def test_invalid_correction_does_not_retire_old_fact(tmp_path):
    s = service(tmp_path)
    old = remember(s)
    with pytest.raises(ValueError):
        s.correct(old.memory_id, title="", summary="", now=20)
    assert s.recall("咖啡", now=21)[0].memory_id == old.memory_id


def test_stale_saved_batch_cannot_resurrect_forgotten_fact(tmp_path):
    s = service(tmp_path)
    old = remember(s)
    cached = s.store.load_memories()
    s.forget(old.memory_id, now=20)
    s.store.save_memories(cached)
    assert not s.recall("咖啡", now=21)


def test_model_invention_cannot_become_completed_shared_experience(tmp_path):
    s = service(tmp_path)
    with pytest.raises(ValueError):
        s.remember(kind="共同经历", title="去了火星", summary="我们已经一起去了火星",
                   source="llm_generated", now=10, user_confirmed=False)
