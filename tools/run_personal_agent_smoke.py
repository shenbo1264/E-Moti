#!/usr/bin/env python3
"""Run the real local task/observation cores with a simulated external authority.

No phone, Relay instance, model, shell command, network listener or device sensor
is used. All runtime data is created in a disposable directory. The optional
JSON report is the only retained output.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from guanghe_companion.device_context import DeviceContextBuffer, Observation, ObservationPolicy
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.personal_tasks import PersonalTaskStore, TaskEvent
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def run() -> dict[str, object]:
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool) -> None:
        checks.append({"name": name, "passed": bool(passed)})

    with TemporaryDirectory(prefix="emoti-personal-agent-smoke-") as directory:
        root = Path(directory)
        controller = PluginEnabledCompanionController(user_data_root=root / "companion", auto_load=False)
        try:
            owner = controller.story_runtime.memory.owner_id
            character = controller.state.character_id
            initial_context = controller.get_expression_context()
            persona_before = initial_context["persona"]["config_hash"]
            memory_before = controller.story_runtime.memory.store.load_memories()
            store_path = root / "work" / "tasks.sqlite3"
            tasks = PersonalTaskStore(store_path, owner_id=owner, character_id=character)
            suggestion = dict(proposal_key="phone-request-1", authority="simulated_authority",
                              title="检查项目的阶段成果", instruction="仅检查和汇报，不提交或发布。", now=100)
            task = tasks.propose(**suggestion)
            check("unapproved_suggestion_not_dispatched", tasks.claim_dispatch(task.task_id, now=101) is None)
            tasks.approve(task.task_id, now=102)
            command = tasks.claim_dispatch(task.task_id, now=103)
            assert command is not None
            check("duplicate_phone_request_same_task", tasks.propose(**suggestion).task_id == task.task_id)

            # Simulate a lost delivery response; do not invoke a real executor.
            tasks.mark_delivery_unknown(task.task_id, command_id=command.command_id, now=104)
            tasks = PersonalTaskStore(store_path, owner_id=owner, character_id=character)
            check("restart_does_not_redispatch_unknown_command", tasks.claim_dispatch(task.task_id, now=105) is None)
            check("lost_receipt_requires_reconciliation", tasks.task_report(task.task_id, now=105)["needs_reconciliation"])
            tasks.record_dispatch_receipt(task.task_id, command_id=command.command_id,
                authority="simulated_authority", external_task_id="fixture-task-1", now=106)
            check("receipt_means_accepted_not_completed", tasks.get(task.task_id).state == "accepted")
            progress = TaskEvent(task.task_id, owner, character, "simulated_authority", command.command_id,
                "fixture-task-1", "fixture-event-1", 1, "running", "模拟执行者报告：第一阶段已开始。", 107)
            tasks.apply_event(progress, now=108)
            check("duplicate_progress_not_applied", tasks.apply_event(progress, now=109) is False)
            stale_report = tasks.task_report(task.task_id, now=500, stale_after=60)
            check("disconnection_is_stale_not_false_success", stale_report["freshness"] == "stale"
                  and stale_report["completion_claim"] is None)
            tasks.request_cancel(task.task_id, now=501)
            check("cancel_request_is_not_stop_confirmation", tasks.get(task.task_id).state == "cancel_requested")
            tasks.apply_event(replace(progress, event_id="fixture-event-2", sequence=2, status="succeeded",
                checkpoint="模拟执行者报告：取消送达前已完成。", observed_at=502,
                evidence_refs=("fixture:simulated-result-not-a-real-test-report",)), now=503)
            final_report = tasks.task_report(task.task_id, now=504)
            check("completion_cancel_race_preserves_authority_result", final_report["cancellation_outcome"] == "completion_won_race")
            check("completion_is_not_independent_acceptance", final_report["completion_claim"] == "reported_by_authority")

            observations = DeviceContextBuffer(owner_id=owner, character_id=character,
                memory_epoch=controller.story_runtime.memory.store.context_epoch)
            check("observation_default_off", observations.context(now=100) == {})
            ticket = observations.grant("simulated_phone", ObservationPolicy(
                kinds=frozenset({"screen_summary"}), allowed_apps=frozenset({"example.browser"}), retention_seconds=60))
            observation = Observation("fixture-frame-1", "simulated_phone", owner, character,
                "screen_summary", "example.browser", 100, "模拟屏幕：木星观测文章", "fixture_summary",
                ticket.token, ticket.memory_epoch)
            observations.ingest(observation, now=100)
            view = observations.context(now=101)
            # Verify only the existing typed request/prompt serialization path.
            # Do not save a chat reply from this temporary observation view.
            expression_context = dict(initial_context)
            expression_context["plugin_context"] = {"device_observations": view}
            request = ExpressionRequest.from_snapshot(controller.get_typed_snapshot(), context=expression_context)
            prompt = controller.ai_expressor.build_prompt(request)
            check("typed_prompt_carries_bounded_observation", "模拟屏幕：木星观测文章" in prompt)
            check("observation_is_current_before_dispatch", observations.is_current(view, now=101))
            observations.revoke("simulated_phone")
            check("revoke_clears_observation_context", observations.context(now=102) == {})
            check("late_derived_result_rejected_by_guard", not observations.is_current(view, now=102))
            check("late_capture_with_old_ticket_rejected", not observations.ingest(
                replace(observation, event_id="fixture-late-frame"), now=102))
            check("work_and_observations_do_not_write_long_term_memory",
                  controller.story_runtime.memory.store.load_memories() == memory_before)
            check("persona_configuration_unchanged",
                  controller.get_expression_context()["persona"]["config_hash"] == persona_before)
            observations.close()
        finally:
            controller.close()

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "simulated_authority_and_phone_with_real_python_cores",
        "passed": sum(item["passed"] for item in checks),
        "total": len(checks),
        "checks": checks,
        "sample_stale_report": stale_report,
        "sample_completion_cancel_race_report": final_report,
        "not_validated": [
            "Android/HyperOS APK or physical phone", "macOS application/TCC", "HarmonyOS HAP",
            "device authentication or transport", "actual Relay/Codex/Claude execution",
            "background scheduler or notifications", "model behavior or response latency",
            "observation-derived chat history or TTS revocation in the desktop UI",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run()
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        print(f"{result['passed']}/{result['total']} local checks passed; report: {args.output}")
    else:
        print(encoded, end="")
    return 0 if result["passed"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
