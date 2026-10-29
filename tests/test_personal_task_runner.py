import sqlite3
from threading import Event

import pytest

from guanghe_companion.personal_tasks import PersonalTaskStore
from guanghe_companion.personal_task_runner import PersonalTaskRunner


@pytest.fixture
def setup(tmp_path):
    store = PersonalTaskStore(tmp_path / "tasks.db", owner_id="owner", character_id="xingxi")
    task = store.propose(proposal_key="one", authority="relay", title="检查测试",
                         instruction="检查已授权测试结果", now=100)
    return store, task, tmp_path / "runner.db"


def test_unavailable_relay_does_not_claim_dispatch(setup):
    store, task, path = setup
    store.approve(task.task_id, now=101)
    runner = PersonalTaskRunner(store, path)
    runner.watch(task.task_id, now=102, deadline=500, max_checks=5)
    runner.step(now=102)
    assert store.get(task.task_id).command_id is None
    assert runner.status(task.task_id)["blocked_reason"] == "authority_unavailable"
    assert runner.status(task.task_id)["checks"] == 0


def test_unknown_delivery_survives_restart_without_retry(setup):
    store, task, path = setup
    store.approve(task.task_id, now=101)
    command = store.claim_dispatch(task.task_id, now=102)
    runner = PersonalTaskRunner(store, path)
    runner.watch(task.task_id, now=103, deadline=500, max_checks=5)
    runner.step(now=103)
    restored = PersonalTaskRunner(store, path)
    restored.step(now=200)
    assert store.get(task.task_id).command_id == command.command_id
    assert store.claim_dispatch(task.task_id, now=201) is None
    assert restored.status(task.task_id)["blocked_reason"] == "authority_unavailable"


def test_deadline_stops_supervision_without_claiming_remote_cancellation(setup):
    store, task, path = setup
    runner = PersonalTaskRunner(store, path)
    runner.watch(task.task_id, now=101, deadline=105, max_checks=5)
    runner.step(now=106)
    assert runner.status(task.task_id)["blocked_reason"] == "deadline_exceeded"
    assert store.get(task.task_id).state == "proposed"


def test_budget_cannot_be_silently_reset_by_rewatch(setup):
    store, task, path = setup
    runner = PersonalTaskRunner(store, path)
    runner.watch(task.task_id, now=101, deadline=500, max_checks=5)
    runner.watch(task.task_id, now=102, deadline=500, max_checks=5)
    with pytest.raises(ValueError, match="already"):
        runner.watch(task.task_id, now=103, deadline=1000, max_checks=100)


def test_journal_is_bound_to_owner_and_character(setup):
    store, task, path = setup
    PersonalTaskRunner(store, path)
    another = PersonalTaskStore(store.path, owner_id="another", character_id="xingxi")
    with pytest.raises(ValueError, match="namespace"):
        PersonalTaskRunner(another, path)


def test_unknown_runner_schema_is_preserved(setup):
    store, task, path = setup
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version=99")
    with pytest.raises(ValueError, match="schema"):
        PersonalTaskRunner(store, path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 99


def test_cancelled_task_finishes_supervision(setup):
    store, task, path = setup
    runner = PersonalTaskRunner(store, path)
    runner.watch(task.task_id, now=101, deadline=500, max_checks=5)
    store.request_cancel(task.task_id, now=102)
    runner.step(now=103)
    assert runner.status(task.task_id)["finished"] == 1


def test_stopped_loop_performs_no_work(setup):
    store, task, path = setup
    runner = PersonalTaskRunner(store, path)
    stopped = Event()
    stopped.set()
    runner.run(stopped)


def test_stage_report_is_available_after_restart(setup):
    store, task, path = setup
    runner = PersonalTaskRunner(store, path)
    runner.watch(task.task_id, now=101, deadline=500, max_checks=5)
    runner.step(now=102)
    restored = PersonalTaskRunner(store, path)
    assert restored.reports()[0]["supervision"]["blocked_reason"] == "awaiting_approval"


def test_expired_deadline_is_checked_before_next_poll(setup):
    store, task, path = setup
    runner = PersonalTaskRunner(store, path)
    runner.watch(task.task_id, now=101, deadline=105, max_checks=5)
    runner.step(now=102)
    runner.step(now=106)
    assert runner.status(task.task_id)["finished"] == 1
