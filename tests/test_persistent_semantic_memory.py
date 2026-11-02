"""Real SQLite cache protocol; deterministic encoders are not quality evidence."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

np = pytest.importorskip("numpy")

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_vector_cache import (
    MemoryVectorCache, VectorCacheSpec, VectorCacheStale,
)
from guanghe_companion.semantic_memory import SemanticMemoryRetriever


class Counting512:
    def __init__(self):
        self.passages = []
        self.before_passage = None

    @staticmethod
    def vector(text):
        return np.tile(np.frombuffer(hashlib.sha256(text.encode()).digest(), dtype=np.uint8), 16).astype(np.float32) + 1

    def passage_embed(self, texts, **kwargs):
        texts = list(texts)
        self.passages.extend(texts)
        if self.before_passage:
            self.before_passage()
        return iter(self.vector(text) for text in texts)

    def query_embed(self, text):
        return iter((self.vector(text),))


@pytest.fixture
def memory(tmp_path):
    return EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")


@pytest.fixture
def cache():
    return MemoryVectorCache(VectorCacheSpec("test-model", "pinned-revision", 8, "test-f32-v1"))


def remember(memory, text="用户喜欢绿茶", **kwargs):
    return memory.remember(kind="玩家希望被记住", title="偏好", summary=text,
        source="explicit_user_request", now=10, source_ids=("statement:" + text,), **kwargs)


def sources(*entries):
    return {entry.memory_id: (entry.evidence_fingerprint(), entry.scope) for entry in entries}


def vector(dim=8):
    raw = np.arange(1, dim + 1, dtype=np.float32)
    return raw / np.linalg.norm(raw)


def write(cache, memory, *entries, now=20):
    return cache.write(memory.store, sources(*entries), {e.memory_id: vector() for e in entries},
        now=now, state=memory.store.current_index_state(now=now))


def read(cache, memory, *entries, now=20):
    return cache.read(memory.store, sources(*entries), now=now,
        state=memory.store.current_index_state(now=now))


def rows(memory):
    with sqlite3.connect(memory.store.state_path) as connection:
        return connection.execute("SELECT memory_id FROM memory_vector_cache ORDER BY memory_id").fetchall()


def retriever(tmp_path, *, persistent_cache=True):
    result = SemanticMemoryRetriever(cache_dir=tmp_path / "models", character_id="xingxi_pixel_pet",
        owner_id="local_user", minimum_cosine=0, persistent_cache=persistent_cache)
    result._model = Counting512()
    return result


def test_cache_same_sqlite_roundtrip_without_authority_or_revision_change(cache, memory):
    first = remember(memory)
    before = memory.store.state_path.read_bytes()
    state = memory.store.current_index_state(now=20)
    result = write(cache, memory, first)
    assert result.available and result.written == 1
    found = read(cache, memory, first)
    np.testing.assert_array_equal(found.vectors[first.memory_id], vector())
    assert memory.store.current_index_state(now=20) == state
    assert len(memory.store.load_memories()) == 1
    with sqlite3.connect(memory.store.state_path) as connection:
        payload = connection.execute("SELECT payload FROM memory_state").fetchone()[0]
        assert "vector" not in json.loads(payload)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
    assert memory.store.state_path.read_bytes() != before


@pytest.mark.parametrize("change", [
    {"model_name": "other-model"}, {"model_revision": "other-revision"},
    {"dimensions": 16}, {"encoding_version": "other-encoding"},
])
def test_model_revision_dimension_and_encoding_namespaces(cache, memory, change):
    entry = remember(memory)
    write(cache, memory, entry)
    other = MemoryVectorCache(replace(cache.spec, **change))
    assert read(other, memory, entry).vectors == {}
    assert entry.memory_id in read(cache, memory, entry).vectors


def test_owner_character_scope_and_source_fingerprint_are_checked(cache, memory):
    entry = remember(memory)
    write(cache, memory, entry)
    for changed in (replace(entry, scope="task_experience"), replace(entry, summary="用户喜欢咖啡")):
        assert read(cache, memory, changed).vectors == {}
    with sqlite3.connect(memory.store.state_path) as connection:
        connection.execute("UPDATE memory_vector_cache SET owner_id='other'")
    assert read(cache, memory, entry).vectors == {}


def test_source_mutation_clears_all_model_vectors_in_same_transaction(cache, memory):
    old, retained = remember(memory), remember(memory, "用户喜欢绘画")
    write(cache, memory, old, retained)
    other = MemoryVectorCache(replace(cache.spec, model_revision="other-revision"))
    write(other, memory, old)
    memory.store.update_memory(replace(old, summary="用户喜欢白茶", version=2))
    assert rows(memory) == [(retained.memory_id,)]
    assert set(read(cache, memory, old, retained).vectors) == {retained.memory_id}


def test_access_touch_keeps_vector_and_does_not_advance_revision(cache, memory):
    entry = remember(memory)
    write(cache, memory, entry)
    state = memory.store.current_index_state(now=20)
    memory.store.update_memory(entry.touch(21))
    assert rows(memory) == [(entry.memory_id,)]
    assert memory.store.current_index_state(now=22) == state
    assert entry.memory_id in read(cache, memory, entry, now=22).vectors


def test_safe_clear_and_missing_cache_metadata_rebuild_only_projection(cache, memory):
    entry = remember(memory)
    write(cache, memory, entry)
    before = memory.store.current_index_state(now=20)
    cache.clear(memory.store, now=20)
    assert rows(memory) == []
    write(cache, memory, entry)
    with sqlite3.connect(memory.store.state_path) as connection:
        connection.execute("DROP TABLE memory_vector_cache_meta")
    assert read(cache, memory, entry).vectors == {}
    assert memory.store.current_index_state(now=20) == before
    write(cache, memory, entry)
    memory.forget(entry.memory_id, now=21)
    assert rows(memory) == []


@pytest.mark.parametrize("removal", ["forget", "physical", "expiry"])
def test_removal_clears_persisted_vectors_without_retriever_call(cache, memory, removal):
    entry = remember(memory, valid_until=25 if removal == "expiry" else 0)
    write(cache, memory, entry)
    if removal == "forget":
        memory.forget(entry.memory_id, now=21)
    elif removal == "physical":
        with memory.store._document() as document:
            document["entries"] = []
    else:
        memory.store.current_index_state(now=26)
    assert rows(memory) == []


def test_dirty_legacy_json_is_repaired_before_cached_vector_can_be_read(cache, memory):
    old = remember(memory)
    write(cache, memory, old)
    with sqlite3.connect(memory.store.state_path) as connection:
        payload = json.loads(connection.execute("SELECT payload FROM memory_state").fetchone()[0])
        payload["entries"][0]["summary"] = "用户喜欢白茶"
        connection.execute("UPDATE memory_state SET payload=?", (json.dumps(payload),))
    assert read(cache, memory, old).vectors == {}
    assert rows(memory) == []


def test_projection_rebuild_changes_generation_clears_cache_and_restores_triggers(cache, memory):
    entry = remember(memory)
    write(cache, memory, entry)
    old_state = memory.store.current_index_state(now=20)
    with sqlite3.connect(memory.store.state_path) as connection:
        connection.execute("DROP TABLE memory_index_entries")
    assert read(cache, memory, entry).vectors == {}
    assert rows(memory) == []
    assert memory.store.current_index_state(now=20)[0] != old_state[0]
    write(cache, memory, entry)
    memory.forget(entry.memory_id, now=21)
    assert rows(memory) == []


@pytest.mark.parametrize("damage", ["nan", "dimension", "checksum", "short", "norm"])
def test_corrupt_vector_is_discarded_and_rebuildable(cache, memory, damage):
    entry = remember(memory)
    write(cache, memory, entry)
    with sqlite3.connect(memory.store.state_path) as connection:
        if damage == "dimension":
            connection.execute("UPDATE memory_vector_cache SET dimensions=7")
        elif damage == "checksum":
            connection.execute("UPDATE memory_vector_cache SET checksum='broken'")
        else:
            raw = np.full(8, np.nan if damage == "nan" else 2, dtype="<f4").tobytes()
            if damage == "short":
                raw = raw[:4]
            connection.execute("UPDATE memory_vector_cache SET vector=?,checksum=?", (raw, hashlib.sha256(raw).hexdigest()))
    result = read(cache, memory, entry)
    assert result.vectors == {}
    assert result.available
    write(cache, memory, entry)
    assert entry.memory_id in read(cache, memory, entry).vectors


def test_concurrent_revocation_rejects_stale_cache_write(cache, memory):
    entry = remember(memory)
    state = memory.store.current_index_state(now=20)
    memory.forget(entry.memory_id, now=21)
    with pytest.raises(VectorCacheStale):
        cache.write(memory.store, sources(entry), {entry.memory_id: vector()}, now=22, state=state)
    assert read(cache, memory, entry, now=22).vectors == {}


def test_cached_vector_cannot_replace_missing_authority(cache, memory):
    from guanghe_companion.memory_document import MemoryStorageError
    entry = remember(memory)
    write(cache, memory, entry)
    state = memory.store.current_index_state(now=20)
    with sqlite3.connect(memory.store.state_path) as connection:
        connection.execute("DELETE FROM memory_state")
    with pytest.raises(MemoryStorageError):
        cache.read(memory.store, sources(entry), now=20, state=state)


def test_cache_error_degrades_to_miss_without_rolling_back_authority(cache, memory, monkeypatch):
    entry = remember(memory)
    def unavailable(connection, meta):
        raise sqlite3.OperationalError("cache-only test error")
    monkeypatch.setattr(cache, "_ensure_schema", unavailable)
    result = read(cache, memory, entry)
    assert result.available is False and result.vectors == {}
    assert result.error == "OperationalError"
    assert memory.store.load_memories()[0].summary == entry.summary


def test_restart_reuses_vectors_without_loading_original_bodies(memory, tmp_path, monkeypatch):
    entry = remember(memory)
    first, second = retriever(tmp_path), retriever(tmp_path)
    try:
        first.prepare_indexed("用户喜欢什么", memory.store, now=20).result(timeout=10)
        assert first.status["last_encoded_entries"] == 1
        original_scores = first.last_cosines
        first.close()
        def no_bodies(*args, **kwargs):
            pytest.fail("persisted current vector should not require source JSON payload")
        monkeypatch.setattr(type(memory.store), "read_indexed_snapshot", no_bodies)
        second.prepare_indexed("用户喜欢什么", memory.store, now=20).result(timeout=10)
        assert second.status["last_encoded_entries"] == 0
        assert second.status["persistent_cache_hits"] == 1
        assert second.status["payload_rows_loaded"] == 0
        assert second.candidate_ids("用户喜欢什么") == (entry.memory_id,)
        assert second.last_cosines == original_scores
    finally:
        first.close()
        second.close()


def test_cache_can_be_disabled_without_creating_tables(memory, tmp_path):
    remember(memory)
    first = retriever(tmp_path, persistent_cache=False)
    try:
        first.prepare_indexed("用户喜欢什么", memory.store, now=20).result(timeout=10)
        with sqlite3.connect(memory.store.state_path) as connection:
            assert connection.execute("SELECT 1 FROM sqlite_master WHERE name='memory_vector_cache'").fetchone() is None
    finally:
        first.close()


def test_persisted_scope_move_and_future_activation_reencode_only_changed_source(memory, tmp_path):
    companion = remember(memory)
    task = remember(memory, "构建依赖缺失", scope="task_experience")
    future = remember(memory, "用户喜欢油画", valid_from=30)
    first, second = retriever(tmp_path), retriever(tmp_path)
    try:
        first.prepare_indexed("用户喜欢什么", memory.store, now=20,
            scopes=("companion", "task_experience")).result(timeout=10)
        assert first.status["last_encoded_entries"] == 2
        memory.store.update_memory(replace(companion, scope="task_experience"))
        assert rows(memory) == [(task.memory_id,)]
        first.close()
        second.prepare_indexed("用户喜欢什么", memory.store, now=31,
            scopes=("companion", "task_experience")).result(timeout=10)
        assert second.status["persistent_cache_hits"] == 1
        assert second.status["last_encoded_entries"] == 2
        assert second.candidate_ids("用户喜欢什么", scope="companion") == (future.memory_id,)
        assert set(second.candidate_ids("用户喜欢什么", scope="task_experience")) == {task.memory_id, companion.memory_id}
    finally:
        first.close()
        second.close()


def test_forget_during_encoding_never_persists_or_publishes_revoked_vector(memory, tmp_path):
    entry = remember(memory)
    first = retriever(tmp_path)
    def revoke_once():
        first._model.before_passage = None
        memory.forget(entry.memory_id, now=19)
    first._model.before_passage = revoke_once
    try:
        first.prepare_indexed("用户喜欢什么", memory.store, now=20).result(timeout=10)
        assert first.candidate_ids("用户喜欢什么") == ()
        assert rows(memory) == []
    finally:
        first.close()


def test_revoke_after_cache_read_is_fenced_before_publication(memory, tmp_path):
    entry = remember(memory)
    first, second = retriever(tmp_path), retriever(tmp_path)
    try:
        first.prepare_indexed("用户喜欢什么", memory.store, now=20).result(timeout=10)
        first.close()
        original = second._persistent_cache.read
        def revoke_after_read(*args, **kwargs):
            result = original(*args, **kwargs)
            if result.vectors:
                memory.forget(entry.memory_id, now=19)
            return result
        second._persistent_cache.read = revoke_after_read
        second.prepare_indexed("用户喜欢什么", memory.store, now=20).result(timeout=10)
        assert second.candidate_ids("用户喜欢什么") == ()
        assert rows(memory) == []
    finally:
        first.close()
        second.close()


def test_concurrent_addition_retries_and_persists_still_current_encoded_vector(memory, tmp_path):
    remember(memory)
    first, second = retriever(tmp_path), retriever(tmp_path)
    def add_once():
        first._model.before_passage = None
        remember(memory, "用户喜欢绘画")
    first._model.before_passage = add_once
    try:
        first.prepare_indexed("用户喜欢什么", memory.store, now=20).result(timeout=10)
        assert first.status["last_encoded_entries"] == 2
        assert first.status["prepare_retries"] == 1
        first.close()
        second.prepare_indexed("用户喜欢什么", memory.store, now=20).result(timeout=10)
        assert second.status["persistent_cache_hits"] == 2
        assert second.status["last_encoded_entries"] == 0
    finally:
        first.close()
        second.close()


def test_transient_cache_write_failure_is_retried_without_passage_reencoding(memory, tmp_path, monkeypatch):
    from guanghe_companion.memory_vector_cache import VectorCacheResult
    remember(memory)
    first = retriever(tmp_path)
    original = first._persistent_cache.write
    failures = [True]
    def unavailable_once(*args, **kwargs):
        if failures:
            failures.pop()
            return VectorCacheResult(available=False, error="OperationalError")
        return original(*args, **kwargs)
    monkeypatch.setattr(first._persistent_cache, "write", unavailable_once)
    try:
        first.prepare_indexed("用户喜欢什么", memory.store, now=20).result(timeout=10)
        assert first.status["persistent_cache_errors"] == 1
        first.prepare_indexed("用户喜欢什么", memory.store, now=20).result(timeout=10)
        assert first.status["last_encoded_entries"] == 0
        assert first.status["persistent_cache_writes"] == 1
        assert len(rows(memory)) == 1
    finally:
        first.close()


def test_real_bge_independent_process_restart_uses_no_passage_encoder(memory, tmp_path):
    pytest.importorskip("fastembed")
    model_cache = os.environ.get("EMOTI_BGE_TEST_CACHE")
    if not model_cache or not Path(model_cache).exists():
        pytest.skip("set EMOTI_BGE_TEST_CACHE to the pinned real model cache")
    entry = remember(memory, "用户喜欢拍摄飞鸟和海边日落。")
    first = SemanticMemoryRetriever(cache_dir=model_cache, character_id=memory.character_id,
        owner_id=memory.owner_id, local_files_only=True)
    try:
        first.prepare_indexed("休息时有什么爱好", memory.store, now=20).result(timeout=90)
        assert first.status["last_encoded_entries"] == 1
    finally:
        first.close()
    script = '''
import json, sys
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.semantic_memory import SemanticMemoryRetriever
memory = EmotionalMemoryService(root=sys.argv[1], character_id='xingxi_pixel_pet')
retriever = SemanticMemoryRetriever(cache_dir=sys.argv[2], character_id=memory.character_id,
    owner_id=memory.owner_id, local_files_only=True)
try:
    retriever.warmup().result(timeout=90)
    def reject_passages(*args, **kwargs):
        raise AssertionError('restart must not reencode persisted passages')
    retriever._model.passage_embed = reject_passages
    retriever.prepare_indexed('休息时有什么爱好', memory.store, now=20).result(timeout=90)
    print(json.dumps({'status': retriever.status, 'ids': retriever.candidate_ids('休息时有什么爱好')}))
finally:
    retriever.close()
'''
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path), model_cache],
        capture_output=True, text=True, timeout=120, check=True)
    data = json.loads(result.stdout)
    assert data["status"]["encoded_entries_total"] == 0
    assert data["status"]["persistent_cache_hits"] == 1
    assert data["ids"] == [entry.memory_id]
