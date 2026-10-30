from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import tempfile
from threading import get_ident
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QCoreApplication

from guanghe_companion.desktop_dialogue_service import DesktopDialogueService
from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.expression_settings import ExpressionSettingsStore
from guanghe_companion.emotional_memory_retrieval import score_memory
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController
from guanghe_companion.expression_clients import OpenAICompatibleChatClient
from memory_holdout import MeteredTransport


class DesktopMeter(MeteredTransport):
    def __init__(self):
        super().__init__()
        self.calls = []

    def __call__(self, request, timeout):
        started = time.perf_counter()
        raw = super().__call__(request, timeout)
        payload = json.loads(raw)
        self.calls.append({"prompt": self.request_prompt, "provider_usage": self.usage,
                           "response_model": self.response_model, "response_id": self.response_id,
                           "elapsed_ms": (time.perf_counter() - started) * 1000,
                           "answer": payload["choices"][0]["message"].get("content")})
        return raw


def wait(app, future):
    deadline = time.monotonic() + 90
    iterations = 0
    while not future.done() and time.monotonic() < deadline:
        app.processEvents()
        iterations += 1
        time.sleep(0.001)
    return future.result(timeout=0), iterations


def open_host(root, live=None):
    expressor = ShinsekaiAIExpressor(enabled=False)
    if live is not None:
        client = OpenAICompatibleChatClient(api_key=os.environ[live.api_key_env], model=live.model,
            base_url=live.base_url, timeout_seconds=60, max_tokens=4096, transport=DesktopMeter())
        expressor = ShinsekaiAIExpressor(llm_client=client, enabled=True, timeout_seconds=60)
    controller = PluginEnabledCompanionController(user_data_root=root,
        ai_expressor=expressor,
        expression_settings_store=ExpressionSettingsStore(root / "offline-expression.json"))
    return controller, DesktopDialogueService(controller)


def send(app, controller, desktop, text, *, live=False):
    started = time.perf_counter()
    snapshot, iterations = wait(app, desktop.submit(DialogueRequest(text, source="desktop_smoke"), include_ai_expression=live))
    result = {"text": text, "elapsed_ms": (time.perf_counter() - started) * 1000,
            "qt_event_iterations": iterations, "owner_thread": get_ident(),
            "memory_result": asdict(controller.last_chat_memory_result),
            "context_epoch": controller._dialogue_context_epoch(),
            "reply_kind": "model_requested" if live else "local_expression", "feedback": snapshot.get("feedback"),
            "events": [{"event_type": event.event_type, **event.to_legacy_dict()} for event in controller.last_events]}
    if live:
        meter = controller.ai_expressor.llm_client.transport
        fallback = controller.ai_expressor.last_fallback_reason
        result["model"] = {"fallback_reason": fallback, "provider_usage": meter.usage,
                           "response_model": meter.response_model, "response_id": meter.response_id,
                           "prompt": meter.request_prompt, "output_budget": 4096,
                           "first_token_latency": "not_measured_nonstreaming"}
        result["reply_kind"] = "local_fallback" if fallback else "model_expression"
    return result


def prompt_preview(controller, query):
    controller._require_host_thread()
    controller._current_player_message = query
    try:
        context = controller.get_expression_context()
        request = ExpressionRequest.from_snapshot(controller.get_typed_snapshot(), context=context)
        prompt = controller.ai_expressor.build_prompt(request)
        recalled = controller.story_runtime.memory.recall(query, now=int(controller.now))
        return {"query": query, "prompt": prompt, "prompt_status": "built_not_sent",
                "persona": request.persona,
                "retrieved": [{"id": row.memory_id, "summary": row.summary,
                                "source": row.source, "source_ids": row.source_ids,
                                "version": row.version,
                                "lexical_relevance": score_memory(row, query, now=int(controller.now)).relevance} for row in recalled],
                "semantic_cosines": controller.story_runtime.memory.semantic_retriever.last_cosines}
    finally:
        controller._current_player_message = ""


def run_extraction(app, root, live):
    controller, desktop = open_host(root, live)
    try:
        step = send(app, controller, desktop, "平常大家都叫我小苔，你也这样叫就好。", live=True)
        memories = [asdict(row) for row in controller.story_runtime.memory.store.load_memories() if not row.deleted]
        calls = controller.ai_expressor.llm_client.transport.calls
        checks = {"extraction_and_expression_called": len(calls) == 2,
                  "name_saved_with_source": any("小苔" in row["summary"] and row["source_ids"] for row in memories),
                  "real_expression_completed": step["reply_kind"] == "model_expression",
                  "usage_returned_for_both": len(calls) == 2 and all(call["provider_usage"] for call in calls)}
        return {"scenario": "natural_name_extraction_expression", "steps": [step], "memories": memories,
                "model_calls": calls, "checks": checks, "passed": all(checks.values())}
    finally:
        desktop.close()
        controller.close()


def run(app, root, cache, live=None):
    controller, desktop = open_host(root, live)
    report = {"scenario": "natural_chat_restart_semantic_correct_forget", "owner_thread": get_ident(),
              "generation_model": "requested" if live else "not_run", "generation_blocker": None if live else "live mode not selected",
              "steps": [], "checks": {}}
    query = "下次见面给我捎点喝的，选哪一种比较合适？"
    try:
        report["steps"].append(send(app, controller, desktop, "我喜欢乌龙茶，不喜欢太甜的饮料。"))
        before = [row for row in controller.story_runtime.memory.store.load_memories() if not row.deleted]
        report["checks"]["ordinary_chat_saved_both_preferences"] = (
            any("乌龙茶" in row.summary for row in before) and any("不喜欢太甜" in row.summary for row in before))
        desktop.close()
        controller.close()
        controller, desktop = open_host(root, live)
        wait(app, controller.enable_semantic_memory(cache_dir=cache, local_files_only=True))
        report["checks"]["restart_kept_preferences"] = len([row for row in controller.story_runtime.memory.store.load_memories() if not row.deleted]) == len(before)
        report["steps"].append(send(app, controller, desktop, query, live=live is not None))
        report["before_correction"] = prompt_preview(controller, query)
        report["checks"]["initial_prompt_has_preferences"] = (
            "乌龙茶" in report["before_correction"]["prompt"] and "不喜欢太甜" in report["before_correction"]["prompt"])
        recalled = report["before_correction"]["retrieved"]
        report["checks"]["real_semantic_recalls_below_lexical_threshold"] = (
            len(recalled) == 2 and all(row["lexical_relevance"] < 0.12 for row in recalled)
            and all(report["before_correction"]["semantic_cosines"].get(row["id"], 0) >= 0.45 for row in recalled))
        report["steps"].append(send(app, controller, desktop, "我现在改喝红茶了。"))
        report["cache_after_correction"] = controller.story_runtime.memory.semantic_retriever.status
        report["checks"]["correction_invalidated_cache"] = report["cache_after_correction"]["indexed_entries"] == 0
        report["steps"].append(send(app, controller, desktop, query, live=live is not None))
        report["after_correction"] = prompt_preview(controller, query)
        report["checks"]["corrected_prompt_has_red_tea_not_oolong"] = (
            "红茶" in report["after_correction"]["prompt"] and "乌龙茶" not in report["after_correction"]["prompt"])
        report["steps"].append(send(app, controller, desktop, "别再记我的饮料偏好了。"))
        report["cache_after_forget"] = controller.story_runtime.memory.semantic_retriever.status
        report["checks"]["forget_invalidated_cache"] = report["cache_after_forget"]["indexed_entries"] == 0
        report["steps"].append(send(app, controller, desktop, query, live=live is not None))
        report["after_forget"] = prompt_preview(controller, query)
        report["checks"]["forgotten_prompt_has_no_preferences"] = not any(
            fragment in report["after_forget"]["prompt"] for fragment in ("乌龙茶", "红茶", "不喜欢太甜"))
        report["checks"]["persona_configuration_stable"] = report["before_correction"]["persona"] == report["after_forget"]["persona"]
        report["checks"]["all_submissions_on_owner_thread"] = all(row["owner_thread"] == report["owner_thread"] for row in report["steps"])
        if live is not None:
            replies = [step for step in report["steps"] if "model" in step]
            texts = [" ".join(event.get("speech", "") for event in step["events"] if event.get("event_type") == "speech") for step in replies]
            report["checks"]["three_real_model_replies"] = len(replies) == 3 and all(step["reply_kind"] == "model_expression" and step["model"]["provider_usage"] for step in replies)
            report["checks"]["model_initial_answer_mentions_oolong"] = "乌龙茶" in texts[0]
            report["checks"]["model_corrected_answer_has_red_not_oolong"] = "红茶" in texts[1] and "乌龙茶" not in texts[1]
            report["checks"]["model_forgotten_answer_has_no_old_fact"] = not any(value in texts[2] for value in ("乌龙茶", "红茶", "不喜欢太甜"))
            report["generation_model"] = "completed" if report["checks"]["three_real_model_replies"] else "failed"
        report["passed"] = all(report["checks"].values())
        return report
    finally:
        desktop.close()
        controller.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "artifacts/codex_handoff/embedding-models")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--extraction-only", action="store_true")
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--api-key-env", default="EMOTI_HOLDOUT_API_KEY")
    args = parser.parse_args()
    if args.live and (not args.base_url or not args.model or not os.environ.get(args.api_key_env)):
        parser.error("--live requires base-url, model and the named credential environment variable")
    if args.extraction_only and not args.live:
        parser.error("--extraction-only requires --live")
    app = QCoreApplication.instance() or QCoreApplication([])
    scratch = ROOT / "artifacts/codex_handoff/desktop-memory-smoke"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        report = (run_extraction(app, Path(directory), args) if args.extraction_only
                  else run(app, Path(directory), args.cache_dir, args if args.live else None))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": report["checks"]}, ensure_ascii=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
