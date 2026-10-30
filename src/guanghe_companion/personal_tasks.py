"""A durable journal for user-approved work delegated to an external authority.

This module neither executes commands nor polls an executor. A trusted host calls
``approve`` after an authenticated user's action, and an adapter delivers claimed
commands. Claims commit *before* delivery. A lost response therefore needs an
authority lookup by command_id, never an automatic second execution.

The external executor still owns scheduling, permissions and actual task state.
Its result references are evidence pointers, not independent proof of success.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import uuid4


_TERMINAL = frozenset({"succeeded", "failed", "cancelled"})
_EXTERNAL_STATES = frozenset({"running", "blocked", *_TERMINAL})


class TaskConflict(ValueError):
    """A reused identity or scope conflicts with the existing durable record."""


class TaskTransitionError(ValueError):
    """The proposed state change is not supported by the current receipt."""


def _text(value: str, name: str, limit: int, *, optional: bool = False) -> str:
    if not isinstance(value, str) or len(value) > limit or (not optional and not value.strip()):
        raise ValueError(f"{name} must be {'optional ' if optional else ''}text of at most {limit} characters")
    return value


def _time(value: float, name: str = "now") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative timestamp")
    return value


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    task_id: str
    owner_id: str
    character_id: str
    proposal_key: str
    authority: str
    title: str
    instruction: str
    created_at: float
    updated_at: float
    state: str = "proposed"
    approved_at: float | None = None
    command_id: str | None = None
    dispatch_claimed_at: float | None = None
    external_task_id: str | None = None
    last_sequence: int = 0
    last_observed_at: float | None = None
    last_received_at: float | None = None
    last_external_status: str | None = None
    checkpoint: str = ""
    evidence_refs: tuple[str, ...] = ()
    cancel_requested_at: float | None = None
    cancel_command_id: str | None = None
    cancel_claimed_at: float | None = None


@dataclass(frozen=True, slots=True)
class TaskCommand:
    """Persisted claim to hand to a trusted adapter, not an executable shell string."""
    command_id: str
    kind: str
    task_id: str
    owner_id: str
    character_id: str
    authority: str
    instruction: str
    external_task_id: str | None


@dataclass(frozen=True, slots=True)
class TaskEvent:
    task_id: str
    owner_id: str
    character_id: str
    authority: str
    command_id: str
    external_task_id: str
    event_id: str
    sequence: int
    status: str
    checkpoint: str
    observed_at: float
    evidence_refs: tuple[str, ...] = ()


class PersonalTaskStore:
    """Scoped local mirror and outbox; no task text is sent to companion memory.

    Do not expose these methods as an unauthenticated API. ``owner_id`` and
    ``character_id`` are host-bound identities, not values to trust from a phone
    request body. The host must also bind each adapter to its authority.
    """

    def __init__(self, path: Path | str, *, owner_id: str, character_id: str):
        self.path = Path(path)
        self.owner_id = _text(owner_id, "owner_id", 128)
        self.character_id = _text(character_id, "character_id", 128)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise TaskConflict("Unsupported task journal version; original database was not changed")
            if version == 0:
                existing = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
                if existing:
                    raise TaskConflict("Unrecognized database; refusing to overwrite existing tables")
                conn.execute("""CREATE TABLE tasks (
                    task_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, character_id TEXT NOT NULL,
                    proposal_key TEXT NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(owner_id, character_id, proposal_key))""")
                conn.execute("""CREATE TABLE task_events (
                    task_id TEXT NOT NULL REFERENCES tasks(task_id), event_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(task_id, event_id))""")
                conn.execute("PRAGMA user_version=1")
            else:
                # An initialized but damaged journal must not silently turn into
                # an empty outbox, which could make a replay execute twice.
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if not {"tasks", "task_events"}.issubset(tables):
                    raise TaskConflict("Initialized task journal is incomplete")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _load(self, conn: sqlite3.Connection, task_id: str) -> TaskSnapshot:
        row = conn.execute(
            "SELECT payload FROM tasks WHERE task_id=? AND owner_id=? AND character_id=?",
            (task_id, self.owner_id, self.character_id),
        ).fetchone()
        if row is None:
            raise KeyError(task_id)
        data = json.loads(row[0])
        data["evidence_refs"] = tuple(data["evidence_refs"])
        result = TaskSnapshot(**data)
        if (result.task_id, result.owner_id, result.character_id) != (task_id, self.owner_id, self.character_id):
            raise TaskConflict("Task payload identity disagrees with its stored namespace")
        return result

    @staticmethod
    def _save(conn: sqlite3.Connection, task: TaskSnapshot) -> TaskSnapshot:
        conn.execute("UPDATE tasks SET payload=? WHERE task_id=?", (_json(asdict(task)), task.task_id))
        return task

    def get(self, task_id: str) -> TaskSnapshot:
        with self._transaction() as conn:
            return self._load(conn, task_id)

    def propose(self, *, proposal_key: str, authority: str, title: str, instruction: str, now: float) -> TaskSnapshot:
        """Record a bounded suggestion. Replaying one key cannot alter its action."""
        _time(now)
        for name, value, limit in (("proposal_key", proposal_key, 128), ("authority", authority, 128),
                                   ("title", title, 200), ("instruction", instruction, 8000)):
            _text(value, name, limit)
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT task_id FROM tasks WHERE owner_id=? AND character_id=? AND proposal_key=?",
                (self.owner_id, self.character_id, proposal_key),
            ).fetchone()
            if row:
                current = self._load(conn, row[0])
                if (current.authority, current.title, current.instruction) != (authority, title, instruction):
                    raise TaskConflict("The proposal key already identifies a different suggestion")
                return current
            task = TaskSnapshot(
                task_id=str(uuid4()), owner_id=self.owner_id, character_id=self.character_id,
                proposal_key=proposal_key, authority=authority, title=title,
                instruction=instruction, created_at=now, updated_at=now,
            )
            conn.execute("INSERT INTO tasks VALUES(?,?,?,?,?)",
                         (task.task_id, self.owner_id, self.character_id, proposal_key, _json(asdict(task))))
            return task

    def approve(self, task_id: str, *, now: float) -> TaskSnapshot:
        """Trusted user-action entry point; approval does not come from model text."""
        _time(now)
        with self._transaction() as conn:
            task = self._load(conn, task_id)
            if task.approved_at is not None:
                return task
            if task.state != "proposed":
                raise TaskTransitionError("Only a pending suggestion can be approved")
            return self._save(conn, replace(task, state="queued", approved_at=now, updated_at=now))

    @staticmethod
    def _command(task: TaskSnapshot, *, cancel: bool = False) -> TaskCommand:
        command_id = task.cancel_command_id if cancel else task.command_id
        assert command_id is not None
        return TaskCommand(
            command_id, "cancel" if cancel else "start", task.task_id,
            task.owner_id, task.character_id, task.authority,
            "" if cancel else task.instruction, task.external_task_id,
        )

    def claim_dispatch(self, task_id: str, *, now: float) -> TaskCommand | None:
        """Claim once, atomically. A network timeout cannot make it claimable again."""
        _time(now)
        with self._transaction() as conn:
            task = self._load(conn, task_id)
            if task.state != "queued":
                return None
            task = self._save(conn, replace(task, state="dispatching", command_id=str(uuid4()),
                                            dispatch_claimed_at=now, updated_at=now))
            return self._command(task)

    def mark_delivery_unknown(self, task_id: str, *, command_id: str, now: float) -> TaskSnapshot:
        """Keep uncertainty explicit after a timeout; do not create a retry."""
        _time(now)
        with self._transaction() as conn:
            task = self._load(conn, task_id)
            if not task.command_id or command_id != task.command_id:
                raise TaskConflict("Delivery outcome belongs to another command")
            if task.state not in {"dispatching", "delivery_unknown", "cancel_requested"} or task.external_task_id:
                raise TaskTransitionError("The task already has a delivery receipt")
            state = "cancel_requested" if task.cancel_requested_at is not None else "delivery_unknown"
            return self._save(conn, replace(task, state=state, updated_at=now))

    def record_dispatch_receipt(self, task_id: str, *, command_id: str, authority: str,
                                external_task_id: str, now: float) -> TaskSnapshot:
        """Record external acceptance; this is not proof that work has started."""
        _time(now)
        _text(external_task_id, "external_task_id", 256)
        with self._transaction() as conn:
            task = self._load(conn, task_id)
            if (authority, command_id) != (task.authority, task.command_id) or task.command_id is None:
                raise TaskConflict("Receipt authority or command does not match")
            if task.external_task_id:
                if task.external_task_id != external_task_id:
                    raise TaskConflict("Command was associated with a different external task")
                return task
            if task.state not in {"dispatching", "delivery_unknown", "cancel_requested"}:
                raise TaskTransitionError("No outstanding dispatch matches this receipt")
            state = "cancel_requested" if task.cancel_requested_at is not None else "accepted"
            return self._save(conn, replace(task, state=state, external_task_id=external_task_id,
                                            last_received_at=now, updated_at=now))

    def request_cancel(self, task_id: str, *, now: float) -> TaskSnapshot:
        """Cancel locally before dispatch; after dispatch wait for the authority."""
        _time(now)
        with self._transaction() as conn:
            task = self._load(conn, task_id)
            if task.state in _TERMINAL or task.cancel_requested_at is not None:
                return task
            if task.command_id is None:
                return self._save(conn, replace(task, state="cancelled", cancel_requested_at=now, updated_at=now))
            return self._save(conn, replace(task, state="cancel_requested", cancel_requested_at=now,
                                            cancel_command_id=str(uuid4()), updated_at=now))

    def claim_cancel(self, task_id: str, *, now: float) -> TaskCommand | None:
        """Only call if the adapter supports cancellation; a claim is not an ack."""
        _time(now)
        with self._transaction() as conn:
            task = self._load(conn, task_id)
            if task.state != "cancel_requested" or not task.external_task_id or task.cancel_claimed_at is not None:
                return None
            task = self._save(conn, replace(task, cancel_claimed_at=now, updated_at=now))
            return self._command(task, cancel=True)

    def apply_event(self, event: TaskEvent, *, now: float) -> bool:
        """Accept a normalized event only from a host-bound, authenticated adapter.

        False means exact duplicate or stale sequence. A contradictory reused ID
        or terminal result raises rather than silently replacing the truth.
        """
        _time(now)
        _time(event.observed_at, "observed_at")
        if event.observed_at > now + 60:
            raise ValueError("Observation clock is more than 60 seconds in the future")
        for name in ("task_id", "owner_id", "character_id", "authority", "command_id", "event_id"):
            _text(getattr(event, name), name, 128)
        _text(event.external_task_id, "external_task_id", 256)
        _text(event.checkpoint, "checkpoint", 2000, optional=True)
        if isinstance(event.sequence, bool) or not isinstance(event.sequence, int) or event.sequence < 1:
            raise ValueError("sequence must be a positive integer")
        if event.status not in _EXTERNAL_STATES:
            raise ValueError("Unsupported external state")
        if not isinstance(event.evidence_refs, (tuple, list)) or len(event.evidence_refs) > 16:
            raise ValueError("At most 16 result references are supported")
        for ref in event.evidence_refs:
            _text(ref, "evidence reference", 1000)
        if event.status == "succeeded" and not event.evidence_refs:
            raise ValueError("Success requires at least one result reference")
        payload = _json(asdict(event))
        fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with self._transaction() as conn:
            task = self._load(conn, event.task_id)
            if (event.owner_id, event.character_id, event.authority, event.command_id) != (
                task.owner_id, task.character_id, task.authority, task.command_id,
            ):
                raise TaskConflict("Event scope, authority or attempt does not match")
            if task.external_task_id is None:
                raise TaskTransitionError("A dispatch receipt is required before accepting task progress")
            if event.external_task_id != task.external_task_id:
                raise TaskConflict("Event belongs to another external task")
            previous = conn.execute("SELECT fingerprint FROM task_events WHERE task_id=? AND event_id=?",
                                    (task.task_id, event.event_id)).fetchone()
            if previous:
                if previous[0] != fingerprint:
                    raise TaskConflict("The event ID was replayed with different content")
                return False
            if event.sequence <= task.last_sequence:
                return False
            if task.state in _TERMINAL:
                raise TaskTransitionError("A terminal result needs explicit reconciliation, not another state update")
            state = event.status
            if task.cancel_requested_at is not None and state not in _TERMINAL:
                state = "cancel_requested"
            updated = replace(
                task, state=state, updated_at=now, last_sequence=event.sequence,
                last_observed_at=event.observed_at, last_received_at=now,
                last_external_status=event.status, checkpoint=event.checkpoint,
                evidence_refs=tuple(event.evidence_refs),
            )
            conn.execute("INSERT INTO task_events VALUES(?,?,?,?)",
                         (task.task_id, event.event_id, fingerprint, payload))
            self._save(conn, updated)
            return True

    def events(self, task_id: str) -> tuple[dict[str, object], ...]:
        """Accepted executor observations, in arrival order; no delivery claim is inferred."""
        with self._transaction() as conn:
            self._load(conn, task_id)
            return tuple(json.loads(row[0]) for row in conn.execute(
                "SELECT payload FROM task_events WHERE task_id=? ORDER BY rowid", (task_id,)))

    @staticmethod
    def _report(task: TaskSnapshot, *, now: float, stale_after: float) -> dict[str, object]:
        last_external = task.last_observed_at if task.last_observed_at is not None else task.last_received_at
        if task.state in _TERMINAL:
            freshness = "terminal"
        elif task.command_id is None:
            freshness = "not_dispatched"
        elif last_external is None:
            freshness = "awaiting_receipt"
        else:
            freshness = "stale" if now - last_external > stale_after else "current"
        cancellation_outcome = None
        if task.cancel_requested_at is not None:
            if task.state == "succeeded":
                cancellation_outcome = "completion_won_race"
            elif task.state == "cancelled":
                cancellation_outcome = "cancelled"
            elif task.state == "failed":
                cancellation_outcome = "executor_failed"
            else:
                cancellation_outcome = "pending_confirmation"
        return {
            "task_id": task.task_id, "title": task.title, "state": task.state,
            "authority": task.authority, "external_task_id": task.external_task_id,
            "command_id": task.command_id, "last_external_status": task.last_external_status,
            "checkpoint": task.checkpoint, "evidence_refs": list(task.evidence_refs),
            "last_observed_at": task.last_observed_at, "last_received_at": task.last_received_at,
            "freshness": freshness, "needs_reconciliation": freshness in {"stale", "awaiting_receipt"},
            "completion_claim": "reported_by_authority" if task.state == "succeeded" else None,
            "cancel_requested_at": task.cancel_requested_at, "cancellation_outcome": cancellation_outcome,
        }

    def task_report(self, task_id: str, *, now: float, stale_after: float = 300) -> dict[str, object]:
        """A grounded status view; a stale running state is not a live-running claim."""
        _time(now)
        _time(stale_after, "stale_after")
        return self._report(self.get(task_id), now=now, stale_after=stale_after)

    def due_for_check(self, *, now: float, stale_after: float = 300) -> tuple[TaskSnapshot, ...]:
        """Read-only work list for a future poll runner; it performs no network I/O."""
        _time(now)
        _time(stale_after, "stale_after")
        with self._transaction() as conn:
            rows = conn.execute("SELECT task_id FROM tasks WHERE owner_id=? AND character_id=? ORDER BY rowid",
                                (self.owner_id, self.character_id)).fetchall()
            tasks = tuple(self._load(conn, row[0]) for row in rows)
            return tuple(task for task in tasks if self._report(task, now=now, stale_after=stale_after)["needs_reconciliation"])
