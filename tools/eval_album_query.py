from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from threading import get_ident
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.memory_album_query import MemoryAlbumQueryService
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController
from eval_ondemand_generation import recorded_app_client, redact


def main():
    parser = argparse.ArgumentParser(description="Real BGE/Flash preparation and Qt album delivery on an isolated archive")
    parser.add_argument("--app-settings", type=Path, required=True)
    parser.add_argument("--model-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    client, meter, provider, secret = recorded_app_client(args.app_settings, max_requests=4)
    report = {"status": "running", "scope": "Qt album retrieval with real BGE and model evidence judgment; no answer generation",
              "provider": provider, "stages": []}
    timer, ticks = QTimer(), []
    timer.timeout.connect(lambda: ticks.append(time.perf_counter()))
    timer.start(5)

    def pump(done):
        deadline = time.monotonic() + 120
        while not done() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.005)
        if not done():
            raise TimeoutError("album query did not finish")

    try:
        with tempfile.TemporaryDirectory(prefix="album-query-", dir=args.output.parent) as directory:
            controller = PluginEnabledCompanionController(user_data_root=directory)
            controller.ai_expressor.close()
            controller.ai_expressor = ShinsekaiAIExpressor(llm_client=client, timeout_seconds=60)
            service = MemoryAlbumQueryService(lambda: controller.memory_album_controller)
            answers, errors, delivery_threads = [], [], []
            service.completed.connect(lambda result: (answers.append(result), delivery_threads.append(get_ident())))
            service.failed.connect(errors.append)
            try:
                future = controller.enable_semantic_memory(cache_dir=args.model_cache, local_files_only=True)
                pump(future.done)
                future.result()
                controller.enable_memory_evidence_judgment()
                memory, album = controller.story_runtime.memory, controller.memory_album_controller
                row = memory.remember(kind="玩家希望被记住", title="饮品", summary="用户泡白茶用玻璃杯。",
                    source="explicit_user_request", now=int(controller.now))
                before = row.to_dict()
                for stage in ("recall", "after_forget"):
                    answers.clear()
                    start_calls, start_ticks = len(meter.records), len(ticks)
                    started = time.perf_counter()
                    service.submit("我喝白茶用哪种杯子？")
                    pump(lambda: bool(answers or errors))
                    if errors:
                        raise RuntimeError(errors[-1])
                    result = answers[-1]
                    report["stages"].append({"stage": stage, "result": result,
                        "latency_ms": (time.perf_counter() - started) * 1000,
                        "qt_timer_ticks": len(ticks) - start_ticks,
                        "provider_call_indices": list(range(start_calls, len(meter.records)))})
                    assert delivery_threads[-1] == get_ident()
                    if stage == "recall":
                        assert result["status"] == "sufficient" and result["claims"][0]["memory_id"] == row.memory_id
                        assert memory.store.load_memories()[0].to_dict() == before
                        album.forget(row.memory_id, expected_epoch=result["context_epoch"])
                    else:
                        assert result["status"] == "unknown" and not result["claims"]
                report["status"] = "passed"
            finally:
                service.close()
                controller.close()
    except Exception as exc:
        report.update(status="failed", error_type=type(exc).__name__)
        raise
    finally:
        timer.stop()
        report.update(actual_requests=meter.calls, provider_calls=meter.records,
                      model_validation="run" if meter.calls else "not_run")
        args.output.write_text(json.dumps(redact(report, secret), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "actual_requests": meter.calls}))


if __name__ == "__main__":
    main()
