from __future__ import annotations

"""Run the acceptance set through DesktopDialogueService with a real metered model.

The key comes from an environment variable and is never written to the report.
Spending is capped: the run stops before the next case once --budget-usd is used.
"""

import argparse
from concurrent.futures import Future
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from PySide6.QtWidgets import QApplication

from companion_acceptance import DATASET, active_text, load_dataset, pending_text
from guanghe_companion.desktop_dialogue_service import DesktopDialogueService
from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.expression_clients import OpenAIResponsesClient, _default_transport
from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.expression_settings import ExpressionSettingsStore
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController

# USD per 1M tokens, standard tier, from developers.openai.com/api/docs/pricing on 2026-10-30.
PRICES = {"gpt-6.1-terra": (1.00, 0.05, 5.00), "gpt-6-luna": (0.10, 0.01, 0.50)}


class BudgetExceeded(RuntimeError):
    pass


class Meter:
    """Transport that records provider usage and refuses calls past the budget."""

    def __init__(self, model: str, budget: float, reasoning: str):
        self.price, self.budget, self.reasoning = PRICES[model], budget, reasoning
        self.spent, self.calls, self.input_tokens, self.output_tokens, self.reasoning_tokens = 0.0, 0, 0, 0, 0
        self.case_calls: list[dict] = []

    def __call__(self, request, timeout):
        if self.spent >= self.budget:
            raise BudgetExceeded(f"budget {self.budget} reached")
        body = json.loads(request.data)
        body["reasoning"] = {"effort": self.reasoning}
        body["max_output_tokens"] = 1200
        request.data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        started = time.perf_counter()
        raw = _default_transport(request, timeout)
        usage = json.loads(raw).get("usage") or {}
        cached = (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
        reasoning = (usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0)
        fresh = usage.get("input_tokens", 0) - cached
        cost = (fresh * self.price[0] + cached * self.price[1] + usage.get("output_tokens", 0) * self.price[2]) / 1e6
        self.spent += cost
        self.calls += 1
        self.input_tokens += usage.get("input_tokens", 0)
        self.output_tokens += usage.get("output_tokens", 0)
        self.reasoning_tokens += reasoning
        self.case_calls.append({"latency_ms": round((time.perf_counter() - started) * 1000), "usage": usage,
                                "cost_usd": round(cost, 6)})
        return raw


def pump(app, future: Future, limit: float) -> None:
    deadline = time.monotonic() + limit
    while not future.done() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


def open_controller(root: Path, new_client) -> PluginEnabledCompanionController:
    return PluginEnabledCompanionController(
        user_data_root=root,
        ai_expressor=ShinsekaiAIExpressor(llm_client=new_client(), enabled=True, timeout_seconds=60),
        expression_settings_store=ExpressionSettingsStore(root / "disabled-expression.json"))


def turn(app, controller, service, text: str) -> dict:
    future = service.submit(DialogueRequest(text=text, source="acceptance"), include_ai_expression=True)
    pump(app, future, 150)
    while service._active is not None and future.done():
        app.processEvents()
    if not future.done():
        service.cancel()
        return {"text": text, "error": "timeout"}
    if future.exception() is not None:
        return {"text": text, "error": f"{type(future.exception()).__name__}: {future.exception()}"}
    speech = [e.speech for e in controller.last_events if e.event_type == "speech"]
    return {"text": text, "reply": speech, "fallback": controller.ai_expressor.last_fallback_reason,
            "memory_result": controller.get_chat_memory_status()["last_result"]}


def run_case(app, case: dict, new_client, meter: Meter, semantic_cache: Path | None) -> dict:
    meter.case_calls = []
    with tempfile.TemporaryDirectory(prefix="emoti-live-") as temp:
        root = Path(temp)
        controller = open_controller(root, new_client)
        service = DesktopDialogueService(controller)
        if semantic_cache:
            pump(app, controller.enable_semantic_memory(cache_dir=semantic_cache, local_files_only=True), 120)
        try:
            controller.now = 100
            for text in case.get("seed", []):
                controller.memory_album_controller.remember_explicit(
                    text, now=int(controller.now), expected_epoch=controller.story_runtime.memory.store.context_epoch)
            turns = []
            for offset, text in enumerate(case.get("chat", []), 1):
                controller.now = 100 + offset * 100
                turns.append(turn(app, controller, service, text))
            if case.get("reopen"):
                service.close()
                controller.close()
                controller = open_controller(root, new_client)
                service = DesktopDialogueService(controller)
                if semantic_cache:
                    pump(app, controller.enable_semantic_memory(cache_dir=semantic_cache, local_files_only=True), 120)
            controller.now = 10000
            if "query" in case:
                turns.append(turn(app, controller, service, case["query"]))
            stored, pending = active_text(controller), pending_text(controller)
            answer = "\n".join(t for row in turns for t in row.get("reply", []))
            missing = [t for t in case.get("stored", []) if t not in stored]
            leaked = [t for t in case.get("not_stored", []) if t in stored or t in pending]
            unanswered = [t for t in case.get("recalled", []) if t not in answer]
            literal = "pending_blind_review" if case["category"] == "persona" else (
                "pass" if not (missing or leaked or unanswered) else "fail")
            return {"id": case["id"], "category": case["category"], "turns": turns, "stored": stored,
                    "pending": pending, "missing": missing, "leaked": leaked, "unanswered": unanswered,
                    "literal_status": literal, "rubric": case.get("rubric"), "calls": meter.case_calls}
        finally:
            service.close()
            controller.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=sorted(PRICES))
    parser.add_argument("--budget-usd", type=float, required=True)
    parser.add_argument("--reasoning", default="low")
    parser.add_argument("--api-key-env", default="EMOTI_HOLDOUT_API_KEY")
    parser.add_argument("--semantic-cache", type=Path)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    dataset = load_dataset(DATASET)
    cases = [c for c in dataset["cases"] if not args.case or c["id"] in args.case]
    meter = Meter(args.model, args.budget_usd, args.reasoning)
    def new_client():
        return OpenAIResponsesClient(api_key=os.environ[args.api_key_env], model=args.model,
                                     timeout_seconds=60, transport=meter)

    report = {"dataset_version": dataset["version"], "model": args.model, "reasoning": args.reasoning,
              "semantic": bool(args.semantic_cache), "persona_behavior": "pending_blind_review", "results": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        if meter.spent >= meter.budget:
            report["stopped"] = "budget"
            break
        report["results"].append(run_case(app, case, new_client, meter, args.semantic_cache))
        report["usage"] = {"calls": meter.calls, "input_tokens": meter.input_tokens, "output_tokens": meter.output_tokens,
                           "reasoning_tokens": meter.reasoning_tokens, "estimated_cost_usd": round(meter.spent, 4)}
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(case["id"], report["results"][-1]["literal_status"], report["usage"]["estimated_cost_usd"], flush=True)
    summary: dict[str, dict[str, int]] = {}
    for row in report["results"]:
        bucket = summary.setdefault(row["category"], {})
        bucket[row["literal_status"]] = bucket.get(row["literal_status"], 0) + 1
    report["summary"] = summary
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"summary": summary, "usage": report.get("usage")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
