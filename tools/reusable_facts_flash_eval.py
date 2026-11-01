from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="在独立存档中验证不同主体和活动的事实更正、重启与遗忘")
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", default=[])
    args = parser.parse_args()
    # 基线工具和生产模块都从同一工作目录导入，避免混入当前实现。
    sys.path[:0] = [str(args.repo / "tools"), str(args.repo / "src")]
    from PySide6.QtWidgets import QApplication
    from companion_flash_eval import Meter
    from companion_live_eval import open_controller, pump, turn
    from companion_acceptance import active_text, pending_text
    from guanghe_companion.desktop_dialogue_service import DesktopDialogueService
    from guanghe_companion.expression_clients import client_config_from_settings
    from guanghe_companion.expression_settings import ExpressionSettingsStore
    import guanghe_companion.chat_memory as memory_module

    settings = ExpressionSettingsStore(Path(os.environ["LOCALAPPDATA"]) / "E-Moti/expression_settings.json").load()
    if settings.model != "deepseek-flash":
        raise ValueError("需要应用配置的 deepseek-flash")
    meter = Meter()

    def new_client():
        client = client_config_from_settings(settings).client
        if client is None:
            raise ValueError("应用模型没有可用凭据")
        client.transport = meter
        return client

    app = QApplication.instance() or QApplication([])
    cases = json.loads(args.dataset.read_text(encoding="utf-8"))["cases"]
    if args.case:
        cases = [case for case in cases if case["id"] in args.case]
    report = {"model": settings.model,
              "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.repo, text=True).strip(),
              "production_module": str(Path(memory_module.__file__).relative_to(args.repo)),
              "working_changes": subprocess.check_output(["git", "diff", "--name-only"], cwd=args.repo, text=True).splitlines(),
              "dataset": args.dataset.name, "cases": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def checkpoint():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    for case in cases:
        root = ROOT / "artifacts/codex_handoff/reusable-facts" / f"{case['id']}-{time.time_ns()}"
        root.mkdir(parents=True)
        row = {"id": case["id"], "expected": case["expected"], "rubric": case["rubric"], "stages": []}
        report["cases"].append(row)

        def open_session():
            controller = open_controller(root, new_client)
            future = controller.enable_semantic_memory(cache_dir=ROOT / "artifacts/codex_handoff/embedding-models", local_files_only=True)
            pump(app, future, 120)
            future.result()
            controller.now = 10000
            return controller, DesktopDialogueService(controller)

        controller, service = open_session()
        try:
            def stage(label, text):
                controller._current_player_message = text
                context = controller.get_expression_context()
                first = len(meter.case_calls)
                started = time.perf_counter()
                result = turn(app, controller, service, text)
                active = [m for m in controller.story_runtime.memory.store.load_memories() if not m.deleted]
                calls = meter.case_calls[first:]
                messages = json.dumps([c["messages"] for c in calls], ensure_ascii=False)
                row["stages"].append({"label": label, "context_before": context, "turn": result,
                    "stored": active_text(controller), "pending": pending_text(controller),
                    "active_facts": [{"id": m.memory_id, "summary": m.summary, "metadata": m.metadata} for m in active],
                    "epoch": controller.story_runtime.memory.store.context_epoch, "calls": calls,
                    "prompt_old_values": [v for v in case["expected"]["old_values"] if v in messages],
                    "prompt_new_values": [v for v in case["expected"]["new_values"] if v in messages],
                    "elapsed_ms": round((time.perf_counter() - started) * 1000)})
                checkpoint()
                print(case["id"], label, result.get("memory_result"), result.get("reply"), flush=True)

            for index, seed in enumerate(case["seed"]):
                if seed["mode"] == "explicit":
                    controller.memory_album_controller.remember_explicit(seed["text"], now=int(controller.now),
                        expected_epoch=controller.story_runtime.memory.store.context_epoch)
                elif seed["mode"] == "chat":
                    stage(f"seed_{index}", seed["text"])
                else:
                    raise ValueError("unsupported seed mode")
            row["seed_stored"] = active_text(controller)
            stage("correction", case["correction"])
            controller.clear_dialogue_history()
            service.close()
            controller.close()
            controller, service = open_session()
            stage("restart_recall_without_history", case["query"])
            stage("forget", case["forget"])
            stage("recall_after_forget", case["query"])
            controller.clear_dialogue_history()
            service.close()
            controller.close()
            controller, service = open_session()
            stage("restart_after_forget_without_history", case["query"])
        finally:
            service.close()
            controller.close()
            checkpoint()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
