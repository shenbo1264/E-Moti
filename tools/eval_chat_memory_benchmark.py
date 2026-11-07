from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from PySide6.QtWidgets import QApplication

from companion_live_eval import open_controller, turn
from persona_behavior_eval import FlashMeter, measured_usage
from guanghe_companion.chat_memory_extraction import should_extract, extract_memory
from guanghe_companion.desktop_dialogue_service import DesktopDialogueService
from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.events import CompanionEvent
from guanghe_companion.expression_clients import client_config_from_settings, LLMProviderError
from guanghe_companion.expression_settings import ExpressionSettingsStore, provider_api_style


def replay_turn(controller, row):
    controller._require_host_thread()
    controller.now = int(datetime.fromisoformat(row["逻辑时间"]).timestamp())
    request = DialogueRequest(row["用户消息"], source="benchmark_replay")
    controller._prepare_host_memory(request)
    extraction_status = "not_needed"
    if (controller.last_chat_memory_result.status in {"ignored", "clarify"}
            and not controller.is_quiet_request(request)
            and should_extract(request.normalized_text(), mode=controller.chat_memory.mode)):
        extraction = controller.chat_memory_extraction
        before = controller._dialogue_context_epoch()
        prepared = extraction.prepare(request.normalized_text(), now=int(controller.now),
            mode=controller.chat_memory.mode, generation=controller.host_context_generation)
        try:
            proposed = extract_memory(prepared, controller.ai_expressor.llm_client)
            controller.last_chat_memory_result = extraction.apply(prepared, proposed,
                now=int(controller.now), generation=controller.host_context_generation,
                mode=controller.chat_memory.mode)
            extraction_status = "completed"
        except (ValueError, LLMProviderError) as exc:
            # 回放保留拒绝原因；不能补造事实或因失败改写固定历史。
            extraction.discard(prepared)
            extraction_status = ("provider_failed:" if isinstance(exc, LLMProviderError) else "rejected:") + str(exc)
        if before != controller._dialogue_context_epoch():
            controller._on_memory_invalidated()
    # 原助手文本只进入原生聊天历史，不生成新回复、不提升为用户事实。
    controller.last_events = [CompanionEvent("speech", controller.state.character_name, row["助手回复"])]
    controller._commit_dialogue_exchange(request, controller._dialogue_context_epoch())
    memory = controller.story_runtime.memory
    if not memory.wait_for_maintenance(timeout=60):
        raise TimeoutError("native memory maintenance did not finish")
    return {"turn": row["轮次"], "now": int(controller.now), "extraction": extraction_status,
        "result": asdict(controller.last_chat_memory_result), "epoch": controller._dialogue_context_epoch(),
        "maintenance": memory.maintenance_status()}


def run(args):
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    reader = args.benchmark_root / "demo" / "read_exam.py"
    payload = subprocess.check_output([sys.executable, str(reader), "--id", args.question_id], encoding="utf-8")
    item = json.loads(payload)
    settings = ExpressionSettingsStore(args.app_settings).load()
    if settings.model != "deepseek-flash":
        raise ValueError("this campaign requires the configured deepseek-flash model")
    meter = FlashMeter(args.max_calls, api_style=provider_api_style(settings.provider),
        journal_path=args.output / "provider-calls.json", secret=settings.api_key)

    def new_client():
        client = client_config_from_settings(settings).client
        if client is None:
            raise ValueError("no enabled provider client")
        client.transport = meter
        return client

    app = QApplication.instance() or QApplication([])
    archive = args.output / "replay-archive"
    initial = EmotionalMemoryService(root=archive, character_id="xingxi_pixel_pet",
        time_basis="unix", timezone_name="Asia/Shanghai")
    initial.close()
    report = {"status": "running", "scope": "public demo adapter pilot; not sealed or full benchmark",
        "upstream_commit": subprocess.check_output(["git", "-C", str(args.benchmark_root), "rev-parse", "HEAD"], text=True).strip(),
        "source_commit": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip()),
        "input": {key: value for key, value in item.items() if key != "history"},
        "model": settings.model, "short_term_turns": 0, "time_basis": "unix",
        "restart_mode": "closed archive copied and reopened by a new controller in the same process",
        "timezone": "Asia/Shanghai", "replayed": [], "grading": "not_run"}
    output = args.output / "result.json"

    def save():
        report["usage"] = measured_usage(meter)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    controller = open_controller(archive, new_client)
    try:
        for row in item["history"]:
            start = meter.calls
            record = replay_turn(controller, row)
            record["provider_call_indices"] = list(range(start, meter.calls))
            report["replayed"].append(record)
            save()
    finally:
        controller.close()
    # 考试在关闭后的副本重启；题目、回答、访问统计均不写回历史主档。
    exam = args.output / "exam-archive"
    shutil.copytree(archive, exam)
    controller = open_controller(exam, new_client)
    desktop = DesktopDialogueService(controller)
    try:
        controller.now = int(datetime.fromisoformat(item["now"]).timestamp())
        controller.dialogue_history = ()
        controller.dialogue_history_store.clear()
        report["memories_after_replay"] = [asdict(entry) for entry in controller.story_runtime.memory.store.load_memories()]
        controller.enable_semantic_memory(cache_dir=args.model_cache, local_files_only=True).result(timeout=180)
        controller.enable_memory_evidence_judgment()
        query_traces = []
        def capture_query(_result):
            trace = controller.story_runtime.memory.last_retrieval_trace
            query_traces.append(trace.to_dict() if trace else None)
        desktop.memory_committed.connect(capture_query)
        report["answer"] = turn(app, controller, desktop, item["question"])
        desktop.memory_committed.disconnect(capture_query)
        # 完成后的快照会做空查询；在表达ticket建立时保存本题实际trace。
        report["retrieval"] = query_traces[-1] if query_traces else None
        report["status"] = "completed" if not report["answer"].get("error") else "failed"
        report["model_status"] = "failed" if (report["answer"].get("error") or report["answer"].get("fallback")) else "completed"
        save()
    finally:
        desktop.close()
        controller.close()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay one public benchmark demo prefix through native E-Moti memory, then answer in an isolated restarted archive.")
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--question-id", default="PUB01-C001/d00")
    parser.add_argument("--app-settings", type=Path, required=True)
    parser.add_argument("--model-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-calls", type=int, default=20)
    result = run(parser.parse_args())
    print(json.dumps({"status": result["status"], "usage": result["usage"]}, ensure_ascii=False))
