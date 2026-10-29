"""Deterministic contracts for the local task journal; no actual executor is used."""
from dataclasses import replace
import sqlite3

import pytest

from guanghe_companion.personal_tasks import (
    PersonalTaskStore, TaskConflict, TaskEvent, TaskTransitionError,
)


@pytest.fixture
def store(tmp_path):
    return PersonalTaskStore(tmp_path / "tasks.sqlite3", owner_id="owner-a", character_id="char-a")


def propose(store, *, key="phone-1"):
    return store.propose(
        proposal_key=key, authority="demo-executor", title="检查项目测试",
        instruction="运行已授权项目的测试，并报告结果；不要提交代码。", now=100,
    )


def dispatch(store, *, key="phone-1"):
    task = propose(store, key=key)
    store.approve(task.task_id, now=101)
    command = store.claim_dispatch(task.task_id, now=102)
    assert command is not None
    return task, command


def accepted(store):
    task, command = dispatch(store)
    store.record_dispatch_receipt(
        task.task_id, command_id=command.command_id, authority="demo-executor",
        external_task_id="external-1", now=103,
    )
    return task, command


def event(task, command, **changes):
    data = dict(
        task_id=task.task_id, owner_id="owner-a", character_id="char-a",
        authority="demo-executor", command_id=command.command_id,
        external_task_id="external-1", event_id="event-1", sequence=1,
        status="running", checkpoint="执行者开始测试。", observed_at=104,
        evidence_refs=(),
    )
    data.update(changes)
    return TaskEvent(**data)


def test_proposal_requires_explicit_approval_before_dispatch(store):
    task = propose(store)
    assert task.state == "proposed"
    assert store.claim_dispatch(task.task_id, now=101) is None
    assert store.get(task.task_id).command_id is None
    approved = store.approve(task.task_id, now=102)
    assert approved.state == "queued"
    command = store.claim_dispatch(task.task_id, now=103)
    assert command.kind == "start"
    assert command.instruction == task.instruction
    assert command.authority == "demo-executor"


def test_proposal_key_and_approval_are_idempotent(store):
    task = propose(store)
    assert propose(store).task_id == task.task_id
    first = store.approve(task.task_id, now=101)
    assert store.approve(task.task_id, now=102) == first
    with pytest.raises(TaskConflict):
        store.propose(proposal_key="phone-1", authority="demo-executor", title="改任务",
                      instruction="执行另一件事情", now=103)


def test_unknown_delivery_survives_restart_and_is_not_reissued(store):
    task, command = dispatch(store)
    restored = PersonalTaskStore(store.path, owner_id="owner-a", character_id="char-a")
    assert restored.claim_dispatch(task.task_id, now=200) is None
    restored.mark_delivery_unknown(task.task_id, command_id=command.command_id, now=200)
    assert restored.get(task.task_id).state == "delivery_unknown"
    assert restored.claim_dispatch(task.task_id, now=201) is None
    assert restored.task_report(task.task_id, now=202)["needs_reconciliation"]
    restored.record_dispatch_receipt(
        task.task_id, command_id=command.command_id, authority="demo-executor",
        external_task_id="external-1", now=203,
    )
    assert restored.get(task.task_id).state == "accepted"


def test_two_handles_cannot_claim_same_task_twice(store):
    task = propose(store)
    store.approve(task.task_id, now=101)
    other = PersonalTaskStore(store.path, owner_id="owner-a", character_id="char-a")
    assert store.claim_dispatch(task.task_id, now=102) is not None
    assert other.claim_dispatch(task.task_id, now=102) is None


def test_dispatch_receipt_does_not_claim_execution_or_completion(store):
    task, _ = accepted(store)
    report = store.task_report(task.task_id, now=104)
    assert report["state"] == "accepted"
    assert report["last_received_at"] == 103
    assert report["completion_claim"] is None


def test_receipt_replay_is_idempotent_but_conflict_is_explicit(store):
    task, command = accepted(store)
    before = store.get(task.task_id)
    store.record_dispatch_receipt(task.task_id, command_id=command.command_id,
                                 authority="demo-executor", external_task_id="external-1", now=105)
    assert store.get(task.task_id) == before
    with pytest.raises(TaskConflict):
        store.record_dispatch_receipt(task.task_id, command_id=command.command_id,
                                     authority="demo-executor", external_task_id="other", now=106)


def test_progress_is_persisted_and_duplicate_does_not_refresh_freshness(store):
    task, command = accepted(store)
    update = event(task, command)
    assert store.apply_event(update, now=105)
    assert not store.apply_event(update, now=106)
    snapshot = store.get(task.task_id)
    assert snapshot.state == "running"
    assert snapshot.last_observed_at == 104
    assert snapshot.last_received_at == 105
    assert snapshot.checkpoint == "执行者开始测试。"
    assert len(store.events(task.task_id)) == 1


def test_out_of_order_events_cannot_regress_progress(store):
    task, command = accepted(store)
    assert store.apply_event(event(task, command, sequence=2, event_id="new", observed_at=105,
                                   checkpoint="第二阶段"), now=106)
    assert not store.apply_event(event(task, command, sequence=1, event_id="old"), now=107)
    assert store.get(task.task_id).checkpoint == "第二阶段"


def test_same_event_id_with_changed_payload_is_a_conflict(store):
    task, command = accepted(store)
    first = event(task, command)
    store.apply_event(first, now=105)
    with pytest.raises(TaskConflict):
        store.apply_event(replace(first, checkpoint="被替换的描述"), now=106)
    assert store.get(task.task_id).checkpoint == first.checkpoint


@pytest.mark.parametrize("field,value", [
    ("owner_id", "other-owner"), ("character_id", "other-character"),
    ("authority", "other-executor"), ("command_id", "old-attempt"),
    ("external_task_id", "other-task"),
])
def test_wrong_scope_or_attempt_cannot_update_task(store, field, value):
    task, command = accepted(store)
    with pytest.raises(TaskConflict):
        store.apply_event(event(task, command, **{field: value}), now=105)
    assert store.get(task.task_id).state == "accepted"


def test_success_requires_result_evidence_and_remains_executor_reported(store):
    task, command = accepted(store)
    with pytest.raises(ValueError):
        store.apply_event(event(task, command, status="succeeded"), now=105)
    assert store.get(task.task_id).state == "accepted"
    done = event(task, command, status="succeeded", evidence_refs=("artifact:test-report-1",),
                 checkpoint="执行者报告：测试完成，见产物。")
    assert store.apply_event(done, now=106)
    report = store.task_report(task.task_id, now=1000)
    assert report["completion_claim"] == "reported_by_authority"
    assert report["evidence_refs"] == ["artifact:test-report-1"]
    assert report["freshness"] == "terminal"


def test_local_cancel_prevents_approved_but_unsent_task_dispatch(store):
    task = propose(store)
    store.approve(task.task_id, now=101)
    assert store.request_cancel(task.task_id, now=102).state == "cancelled"
    assert store.claim_dispatch(task.task_id, now=103) is None
    assert store.claim_cancel(task.task_id, now=103) is None


def test_remote_cancel_waits_for_external_confirmation_and_is_not_resent(store):
    task, command = accepted(store)
    assert store.request_cancel(task.task_id, now=104).state == "cancel_requested"
    cancel = store.claim_cancel(task.task_id, now=105)
    assert cancel.kind == "cancel"
    assert cancel.external_task_id == "external-1"
    assert cancel.command_id != command.command_id
    restored = PersonalTaskStore(store.path, owner_id="owner-a", character_id="char-a")
    assert restored.claim_cancel(task.task_id, now=106) is None
    assert restored.get(task.task_id).state == "cancel_requested"
    assert restored.apply_event(event(task, command, status="cancelled", checkpoint="已停止"), now=107)
    assert restored.get(task.task_id).state == "cancelled"


def test_cancelling_unknown_dispatch_waits_for_receipt_before_cancel_command(store):
    task, command = dispatch(store)
    store.request_cancel(task.task_id, now=103)
    assert store.claim_cancel(task.task_id, now=104) is None
    store.record_dispatch_receipt(task.task_id, command_id=command.command_id,
                                 authority="demo-executor", external_task_id="external-1", now=105)
    assert store.get(task.task_id).state == "cancel_requested"
    assert store.claim_cancel(task.task_id, now=106) is not None


def test_running_event_does_not_erase_user_cancellation_request(store):
    task, command = accepted(store)
    store.request_cancel(task.task_id, now=104)
    assert store.apply_event(event(task, command, observed_at=105), now=106)
    assert store.get(task.task_id).state == "cancel_requested"


def test_success_before_cancel_takes_effect_keeps_true_result_and_cancel_intent(store):
    task, command = accepted(store)
    store.request_cancel(task.task_id, now=104)
    store.apply_event(event(task, command, status="succeeded", observed_at=105,
                           evidence_refs=("artifact:result",)), now=106)
    report = store.task_report(task.task_id, now=107)
    assert report["state"] == "succeeded"
    assert report["cancel_requested_at"] == 104
    assert report["cancellation_outcome"] == "completion_won_race"


def test_terminal_conflicts_are_not_silently_overwritten(store):
    task, command = accepted(store)
    store.apply_event(event(task, command, status="cancelled"), now=105)
    with pytest.raises(TaskTransitionError):
        store.apply_event(event(task, command, event_id="late", sequence=2,
                               status="succeeded", evidence_refs=("artifact:late",)), now=106)
    assert store.get(task.task_id).state == "cancelled"


def test_stale_report_and_due_checks_use_external_time_not_local_actions(store):
    task, command = accepted(store)
    store.apply_event(event(task, command), now=105)
    store.request_cancel(task.task_id, now=500)
    report = store.task_report(task.task_id, now=501, stale_after=60)
    assert report["freshness"] == "stale"
    assert report["last_observed_at"] == 104
    assert report["needs_reconciliation"]
    assert [item.task_id for item in store.due_for_check(now=501, stale_after=60)] == [task.task_id]


def test_different_owners_and_characters_are_isolated_in_shared_file(store):
    task = propose(store)
    for owner, character in [("other", "char-a"), ("owner-a", "other")]:
        other = PersonalTaskStore(store.path, owner_id=owner, character_id=character)
        with pytest.raises(KeyError):
            other.get(task.task_id)
        assert other.due_for_check(now=500) == ()
        assert propose(other).task_id != task.task_id


def test_events_cannot_arrive_before_dispatch_acknowledgement(store):
    task, command = dispatch(store)
    with pytest.raises(TaskTransitionError):
        store.apply_event(event(task, command), now=105)


def test_invalid_event_does_not_partially_commit_audit_or_state(store):
    task, command = accepted(store)
    invalid = event(task, command, sequence=True)
    with pytest.raises(ValueError):
        store.apply_event(invalid, now=105)
    assert store.events(task.task_id) == ()
    assert store.get(task.task_id).last_sequence == 0


def test_unknown_database_version_is_rejected_without_changing_it(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version=99")
    with pytest.raises(TaskConflict):
        PersonalTaskStore(path, owner_id="owner-a", character_id="char-a")
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 99


def test_task_journal_creates_no_companion_memory_or_persona_files(store):
    task, command = accepted(store)
    store.apply_event(event(task, command, status="succeeded", evidence_refs=("artifact:1",)), now=105)
    assert {path.name for path in store.path.parent.iterdir()} == {"tasks.sqlite3"}
