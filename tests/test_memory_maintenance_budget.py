"""Maintenance operates on evidence and a bounded window, never invented days."""
from dataclasses import replace

import pytest

from guanghe_companion.emotional_memory import EmotionalMemoryEntry, EmotionalMemoryStore
from guanghe_companion.memory_maintenance import MaintenanceBudget, run_memory_maintenance


def memory(tmp_path):
    return EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")


def event(key, **kw):
    values = dict(memory_id=key, character_id="xingxi_pixel_pet", owner_id="local_user",
        kind="共同经历", title="共同日常", summary=f"我们完成了第 {key} 次共同观测。", source="game_event",
        occurred_at=10, created_at=10, updated_at=10, importance=.8,
        source_ids=("actual-event:" + key,), metadata={"event_status": "completed",
            "participants": ["user:self", "character:self"]})
    values.update(kw)
    return EmotionalMemoryEntry(**values)


def test_only_actual_completed_shared_events_become_a_chapter(tmp_path):
    store = memory(tmp_path)
    actual = [event(str(i)) for i in range(3)]
    store.save_memories([*actual,
        event("planned", metadata={"event_status": "planned", "participants": ["user:self", "character:self"]}),
        event("pending", kind="玩耍", metadata={"event_status": "pending"}),
        event("model", source="assistant"),
        event("preference", kind="用户自述", source="user_chat", metadata={"fact_slot": "饮料偏好", "fact_value": "咖啡"})])
    report = run_memory_maintenance(store, now=20)
    assert report.checked_sources == 7 and report.shared_sources == 3
    assert report.created_chapter is not None
    assert set(report.created_chapter.source_memory_ids) == {row.memory_id for row in actual}
    assert report.created_chapter.source_fingerprints == {row.memory_id: row.evidence_fingerprint() for row in actual}
    assert all(row.access_count == 0 for row in store.load_memories())


def test_repeated_maintenance_deduplicates_without_reading_canonical_document(tmp_path, monkeypatch):
    store = memory(tmp_path)
    store.save_memories([event(str(i)) for i in range(3)])
    first = run_memory_maintenance(store, now=20)
    assert first.created_chapter

    def reject(*args, **kwargs):
        raise AssertionError("Unchanged maintenance should read bounded projections only")

    monkeypatch.setattr(EmotionalMemoryStore, "_document", reject)
    again = run_memory_maintenance(store, now=21)
    assert again.created_chapter is None and again.existing_chapter == first.created_chapter
    assert "already_consolidated" in again.skipped
    assert not again.write_started


def test_source_budget_caps_window_and_marks_partial_scope(tmp_path, monkeypatch):
    store = memory(tmp_path)
    store.save_memories([event(str(i), kind="用户自述", source="user_chat", metadata={}) for i in range(300)])
    monkeypatch.setattr(EmotionalMemoryStore, "load_memories", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("maintenance may not scan all bodies")))
    report = run_memory_maintenance(store, now=20, budget=MaintenanceBudget(max_sources=999))
    assert report.checked_sources == 128 and report.partial_scan
    assert report.created_chapter is None


def test_zero_admission_budget_never_opens_a_store(tmp_path):
    store = memory(tmp_path)
    result = run_memory_maintenance(store, now=20, budget=MaintenanceBudget(admission_ms=0))
    assert result.checked_sources == 0 and "admission_budget" in result.skipped
    assert not store.state_path.exists()


def test_duplicate_source_copies_do_not_invent_repeated_experiences(tmp_path):
    store = memory(tmp_path)
    original = event("original")
    store.save_memories([replace(original, memory_id=str(i)) for i in range(3)])
    result = run_memory_maintenance(store, now=20)
    assert result.shared_sources == 1 and result.created_chapter is None
    assert "overlapping_event_sources" in result.skipped


def test_duplicate_facts_and_single_value_conflicts_are_reports_not_deletions(tmp_path):
    store = memory(tmp_path)
    def fact(key, value, predicate="name"):
        return event(key, kind="用户自述", source="user_chat", summary=f"用户的{predicate}是{value}",
            metadata={"fact_subject": "user:self", "fact_predicate": predicate,
                      "fact_slot": predicate, "fact_value": value})
    store.save_memories([fact("a", "小林"), fact("b", "小林"), fact("c", "小青"),
                         fact("p1", "咖啡", "preference"), fact("p2", "茶", "preference")])
    result = run_memory_maintenance(store, now=20)
    assert result.duplicate_fact_groups == (("a", "b"),)
    assert len(result.conflicts) == 1 and set(result.conflicts[0].memory_ids) == {"a", "b", "c"}
    assert result.created_chapter is None
    assert len(store.load_memories()) == 5 and all(not row.deleted for row in store.load_memories())


@pytest.mark.parametrize("legacy", [False, True])
def test_racing_source_revocation_or_raw_change_cannot_publish_a_chapter(tmp_path, monkeypatch, legacy):
    store = memory(tmp_path)
    store.save_memories([event(str(i)) for i in range(3)])
    original = EmotionalMemoryStore.upsert_chapter

    def racing(self, chapter, **kw):
        if legacy:
            with self._document() as document:
                document["entries"][0]["summary"] = "这不是此前的事件"
        else:
            self.forget_memory("0", now=19)
        return original(self, chapter, **kw)

    monkeypatch.setattr(EmotionalMemoryStore, "upsert_chapter", racing)
    result = run_memory_maintenance(store, now=20)
    assert result.created_chapter is None
    assert "source_changed" in result.skipped
    assert not store.load_chapters()


def test_expired_event_is_not_consolidated_as_current(tmp_path):
    store = memory(tmp_path)
    store.save_memories([event("a", valid_until=20), event("b"), event("c")])
    report = run_memory_maintenance(store, now=21)
    assert report.checked_sources == 2 and report.created_chapter is None


def test_failed_completed_event_is_kept_as_failure_not_rewritten_as_success(tmp_path):
    store = memory(tmp_path)
    failed = event("failed", summary="我们一起尝试部署，部署失败了。", metadata={
        "event_status": "failed", "participants": ["user:self", "character:self"]})
    store.save_memories([failed, event("a"), event("b")])
    report = run_memory_maintenance(store, now=20)
    assert report.created_chapter and "部署失败" in report.created_chapter.summary
    assert "部署成功" not in report.created_chapter.summary


def test_admitted_atomic_write_can_overrun_budget_but_is_not_interrupted(tmp_path, monkeypatch):
    store = memory(tmp_path)
    store.save_memories([event(str(i)) for i in range(3)])
    elapsed = [0.0]
    original = EmotionalMemoryStore.upsert_chapter

    def slow_write(self, chapter, **kw):
        result = original(self, chapter, **kw)
        elapsed[0] = .5
        return result

    monkeypatch.setattr(EmotionalMemoryStore, "upsert_chapter", slow_write)
    report = run_memory_maintenance(store, now=20, budget=MaintenanceBudget(admission_ms=50), clock=lambda: elapsed[0])
    assert report.created_chapter and report.write_started and report.budget_overrun
    assert report.elapsed_ms == 500


def test_disabling_writes_preserves_diagnostics_and_does_not_make_a_chapter(tmp_path):
    store = memory(tmp_path)
    store.save_memories([event(str(i)) for i in range(3)])
    report = run_memory_maintenance(store, now=20, budget=MaintenanceBudget(max_chapter_writes=0))
    assert report.checked_sources == 3 and report.created_chapter is None
    assert "writes_disabled" in report.skipped


def test_reflection_cannot_append_an_unsupported_shared_experience(tmp_path):
    from guanghe_companion.emotional_memory_reflection import MemoryReflectionService
    class InventedChapter(MemoryReflectionService):
        def build_chapter(self, *args, **kwargs):
            chapter = super().build_chapter(*args, **kwargs)
            return replace(chapter, summary=chapter.summary + "我们还一起去了海边。")
    store = memory(tmp_path)
    store.save_memories([event(str(i)) for i in range(3)])
    result = run_memory_maintenance(store, now=20, reflection=InventedChapter())
    assert result.created_chapter is None
    assert "unsupported_chapter_text" in result.skipped
    assert not store.load_chapters()


def test_scheduler_coalesces_pending_requests_and_never_reenters(tmp_path):
    from threading import Event, Lock
    from guanghe_companion.memory_maintenance import MemoryMaintenanceScheduler
    store = memory(tmp_path)
    store.save_memories([event(str(i)) for i in range(3)])
    first_done, release = Event(), Event()
    observed, active, peaks = [], [0], []
    lock = Lock()

    def runner(*args, **kwargs):
        with lock:
            active[0] += 1
            peaks.append(active[0])
            observed.append(kwargs["now"])
        try:
            result = run_memory_maintenance(*args, **kwargs)
            if len(observed) == 1:
                first_done.set()
                assert release.wait(5)
            return result
        finally:
            with lock:
                active[0] -= 1

    scheduler = MemoryMaintenanceScheduler(store, runner=runner)
    try:
        assert scheduler.request(now=20, budget=MaintenanceBudget(admission_ms=1000))
        assert first_done.wait(5)
        store.upsert_memory(event("new", occurred_at=21, created_at=21, updated_at=21))
        assert scheduler.request(now=21, budget=MaintenanceBudget(admission_ms=1000))
        assert scheduler.request(now=22, budget=MaintenanceBudget(admission_ms=1000))
        assert scheduler.snapshot().pending
        release.set()
        assert scheduler.wait_idle(timeout=5)
        state = scheduler.snapshot()
        assert observed == [20, 22] and max(peaks) == 1
        assert state.completed_runs == 2 and state.last_result.shared_sources == 4
        assert state.last_result.created_chapter
        assert "new" in state.last_result.created_chapter.source_memory_ids
    finally:
        release.set()
        scheduler.close(wait=True)


def test_scheduler_close_drops_pending_but_finishes_real_sqlite_write(tmp_path, monkeypatch):
    import sqlite3
    from threading import Event, current_thread
    from guanghe_companion.memory_maintenance import MemoryMaintenanceScheduler
    store = memory(tmp_path)
    store.save_memories([event(str(i)) for i in range(3)])
    inside_write, release = Event(), Event()
    original = sqlite3.connect

    def traced(*args, **kwargs):
        connection = original(*args, **kwargs)
        def trace(sql):
            if (current_thread().name.startswith("emoti-memory-maintenance")
                    and sql.startswith("INSERT INTO memory_state(id,payload)")):
                inside_write.set()
                assert release.wait(5)
        connection.set_trace_callback(trace)
        return connection

    monkeypatch.setattr(sqlite3, "connect", traced)
    scheduler = MemoryMaintenanceScheduler(store)
    try:
        scheduler.request(now=20, budget=MaintenanceBudget(admission_ms=1000))
        assert inside_write.wait(5)
        assert scheduler.request(now=21)
        scheduler.close(wait=False)
        assert not scheduler.request(now=22)
        assert scheduler.snapshot().closed and not scheduler.snapshot().pending
        release.set()
        assert scheduler.wait_idle(timeout=5)
        state = scheduler.snapshot()
        assert state.completed_runs == 1 and state.last_result.created_chapter
        assert len(store.load_chapters()) == 1
    finally:
        release.set()
        scheduler.close(wait=True)


def test_scheduler_exposes_storage_failure_and_becomes_idle(tmp_path):
    from guanghe_companion.memory_maintenance import MemoryMaintenanceScheduler
    store = memory(tmp_path)
    store.save_memories([event(str(i)) for i in range(3)])
    store.state_path.write_bytes(b"corrupt authoritative SQLite")
    scheduler = MemoryMaintenanceScheduler(store)
    try:
        assert scheduler.request(now=20)
        assert scheduler.wait_idle(timeout=5)
        state = scheduler.snapshot()
        assert state.completed_runs == 1 and not state.running
        assert state.last_result is None and "MemoryStorageError" in state.last_error
    finally:
        scheduler.close(wait=True)
