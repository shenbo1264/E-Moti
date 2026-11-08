"""Budgeted maintenance over the existing authority and reflection implementation.

The time budget admits work; it cannot interrupt an already admitted SQLite
transaction. Callers should schedule this service outside the UI thread. A run
examines a bounded recent window, not an implicit claim to have swept all saves.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from concurrent.futures import Future, ThreadPoolExecutor
import math
from threading import Condition
from time import perf_counter
from typing import Callable

from .emotional_memory import EmotionalMemoryStore, MemoryChapter, make_memory_id
from .emotional_memory_reflection import MemoryReflectionService, _chapter_summary, _chapter_title
from .memory_document import _strict_json_loads
from .memory_index import IndexedMemoryQuery, _ready
from .retrieval_evidence import grounded_shared_event
from .retrieval_fact_schema import read_fact_view


@dataclass(frozen=True, slots=True)
class MaintenanceBudget:
    max_sources: int = 128
    max_chapter_writes: int = 1
    admission_ms: float = 100.0


@dataclass(frozen=True, slots=True)
class MemoryFactConflict:
    subject: str
    predicate: str
    memory_ids: tuple[str, ...]
    values: tuple[str, ...]
    fact_object: str = ""
    reason: str = "potential_single_value_conflict"


@dataclass(frozen=True, slots=True)
class MaintenanceResult:
    checked_sources: int = 0
    shared_sources: int = 0
    duplicate_fact_groups: tuple[tuple[str, ...], ...] = ()
    conflicts: tuple[MemoryFactConflict, ...] = ()
    created_chapter: MemoryChapter | None = None
    existing_chapter: MemoryChapter | None = None
    skipped: tuple[str, ...] = ()
    elapsed_ms: float = 0.0
    write_started: bool = False
    budget_overrun: bool = False
    partial_scan: bool = False
    total_candidates: int = 0
    context_epoch: int | None = None
    index_revision: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "checked_sources": self.checked_sources, "shared_sources": self.shared_sources,
            "duplicate_fact_groups": [list(group) for group in self.duplicate_fact_groups],
            "conflicts": [{"subject": row.subject, "predicate": row.predicate,
                "memory_ids": list(row.memory_ids), "values": list(row.values),
                "fact_object": row.fact_object, "reason": row.reason} for row in self.conflicts],
            "created_chapter": self.created_chapter.to_dict() if self.created_chapter else None,
            "existing_chapter": self.existing_chapter.to_dict() if self.existing_chapter else None,
            "skipped": list(self.skipped), "elapsed_ms": self.elapsed_ms,
            "write_started": self.write_started, "budget_overrun": self.budget_overrun,
            "partial_scan": self.partial_scan, "total_candidates": self.total_candidates,
            "context_epoch": self.context_epoch, "index_revision": self.index_revision,
        }


@dataclass(frozen=True, slots=True)
class MaintenanceSchedulerState:
    running: bool
    pending: bool
    closed: bool
    completed_runs: int
    last_result: MaintenanceResult | None
    last_error: str

    def to_dict(self) -> dict[str, object]:
        return {"running": self.running, "pending": self.pending, "closed": self.closed,
            "completed_runs": self.completed_runs,
            "last_result": self.last_result.to_dict() if self.last_result else None,
            "last_error": self.last_error}


class MemoryMaintenanceScheduler:
    """One worker, one coalesced pending request, observable immutable results.

    No Qt objects or UI callbacks are invoked on the worker. Consumers poll
    snapshot() or bridge the result using their own main-thread signal. Closing
    drops pending work; an already running SQLite transaction finishes normally.
    """

    def __init__(self, store: EmotionalMemoryStore, *, reflection=None, runner=None):
        self.store = store
        self.reflection = reflection or MemoryReflectionService()
        self._runner = runner or run_memory_maintenance
        self._condition = Condition()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="emoti-memory-maintenance")
        self._future: Future | None = None
        self._pending: tuple[int, MaintenanceBudget] | None = None
        self._running = False
        self._closed = False
        self._completed_runs = 0
        self._last_result: MaintenanceResult | None = None
        self._last_error = ""

    def request(self, *, now: int, budget: MaintenanceBudget | None = None) -> bool:
        with self._condition:
            if self._closed:
                return False
            self._pending = (now, budget or MaintenanceBudget())
            if not self._running:
                self._running = True
                try:
                    self._future = self._executor.submit(self._drain)
                except RuntimeError as exc:
                    self._running, self._closed, self._pending = False, True, None
                    self._last_error = f"{type(exc).__name__}: {exc}"
                    self._condition.notify_all()
                    return False
            return True

    def _drain(self) -> None:
        while True:
            with self._condition:
                if self._closed or self._pending is None:
                    self._running = False
                    self._condition.notify_all()
                    return
                now, budget = self._pending
                self._pending = None
            result, error = None, ""
            try:
                result = self._runner(self.store, now=now, reflection=self.reflection, budget=budget)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            with self._condition:
                self._completed_runs += 1
                self._last_result, self._last_error = result, error
                self._condition.notify_all()

    def snapshot(self) -> MaintenanceSchedulerState:
        with self._condition:
            return MaintenanceSchedulerState(self._running, self._pending is not None,
                self._closed, self._completed_runs, self._last_result, self._last_error)

    def wait_idle(self, *, timeout: float | None = 5.0) -> bool:
        with self._condition:
            return self._condition.wait_for(lambda: not self._running and self._pending is None,
                                            timeout=timeout)

    def close(self, *, wait: bool = False) -> None:
        with self._condition:
            self._closed = True
            self._pending = None
        # Never hold the condition while waiting for the worker to finish.
        self._executor.shutdown(wait=wait, cancel_futures=True)
        with self._condition:
            if self._future is None or self._future.cancelled():
                self._running = False
            self._condition.notify_all()


_SINGLE_VALUE = frozenset({"name", "residence", "occupation", "birthday", "phone", "serial_number",
    "device_model", "device_brand", "姓名", "称呼", "居住地", "职业", "生日", "手机号"})
_UNFINISHED = frozenset({"planned", "proposed", "pending", "queued", "running", "in_progress",
    "awaiting_confirmation", "cancelled", "canceled"})


def _is_unfinished(entry) -> bool:
    return (entry.metadata.get("planned") is True or any(
        entry.metadata.get(key) in _UNFINISHED
        for key in ("event_status", "plan_status", "task_status", "status")
        if isinstance(entry.metadata.get(key), str)))


def _fact_diagnostics(entries):
    groups = {}
    for entry in entries:
        if _is_unfinished(entry) or entry.metadata.get("fact_status") == "historical":
            continue
        view = read_fact_view(entry)
        meta = view.metadata
        value = meta.get("fact_value")
        predicate = meta.get("fact_predicate") or meta.get("fact_slot")
        if not isinstance(value, str) or not value.strip() or not isinstance(predicate, str):
            continue
        subject = str(meta.get("fact_subject") or "user:self")
        slot = str(meta.get("fact_slot") or predicate)
        obj = str(meta.get("fact_object") or "")
        groups.setdefault((subject, predicate, slot, obj), {}).setdefault(value.strip(), []).append(entry.memory_id)
    duplicates, conflicts = [], []
    for (subject, predicate, slot, obj), values in sorted(groups.items()):
        duplicates.extend(tuple(sorted(ids)) for ids in values.values() if len(ids) > 1)
        if (predicate in _SINGLE_VALUE or slot in _SINGLE_VALUE) and len(values) > 1:
            conflicts.append(MemoryFactConflict(subject, predicate,
                tuple(sorted(key for keys in values.values() for key in keys)), tuple(sorted(values)), obj))
    return tuple(sorted(duplicates)), tuple(conflicts)


def _matching_chapter(store, chapter, *, now):
    """Read at most 128 small chapter projections, no extra memory bodies."""
    sources = set(chapter.source_memory_ids)
    first = chapter.source_memory_ids[0]
    with _ready(store, now=now) as (connection, _):
        rows = connection.execute("""SELECT c.payload FROM memory_index_chapters c
            JOIN memory_index_chapter_sources s ON s.chapter_id=c.chapter_id
            WHERE s.memory_id=? ORDER BY c.created_at DESC,c.chapter_id LIMIT 128""", (first,))
        for row in rows:
            existing = MemoryChapter.from_dict(_strict_json_loads(row[0]))
            if (existing is not None and set(existing.source_memory_ids) == sources
                    and existing.source_fingerprints == chapter.source_fingerprints):
                return existing
    return None


def run_memory_maintenance(store: EmotionalMemoryStore, *, now: int,
                           reflection: MemoryReflectionService | None = None,
                           budget: MaintenanceBudget | None = None,
                           clock: Callable[[], float] = perf_counter) -> MaintenanceResult:
    budget = budget or MaintenanceBudget()
    reflection = reflection or MemoryReflectionService()
    started = clock()
    cap = max(0, min(128, int(budget.max_sources)))
    admission = float(budget.admission_ms)
    if not math.isfinite(admission):
        admission = 0.0
    snapshot = None
    shared = []
    duplicate_groups, conflicts = (), ()
    skipped = []
    write_started = False

    def finish(reason="", *, created=None, existing=None):
        if reason:
            skipped.append(reason)
        elapsed = max(0.0, (clock() - started) * 1000)
        count = len(snapshot.entries) if snapshot is not None else 0
        total = snapshot.total_candidates if snapshot is not None else 0
        return MaintenanceResult(count, len(shared), duplicate_groups, conflicts,
            created, existing, tuple(dict.fromkeys(skipped)), elapsed, write_started,
            write_started and elapsed > admission, count < total, total,
            snapshot.context_epoch if snapshot is not None else None,
            snapshot.index_revision if snapshot is not None else None)

    def time_left():
        return (clock() - started) * 1000 < admission

    if admission <= 0:
        return finish("admission_budget")
    if cap == 0:
        return finish("source_budget")
    snapshot = store.read_indexed_snapshot(IndexedMemoryQuery(limit=cap), now=now,
        include_chapters=False, include_profile_sources=False)
    state = (snapshot.index_generation, snapshot.index_revision, snapshot.context_epoch)
    if not time_left():
        return finish("admission_budget")
    duplicate_groups, conflicts = _fact_diagnostics(snapshot.entries)
    used_origins = set()
    # A replayed event must not count as another day together. Conservative
    # source-disjoint selection also avoids counting overlapping event bundles
    # as independent repeated experiences; no authority rows are deleted.
    for entry in sorted(snapshot.entries, key=lambda row: (row.occurred_at, row.importance), reverse=True):
        if _is_unfinished(entry) or not grounded_shared_event(entry):
            continue
        if used_origins.intersection(entry.source_ids):
            skipped.append("overlapping_event_sources")
            continue
        shared.append(entry)
        used_origins.update(entry.source_ids)
    if not reflection.should_consolidate(shared):
        return finish("not_enough_significant_shared_events")
    if int(budget.max_chapter_writes) <= 0:
        return finish("writes_disabled")
    if not time_left():
        return finish("admission_budget")
    chapter = reflection.build_chapter(shared, character_id=store.character_id, now=now)
    if chapter is None:
        return finish("chapter_text_budget")
    by_id = {row.memory_id: row for row in shared}
    if (not chapter.source_memory_ids
            or len(set(chapter.source_memory_ids)) != len(chapter.source_memory_ids)
            or set(chapter.source_fingerprints) != set(chapter.source_memory_ids)
            or any(key not in by_id or chapter.source_fingerprints.get(key) != by_id[key].evidence_fingerprint()
                   for key in chapter.source_memory_ids)):
        return finish("unsupported_chapter_sources")
    represented = [by_id[key] for key in chapter.source_memory_ids]
    if chapter.summary != _chapter_summary(represented) or chapter.title != _chapter_title(represented):
        # A custom/future reflection writer may not make a truthful source list
        # a license to append an invented event. This release admits only the
        # existing deterministic, extractive chapter representation.
        return finish("unsupported_chapter_text")
    # Stable IDs make two racing, identical maintenance runs idempotent. The
    # existing store still verifies every source fingerprint inside its write.
    stable_id = make_memory_id(store.character_id, "maintenance-v1", *(
        key + ":" + chapter.source_fingerprints[key] for key in sorted(chapter.source_memory_ids)))
    chapter = replace(chapter, chapter_id=stable_id)
    existing = _matching_chapter(store, chapter, now=now)
    if store.current_index_state(now=now) != state:
        return finish("source_changed")
    if existing is not None:
        return finish("already_consolidated", existing=existing)
    if not time_left():
        return finish("admission_budget")
    write_started = True
    try:
        saved = store.upsert_chapter(chapter, expected_epoch=snapshot.context_epoch)
    except ValueError:
        # Corrections/forgets and raw legacy edits are rechecked by the store
        # inside the write transaction. Do not retry with a weaker source set.
        return finish("source_changed")
    return finish(created=saved)
