from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--app-settings", type=Path, required=True)
    parser.add_argument("--model-cache", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source_root / "src"))
    # 先绑定被测生产包；公共评测工具随后导入时不得切换到工具目录所属版本。
    import guanghe_companion
    from PySide6.QtWidgets import QApplication
    from companion_live_eval import open_controller, turn
    from persona_behavior_eval import FlashMeter, measured_usage
    from guanghe_companion.desktop_dialogue_service import DesktopDialogueService
    from guanghe_companion.expression_clients import client_config_from_settings
    from guanghe_companion.expression_settings import ExpressionSettingsStore, provider_api_style

    args.output.mkdir(parents=True, exist_ok=False)
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    settings = ExpressionSettingsStore(args.app_settings).load()
    if settings.model != "deepseek-flash":
        raise ValueError("lifecycle comparison requires deepseek-flash")
    meter = FlashMeter(160, api_style=provider_api_style(settings.provider),
        journal_path=args.output / "provider-calls.json", secret=settings.api_key)
    app = QApplication.instance() or QApplication([])

    def new_client():
        client = client_config_from_settings(settings).client
        client.transport = meter
        return client

    def reopen(root):
        controller = open_controller(root, new_client)
        controller.enable_semantic_memory(cache_dir=args.model_cache, local_files_only=True).result(timeout=180)
        controller.enable_memory_evidence_judgment()
        return controller, DesktopDialogueService(controller)

    report = {"source_root": str(args.source_root), "package_path": str(guanghe_companion.__file__),
        "source_commit": subprocess.check_output(["git", "-C", str(args.source_root), "rev-parse", "HEAD"], text=True).strip(),
        "model": settings.model, "dataset": dataset.get("name", args.dataset.stem), "status": "running",
        "restart_mode": "controller and storage closed/reopened in same process; history cleared before reopen",
        "grading": "pending_semantic_review", "scenarios": []}

    def save():
        report["usage"] = measured_usage(meter)
        (args.output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    for scenario in dataset["scenarios"]:
        root = args.output / "archives" / scenario["id"]
        controller, desktop = reopen(root)
        rows = []
        report["scenarios"].append({"id": scenario["id"], "turns": rows})
        try:
            for index, item in enumerate(scenario["turns"]):
                if item.get("new_conversation"):
                    controller.dialogue_history = ()
                    controller.dialogue_history_store.clear()
                    desktop.close()
                    controller.close()
                    controller, desktop = reopen(root)
                controller.now = 100 + index * 100
                traces = []

                def capture(_result):
                    trace = controller.story_runtime.memory.last_retrieval_trace
                    traces.append(trace.to_dict() if trace else None)

                start = meter.calls
                desktop.memory_committed.connect(capture)
                try:
                    answer = turn(app, controller, desktop, item["text"])
                finally:
                    desktop.memory_committed.disconnect(capture)
                memory = controller.story_runtime.memory
                if not memory.wait_for_maintenance(timeout=60):
                    raise TimeoutError("memory maintenance did not finish")
                rows.append({"index": index, "phase": item["phase"], "expected": item.get("expected"),
                    "answer": answer, "provider_call_indices": list(range(start, meter.calls)),
                    "retrieval": traces, "epoch": memory.store.context_epoch,
                    "memories": [asdict(entry) for entry in memory.store.load_memories()]})
                save()
                print(scenario["id"], index, answer, flush=True)
        finally:
            desktop.close()
            controller.close()
    report["status"] = "completed"
    save()


if __name__ == "__main__":
    main()
