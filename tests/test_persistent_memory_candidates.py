from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import json
import shutil
import sqlite3

import pytest

from guanghe_companion.emotional_memory_policy import MemoryCandidate
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_document import MemoryStorageError


def service(root):
    return EmotionalMemoryService(root=root, character_id="xingxi_pixel_pet")


def candidate(**changes):
    value = MemoryCandidate(character_id="xingxi_pixel_pet", owner_id="local_user",
        kind="玩家希望被记住", title="饮品偏好", summary="我喜欢桂花茶",
        source="user_statement", occurred_at=10, source_ids=("turn-001:fact-0",),
        requires_user_confirmation=True, metadata={"source_text": "也许以后会常喝桂花茶"})
    return replace(value, **changes)


def test_pending_candidate_and_source_survive_restart_without_becoming_fact(tmp_path):
    first = service(tmp_path)
    first.propose_candidate(candidate(), pending_id="proposal-1", expected_epoch=0)
    restarted = service(tmp_path)
    assert restarted.pending_candidates["proposal-1"] == candidate()
    assert not restarted.recall("饮品", now=11)
    saved = restarted.confirm_candidate("proposal-1", now=12)
    assert saved.user_confirmed and saved.source_ids == ("turn-001:fact-0",)
    assert saved.occurred_at == 10 and saved.created_at == 12
    assert saved.metadata["source_text"] == "也许以后会常喝桂花茶"
    assert not service(tmp_path).pending_candidates


def test_same_source_deduplicates_proposal_across_ids_and_restart(tmp_path):
    first = service(tmp_path)
    first.propose_candidate(candidate(), pending_id="first", expected_epoch=0)
    restarted = service(tmp_path)
    assert restarted.propose_candidate(candidate(), pending_id="retry", expected_epoch=0) == "first"
    assert list(restarted.pending_candidates) == ["first"]
    restarted.confirm_candidate("first", now=11)
    with pytest.raises(ValueError, match="resolved"):
        service(tmp_path).propose_candidate(candidate(), pending_id="again", expected_epoch=0)
    assert len(service(tmp_path).store.load_memories()) == 1


def test_rejection_is_durable_and_source_cannot_be_reproposed(tmp_path):
    first = service(tmp_path)
    first.propose_candidate(candidate(), pending_id="first", expected_epoch=0)
    assert service(tmp_path).reject_candidate("first")
    assert not first.pending_candidates
    with pytest.raises(ValueError, match="resolved"):
        first.propose_candidate(candidate(summary="桂花茶偏好"), pending_id="retry", expected_epoch=0)
    assert not first.store.load_memories()


def test_explicit_pending_forget_revokes_source_and_epoch_across_restart(tmp_path):
    first = service(tmp_path)
    first.propose_candidate(candidate(), pending_id="first", expected_epoch=0)
    assert first.reject_candidate("first", revoke_context=True)
    restarted = service(tmp_path)
    assert restarted.store.context_epoch == 1
    assert not restarted.pending_candidates
    stale = candidate().to_memory(now=12, user_confirmed=True)
    assert restarted.store.upsert_memory(stale).deleted
    assert not restarted.store.load_memories()
    assert not restarted.reject_candidate("first", revoke_context=True)
    assert restarted.store.context_epoch == 1


def test_real_change_uses_new_event_time_but_correction_preserves_it(tmp_path):
    first = service(tmp_path)
    old = first.remember(kind="玩家希望被记住", title="饮品", summary="喜欢茶",
                         source="user_chat", now=10, source_ids=("old",))
    changed = first.remember(kind=old.kind, title="饮品", summary="现在改喝咖啡",
        source="user_chat", now=20, source_ids=("new",), supersedes=old.memory_id,
        preserve_occurred_at=False)
    assert changed.occurred_at == 20
    corrected = first.correct(changed.memory_id, title="饮品", summary="实际是低因咖啡", now=30)
    assert corrected.occurred_at == 20
    assert corrected.created_at == 30


def test_reusing_proposal_id_for_another_source_is_rejected(tmp_path):
    first = service(tmp_path)
    first.propose_candidate(candidate(), pending_id="first", expected_epoch=0)
    with pytest.raises(ValueError, match="conflict"):
        first.propose_candidate(candidate(source_ids=("other-turn",)), pending_id="first", expected_epoch=0)


@pytest.mark.parametrize("edit", ["forget", "correct"])
def test_cross_instance_source_edit_fences_persisted_candidate(tmp_path, edit):
    first = service(tmp_path)
    original = first.remember(kind="玩家希望被记住", title="原事实", summary="我喜欢茶",
                              source="user_statement", now=1, source_ids=("original-turn",))
    first.propose_candidate(candidate(metadata={"source_memory_ids": [original.memory_id]}),
                            pending_id="derived", expected_epoch=0)
    other = service(tmp_path)
    if edit == "forget":
        other.forget(original.memory_id, now=11)
    else:
        other.correct(original.memory_id, title="原事实", summary="我喜欢白水", now=11)
    with pytest.raises(ValueError, match="stale"):
        service(tmp_path).confirm_candidate("derived", now=12)
    assert "derived" not in first.pending_candidates
    assert not any(row.summary == "我喜欢桂花茶" for row in first.store.load_memories())


def test_candidate_rejects_missing_source_reference(tmp_path):
    with pytest.raises(ValueError, match="source"):
        service(tmp_path).propose_candidate(candidate(metadata={"source_memory_ids": ["missing"]}),
                                            pending_id="derived", expected_epoch=0)


def test_explicit_new_statement_can_be_confirmed_after_same_text_was_forgotten(tmp_path):
    first = service(tmp_path)
    old_id = first.propose_explicit_user_memory("请记住：我喜欢茶", now=10)
    old = first.confirm_candidate(old_id, now=10)
    first.forget(old.memory_id, now=10)
    new_id = service(tmp_path).propose_explicit_user_memory("请记住：我喜欢茶", now=10)
    assert new_id != old_id
    new = first.confirm_candidate(new_id, now=10)
    assert new.user_confirmed and not new.deleted


def test_correction_appends_new_provenance_and_preserves_old_event_time(tmp_path):
    first = service(tmp_path)
    old = first.remember(kind="玩家希望被记住", title="饮品", summary="我喜欢咖啡",
        source="user_statement", now=10, source_ids=("old-turn",), metadata={"fact_key": "drink"})
    new = first.correct(old.memory_id, title="饮品", summary="我喜欢桂花茶", now=20,
        source_ids=("new-turn",), metadata={"source_text": "刚才说错了，我喜欢桂花茶"})
    assert new.source_ids == ("old-turn", "new-turn")
    assert new.metadata["fact_key"] == "drink"
    assert new.metadata["source_text"] == "刚才说错了，我喜欢桂花茶"
    assert new.occurred_at == 10 and new.created_at == 20


def test_existing_document_upgrade_on_copy_preserves_original_and_revocations(tmp_path):
    original_root = tmp_path / "original"
    original = service(original_root)
    old = original.remember(kind="玩家希望被记住", title="旧事实", summary="不再使用的事实",
                            source="user_statement", now=1, source_ids=("old-turn",))
    original.forget(old.memory_id, now=2)
    before = original.store.state_path.read_bytes()
    copied_root = tmp_path / "copy"
    shutil.copytree(original_root, copied_root)
    copied = service(copied_root)
    pending = copied.propose_explicit_user_memory("请记住：新的独立事实", now=3)
    service(copied_root).confirm_candidate(pending, now=4)
    assert copied.store.is_retired_origin(entry=old)
    assert original.store.state_path.read_bytes() == before
    assert not original.pending_candidates


def test_malformed_persisted_candidate_fails_without_overwriting_document(tmp_path):
    first = service(tmp_path)
    first.store.load_memories()
    with sqlite3.connect(first.store.state_path) as db:
        payload = json.loads(db.execute("SELECT payload FROM memory_state").fetchone()[0])
        payload["pending_candidates"] = {"broken": {"entry": {"summary": "坏结构"}}}
        serialized = json.dumps(payload)
        db.execute("UPDATE memory_state SET payload=?", (serialized,))
    with pytest.raises(MemoryStorageError):
        service(tmp_path).pending_candidates
    with sqlite3.connect(first.store.state_path) as db:
        assert db.execute("SELECT payload FROM memory_state").fetchone()[0] == serialized


def test_pending_source_expiry_is_checked_inside_confirmation(tmp_path):
    first = service(tmp_path)
    origin = first.remember(kind="玩家希望被记住", title="短时事实", summary="今日喝茶",
        source="user_statement", now=1, valid_until=12)
    first.propose_candidate(candidate(metadata={"source_memory_ids": [origin.memory_id]}),
                            pending_id="derived", expected_epoch=0)
    with pytest.raises(ValueError, match="stale"):
        service(tmp_path).confirm_candidate("derived", now=13)
    assert not first.pending_candidates


def test_concurrent_confirmations_commit_only_one_fact(tmp_path):
    first = service(tmp_path)
    first.propose_candidate(candidate(), pending_id="shared", expected_epoch=0)
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(service(tmp_path).confirm_candidate, "shared", now=20) for _ in range(2)]
        successes, missing = [], []
        for future in futures:
            try:
                successes.append(future.result())
            except KeyError as exc:
                missing.append(exc)
    assert len(successes) == len(missing) == 1
    assert len(first.store.load_memories()) == 1
    assert not first.pending_candidates


def test_proposal_record_time_is_separate_from_event_time(tmp_path):
    first = service(tmp_path)
    first.propose_candidate(candidate(occurred_at=1), pending_id="historical", expected_epoch=0, now=20)
    stored = first.store.load_pending_candidates()["historical"][0]
    assert stored.occurred_at == 1 and stored.created_at == 20


def test_correction_rejects_source_overflow_without_retiring_original(tmp_path):
    from guanghe_companion.emotional_memory import MAX_SOURCE_IDS
    first = service(tmp_path)
    original = first.remember(kind="玩家希望被记住", title="饮品", summary="我喜欢茶",
        source="user_statement", now=1, source_ids=tuple(f"source-{n}" for n in range(MAX_SOURCE_IDS)))
    with pytest.raises(ValueError, match="source"):
        first.correct(original.memory_id, title="饮品", summary="我喜欢白水", now=2, source_ids=("new-turn",))
    assert first.store.load_memories()[0].summary == "我喜欢茶"
    assert first.store.context_epoch == 0


def test_confirmed_conflict_atomically_replaces_bound_original(tmp_path):
    first = service(tmp_path)
    original = first.remember(kind="玩家希望被记住", title="饮品", summary="我喜欢咖啡",
        source="user_statement", now=1, source_ids=("old-turn",), metadata={"fact_key": "drink"})
    proposed = candidate(metadata={"supersedes_memory_id": original.memory_id,
                                   "source_memory_ids": [original.memory_id], "fact_key": "drink"})
    first.propose_candidate(proposed, pending_id="conflict", expected_epoch=0)
    result = service(tmp_path).confirm_candidate("conflict", now=20)
    active = [row for row in first.store.load_memories() if not row.deleted]
    assert [row.memory_id for row in active] == [result.memory_id]
    assert result.supersedes == original.memory_id and result.version == 2
    assert result.source_ids == ("old-turn", "turn-001:fact-0")
    assert result.occurred_at == 1 and result.created_at == 20
    assert result.metadata["corrected_by_user"] is True
    assert first.store.context_epoch == 1
    assert not first.pending_candidates


def test_conflict_candidate_cannot_replace_an_unbound_memory(tmp_path):
    first = service(tmp_path)
    original = first.remember(kind="玩家希望被记住", title="饮品", summary="我喜欢咖啡",
        source="user_statement", now=1)
    with pytest.raises(ValueError, match="source"):
        first.propose_candidate(candidate(metadata={"supersedes_memory_id": original.memory_id}),
                                pending_id="unbound", expected_epoch=0)
    assert first.store.load_memories()[0].summary == "我喜欢咖啡"
    assert not first.pending_candidates
