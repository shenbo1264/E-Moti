from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from PySide6.QtWidgets import QApplication

from companion_live_eval import open_controller, turn
from eval_chat_memory_benchmark import replay_turn
from persona_behavior_eval import FlashMeter, measured_usage
from guanghe_companion.desktop_dialogue_service import DesktopDialogueService
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.events import CompanionEvent
from guanghe_companion.expression_clients import client_config_from_settings
from guanghe_companion.expression_settings import ExpressionSettingsStore, provider_api_style

UPSTREAM_COMMIT = "07a11f4074cde1106c5fed9f627e662ff1a3abc1"
DATA_RELATIVE = "datasets/natural-timegrid-20261101-v2"


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".pending")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity():
    paths = list((ROOT / "src/guanghe_companion").glob("*.py"))
    paths += [Path(__file__), ROOT / "tools/eval_chat_memory_benchmark.py",
              ROOT / "tools/companion_live_eval.py", ROOT / "tools/persona_behavior_eval.py"]
    return {str(path.relative_to(ROOT)).replace("\\", "/"): sha(path) for path in sorted(paths)}


def load_inputs(upstream):
    commit = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    if commit != UPSTREAM_COMMIT:
        raise ValueError("benchmark upstream must use the declared fixed commit")
    folder = upstream / DATA_RELATIVE
    reader_path = folder / "read_exam.py"
    spec = importlib.util.spec_from_file_location("emoti_formal_input_reader", reader_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = read_json(folder / "manifest.json")
    if sha(folder / "exam-inputs.jsonl") != manifest["file_sha256"]["exam-inputs.jsonl"]:
        raise ValueError("exam input differs from fixed manifest")
    records = module.rows(folder / "exam-inputs.jsonl")
    if len({row["id"] for row in records}) != len(records):
        raise ValueError("duplicate question ID")
    return folder, module, records


def ordered_questions(records, persona):
    rows = sorted((row for row in records if row["persona"] == persona),
        key=lambda row: (datetime.fromisoformat(row["now"]), row["id"]))
    if not rows:
        raise ValueError("unknown persona")
    if any(a["cutoff_turn"] > b["cutoff_turn"] for a, b in zip(rows, rows[1:])):
        raise ValueError("exam chronology reverses history cutoff")
    return rows


def load_checkpoint(path, config, *, resume, accept_runner_recovery=False):
    if not path.exists():
        return {"config": config, "status": "running", "committed_turn": 0,
                "completed_ids": [], "calls": 0, "inflight": None}
    if not resume:
        raise FileExistsError(path)
    state = read_json(path)
    if state["config"] != config:
        old = state["config"]
        changed = {key for key in set(old.get("source_files", {})) | set(config.get("source_files", {}))
                   if old.get("source_files", {}).get(key) != config.get("source_files", {}).get(key)}
        allowed = {"tools/eval_chat_memory_formal.py", "tools/eval_chat_memory_benchmark.py"}
        if (not accept_runner_recovery or not changed or not changed <= allowed
                or {k: v for k, v in old.items() if k != "source_files"}
                != {k: v for k, v in config.items() if k != "source_files"}):
            raise ValueError("resume configuration or source changed")
        revision = {"reason": "retain provider failure and continue fixed history without retry",
                    "source_files": config["source_files"]}
        if revision not in state.setdefault("runner_revisions", []):
            state["runner_revisions"].append(revision)
    if (state.get("inflight") or {}).get("kind") == "replay" and not accept_runner_recovery:
        raise RuntimeError("uncertain replay commit; inspect the saved archive and journal before any retry")
    return state


def collect_answers(output):
    completed, failed = [], []
    for path in sorted(output.glob("*/answers/*.json")):
        row = read_json(path)
        reply = "\n".join(row.get("answer", {}).get("reply", []))
        if row.get("model_status") == "completed" and reply.strip():
            completed.append({"id": row["id"], "answer": reply})
        else:
            failed.append({"id": row["id"], "status": row.get("model_status"),
                           "error": row.get("error", row.get("answer", {}).get("error"))})
    if len({row["id"] for row in completed + failed}) != len(completed + failed):
        raise ValueError("duplicate output question ID")
    (output / "answers.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in completed), encoding="utf-8")
    report = {"answered": len(completed), "failed": len(failed), "failed_cases": failed,
              "full_dataset_questions": 714, "grading": "not_run"}
    save_json(output / "answer-manifest.json", report)
    return report


def run_worker(args):
    folder, reader, records = load_inputs(args.benchmark_root)
    questions = ordered_questions(records, args.persona)
    if args.limit:
        questions = questions[:args.limit]
    output = args.output / args.persona
    output.mkdir(parents=True, exist_ok=True)
    settings = ExpressionSettingsStore(args.app_settings).load()
    if settings.model != "deepseek-flash":
        raise ValueError("campaign requires configured deepseek-flash")
    config = {"persona": args.persona, "ids": [row["id"] for row in questions],
        "upstream_commit": UPSTREAM_COMMIT, "history_sha256": questions[0]["history_sha256"],
        "source_files": source_identity(), "model": settings.model, "base_url": settings.base_url,
        "provider": settings.provider, "timeout_seconds": settings.timeout_seconds, "max_output_tokens": 4096,
        "short_term_turns": 0, "time_basis": "unix", "timezone": "Asia/Shanghai",
        "evidence_judgment": True, "maintenance": "native scheduling plus exam-time bounded maintenance"}
    checkpoint = output / "checkpoint.json"
    state = load_checkpoint(checkpoint, config, resume=args.resume, accept_runner_recovery=args.accept_runner_recovery)
    if "source_commit_at_start" not in state:
        state["source_commit_at_start"] = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    app = QApplication.instance() or QApplication([])
    meter = None

    def new_client():
        client = client_config_from_settings(settings).client
        if client is None:
            raise ValueError("missing enabled model client")
        client.transport = meter
        return client

    def begin(kind, ident):
        nonlocal meter
        if source_identity() != config["source_files"]:
            raise RuntimeError("source changed during benchmark; stop before the next request")
        if state["calls"] >= args.max_calls:
            state["status"] = "budget_exhausted"
            save_json(checkpoint, state)
            return False
        key = hashlib.sha256(ident.encode()).hexdigest()[:24]
        journal = output / "calls" / f"{kind}-{key}.json"
        if journal.exists():
            raise FileExistsError("never overwrite an actual provider journal: " + str(journal))
        journal.parent.mkdir(exist_ok=True)
        meter = FlashMeter(args.max_calls - state["calls"], api_style=provider_api_style(settings.provider),
            journal_path=journal, secret=settings.api_key)
        state["inflight"] = {"kind": kind, "id": ident, "journal": str(journal)}
        save_json(checkpoint, state)
        return True

    def finish():
        state["calls"] += meter.calls
        state["inflight"] = None
        save_json(checkpoint, state)

    # 未完成的考试不重试刷答案；回放档案未受影响，可继续其他题。
    inflight = state.get("inflight")
    if inflight and inflight["kind"] == "replay":
        # 已确认失败在提取apply之前。保留已发生的到期清理，只补交固定对话，不重新提取。
        if state.get("status") != "replay_failed" or "invalid_response_text" not in state.get("error", ""):
            raise RuntimeError("replay interruption is not a verified pre-apply provider failure")
        journal = read_json(Path(inflight["journal"]))
        response = journal["calls"][-1]["provider_response"]["choices"][0]
        if response.get("finish_reason") != "length" or response["message"].get("content"):
            raise RuntimeError("replay recovery requires the recorded empty truncated provider response")
        failed_turn = int(inflight["id"])
        row = next(row for row in reader.read_input(folder, questions[-1])["history"] if row["turn"] == failed_turn)
        if failed_turn != state["committed_turn"] + 1:
            raise RuntimeError("failed replay is not the next uncommitted turn")
        meter = FlashMeter(0, api_style=provider_api_style(settings.provider), secret=settings.api_key)
        controller = open_controller(output / "replay-archive", new_client)
        try:
            controller.now = int(datetime.fromisoformat(row["time"]).timestamp())
            request = DialogueRequest(row["user"], source="benchmark_replay")
            controller.last_events = [CompanionEvent("speech", controller.state.character_name, row["assistant"])]
            controller._commit_dialogue_exchange(request, controller._dialogue_context_epoch())
            if not controller.story_runtime.memory.wait_for_maintenance(timeout=60):
                raise TimeoutError("recovery maintenance did not finish")
            recovery = {"turn": failed_turn, "now": int(controller.now), "extraction": "provider_failed",
                "error": state["error"], "original_journal": inflight["journal"], "model_retried": False,
                "usage": state["inflight_usage"], "recovery": "fixed dialogue committed without re-running memory preparation"}
            save_json(output / "replayed" / f"{failed_turn:04d}.json", recovery)
        finally:
            controller.close()
        state.setdefault("recovered_provider_failures", []).append(recovery)
        state["committed_turn"] = failed_turn
        state["inflight"] = None
        state["status"] = "running"
        save_json(checkpoint, state)
        inflight = None
    if inflight:
        ident = inflight["id"]
        path = output / "answers" / (hashlib.sha256(ident.encode()).hexdigest()[:24] + ".json")
        if not path.exists():
            save_json(path, {"id": ident, "model_status": "interrupted", "error": "worker interrupted; not retried"})
        journal = Path(inflight["journal"])
        state["calls"] += len(read_json(journal)["calls"]) if journal.exists() else 0
        state["completed_ids"].append(ident)
        state["inflight"] = None
        save_json(checkpoint, state)
    archive = output / "replay-archive"
    if not checkpoint.exists() and archive.exists():
        raise FileExistsError("replay archive exists without its checkpoint")
    if state["committed_turn"] and not archive.exists():
        raise FileNotFoundError("committed replay archive is missing")
    if not archive.exists():
        initial = EmotionalMemoryService(root=archive, character_id="xingxi_pixel_pet",
            time_basis="unix", timezone_name="Asia/Shanghai")
        initial.close(wait=True)
    save_json(checkpoint, state)
    for record in questions:
        if record["id"] in state["completed_ids"]:
            continue
        item = reader.read_input(folder, record)
        for row in item["history"][state["committed_turn"]:]:
            ident = str(row["turn"])
            if not begin("replay", ident):
                return 2
            controller = open_controller(archive, new_client)
            try:
                native = {"轮次": row["turn"], "逻辑时间": row["time"], "用户消息": row["user"], "助手回复": row["assistant"]}
                result = replay_turn(controller, native)
                save_json(output / "replayed" / f"{row['turn']:04d}.json", {**result, "usage": measured_usage(meter)})
            except Exception as exc:
                state["status"] = "replay_failed"
                state["error"] = type(exc).__name__ + ": " + str(exc)
                state["calls"] += meter.calls
                state["inflight_usage"] = measured_usage(meter)
                save_json(checkpoint, state)
                raise
            finally:
                controller.close()
            state["committed_turn"] = row["turn"]
            finish()
        ident = record["id"]
        if not begin("exam", ident):
            return 2
        key = hashlib.sha256(ident.encode()).hexdigest()[:24]
        exam = output / "exam-archives" / key
        shutil.copytree(archive, exam)
        controller = open_controller(exam, new_client)
        desktop = DesktopDialogueService(controller)
        result = {"id": ident, "persona": args.persona, "now": item["now"], "cutoff_turn": record["cutoff_turn"],
                  "history_sha256": record["history_sha256"], "short_term_turns": 0}
        try:
            controller.now = int(datetime.fromisoformat(item["now"]).timestamp())
            memory = controller.story_runtime.memory
            result["maintenance"] = memory.maintain(now=int(controller.now)).to_dict()
            controller.dialogue_history = ()
            controller.dialogue_history_store.clear()
            controller.enable_semantic_memory(cache_dir=args.model_cache, local_files_only=True).result(timeout=180)
            controller.enable_memory_evidence_judgment()
            traces = []
            def capture(_result):
                trace = memory.last_retrieval_trace
                traces.append(trace.to_dict() if trace else None)
            desktop.memory_committed.connect(capture)
            result["answer"] = turn(app, controller, desktop, item["question"])
            desktop.memory_committed.disconnect(capture)
            result["retrieval"] = traces[-1] if traces else None
            result["model_status"] = "failed" if result["answer"].get("error") or result["answer"].get("fallback") else "completed"
        except Exception as exc:
            result.update(model_status="failed", error=type(exc).__name__ + ": " + str(exc))
        finally:
            desktop.close()
            controller.close()
        result["usage"] = measured_usage(meter)
        save_json(output / "answers" / (key + ".json"), result)
        state["completed_ids"].append(ident)
        finish()
        print(json.dumps({"persona": args.persona, "answered": len(state["completed_ids"]),
            "planned": len(questions), "calls": state["calls"], "model_status": result["model_status"]}), flush=True)
    if source_identity() != config["source_files"]:
        state["status"] = "source_changed_during_run"
        save_json(checkpoint, state)
        return 3
    state["status"] = "completed"
    save_json(checkpoint, state)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Native six-person chat memory benchmark replay; answer keys are only used by the separate upstream grader.")
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--app-settings", type=Path)
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--personas", nargs="+")
    parser.add_argument("--persona", help=argparse.SUPPRESS)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--max-calls", type=int, default=9000, help="Total call cap divided among selected persona workers")
    parser.add_argument("--limit", type=int, help="First N chronological questions per persona; partial pilot only")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--accept-runner-recovery", action="store_true", help="Allow documented runner-only repair and verified pre-apply provider failure recovery")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    folder, reader, records = load_inputs(args.benchmark_root)
    if args.validate_only:
        for record in records:
            reader.read_input(folder, record)
        print(json.dumps({"questions": len(records), "personas": len({r['persona'] for r in records}), "model_calls": 0}))
        return 0
    if not args.app_settings or not args.model_cache or args.jobs < 1 or args.max_calls < 1:
        parser.error("model settings/cache and positive jobs/call budget required")
    if args.persona:
        return run_worker(args)
    personas = args.personas or sorted({row["persona"] for row in records})
    if len(set(personas)) != len(personas):
        parser.error("duplicate persona")
    for persona in personas:
        ordered_questions(records, persona)
    args.output.mkdir(parents=True, exist_ok=True)
    per_worker = args.max_calls // len(personas)
    if per_worker < 1:
        parser.error("budget smaller than worker count")
    def launch(persona):
        command = [sys.executable, str(Path(__file__)), "--benchmark-root", str(args.benchmark_root),
            "--app-settings", str(args.app_settings), "--model-cache", str(args.model_cache),
            "--output", str(args.output), "--persona", persona, "--max-calls", str(per_worker)]
        if args.resume:
            command.append("--resume")
        if args.accept_runner_recovery:
            command.append("--accept-runner-recovery")
        if args.limit:
            command.extend(("--limit", str(args.limit)))
        log = args.output / f"{persona}.log"
        with log.open("a" if args.resume else "x", encoding="utf-8") as handle:
            process = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT,
                env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONUTF8": "1"})
        return {"persona": persona, "returncode": process.returncode, "log": str(log)}
    with ThreadPoolExecutor(max_workers=min(args.jobs, len(personas))) as executor:
        runs = list(executor.map(launch, personas))
    report = {"workers": runs, "max_calls_total": args.max_calls, "per_worker_call_cap": per_worker,
        "answers": collect_answers(args.output), "status": "completed" if all(r["returncode"] == 0 for r in runs) else "partial"}
    save_json(args.output / "run-manifest.json", report)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
