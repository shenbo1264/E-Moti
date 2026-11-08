"""The derived SQLite index must save reads without weakening authority."""
from dataclasses import replace
import json
import sqlite3

import pytest

from guanghe_companion.emotional_memory import (
    CoreBondProfile, EmotionalMemoryEntry, EmotionalMemoryStore, MemoryChapter,
)
from guanghe_companion.memory_document import MemoryStorageError
from guanghe_companion.memory_index import IndexedMemoryQuery


def entry(key, summary="用户的牙医叫林清", **kw):
    values = dict(memory_id=key, character_id="xingxi_pixel_pet", owner_id="local_user",
                  kind="用户自述", title="人物姓名", summary=summary, source="user_chat",
                  occurred_at=10, created_at=10, updated_at=10,
                  source_ids=("message:" + key,), metadata={"fact_subject": "relation:牙医",
                    "fact_predicate": "name", "fact_slot": "relation:牙医:name", "fact_value": "林清"})
    values.update(kw)
    return EmotionalMemoryEntry(**values)


def store(tmp_path):
    return EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")


def query(**kw):
    return IndexedMemoryQuery(**kw)


def test_subject_field_time_scope_are_applied_before_candidate_limit(tmp_path):
    memory = store(tmp_path)
    rows = [entry("dentist"), entry("teacher", "用户的吉他老师叫周明", metadata={
        "fact_subject": "relation:吉他老师", "fact_predicate": "name"}),
        entry("address", "用户的牙医住在南街", metadata={"fact_subject": "relation:牙医",
            "fact_predicate": "residence"}), entry("work", scope="work"),
        entry("expired", valid_until=20), entry("future", valid_from=40)]
    memory.save_memories(rows)
    snapshot = memory.read_indexed_snapshot(query(subjects=("relation:牙医",), predicates=("name",)), now=30)
    assert [row.memory_id for row in snapshot.entries] == ["dentist"]
    assert snapshot.total_candidates == 1
    assert snapshot.rows_loaded == 1
    assert snapshot.candidate_ids == ("dentist",)


def test_normal_fast_read_and_finalize_never_decode_document(tmp_path, monkeypatch):
    memory = store(tmp_path)
    memory.save_memories([entry(str(i), summary="共同研究天文学 " + str(i), metadata={}) for i in range(300)])

    def reject_document(*args, **kwargs):
        raise AssertionError("Stable indexed reads must not read the whole JSON document")

    monkeypatch.setattr(EmotionalMemoryStore, "_document", reject_document)
    snapshot = memory.read_indexed_snapshot(query(memory_ids=("42",)), now=30)
    assert snapshot.rows_loaded == 1
    touched = memory.finalize_indexed_recall(snapshot.entries, expected_epoch=snapshot.context_epoch, now=31)
    assert touched[0].access_count == 1
    current = memory.read_indexed_snapshot(query(memory_ids=("42",)), now=32)
    assert current.entries[0].access_count == 1


def test_metadata_only_profile_sources_are_bounded_and_authenticated(tmp_path):
    memory = store(tmp_path)
    a, b = entry("a"), entry("b", scope="work")
    memory.save_memories([a, b])
    memory.save_profile(CoreBondProfile(memory.character_id, stable_preferences=("可信", "越界"), evidence={
        "stable_preferences:可信": {a.memory_id: a.evidence_fingerprint()},
        "stable_preferences:越界": {b.memory_id: b.evidence_fingerprint()}}))
    snapshot = memory.read_indexed_snapshot(query(memory_ids=()), now=30, include_chapters=False)
    assert snapshot.entries == ()
    assert snapshot.total_candidates == 0
    assert [row.memory_id for row in snapshot.source_entries] == ["a"]
    assert snapshot.source_eligibility["a"].eligible
    assert not snapshot.source_eligibility["b"].eligible
    assert snapshot.source_eligibility["b"].reason == "scope"
    assert snapshot.rows_loaded == 1


def test_chapter_sources_and_profile_expire_atomically_and_only_once(tmp_path):
    memory = store(tmp_path)
    fact = entry("a", valid_until=30)
    memory.save_memories([fact])
    memory.save_profile(CoreBondProfile(memory.character_id, stable_preferences=("牙医",), evidence={
        "stable_preferences:牙医": {"a": fact.evidence_fingerprint()}}))
    memory.save_chapters([MemoryChapter("chapter", memory.character_id, "阶段回忆", "见到了牙医",
        ("a",), 20, source_fingerprints={"a": fact.evidence_fingerprint()})])
    before = memory.read_indexed_snapshot(now=29)
    assert before.chapters and before.source_entries
    expired = memory.read_indexed_snapshot(now=30)
    assert not expired.entries and not expired.chapters and not expired.profile.stable_preferences
    assert expired.context_epoch == before.context_epoch + 1
    again = memory.read_indexed_snapshot(now=31)
    assert again.context_epoch == expired.context_epoch
    assert memory.finalize_indexed_recall(before.entries, expected_epoch=before.context_epoch, now=31) is None


def test_correction_forget_manifest_and_unrelated_fact_preservation(tmp_path):
    memory = store(tmp_path)
    original, unrelated = entry("a"), entry("unrelated", "一起观察火星", metadata={})
    memory.save_memories([original, unrelated])
    first = memory.index_manifest(now=20)
    changed = memory.replace_memory("a", replace(original, memory_id="b", summary="用户的牙医叫陈静"), now=21)
    delta = memory.index_manifest(now=22, after_revision=first.revision)
    assert "a" in delta.removed_ids
    assert any(row.memory_id == "b" and row.fingerprint == changed.evidence_fingerprint() for row in delta.records)
    memory.forget_memory("a", now=23)
    snapshot = memory.read_indexed_snapshot(now=24)
    assert [row.memory_id for row in snapshot.entries] == ["unrelated"]
    forgotten = memory.index_manifest(now=24, after_revision=delta.revision)
    assert "b" in forgotten.removed_ids
    assert "unrelated" not in forgotten.removed_ids


def test_history_never_bypasses_explicit_revocation(tmp_path):
    memory = store(tmp_path)
    memory.save_memories([entry("expired", valid_until=20), entry("forgotten")])
    memory.forget_memory("forgotten", now=21)
    snapshot = memory.read_indexed_snapshot(query(history=True), now=30)
    assert [row.memory_id for row in snapshot.entries] == ["expired"]
    assert not snapshot.source_entries
    assert memory.finalize_indexed_recall(snapshot.entries, expected_epoch=snapshot.context_epoch, now=30) is None
    assert memory.finalize_indexed_recall(snapshot.entries, expected_epoch=snapshot.context_epoch,
                                         now=30, allow_history=True)


def test_duplicate_ids_follow_last_valid_owned_row_before_filtering(tmp_path):
    memory = store(tmp_path)
    a = entry("dup")
    memory.save_memories([a])
    with memory._document() as document:
        document["entries"].extend([replace(a, scope="work").to_dict(),
            replace(a, character_id="other").to_dict(), {"memory_id": "dup"}])
    assert not memory.read_indexed_snapshot(now=20).entries
    result = memory.read_indexed_snapshot(query(scopes=("work",)), now=20)
    assert [row.memory_id for row in result.entries] == ["dup"]


def test_raw_sql_authority_edit_marks_projection_dirty_before_read(tmp_path):
    memory = store(tmp_path)
    memory.save_memories([entry("a")])
    with sqlite3.connect(memory.state_path) as connection:
        doc = json.loads(connection.execute("SELECT payload FROM memory_state").fetchone()[0])
        doc["retired_ids"] = ["a"]
        doc["context_epoch"] += 1
        connection.execute("UPDATE memory_state SET payload=?", (json.dumps(doc),))
    assert memory.read_indexed_snapshot(now=20).entries == ()


@pytest.mark.parametrize("damage", ["row", "table", "database", "corrupt"])
def test_missing_or_corrupt_authority_never_serves_projection_or_old_json(tmp_path, damage):
    memory = store(tmp_path)
    memory.save_memories([entry("a")])
    memory.memories_path.write_text(json.dumps({"schema_version": 1, "entries": [entry("a").to_dict()]}))
    memory.forget_memory("a", now=20)
    if damage == "database":
        memory.state_path.unlink()
    elif damage == "corrupt":
        memory.state_path.write_bytes(b"broken sqlite")
    else:
        with sqlite3.connect(memory.state_path) as connection:
            connection.execute("DELETE FROM memory_state" if damage == "row" else "DROP TABLE memory_state")
    with pytest.raises(MemoryStorageError):
        memory.read_indexed_snapshot(now=21)


def test_missing_projection_rebuilds_only_from_current_authority(tmp_path):
    memory = store(tmp_path)
    memory.save_memories([entry("a"), entry("b")])
    memory.forget_memory("a", now=20)
    before = memory.index_manifest(now=21)
    with sqlite3.connect(memory.state_path) as connection:
        connection.execute("DROP TABLE memory_index_entries")
    snapshot = memory.read_indexed_snapshot(now=22)
    assert [row.memory_id for row in snapshot.entries] == ["b"]
    assert memory.index_manifest(now=22).generation != before.generation


def test_failed_write_rolls_back_authority_and_projection(tmp_path):
    memory = store(tmp_path)
    memory.save_memories([entry("a")])
    before = memory.index_manifest(now=20)
    with pytest.raises(RuntimeError):
        with memory._document() as document:
            document["entries"] = []
            raise RuntimeError("cancel transaction")
    after = memory.index_manifest(now=21)
    assert after.revision == before.revision
    assert [row.memory_id for row in memory.read_indexed_snapshot(now=21).entries] == ["a"]


def test_finalize_checks_content_even_without_epoch_change_and_preserves_raw_rows(tmp_path):
    memory = store(tmp_path)
    memory.save_memories([entry("a")])
    snapshot = memory.read_indexed_snapshot(now=20)
    with memory._document() as document:
        document["entries"][0]["summary"] = "用户的牙医叫另一个人"
        document["entries"].append({"unknown_future_format": True})
    assert memory.finalize_indexed_recall(snapshot.entries, expected_epoch=snapshot.context_epoch, now=21) is None
    current = memory.read_indexed_snapshot(now=22)
    assert memory.finalize_indexed_recall(current.entries, expected_epoch=current.context_epoch, now=23)
    with memory._document() as document:
        assert document["entries"][1] == {"unknown_future_format": True}


def test_chinese_fts_bigrams_and_ascii_terms_without_query_syntax_injection(tmp_path):
    memory = store(tmp_path)
    memory.save_memories([entry("a", "一起在杭州看流星雨", metadata={}),
        entry("b", "一起研究 SQLite 部署故障", metadata={}), entry("c", "去看牙医", metadata={})])
    assert [row.memory_id for row in memory.read_indexed_snapshot(query(query="流星雨"), now=20).entries] == ["a"]
    assert [row.memory_id for row in memory.read_indexed_snapshot(query(query="SQLite"), now=20).entries] == ["b"]
    # Operators and punctuation are plain user text, never raw FTS syntax.
    memory.read_indexed_snapshot(query(query='" OR * : NEAR('), now=20)


def test_aliases_have_owner_role_isolation_and_are_not_inferred(tmp_path):
    memory = store(tmp_path)
    memory.save_memories([entry("a", metadata={"fact_subject": "relation:牙医", "fact_predicate": "name",
        "entity_id": "person:dentist", "entity_aliases": ["林医生"]})])
    assert [row.memory_id for row in memory.read_indexed_snapshot(query(subjects=("林医生",)), now=20).entries] == ["a"]
    other = EmotionalMemoryStore(tmp_path, memory.character_id, "other-user")
    assert not other.read_indexed_snapshot(query(subjects=("林医生",)), now=20).entries


def test_manifest_pagination_has_complete_denominator_and_expiry_tombstone(tmp_path):
    memory = store(tmp_path)
    memory.save_memories([entry(str(i), valid_until=30 if i == 0 else 0) for i in range(5)])
    first = memory.index_manifest(now=20, limit=2)
    assert first.has_more and len(first.records) == 2
    second = memory.index_manifest(now=20, limit=2, after_id=first.next_after_id)
    third = memory.index_manifest(now=20, limit=2, after_id=second.next_after_id)
    assert {row.memory_id for page in (first, second, third) for row in page.records} == {str(i) for i in range(5)}
    expired = memory.index_manifest(now=30, after_revision=first.revision)
    assert "0" in expired.removed_ids


def test_finalization_supports_explicit_multi_scope_without_companion_leak(tmp_path):
    memory = store(tmp_path)
    memory.save_memories([entry("a"), entry("b", scope="work")])
    snapshot = memory.read_indexed_snapshot(query(scopes=("companion", "work")), now=20)
    assert len(snapshot.entries) == 2
    assert memory.finalize_indexed_recall(snapshot.entries, expected_epoch=snapshot.context_epoch, now=21) is None
    assert len(memory.finalize_indexed_recall(snapshot.entries, expected_epoch=snapshot.context_epoch,
        now=21, scopes=("companion", "work"))) == 2


def test_alias_resolves_other_fields_and_revokes_with_binding_source(tmp_path):
    memory = store(tmp_path)
    name = entry("name", "用户的陶艺老师叫伍言", metadata={"fact_subject": "relation:陶艺老师",
        "fact_predicate": "name", "fact_value": "伍言", "subject_aliases": ["伍老师"]})
    occupation = entry("job", "用户的陶艺老师职业是产品设计师", metadata={
        "fact_subject": "relation:陶艺老师", "fact_predicate": "occupation", "fact_value": "产品设计师"})
    memory.save_memories([name, occupation])
    assert memory.resolve_subjects(("伍言", "伍老师"), now=20) == {
        "伍言": ("relation:陶艺老师",), "伍老师": ("relation:陶艺老师",)}
    assert [row.memory_id for row in memory.read_indexed_snapshot(query(subjects=("伍老师",),
        predicates=("occupation",)), now=20).entries] == ["job"]
    memory.forget_memory("name", now=21)
    assert memory.resolve_subjects(("伍言", "伍老师"), now=22) == {"伍言": (), "伍老师": ()}
    assert not memory.read_indexed_snapshot(query(subjects=("伍老师",), predicates=("occupation",)), now=22).entries


def test_alias_ambiguity_is_returned_without_selecting_a_person(tmp_path):
    memory = store(tmp_path)
    memory.save_memories([entry("a", metadata={"fact_subject": "relation:牙医", "fact_predicate": "name",
        "subject_aliases": ["小林"]}), entry("b", metadata={"fact_subject": "relation:老师", "fact_predicate": "name",
        "subject_aliases": ["小林"]}), entry("work", scope="work", metadata={"fact_subject": "relation:同事",
        "fact_predicate": "name", "subject_aliases": ["小林"]})])
    assert set(memory.resolve_subjects(("小林",), now=20)["小林"]) == {"relation:牙医", "relation:老师"}


def test_manifest_and_projection_fetch_can_skip_profile_source_bodies(tmp_path, monkeypatch):
    memory = store(tmp_path)
    a, b = entry("a"), entry("b")
    memory.save_memories([a, b])
    memory.save_profile(CoreBondProfile(memory.character_id, stable_preferences=("记住",),
        evidence={"stable_preferences:记住": {"a": a.evidence_fingerprint()}}))
    snapshot = memory.read_indexed_snapshot(query(memory_ids=("b",)), now=20,
        include_chapters=False, include_profile_sources=False)
    assert snapshot.rows_loaded == 1 and not snapshot.source_entries


def test_touch_only_recall_does_not_invalidate_semantic_manifest(tmp_path):
    memory = store(tmp_path)
    memory.save_memories([entry("a")])
    before = memory.index_manifest(now=20)
    snapshot = memory.read_indexed_snapshot(now=20)
    memory.finalize_indexed_recall(snapshot.entries, expected_epoch=snapshot.context_epoch, now=21)
    after = memory.index_manifest(now=22, after_revision=before.revision)
    assert after.revision == before.revision
    assert not after.records and not after.removed_ids


def test_fts_rowids_remain_directly_addressable_after_revision_and_retirement(tmp_path):
    memory = store(tmp_path)
    a, b = entry("a", "天文观测", metadata={}), entry("b", "合作游戏", metadata={})
    memory.save_memories([a, b])
    memory.update_memory(replace(a, summary="研究星系"))
    with sqlite3.connect(memory.state_path) as connection:
        assert connection.execute("SELECT e.rowid,f.rowid FROM memory_index_entries e JOIN memory_index_fts f ON e.memory_id=f.memory_id WHERE e.memory_id='a'").fetchone() == (1, 1)
    memory.forget_memory("a", now=20)
    with sqlite3.connect(memory.state_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM memory_index_fts WHERE memory_id='a'").fetchone()[0] == 0
    assert [r.memory_id for r in memory.read_indexed_snapshot(query(query="合作游戏"), now=21).entries] == ["b"]


def test_subject_resolution_includes_the_exact_name_binding_source(tmp_path):
    memory = store(tmp_path)
    name = entry("name", "用户的陶艺老师叫伍言", metadata={"fact_subject": "relation:陶艺老师",
        "fact_predicate": "name", "fact_value": "伍言"})
    occupation = entry("job", "用户的陶艺老师从事设计", metadata={
        "fact_subject": "relation:陶艺老师", "fact_predicate": "occupation"})
    memory.save_memories([name, occupation])
    resolution = memory.resolve_subject_bindings(("伍言",), now=20)
    assert resolution.mapping == {"伍言": ("relation:陶艺老师",)}
    assert resolution.source_ids == ("name",)
    assert resolution.source_fingerprints == {"name": name.evidence_fingerprint()}
    assert resolution.sources_by_input == {"伍言": ("name",)}
    generation, revision, epoch = memory.current_index_state(now=20)
    assert (resolution.index_generation, resolution.index_revision, resolution.context_epoch) == (generation, revision, epoch)
    assert not memory.resolve_subject_bindings(("relation:陶艺老师",), now=20).source_ids


def test_dependency_sources_are_verified_without_changing_their_access_count(tmp_path):
    memory = store(tmp_path)
    name, occupation = entry("name"), entry("job", "牙医的工作场所", metadata={})
    memory.save_memories([name, occupation])
    snap = memory.read_indexed_snapshot(now=20)
    selected = next(row for row in snap.entries if row.memory_id == "job")
    dependency = next(row for row in snap.entries if row.memory_id == "name")
    result = memory.finalize_indexed_recall((selected,), expected_epoch=snap.context_epoch, now=21,
        dependency_entries=(dependency,))
    assert result[0].access_count == 1
    current = {row.memory_id: row for row in memory.read_indexed_snapshot(now=22).entries}
    assert current["name"].access_count == 0 and current["job"].access_count == 1


def test_legacy_dependency_edit_repairs_epoch_and_rejects_old_fingerprints(tmp_path):
    memory = store(tmp_path)
    name, occupation = entry("name"), entry("job", "牙医的工作场所", metadata={})
    memory.save_memories([name, occupation])
    snap = memory.read_indexed_snapshot(now=20)
    selected = next(row for row in snap.entries if row.memory_id == "job")
    dependency = next(row for row in snap.entries if row.memory_id == "name")
    with memory._document() as document:
        row = next(raw for raw in document["entries"] if raw["memory_id"] == "name")
        row["summary"] = "用户的牙医叫另一位医生"
        row["metadata"]["fact_value"] = "另一位医生"
    assert memory.current_context_epoch() == snap.context_epoch + 1
    assert memory.finalize_indexed_recall((selected,), expected_epoch=snap.context_epoch, now=21,
        dependency_entries=(dependency,)) is None
    # Supplying the new epoch cannot authenticate the old alias/name proof.
    assert memory.finalize_indexed_recall((selected,), expected_epoch=snap.context_epoch + 1, now=21,
        dependency_entries=(dependency,)) is None
    assert all(row.access_count == 0 for row in memory.read_indexed_snapshot(now=22).entries)


def test_history_does_not_make_expired_identity_bindings_current(tmp_path):
    memory = store(tmp_path)
    memory.save_memories([entry("old", valid_until=20), entry("name", valid_until=20)])
    snap = memory.read_indexed_snapshot(query(history=True), now=30)
    assert memory.finalize_indexed_recall((snap.entries[0],), expected_epoch=snap.context_epoch,
        now=30, allow_history=True, dependency_entries=(snap.entries[1],)) is None


def test_current_index_state_reads_header_only_and_tracks_raw_legacy_changes(tmp_path, monkeypatch):
    memory = store(tmp_path)
    memory.save_memories([entry("a")])
    before = memory.current_index_state()
    with memory._document() as document:
        document["entries"][0]["summary"] = "另一个明确事实"
    after = memory.current_index_state()
    assert before[0] == after[0] and before[1] < after[1] and before[2] + 1 == after[2]
    monkeypatch.setattr(EmotionalMemoryStore, "_document", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("header-only read decoded document")))
    assert memory.current_index_state(now=30) == after


def test_four_id_lookups_do_not_scan_thousands_of_eligible_rows(tmp_path, monkeypatch):
    # VM-step counts avoid wall-clock assertions on a shared CI host. This
    # catches SQLite choosing the broad eligibility index over the four IDs.
    small, large = store(tmp_path / "small"), store(tmp_path / "large")
    small.save_memories([entry(str(i)) for i in range(100)])
    large.save_memories([entry(str(i)) for i in range(3000)])
    original = sqlite3.connect
    steps = []

    def traced(*args, **kwargs):
        connection = original(*args, **kwargs)
        connection.set_progress_handler(lambda: steps.append(1) and 0, 1000)
        return connection

    monkeypatch.setattr(sqlite3, "connect", traced)
    small.read_indexed_snapshot(query(memory_ids=("1", "2", "3", "4")), now=20,
        include_chapters=False, include_profile_sources=False)
    small_steps = len(steps)
    steps.clear()
    snapshot = large.read_indexed_snapshot(query(memory_ids=("1", "2", "3", "4")), now=20,
        include_chapters=False, include_profile_sources=False)
    assert snapshot.rows_loaded == 4
    assert len(steps) <= small_steps + 15


def test_fts_postings_drive_the_join_instead_of_repeating_match_per_record(tmp_path, monkeypatch):
    memory = store(tmp_path)
    memory.save_memories([entry(str(i), "一起研究天文学", metadata={}) for i in range(30)])
    original = sqlite3.connect
    queries = []

    def traced(*args, **kwargs):
        connection = original(*args, **kwargs)
        connection.set_trace_callback(queries.append)
        return connection

    monkeypatch.setattr(sqlite3, "connect", traced)
    memory.read_indexed_snapshot(query(query="天文"), now=20, include_chapters=False)
    sql = next(sql for sql in queries if sql.startswith("SELECT e.*") and "MATCH" in sql)
    with original(memory.state_path) as connection:
        plan = [row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + sql)]
    fts_position = next(i for i, step in enumerate(plan) if "memory_index_fts" in step)
    entry_position = next(i for i, step in enumerate(plan) if "SEARCH e " in step or "SCAN e" in step)
    assert fts_position < entry_position, plan


def test_projection_does_not_renormalize_unchanged_rows_on_a_single_fact_write(tmp_path, monkeypatch):
    memory = store(tmp_path)
    corpus = [entry(str(i), summary="共同经历 " + str(i), metadata={}) for i in range(100)]
    memory.save_memories(corpus)
    original = EmotionalMemoryEntry.from_dict.__func__
    normalized = []

    def counted(cls, raw):
        normalized.append(raw.get("memory_id") if isinstance(raw, dict) else None)
        return original(cls, raw)

    monkeypatch.setattr(EmotionalMemoryEntry, "from_dict", classmethod(counted))
    memory.update_memory(replace(corpus[42], summary="共同经历的准确更正"))
    # The retained canonical writer currently normalizes all N rows. The
    # projection must add only the changed K rows, not a second full N pass.
    assert len(normalized) <= len(corpus) + 1
    result = memory.read_indexed_snapshot(query(memory_ids=("42",)), now=20)
    assert result.entries[0].summary == "共同经历的准确更正"


def test_incremental_projection_tracks_metadata_revision_and_reordered_ordinals(tmp_path):
    memory = store(tmp_path)
    a, b = entry("a"), entry("b", "一个独立来源", metadata={})
    memory.save_memories([a, b])
    before = memory.current_index_state()
    with memory._document() as document:
        document["entries"][0]["metadata"]["fact_subject"] = "relation:新牙医"
    after = memory.current_index_state()
    assert after[1] > before[1] and after[2] == before[2] + 1
    assert not memory.read_indexed_snapshot(query(subjects=("relation:牙医",)), now=20).entries
    assert [r.memory_id for r in memory.read_indexed_snapshot(query(subjects=("relation:新牙医",)), now=20).entries] == ["a"]
    memory.upsert_memory(entry("front", "新的最近事件", metadata={}))
    snap = memory.read_indexed_snapshot(query(memory_ids=("b",)), now=21)
    memory.finalize_indexed_recall(snap.entries, expected_epoch=snap.context_epoch, now=22)
    with memory._document() as document:
        counts = {r["memory_id"]: r["access_count"] for r in document["entries"]}
        assert counts == {"front": 0, "a": 0, "b": 1}


def test_literal_parser_v1_projection_rebuilds_without_changing_authority(tmp_path):
    memory = store(tmp_path)
    original = entry("drink", "我的饮品是紫苏冰饮", title="饮品偏好", metadata={},
                     source="explicit_user_request")
    memory.save_memories([original])
    before = memory.current_index_state()
    with sqlite3.connect(memory.state_path) as connection:
        connection.execute("UPDATE memory_index_meta SET algorithm_version=? WHERE id=1",
            ("typed-literal-v1:cn-grams-v1:fts-rowid-v1:structured-pk-v1:raw-diff-v1",))
    snapshot = memory.read_indexed_snapshot(query(subjects=("user:self",), predicates=("饮料偏好",)), now=20)
    assert snapshot.index_generation != before[0]
    assert snapshot.context_epoch == before[2]
    assert [row.memory_id for row in snapshot.entries] == ["drink"]
    unchanged = memory.load_memories()[0]
    assert unchanged.summary == original.summary and unchanged.metadata == {}
