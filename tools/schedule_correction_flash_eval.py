from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication

from companion_flash_eval import Meter
from companion_live_eval import open_controller, pump, turn
from companion_acceptance import active_text, pending_text
from guanghe_companion.desktop_dialogue_service import DesktopDialogueService
from guanghe_companion.expression_clients import client_config_from_settings
from guanghe_companion.expression_settings import ExpressionSettingsStore


def main():
    parser = argparse.ArgumentParser(description="真实 Flash 每周安排改期、空历史重启召回与遗忘")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--independent", action="store_true")
    args = parser.parse_args()
    settings = ExpressionSettingsStore(Path(os.environ["LOCALAPPDATA"]) / "E-Moti/expression_settings.json").load()
    if settings.model != "deepseek-flash":
        raise ValueError("需要应用的 deepseek-flash 配置")
    meter = Meter()

    def new_client():
        client = client_config_from_settings(settings).client
        if client is None:
            raise ValueError("应用没有可用的模型凭据")
        client.transport = meter
        return client

    app = QApplication.instance() or QApplication([])
    activity, old_day, new_day = ("跑步", "三", "五") if args.independent else ("游泳", "六", "日")
    root = ROOT / "artifacts/codex_handoff/schedule-thanks" / f"session-{time.time_ns()}"
    root.mkdir(parents=True)
    report = {"model": settings.model, "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "working_changes": subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT, text=True).splitlines(),
              "synthetic_data_root": str(root), "activity": activity, "old_day": old_day,
              "new_day": new_day, "initial_mode": "ordinary_chat" if args.independent else "explicit_memory", "stages": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def checkpoint():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def open_session():
        controller = open_controller(root, new_client)
        future = controller.enable_semantic_memory(cache_dir=ROOT / "artifacts/codex_handoff/embedding-models", local_files_only=True)
        pump(app, future, 120)
        future.result()
        controller.now = 10000
        return controller, DesktopDialogueService(controller)

    controller, service = open_session()
    try:
        if not args.independent:
            controller.memory_album_controller.remember_explicit(f"我每周{old_day}去{activity}。", now=int(controller.now),
                expected_epoch=controller.story_runtime.memory.store.context_epoch)
        controller.memory_album_controller.remember_explicit("我的名字是许安。", now=int(controller.now),
            expected_epoch=controller.story_runtime.memory.store.context_epoch)
        report["seed_stored"] = active_text(controller)

        def stage(label, text):
            controller._current_player_message = text
            context = controller.get_expression_context()
            first = len(meter.case_calls)
            started = time.perf_counter()
            result = turn(app, controller, service, text)
            rows = [m for m in controller.story_runtime.memory.store.load_memories() if not m.deleted]
            report["stages"].append({"label": label, "context_before": context, "turn": result,
                "stored": active_text(controller), "pending": pending_text(controller),
                "active_facts": [{"id": m.memory_id, "summary": m.summary, "metadata": m.metadata} for m in rows],
                "epoch": controller.story_runtime.memory.store.context_epoch,
                "calls": meter.case_calls[first:], "elapsed_ms": round((time.perf_counter()-started)*1000)})
            checkpoint()
            print(label, result.get("memory_result"), result.get("reply"), flush=True)

        if args.independent:
            stage("initial_ordinary_chat", f"我每周{old_day}去{activity}。")
        stage("reschedule", f"我以后改成周{new_day}去{activity}了。")
        controller.clear_dialogue_history()
        service.close()
        controller.close()
        controller, service = open_session()
        stage("restart_recall_without_history", f"我每周几去{activity}？")
        stage("forget", f"请忘记我的{activity}安排。")
        stage("recall_after_forget", f"我每周几去{activity}？")
        controller.clear_dialogue_history()
        service.close()
        controller.close()
        controller, service = open_session()
        stage("restart_after_forget_without_history", f"我每周几去{activity}？")
    finally:
        service.close()
        controller.close()
        checkpoint()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
