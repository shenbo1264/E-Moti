import argparse
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools"), str(ROOT)]

from eval_memory_small_batch import BatchMeter, reserve_request, usage_cost, balance
from eval_ondemand_generation import redact


STAGES = ("save", "recall_forget", "verify")


def write_json(path, value):
    pending = path.with_suffix(path.suffix + ".pending")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    pending.replace(path)


def initialize_budget(path):
    if path.exists():
        raise FileExistsError(path)
    write_json(path, {"calls": 0, "reserved_peak_cny": "0", "in_flight": False, "stopped": False})


def read_budget(path):
    state = json.loads(path.read_text(encoding="utf-8"))
    if state["in_flight"]:
        raise ValueError("budget has an unresolved in-flight request; automatic continuation is forbidden")
    if state["stopped"]:
        raise ValueError("batch is stopped")
    if not 0 <= state["calls"] <= 10 or not Decimal("0") <= Decimal(state["reserved_peak_cny"]) <= Decimal("0.50"):
        raise ValueError("invalid persisted budget")
    return state


def reserve_on_disk(path, payload):
    state = read_budget(path)
    reserved = reserve_request(payload, Decimal(state["reserved_peak_cny"]), state["calls"])
    state.update(calls=state["calls"] + 1, reserved_peak_cny=str(reserved), in_flight=True)
    write_json(path, state)
    return state


class ProcessBatchMeter(BatchMeter):
    def __init__(self, output, secret):
        super().__init__(output / "provider-calls.json", secret)
        self.budget_path = output / "budget.json"
        state = read_budget(self.budget_path)
        self.records = json.loads(self.output.read_text(encoding="utf-8"))["calls"] if self.output.exists() else []
        reconstructed = Decimal("0")
        for index, record in enumerate(self.records):
            reconstructed = reserve_request(record["wire_payload"], reconstructed, index)
        if state["calls"] != len(self.records) or reconstructed != Decimal(state["reserved_peak_cny"]):
            raise ValueError("journal and cumulative budget disagree")
        self.calls, self.reserved = state["calls"], reconstructed
        self.request_lock = Lock()
        self.lock_path = output / "provider.lock"
        self.lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(self.lock_fd, str(os.getpid()).encode("ascii"))

    def __call__(self, req, timeout):
        with self.request_lock:
            return self._request(req, timeout)

    def _request(self, req, timeout):
        if self.stopped:
            raise RuntimeError("batch already stopped")
        try:
            if datetime.now(ZoneInfo("Asia/Shanghai")).weekday() >= 5:
                reserved = reserve_on_disk(self.budget_path, json.loads(req.data))
            else:
                raise ValueError("weekday pricing must be verified before any further request")
        except Exception:
            self.stopped = True
            state = json.loads(self.budget_path.read_text(encoding="utf-8"))
            state["stopped"] = True
            write_json(self.budget_path, state)
            raise
        try:
            raw = super().__call__(req, timeout)
            choices = self.records[-1].get("provider_response", {}).get("choices", [])
            if not choices or choices[0].get("finish_reason") == "length" or not choices[0].get("message", {}).get("content"):
                self.stopped = True
                raise RuntimeError("empty or truncated provider output; no automatic repeat")
            return raw
        finally:
            # 出站前已保留最坏费用；异常退出不释放预留，也不在新进程重置调用计数。
            reserved.update(stopped=self.stopped, in_flight=len(self.records) != reserved["calls"])
            write_json(self.budget_path, reserved)

    def close(self):
        os.close(self.lock_fd)
        self.lock_path.unlink()


def load_scenario(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {"id", "seed", "recall", "forget", "after_forget"}
    if not isinstance(value, dict) or not required <= set(value) <= required | {"correction"}:
        raise ValueError("scenario requires id, seed, recall, forget, after_forget; optional correction")
    if not isinstance(value["seed"], list) or not 1 <= len(value["seed"]) <= 2:
        raise ValueError("one scenario with one or two ordinary seed messages only")
    strings = [value[key] for key in value if key != "seed"] + value["seed"]
    if any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in strings):
        raise ValueError("scenario strings must be nonempty and at most 500 characters")
    return value


def storage(controller):
    memory = controller.story_runtime.memory
    if not memory.wait_for_maintenance(timeout=60):
        raise TimeoutError("memory maintenance did not finish")
    entries = memory.store.load_memories()
    return {"epoch": memory.store.context_epoch,
        "active": [asdict(entry) for entry in entries if entry.is_active(now=int(controller.now))],
        "retired": [asdict(entry) for entry in entries if not entry.is_active(now=int(controller.now))]}


def core_message(controller, text, execute):
    from guanghe_companion.chat_memory_extraction import should_extract, extract_memory
    from guanghe_companion.dialogue import DialogueRequest

    request = DialogueRequest(text, source="process_restart_evaluation")
    controller._prepare_host_memory(request)
    result = controller.last_chat_memory_result
    if result.status in {"ignored", "clarify"} and should_extract(text, mode=controller.chat_memory.mode):
        if not execute:
            raise ValueError("offline check cannot replace model extraction; use a locally parsed ordinary fact")
        extraction = controller.chat_memory_extraction
        prepared = extraction.prepare(text, now=int(controller.now), mode=controller.chat_memory.mode,
            generation=controller.host_context_generation)
        proposals = extract_memory(prepared, controller.ai_expressor.llm_client)
        result = extraction.apply(prepared, proposals, now=int(controller.now), mode=controller.chat_memory.mode,
            generation=controller.host_context_generation)
        controller.last_chat_memory_result = result
        if prepared.epoch != controller._dialogue_context_epoch():
            controller._on_memory_invalidated()
    if result.status not in {"saved", "forgotten"}:
        raise RuntimeError("core memory did not commit: " + result.status)
    return {"text": text, "path": "native_core_no_confirmation_generation", "memory_result": asdict(result)}


def worker(args):
    from PySide6.QtWidgets import QApplication
    from companion_live_eval import open_controller, turn
    from guanghe_companion.desktop_dialogue_service import DesktopDialogueService
    from guanghe_companion.expression_clients import client_config_from_settings
    from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
    from guanghe_companion.expression_settings import ExpressionSettingsStore
    from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController

    output = args.output
    scenario = load_scenario(output / "scenario.json")
    stage_path = output / (args.worker + ".json")
    report = {"stage": args.worker, "pid": os.getpid(), "parent_pid": os.getppid(), "status": "running", "rows": []}
    write_json(stage_path, report)
    meter = None
    initial_calls = 0
    controller = None
    desktop = None
    secret = ""
    try:
        app = QApplication.instance() or QApplication([])
        if args.execute:
            settings = ExpressionSettingsStore(args.app_settings).load()
            secret = settings.api_key
            meter = ProcessBatchMeter(output, secret)
            initial_calls = meter.calls
            def new_client():
                client = client_config_from_settings(settings).client
                client.max_tokens = 4096
                client.transport = meter
                return client
            controller = open_controller(output / "test-archive", new_client)
            controller.enable_semantic_memory(cache_dir=args.model_cache, local_files_only=True).result(timeout=180)
            controller.enable_memory_evidence_judgment()
        else:
            controller = PluginEnabledCompanionController(user_data_root=output / "test-archive",
                ai_expressor=ShinsekaiAIExpressor(enabled=False),
                expression_settings_store=ExpressionSettingsStore(output / "disabled-expression.json"))
        controller.now = 100 + STAGES.index(args.worker) * 100
        report["history_removed_count"] = len(controller.dialogue_history_store.load())
        controller.dialogue_history = ()
        controller.dialogue_history_store.clear()
        report["history_before"] = [asdict(item) for item in controller.dialogue_history_store.load()]
        report["storage_before"] = storage(controller)
        desktop = DesktopDialogueService(controller)

        def answer(text):
            if not args.execute:
                retrieved = controller.story_runtime.memory.retrieve(text, now=int(controller.now), top_k=4)
                return {"text": text, "model_status": "not_run", "offline_retrieval": retrieved.trace.to_dict()}
            traces = []
            def capture(_result):
                trace = controller.story_runtime.memory.last_retrieval_trace
                traces.append(trace.to_dict() if trace else None)
            desktop.memory_committed.connect(capture)
            try:
                result = turn(app, controller, desktop, text)
            finally:
                desktop.memory_committed.disconnect(capture)
            result["retrieval"] = traces
            if result.get("error") or result.get("fallback") or meter.stopped:
                report["failed_answer"] = result
                raise RuntimeError("expression failed; stopping process chain")
            return result

        start = meter.calls if meter else 0
        if args.worker == "save":
            for text in scenario["seed"] + ([scenario["correction"]] if "correction" in scenario else []):
                report["rows"].append(core_message(controller, text, args.execute))
                write_json(stage_path, redact(report, secret))
        elif args.worker == "recall_forget":
            report["rows"].append(answer(scenario["recall"]))
            report["storage_after_recall"] = storage(controller)
            report["rows"].append(core_message(controller, scenario["forget"], args.execute))
            if report["rows"][-1]["memory_result"]["status"] != "forgotten":
                raise RuntimeError("natural forget did not revoke the target")
        else:
            report["rows"].append(answer(scenario["after_forget"]))
        report.update(status="completed" if args.execute else "offline_checked",
            storage_after=storage(controller), provider_call_indices=list(range(start, meter.calls if meter else 0)))
        return 0
    except Exception as exc:
        report.update(status="stopped", error_type=type(exc).__name__, error=str(exc))
        if controller is not None:
            try:
                report["storage_after"] = storage(controller)
            except Exception as snapshot_error:
                report["storage_snapshot_error"] = type(snapshot_error).__name__
        if meter is not None:
            meter.stopped = True
            state = json.loads(meter.budget_path.read_text(encoding="utf-8"))
            state["stopped"] = True
            write_json(meter.budget_path, state)
        return 1
    finally:
        if desktop is not None:
            desktop.close()
        if controller is not None:
            controller.close()
        if meter is not None:
            report["provider_call_indices"] = list(range(initial_calls, meter.calls))
            report["cumulative_usage_cost_cny"] = usage_cost(meter.records)
            meter.close()
        write_json(stage_path, redact(report, secret))


def run(args):
    scenario = load_scenario(args.scenario)
    settings = None
    if args.execute:
        from guanghe_companion.expression_settings import ExpressionSettingsStore
        if args.app_settings is None or args.model_cache is None:
            raise ValueError("execute requires app-settings and an existing local model-cache")
        settings = ExpressionSettingsStore(args.app_settings).load()
        if settings.model != "deepseek-flash" or settings.base_url.rstrip("/") not in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}:
            raise ValueError("only configured official Flash is allowed")
        if datetime.now(ZoneInfo("Asia/Shanghai")).weekday() < 5:
            raise ValueError("shared usage_cost requires verified weekday pricing before execution")
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "scenario.json", scenario)
    initialize_budget(args.output / "budget.json")
    report = {"pid": os.getpid(), "status": "running", "model_status": "not_run", "stages": [],
        "scope": "core ordinary-chat writes and full expression recall across separate processes, not every-turn desktop dialogue",
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "quality_grading": "pending_manual_review" if args.execute else "not_run",
        "pricing_basis": "shared eval_memory_small_batch weekend usage_cost and peak reserve_request",
        "limits": {"cumulative_calls": 10, "cumulative_peak_reserved_cny": "0.50", "max_output_tokens": 4096},
        "archive_origin": "fresh isolated test-archive; no facts imported from history or direct seed writes"}
    write_json(args.output / "results.json", report)
    try:
        if settings:
            report["balance_before"] = balance(settings)
        for stage in STAGES:
            command = [sys.executable, str(Path(__file__).resolve()), "--output", str(args.output.resolve()), "--worker", stage]
            if args.execute:
                command += ["--execute", "--app-settings", str(args.app_settings.resolve()), "--model-cache", str(args.model_cache.resolve())]
            env = dict(os.environ, PYTHONUTF8="1", QT_QPA_PLATFORM="offscreen")
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8")
            timed_out = False
            try:
                stdout, stderr = process.communicate(timeout=600)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                stdout, stderr = process.communicate()
            (args.output / (stage + ".log")).write_text(stdout + stderr, encoding="utf-8")
            record_path = args.output / (stage + ".json")
            record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else {"stage": stage, "status": "crashed"}
            record.update(exit_code=process.returncode, timed_out=timed_out)
            report["stages"].append(record)
            write_json(args.output / "results.json", report)
            if process.returncode or timed_out or record["status"] not in {"completed", "offline_checked"}:
                report.update(status="stopped", model_status="failed" if args.execute else "not_run")
                return 1
        report.update(status="completed" if args.execute else "offline_checked", model_status="completed" if args.execute else "not_run")
        return 0
    except Exception as exc:
        report.update(status="stopped", error_type=type(exc).__name__, error=str(exc))
        return 1
    finally:
        report["budget"] = json.loads((args.output / "budget.json").read_text(encoding="utf-8"))
        journal = args.output / "provider-calls.json"
        if journal.exists():
            report["usage_price_cny"] = usage_cost(json.loads(journal.read_text(encoding="utf-8"))["calls"])
        if settings:
            try:
                report["balance_after"] = balance(settings)
            except Exception as exc:
                report["balance_after_error"] = type(exc).__name__
        write_json(args.output / "results.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Separate-process memory lifecycle; offline by default, one capped batch with --execute.")
    parser.add_argument("--scenario", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--app-settings", type=Path)
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--worker", choices=STAGES, help=argparse.SUPPRESS)
    parsed = parser.parse_args()
    if not parsed.worker and parsed.scenario is None:
        parser.error("--scenario is required")
    sys.exit(worker(parsed) if parsed.worker else run(parsed))
