from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sqlite3
from threading import Event
import time
from typing import Iterator, Protocol

from .personal_tasks import PersonalTaskStore, TaskCommand, TaskConflict, TaskEvent, TaskSnapshot


@dataclass(frozen=True)
class ExecutorCapabilities:
    submit: bool = False
    lookup_command: bool = False
    events: bool = False
    cancel: bool = False


class TaskExecutor(Protocol):
    # 实现者必须限制网络调用时长，并只返回已经认证的权威结果。
    capabilities: ExecutorCapabilities

    def submit(self, command: TaskCommand) -> str: ...

    def lookup_command(self, command_id: str) -> str | None: ...

    def events(self, task: TaskSnapshot) -> tuple[TaskEvent, ...]: ...

    def cancel(self, command: TaskCommand) -> None: ...


class PersonalTaskRunner:
    def __init__(self, tasks: PersonalTaskStore, path: Path | str,
                 executors: Mapping[str, TaskExecutor] | None = None):
        self.tasks = tasks
        self.path = Path(path)
        if self.path.resolve() == tasks.path.resolve():
            raise ValueError("Runner schedule requires its own database")
        self.executors = dict(executors or {})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("Unsupported runner schema")
            if version == 0:
                if conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                    raise ValueError("Unrecognized runner schema")
                conn.execute("CREATE TABLE namespace(owner TEXT NOT NULL, character TEXT NOT NULL)")
                conn.execute("INSERT INTO namespace VALUES(?,?)", (tasks.owner_id, tasks.character_id))
                conn.execute("""CREATE TABLE schedules(
                    task_id TEXT PRIMARY KEY, deadline REAL NOT NULL, max_checks INTEGER NOT NULL,
                    checks INTEGER NOT NULL DEFAULT 0, next_check REAL NOT NULL,
                    failures INTEGER NOT NULL DEFAULT 0, blocked_reason TEXT,
                    finished INTEGER NOT NULL DEFAULT 0, report TEXT)""")
                conn.execute("PRAGMA user_version=1")
            namespace = conn.execute("SELECT owner,character FROM namespace").fetchall()
            if [tuple(row) for row in namespace] != [(tasks.owner_id, tasks.character_id)]:
                raise ValueError("Runner namespace does not match task store")
            conn.execute("SELECT task_id,deadline,max_checks,checks,next_check,failures,blocked_reason,finished,report FROM schedules LIMIT 0")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA synchronous=FULL")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def watch(self, task_id: str, *, now: float, deadline: float, max_checks: int) -> None:
        self.tasks.get(task_id)
        if (type(max_checks) is not int or max_checks < 1
                or not math.isfinite(now) or not math.isfinite(deadline) or now < 0 or deadline <= now):
            raise ValueError("A future deadline and positive check budget are required")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            previous = conn.execute("SELECT deadline,max_checks FROM schedules WHERE task_id=?", (task_id,)).fetchone()
            if previous:
                if tuple(previous) != (deadline, max_checks):
                    raise ValueError("Task already has a supervision budget; approval cannot silently expand it")
                return
            conn.execute("INSERT INTO schedules(task_id,deadline,max_checks,next_check) VALUES(?,?,?,?)",
                         (task_id, deadline, max_checks, now))

    def status(self, task_id: str) -> dict[str, object]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM schedules WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            result = dict(row)
            result.pop("report")
            return result

    def step(self, *, now: float) -> tuple[dict[str, object], ...]:
        if not math.isfinite(now) or now < 0:
            raise ValueError("Invalid runner time")
        reports = []
        with self._connect() as conn:
            # 保持一个调度事务，防止两个循环同时花费同一预算；任务发送权另由原日志保护。
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute("SELECT * FROM schedules WHERE finished=0 AND (next_check<=? OR deadline<=?) ORDER BY next_check", (now, now)).fetchall()
            for row in rows:
                task = self.tasks.get(row["task_id"])
                reason = None
                finished = task.state in {"succeeded", "failed", "cancelled"}
                failures = row["failures"]
                if finished:
                    pass
                elif now >= row["deadline"]:
                    reason, finished = "deadline_exceeded", True
                elif row["checks"] >= row["max_checks"]:
                    reason, finished = "check_budget_exhausted", True
                elif task.state == "proposed":
                    reason = "awaiting_approval"
                else:
                    adapter = self.executors.get(task.authority)
                    if adapter is None:
                        reason = "authority_unavailable"
                    else:
                        # 在任何 I/O 之前单独持久化预算；进程崩溃不能赠送一次检查。
                        conn.execute("UPDATE schedules SET checks=checks+1,next_check=? WHERE task_id=?", (now + 30, task.task_id))
                        conn.commit()
                        try:
                            reason = self._advance(adapter, task, now)
                            failures = 0
                        except (TimeoutError, ConnectionError, OSError):
                            current = self.tasks.get(task.task_id)
                            if current.command_id and not current.external_task_id:
                                self.tasks.mark_delivery_unknown(task.task_id, command_id=current.command_id, now=now)
                            reason = "transport_unavailable"
                            failures += 1
                        conn.execute("BEGIN IMMEDIATE")
                        if self.tasks.get(task.task_id).state in {"succeeded", "failed", "cancelled"}:
                            finished, reason = True, None
                delay = min(900, 30 * (2 ** min(failures, 5)))
                conn.execute("UPDATE schedules SET next_check=?,failures=?,blocked_reason=?,finished=? WHERE task_id=?",
                             (now + delay, failures, reason, int(finished), task.task_id))
                report = self.tasks.task_report(task.task_id, now=now)
                report["supervision"] = {"blocked_reason": reason, "finished": finished}
                # 新鲜度与内容变化产生阶段事实；通知仍由宿主现有安静时段和节流策略决定。
                fingerprint = json.dumps(report, sort_keys=True, ensure_ascii=False)
                if fingerprint != row["report"]:
                    reports.append(report)
                    conn.execute("UPDATE schedules SET report=? WHERE task_id=?", (fingerprint, task.task_id))
        return tuple(reports)

    def reports(self) -> tuple[dict[str, object], ...]:
        with self._connect() as conn:
            return tuple(json.loads(row[0]) for row in conn.execute(
                "SELECT report FROM schedules WHERE report IS NOT NULL ORDER BY rowid"))

    def _advance(self, adapter: TaskExecutor, task: TaskSnapshot, now: float) -> str | None:
        capabilities = adapter.capabilities
        if task.state == "queued":
            if not capabilities.submit:
                return "submit_unsupported"
            command = self.tasks.claim_dispatch(task.task_id, now=now)
            if command is not None:
                external_id = adapter.submit(command)
                self.tasks.record_dispatch_receipt(task.task_id, command_id=command.command_id,
                                                   authority=task.authority, external_task_id=external_id, now=now)
            return None
        if task.command_id and not task.external_task_id:
            if not capabilities.lookup_command:
                return "command_lookup_unsupported"
            external_id = adapter.lookup_command(task.command_id)
            if external_id is None:
                return "delivery_unresolved"
            self.tasks.record_dispatch_receipt(task.task_id, command_id=task.command_id,
                                               authority=task.authority, external_task_id=external_id, now=now)
            return None
        if task.state == "cancel_requested" and task.cancel_claimed_at is None:
            if capabilities.cancel:
                command = self.tasks.claim_cancel(task.task_id, now=now)
                if command is not None:
                    adapter.cancel(command)
                    return "cancellation_pending"
            elif not capabilities.events:
                return "cancel_unsupported"
        if not capabilities.events:
            return "status_unsupported"
        events = adapter.events(task)
        if any(event.task_id != task.task_id for event in events):
            raise TaskConflict("Executor returned events belonging to another supervised task")
        for event in events:
            self.tasks.apply_event(event, now=now)
        if task.state == "cancel_requested" and not capabilities.cancel:
            return "cancel_unsupported"
        return None

    def run(self, stop: Event, *, interval: float = 1.0) -> None:
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("Polling interval must be positive")
        while not stop.is_set():
            self.step(now=time.time())
            stop.wait(interval)
