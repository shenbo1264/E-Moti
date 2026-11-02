"""Cache protocol tests use a counting encoder, not retrieval-quality evidence.

The optional real BGE test at the end exercises the actual encoder and SQLite.
"""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import sqlite3

import pytest

np = pytest.importorskip("numpy")

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.semantic_memory import SemanticMemoryRetriever, _identity


class CountingEncoder:
    def __init__(self):
        self.passages = []
        self.queries = []
        self.before_passage = None

    @staticmethod
    def vector(text):
        return np.asarray([1 + byte / 255 for byte in hashlib.sha256(text.encode()).digest()[:8]], dtype=np.float32)

    def passage_embed(self, texts, **kwargs):
        assert kwargs.get("batch_size") == 64
        texts = list(texts)
        self.passages.extend(texts)
        if self.before_passage:
            self.before_passage()
        return iter(self.vector(text) for text in texts)

    def query_embed(self, text):
        self.queries.append(text)
        return iter((self.vector(text),))


@pytest.fixture
def memory(tmp_path):
    return EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")


@pytest.fixture
def semantic(tmp_path):
    retriever = SemanticMemoryRetriever(cache_dir=tmp_path / "models", character_id="xingxi_pixel_pet",
                                         owner_id="local_user", minimum_cosine=0, persistent_cache=False)
    retriever._model = CountingEncoder()
    yield retriever
    retriever.close()


def remember(memory, text="用户喜欢绿茶", now=10, **kwargs):
    return memory.remember(kind="玩家希望被记住", title="偏好", summary=text,
        source="explicit_user_request", now=now, source_ids=("statement:" + text,), **kwargs)


def prepare(semantic, memory, query="喜欢什么", now=20, scopes=("companion",)):
    semantic.prepare_indexed(query, memory.store, now=now, scopes=scopes).result(timeout=10)


def test_identity_authenticates_semantic_metadata(memory):
    entry = remember(memory, metadata={"fact_value": "绿茶"})
    assert _identity(entry) != _identity(replace(entry, metadata={"fact_value": "咖啡"}))
    assert _identity(entry) == _identity(entry.touch(30))


def test_unchanged_revision_never_reencodes_passages(semantic, memory):
    entry = remember(memory)
    prepare(semantic, memory)
    prepare(semantic, memory, query="爱喝什么")
    assert len(semantic._model.passages) == 1
    assert semantic.status["last_encoded_entries"] == 0
    assert semantic.status["encoded_entries_total"] == 1
    assert semantic.status["query_embed_count"] == 2
    assert semantic("爱喝什么", (entry,))
    assert semantic.candidate_ids("爱喝什么") == (entry.memory_id,)


def test_addition_only_encodes_new_revision(semantic, memory):
    first = remember(memory)
    prepare(semantic, memory)
    second = remember(memory, "用户喜欢摄影", now=21)
    prepare(semantic, memory, now=22)
    assert len(semantic._model.passages) == 2
    assert semantic.status["last_encoded_entries"] == 1
    assert set(semantic.candidate_ids("喜欢什么")) == {first.memory_id, second.memory_id}


def test_metadata_revision_invalidates_old_vector(semantic, memory):
    old = remember(memory, metadata={"fact_value": "绿茶"})
    prepare(semantic, memory)
    memory.store.update_memory(replace(old, metadata={"fact_value": "白茶"}))
    assert semantic("喜欢什么", (old,)) == {}


def test_legacy_writer_is_given_revocation_epoch_and_fences_old_scores(semantic, memory):
    old = remember(memory)
    prepare(semantic, memory)
    epoch = memory.store.current_context_epoch()
    with memory.store._document() as document:
        document["entries"][0]["metadata"] = {"fact_value": "咖啡"}
    assert memory.store.current_context_epoch() > epoch
    assert semantic.candidate_ids("喜欢什么") == ()
    assert semantic("喜欢什么", (old,)) == {}
    prepare(semantic, memory)
    current = next(m for m in memory.store.load_memories() if m.memory_id == old.memory_id)
    assert semantic.status["last_encoded_entries"] == 1
    assert semantic("喜欢什么", (current,))
    assert semantic("喜欢什么", (old,)) == {}


def test_invalidate_clears_scores_but_reuses_reauthorized_vectors(semantic, memory):
    entry = remember(memory)
    prepare(semantic, memory)
    semantic.invalidate()
    assert semantic("喜欢什么", (entry,)) == {}
    assert semantic.candidate_ids("喜欢什么") == ()
    prepare(semantic, memory)
    assert len(semantic._model.passages) == 1
    assert semantic("喜欢什么", (entry,))


def test_forget_removes_only_affected_vector(semantic, memory):
    old = remember(memory)
    retained = remember(memory, "用户喜欢绘画")
    prepare(semantic, memory)
    memory.forget(old.memory_id, now=21)
    assert semantic("喜欢什么", (old,)) == {}
    assert semantic.candidate_ids("喜欢什么") == ()
    semantic.invalidate()
    prepare(semantic, memory, now=22)
    assert len(semantic._model.passages) == 2
    assert semantic.status["indexed_entries"] == 1
    assert semantic.candidate_ids("喜欢什么") == (retained.memory_id,)
    assert all(old.memory_id not in {key[0] for key in keys} for keys in semantic._matrix_cache)


def test_expiry_and_future_activation_without_full_reencoding(semantic, memory):
    expires = remember(memory, valid_until=25)
    future = remember(memory, "用户喜欢油画", valid_from=30)
    prepare(semantic, memory, now=20)
    assert semantic.candidate_ids("喜欢什么") == (expires.memory_id,)
    prepare(semantic, memory, now=26)
    assert semantic.candidate_ids("喜欢什么") == ()
    prepare(semantic, memory, now=31)
    assert semantic.candidate_ids("喜欢什么") == (future.memory_id,)
    assert len(semantic._model.passages) == 2


def test_scope_switch_keeps_independent_revision_cursors(semantic, memory):
    companion = remember(memory)
    task = remember(memory, "构建依赖缺失", scope="task_experience")
    prepare(semantic, memory)
    prepare(semantic, memory, scopes=("task_experience",))
    assert semantic.candidate_ids("喜欢什么") == (task.memory_id,)
    assert semantic.candidate_ids("喜欢什么", scope="companion") == ()
    prepare(semantic, memory)
    assert semantic.candidate_ids("喜欢什么") == (companion.memory_id,)
    assert len(semantic._model.passages) == 2


def test_move_out_of_scope_evicts_previous_membership(semantic, memory):
    entry = remember(memory)
    prepare(semantic, memory)
    memory.store.update_memory(replace(entry, scope="task_experience"))
    prepare(semantic, memory)
    assert semantic.candidate_ids("喜欢什么") == ()
    prepare(semantic, memory, scopes=("task_experience",))
    assert semantic.candidate_ids("喜欢什么") == (entry.memory_id,)
    assert semantic.status["indexed_entries"] == 1


def test_two_scopes_one_query_is_one_bounded_search(semantic, memory):
    first = remember(memory)
    second = remember(memory, "构建依赖缺失", scope="task_experience")
    prepare(semantic, memory, scopes=("companion", "task_experience"))
    assert set(semantic.candidate_ids("喜欢什么")) == {first.memory_id, second.memory_id}
    assert semantic.candidate_ids("喜欢什么", scope="task_experience") == (second.memory_id,)
    assert semantic.status["query_embed_count"] == 1


def test_wrong_store_owner_is_rejected_before_model(semantic, memory, tmp_path):
    other = EmotionalMemoryService(root=tmp_path, character_id="other")
    with pytest.raises(ValueError, match="owner|character"):
        semantic.prepare_indexed("喜欢什么", other.store, now=20)
    assert not semantic._model.passages


def test_blank_query_and_empty_store_never_load_encoder(semantic, memory):
    remember(memory)
    prepare(semantic, memory, query="")
    assert not semantic._model.passages
    assert not semantic._model.queries
    assert semantic.candidate_ids("") == ()


def test_forget_during_encoding_never_publishes_old_score(semantic, memory):
    old = remember(memory)
    def forget_once():
        semantic._model.before_passage = None
        memory.forget(old.memory_id, now=19)
    semantic._model.before_passage = forget_once
    prepare(semantic, memory)
    assert semantic.candidate_ids("喜欢什么") == ()
    assert semantic("喜欢什么", (old,)) == {}


def test_generation_cancel_during_encoding_does_not_publish(semantic, memory):
    old = remember(memory)
    semantic._model.before_passage = semantic.invalidate
    prepare(semantic, memory)
    assert semantic("喜欢什么", (old,)) == {}
    assert semantic.candidate_ids("喜欢什么") == ()


def test_full_manifest_pagination_reads_only_changed_payloads(semantic, memory, monkeypatch):
    entries = [remember(memory, f"用户偏好编号{i}", now=i + 1) for i in range(8)]
    original_manifest = type(memory.store).index_manifest
    original_read = type(memory.store).read_indexed_snapshot
    loaded = []
    def paginated(store, **kwargs):
        kwargs["limit"] = 3
        return original_manifest(store, **kwargs)
    def counted(store, request=None, **kwargs):
        result = original_read(store, request, **kwargs)
        loaded.append(len(result.entries))
        return result
    monkeypatch.setattr(type(memory.store), "index_manifest", paginated)
    monkeypatch.setattr(type(memory.store), "read_indexed_snapshot", counted)
    prepare(semantic, memory)
    assert len(semantic._model.passages) == 8
    loaded.clear()
    prepare(semantic, memory)
    assert sum(loaded) == 0
    assert set(semantic.candidate_ids("喜欢什么")) == {e.memory_id for e in entries}


def test_final_publish_fence_reads_only_header_state(semantic, memory, monkeypatch):
    remember(memory)
    original_manifest = type(memory.store).index_manifest
    original_state = type(memory.store).current_index_state
    calls = {"manifest": 0, "state": 0}
    def manifest(store, **kwargs):
        calls["manifest"] += 1
        return original_manifest(store, **kwargs)
    def state(store, **kwargs):
        calls["state"] += 1
        return original_state(store, **kwargs)
    monkeypatch.setattr(type(memory.store), "index_manifest", manifest)
    monkeypatch.setattr(type(memory.store), "current_index_state", state)
    prepare(semantic, memory)
    assert calls == {"manifest": 1, "state": 1}


def test_projection_generation_change_rebuilds_derived_vectors(semantic, memory):
    entry = remember(memory)
    prepare(semantic, memory)
    before_generation = semantic.status["index_generation"]
    with sqlite3.connect(memory.store.state_path) as connection:
        connection.execute("DROP TABLE memory_index_entries")
    prepare(semantic, memory)
    assert semantic.status["index_generation"] != before_generation
    assert semantic.candidate_ids("喜欢什么") == (entry.memory_id,)
    assert semantic.status["last_encoded_entries"] == 1


def test_physical_removal_tombstone_cannot_keep_vector(semantic, memory):
    old = remember(memory)
    retained = remember(memory, "用户喜欢绘画")
    prepare(semantic, memory)
    # Simulate a compatible legacy editor writing the same authoritative JSON.
    with memory.store._document() as document:
        document["entries"] = [row for row in document["entries"] if row["memory_id"] != old.memory_id]
    prepare(semantic, memory)
    assert semantic.candidate_ids("喜欢什么") == (retained.memory_id,)
    assert semantic.status["last_encoded_entries"] == 0


def test_revision_change_during_pagination_retries_consistent_manifest(semantic, memory, monkeypatch):
    entries = [remember(memory, f"用户偏好编号{i}", now=i + 1) for i in range(5)]
    original = type(memory.store).index_manifest
    changed = False
    def race(store, **kwargs):
        nonlocal changed
        kwargs["limit"] = 2
        page = original(store, **kwargs)
        if page.has_more and not changed:
            changed = True
            memory.forget(entries[-1].memory_id, now=18)
        return page
    monkeypatch.setattr(type(memory.store), "index_manifest", race)
    prepare(semantic, memory)
    assert entries[-1].memory_id not in semantic.candidate_ids("喜欢什么")
    assert semantic.status["prepare_retries"] == 1
    assert semantic.status["indexed_entries"] == 4


def test_switching_database_for_same_owner_character_does_not_mix_sources(semantic, memory, tmp_path):
    first = remember(memory)
    prepare(semantic, memory)
    other = EmotionalMemoryService(root=tmp_path / "other", character_id=memory.character_id)
    second = remember(other, "用户喜欢户外露营")
    prepare(semantic, other)
    assert semantic.candidate_ids("喜欢什么") == (second.memory_id,)
    assert semantic("喜欢什么", (first,)) == {}


def test_real_bge_indexed_lifecycle(tmp_path):
    pytest.importorskip("fastembed")
    cache = os.environ.get("EMOTI_BGE_TEST_CACHE")
    if not cache or not Path(cache).exists():
        pytest.skip("set EMOTI_BGE_TEST_CACHE to the pinned real model cache")
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    first = remember(memory, "我对花生过敏，不能吃含有花生的食品。")
    unrelated = remember(memory, "用户周末喜欢拍摄飞鸟。")
    retriever = SemanticMemoryRetriever(cache_dir=cache, character_id="xingxi_pixel_pet",
        owner_id="local_user", local_files_only=True)
    try:
        retriever.prepare_indexed("点餐应该避开什么食材", memory.store, now=20).result(timeout=120)
        assert first.memory_id in retriever.candidate_ids("点餐应该避开什么食材")
        initial = retriever.status["encoded_entries_total"]
        retriever.prepare_indexed("用户喜欢什么活动", memory.store, now=20).result(timeout=120)
        assert retriever.status["encoded_entries_total"] == initial == 2
        memory.forget(first.memory_id, now=21)
        retriever.invalidate()
        retriever.prepare_indexed("点餐应该避开什么食材", memory.store, now=22).result(timeout=120)
        assert first.memory_id not in retriever.candidate_ids("点餐应该避开什么食材")
        assert retriever.status["encoded_entries_total"] == 2
        assert retriever.status["indexed_entries"] == 1
        assert unrelated.memory_id in retriever.last_cosines
    finally:
        retriever.close()
