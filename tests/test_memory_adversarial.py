"""Adversarial lifecycle regressions for public persistence entry points."""
from dataclasses import replace
import json
import sqlite3

import pytest

from guanghe_companion.emotional_memory import CoreBondProfile, EmotionalMemoryStore, MemoryChapter
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_document import MemoryStorageError


def _service(root):
    return EmotionalMemoryService(root=root, character_id="xingxi_pixel_pet")


def _remember(service, **kwargs):
    return service.remember(
        kind="玩家希望被记住", title="饮品偏好", summary="喜欢紫苏冰饮",
        source="explicit_user_request", now=10, **kwargs,
    )


@pytest.mark.parametrize("write_method", ["save_memories", "upsert_memory"])
def test_public_deleted_write_creates_durable_revocation(tmp_path, write_method):
    service = _service(tmp_path)
    original = _remember(service, source_ids=("drink-preference-event",))
    epoch = service.store.context_epoch
    writer = getattr(service.store, write_method)
    deleted = replace(original, deleted=True, updated_at=20)
    writer([deleted] if write_method == "save_memories" else deleted)
    # A stale caller must not be able to undo a public deletion with its cache.
    writer([original] if write_method == "save_memories" else original)
    restarted = _service(tmp_path)
    assert not restarted.recall("紫苏冰饮", now=30)
    assert restarted.store.context_epoch > epoch
    assert restarted.store.is_retired_origin(entry=original)


@pytest.mark.parametrize("origin", [
    {"source_ids": ("event-drink",)},
    {"metadata": {"legacy_key": "preference:drink"}},
    {"metadata": {"plugin_event_id": "event-drink"}},
    {"metadata": {"plugin_proposal_id": "proposal-drink"}},
])
def test_batch_save_cannot_replay_forgotten_origin_with_new_id(tmp_path, origin):
    service = _service(tmp_path)
    original = _remember(service, **origin)
    service.forget(original.memory_id, now=20)
    replay = replace(original, memory_id="later-replay-id", created_at=30, updated_at=30)
    service.store.save_memories([replay])
    assert not _service(tmp_path).recall("紫苏冰饮", now=31)


@pytest.mark.parametrize("field", ["confidence", "valid_from", "valid_until"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_lifecycle_values_are_rejected_before_persistence(tmp_path, field, value):
    service = _service(tmp_path)
    with pytest.raises(ValueError):
        _remember(service, **{field: value})
    assert not service.store.load_memories()


def test_legacy_nan_expiry_fails_closed_and_preserves_original(tmp_path):
    seed = _service(tmp_path / "seed")
    original = _remember(seed)
    store = EmotionalMemoryStore(tmp_path / "legacy", "xingxi_pixel_pet")
    store.character_root.mkdir(parents=True)
    row = {**original.to_dict(), "valid_until": float("nan")}
    raw = json.dumps({"schema_version": 1, "entries": [row]})
    store.memories_path.write_text(raw, encoding="utf-8")
    with pytest.raises(MemoryStorageError):
        store.load_memories()
    assert store.memories_path.read_text(encoding="utf-8") == raw


@pytest.mark.parametrize("operation", ["replace", "forget"])
def test_revocation_writes_check_epoch_inside_transaction(tmp_path, operation):
    service = _service(tmp_path)
    original = _remember(service)
    epoch = service.store.context_epoch
    other = service.store.upsert_memory(replace(original, memory_id="other-fact", summary="练习吉他"))
    _service(tmp_path).forget(other.memory_id, now=20)
    with pytest.raises(ValueError, match="stale"):
        if operation == "replace":
            replacement = replace(original, memory_id="corrected-fact", summary="喜欢白开水")
            service.store.replace_memory(original.memory_id, replacement, now=30, expected_epoch=epoch)
        else:
            service.store.forget_memory(original.memory_id, now=30, expected_epoch=epoch)
    assert service.recall("紫苏冰饮", now=31)


@pytest.mark.parametrize("retired", [False, True])
def test_correction_cannot_reuse_an_existing_or_retired_id(tmp_path, retired):
    service = _service(tmp_path)
    original = _remember(service)
    other = service.store.upsert_memory(replace(original, memory_id="other-fact", summary="练习吉他"))
    if retired:
        service.forget(other.memory_id, now=20)
    replacement = replace(original, memory_id=other.memory_id, summary="喜欢白开水")
    with pytest.raises(ValueError):
        service.store.replace_memory(original.memory_id, replacement, now=30)
    assert service.recall("紫苏冰饮", now=31)
    rows = service.store.load_memories()
    assert len({entry.memory_id for entry in rows}) == len(rows)


def test_profile_change_invalidates_old_context_epoch(tmp_path):
    service = _service(tmp_path)
    service.update_bond_profile(now=10, player_alias="阿紫")
    before = service.build_context("我的称呼", now=11)
    assert before.bond_profile.player_alias == "阿紫"
    service.update_bond_profile(now=20, player_alias="阿青")
    assert service.store.context_epoch > before.context_epoch
    assert service.build_context("我的称呼", now=21).bond_profile.player_alias == "阿青"


def test_profile_write_checks_expected_epoch_without_clobbering_newer_profile(tmp_path):
    service = _service(tmp_path)
    service.update_bond_profile(now=10, player_alias="阿紫")
    stale = service.store.load_profile()
    epoch = service.store.context_epoch
    _service(tmp_path).update_bond_profile(now=20, player_alias="阿青")
    with pytest.raises(ValueError, match="stale"):
        service.store.save_profile(replace(stale, updated_at=30), expected_epoch=epoch)
    assert service.valid_profile(now=31).player_alias == "阿青"


def test_profile_timestamp_only_touch_does_not_advance_epoch(tmp_path):
    service = _service(tmp_path)
    service.update_bond_profile(now=10, player_alias="阿紫")
    epoch = service.store.context_epoch
    service.store.save_profile(replace(service.store.load_profile(), updated_at=20))
    assert service.store.context_epoch == epoch


@pytest.mark.parametrize("damage", ["row", "table", "database"])
def test_missing_authoritative_state_never_reimports_forgotten_legacy_data(tmp_path, damage):
    seed = _service(tmp_path / "seed")
    original = _remember(seed)
    store = EmotionalMemoryStore(tmp_path / "legacy", "xingxi_pixel_pet")
    store.character_root.mkdir(parents=True)
    raw = json.dumps({"schema_version": 1, "entries": [original.to_dict()]})
    store.memories_path.write_text(raw, encoding="utf-8")
    store.load_memories()
    store.forget_memory(original.memory_id, now=20)
    if damage == "database":
        store.state_path.unlink()
    else:
        with sqlite3.connect(store.state_path) as connection:
            connection.execute("DELETE FROM memory_state" if damage == "row" else "DROP TABLE memory_state")
    with pytest.raises(MemoryStorageError):
        store.load_memories()
    assert store.memories_path.read_text(encoding="utf-8") == raw


@pytest.mark.parametrize("has_table", [False, True])
def test_preexisting_empty_database_is_not_treated_as_first_run(tmp_path, has_table):
    store = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    store.character_root.mkdir(parents=True)
    if has_table:
        with sqlite3.connect(store.state_path) as connection:
            connection.execute("CREATE TABLE memory_state (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
    else:
        store.state_path.touch()
    with pytest.raises(MemoryStorageError):
        store.load_memories()


def test_failed_first_legacy_parse_can_be_fixed_and_retried(tmp_path):
    store = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    store.character_root.mkdir(parents=True)
    store.memories_path.write_text("{broken json", encoding="utf-8")
    with pytest.raises(MemoryStorageError):
        store.load_memories()
    store.memories_path.write_text('{"schema_version":1,"entries":[]}', encoding="utf-8")
    assert store.load_memories() == ()


def test_failed_first_user_operation_does_not_break_store_initialization(tmp_path):
    service = _service(tmp_path)
    with pytest.raises(KeyError):
        service.correct("missing-id", title="饮品偏好", summary="喜欢紫苏冰饮", now=10)
    original = _remember(service)
    assert service.recall("紫苏冰饮", now=11)[0].memory_id == original.memory_id


@pytest.mark.parametrize("entries", [None, {}, "broken entries", [None], [{"memory_id": "missing-fields"}]])
def test_invalid_legacy_rows_fail_without_committing_and_can_be_repaired(tmp_path, entries):
    original = _remember(_service(tmp_path / "seed"))
    store = EmotionalMemoryStore(tmp_path / "legacy", "xingxi_pixel_pet")
    store.character_root.mkdir(parents=True)
    raw = json.dumps({"schema_version": 1, "entries": entries})
    store.memories_path.write_text(raw, encoding="utf-8")
    with pytest.raises(MemoryStorageError):
        store.load_memories()
    assert store.memories_path.read_text(encoding="utf-8") == raw
    assert not store.state_path.exists()
    repaired = json.dumps({"schema_version": 1, "entries": [original.to_dict()]})
    store.memories_path.write_text(repaired, encoding="utf-8")
    assert store.load_memories() == (original,)


def _shared_owner_legacy(root, original):
    shared = EmotionalMemoryStore(root, original.character_id)
    shared.character_root.mkdir(parents=True)
    alice = replace(original, owner_id="alice", memory_id="alice-fact", summary="Alice喜欢紫苏冰饮")
    bob = replace(original, owner_id="bob", memory_id="bob-fact", summary="Bob喜欢柠檬茶")
    deleted = replace(alice, memory_id="alice-deleted", summary="Alice已忘记的秘密", deleted=True)
    expired = replace(alice, memory_id="alice-expired", summary="Alice过时的地址", valid_until=1)
    rows = [original, alice, bob, deleted, expired]
    shared.memories_path.write_text(json.dumps({"schema_version": 1, "entries": [row.to_dict() for row in rows]}), encoding="utf-8")
    profile = CoreBondProfile(character_id=shared.character_id, owner_id="alice", player_alias="Alice",
                              stable_preferences=("喜欢紫苏冰饮",))
    shared.profile_path.write_text(json.dumps({"schema_version": 1, "profile": profile.to_dict()}), encoding="utf-8")
    chapters = [MemoryChapter(chapter_id=chapter_id, character_id=shared.character_id,
        title=chapter_id, summary=chapter_id, source_memory_ids=ids, created_at=20)
        for chapter_id, ids in (
            ("alice-safe", (alice.memory_id,)),
            ("cross-owner", (alice.memory_id, bob.memory_id)),
            ("cross-local-user", (alice.memory_id, original.memory_id)),
            ("deleted-source", (alice.memory_id, deleted.memory_id)),
            ("expired-source", (alice.memory_id, expired.memory_id)),
            ("missing-source", (alice.memory_id, "unknown-source")),
        )]
    shared.chapters_path.write_text(json.dumps({"schema_version": 1, "chapters": [row.to_dict() for row in chapters]}), encoding="utf-8")
    return shared, alice, bob


def test_nondefault_owner_migrates_only_its_legacy_shared_directory_data(tmp_path):
    original = _remember(_service(tmp_path / "seed"))
    shared, alice, bob = _shared_owner_legacy(tmp_path / "legacy", original)
    originals = {path: path.read_bytes() for path in (shared.memories_path, shared.profile_path, shared.chapters_path)}
    store = EmotionalMemoryStore(tmp_path / "legacy", original.character_id, "alice")
    rows = store.load_memories()
    assert alice in rows
    assert rows and all(row.owner_id == "alice" for row in rows)
    assert bob.memory_id not in {row.memory_id for row in rows}
    assert original.memory_id not in {row.memory_id for row in rows}
    assert store.load_profile().player_alias == "Alice"
    assert {chapter.chapter_id for chapter in store.load_chapters()} == {"alice-safe"}
    # Old chapters without revision evidence remain inspectable, not newly certified.
    assert store.load_chapters()[0].source_fingerprints == {}
    assert all(path.read_bytes() == content for path, content in originals.items())


def test_other_owner_cannot_import_the_shared_profile_or_chapter(tmp_path):
    original = _remember(_service(tmp_path / "seed"))
    _, _, bob = _shared_owner_legacy(tmp_path / "legacy", original)
    store = EmotionalMemoryStore(tmp_path / "legacy", original.character_id, "bob")
    assert store.load_memories() == (bob,)
    assert store.load_profile().player_alias == ""
    assert not store.load_chapters()


def test_owner_specific_legacy_memory_takes_precedence_over_shared_directory(tmp_path):
    original = _remember(_service(tmp_path / "seed"))
    _, alice, _ = _shared_owner_legacy(tmp_path / "legacy", original)
    store = EmotionalMemoryStore(tmp_path / "legacy", original.character_id, "alice")
    store.character_root.mkdir(parents=True)
    specific = replace(alice, memory_id="owner-specific", summary="Alice专用存档")
    store.memories_path.write_text(json.dumps({"schema_version": 1, "entries": [specific.to_dict()]}), encoding="utf-8")
    assert store.load_memories() == (specific,)
    assert not store.load_chapters()


def test_initialized_owner_never_reimports_shared_legacy_after_forget(tmp_path):
    original = _remember(_service(tmp_path / "seed"))
    shared, alice, _ = _shared_owner_legacy(tmp_path / "legacy", original)
    store = EmotionalMemoryStore(tmp_path / "legacy", original.character_id, "alice")
    assert alice in store.load_memories()
    store.forget_memory(alice.memory_id, now=30)
    raw = shared.memories_path.read_bytes()
    restarted = EmotionalMemoryStore(tmp_path / "legacy", original.character_id, "alice")
    assert next(row for row in restarted.load_memories() if row.memory_id == alice.memory_id).deleted
    store.state_path.unlink()
    with pytest.raises(MemoryStorageError):
        restarted.load_memories()
    assert shared.memories_path.read_bytes() == raw


def test_shared_chapter_cannot_hide_foreign_source_beyond_display_limit(tmp_path):
    original = _remember(_service(tmp_path / "seed"))
    shared, alice, bob = _shared_owner_legacy(tmp_path / "legacy", original)
    memories = json.loads(shared.memories_path.read_text(encoding="utf-8"))
    additional = [replace(alice, memory_id=f"alice-extra-{index}") for index in range(15)]
    memories["entries"].extend(row.to_dict() for row in additional)
    shared.memories_path.write_text(json.dumps(memories), encoding="utf-8")
    chapters = json.loads(shared.chapters_path.read_text(encoding="utf-8"))
    chapters["chapters"].append({
        "chapter_id": "foreign-seventeenth-source", "character_id": alice.character_id,
        "title": "mixed owner summary", "summary": "内容还来自 Bob",
        "source_memory_ids": [alice.memory_id, *(row.memory_id for row in additional), bob.memory_id],
        "created_at": 20,
    })
    shared.chapters_path.write_text(json.dumps(chapters), encoding="utf-8")
    store = EmotionalMemoryStore(tmp_path / "legacy", original.character_id, "alice")
    assert "foreign-seventeenth-source" not in {chapter.chapter_id for chapter in store.load_chapters()}
