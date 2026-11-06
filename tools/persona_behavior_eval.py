from __future__ import annotations

"""Third persona layer: real multi-turn behaviour through DesktopDialogueService.

Layers one and two (config stability, delivery in the final prompt) are contract
tests in tests/test_persona_contract.py. This tool only reports what a real model
said. Raw replies are kept; an AI judge may be added but never replaces the two
independent human reviewers, whose status stays not_run until sheets are returned.

The key comes from an environment variable and is never written to the report.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from PySide6.QtWidgets import QApplication

from companion_live_eval import PRICES, BudgetExceeded, Meter, open_controller, turn
from guanghe_companion import persona as persona_module
from guanghe_companion.desktop_dialogue_service import DesktopDialogueService
from guanghe_companion.expression_clients import (OpenAICompatibleChatClient, OpenAIResponsesClient,
                                                   _default_transport)
from guanghe_companion.expression_settings import (DEFAULT_DEEPSEEK_EXPRESSION_BASE_URL,
                                                    DEFAULT_DEEPSEEK_EXPRESSION_MODEL)

DATA = ROOT / "docs" / "modernization" / "persona-behavior"


class CapturingMeter(Meter):
    """Keeps the prompt that actually left the process, for layer-two evidence."""

    def __init__(self, *args):
        super().__init__(*args)
        self.prompts: list[str] = []

    def __call__(self, request, timeout):
        self.prompts.append(json.dumps(json.loads(request.data).get("input", ""), ensure_ascii=False))
        return super().__call__(request, timeout)


class FlashMeter:
    """DeepSeek has no price table here: spending is capped by calls, cost is not reported."""

    def __init__(self, max_calls: int):
        self.max_calls, self.calls, self.input_tokens, self.output_tokens = max_calls, 0, 0, 0
        self.reasoning_tokens, self.spent, self.budget = 0, 0.0, 1.0
        self.case_calls: list[dict] = []
        self.prompts: list[str] = []

    def __call__(self, request, timeout):
        if self.calls >= self.max_calls:
            self.spent = self.budget
            raise BudgetExceeded(f"call cap {self.max_calls} reached")
        self.prompts.append(json.dumps(json.loads(request.data).get("messages", ""), ensure_ascii=False))
        started = time.perf_counter()
        raw = _default_transport(request, timeout)
        usage = json.loads(raw).get("usage") or {}
        self.calls += 1
        self.input_tokens += usage.get("prompt_tokens", 0)
        self.output_tokens += usage.get("completion_tokens", 0)
        self.case_calls.append({"latency_ms": round((time.perf_counter() - started) * 1000), "usage": usage})
        return raw


def run_scenario(app, scenario: dict, new_client, meter: CapturingMeter) -> dict:
    meter.case_calls, meter.prompts = [], []
    with tempfile.TemporaryDirectory(prefix="emoti-persona-") as temp:
        controller = open_controller(Path(temp), new_client)
        service = DesktopDialogueService(controller)
        try:
            controller.now = 100
            for text in scenario.get("seed", []):
                controller.memory_album_controller.remember_explicit(
                    text, now=int(controller.now), expected_epoch=controller.story_runtime.memory.store.context_epoch)
            turns = []
            for offset, text in enumerate(scenario["turns"], 1):
                controller.now = 100 + offset * 100
                statuses = []
                capture = lambda _result: statuses.append(
                    getattr(controller.story_runtime.memory.last_retrieval_trace, "status", "not_run"))
                service.memory_committed.connect(capture)
                row = turn(app, controller, service, text)
                service.memory_committed.disconnect(capture)
                row["retrieval_status"] = statuses[-1] if statuses else "not_run"
                turns.append(row)
            persona = controller._persona_payload
            # 事实抽取调用本来就不带人格，只检查表达调用。
            expression = [prompt for prompt in meter.prompts if "player_message" in prompt]
            return {"id": scenario["id"], "dimensions": scenario["dimensions"], "turns": turns,
                    "persona_hash": persona["config_hash"], "persona_source": persona["source"],
                    "persona_in_prompt": bool(expression) and all(persona["identity_version"] in p for p in expression),
                    "model_status": "completed" if meter.case_calls and not any(
                        row.get("error") or row.get("fallback") for row in turns) else "failed" if meter.case_calls else "not_run",
                    "calls": meter.case_calls}
        finally:
            service.close()
            controller.close()


def judge(scenarios: list[dict], rubric: dict, client, meter: CapturingMeter) -> list[dict]:
    """AI-assisted scoring. It widens coverage; it is not a human review."""
    rules = json.dumps(rubric["dimensions"], ensure_ascii=False)
    scored = []
    for row in scenarios:
        if meter.spent >= meter.budget:
            scored.append({"id": row["id"], "status": "not_run", "reason": "budget"})
            continue
        dialogue = [{"user": t["text"], "reply": t.get("reply")} for t in row["turns"]]
        prompt = ("你是中文对话评审。严格按评分表给这段桌面伙伴对话打分，0/1/2 或 na，并为每个非 2 分引用原句说明。"
                  "只输出 JSON：{\"scores\":{维度id:{\"score\":..,\"quote\":..,\"why\":..}}}。\n"
                  f"评分表：{rules}\n只需要评这些维度：{row['dimensions']}\n对话：{json.dumps(dialogue, ensure_ascii=False)}")
        try:
            scored.append({"id": row["id"], "status": "completed", "raw": client(prompt)})
        except BudgetExceeded:
            scored.append({"id": row["id"], "status": "not_run", "reason": "budget"})
    return scored


def write_blind_sheets(report: dict, out: Path, seed: int) -> None:
    """Reviewer sheets carry no run label, so before and after cannot be told apart."""
    rows = [(label, row) for label, run in report["runs"].items() for row in run["results"]]
    random.Random(seed).shuffle(rows)
    key, lines = {}, ["# 人格行为盲评表", "", "按 rubric.json 为每段打 0/1/2/na，并填写事实正确、自然度、有用性、打扰程度。", ""]
    for index, (label, row) in enumerate(rows, 1):
        key[f"S{index:03d}"] = {"run": label, "scenario": row["id"]}
        lines += [f"## S{index:03d}", f"需评维度：{', '.join(row['dimensions'])}", ""]
        for item in row["turns"]:
            lines += [f"- 用户：{item['text']}", f"- 星汐：{' / '.join(item.get('reply') or ['（无回答）'])}"]
        lines += ["", "评分：", ""]
    (out / "blind-review-sheet.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "blind-review-key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_DEEPSEEK_EXPRESSION_MODEL)
    parser.add_argument("--provider", choices=("deepseek", "openai"), default="deepseek")
    parser.add_argument("--budget-usd", type=float, default=0.0, help="openai only")
    parser.add_argument("--max-calls", type=int, default=400, help="deepseek only")
    parser.add_argument("--reasoning", default="low")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--scenario", action="append", default=[])
    parser.add_argument("--with-baseline", action="store_true", help="also run without persona.json for comparison")
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--seed", type=int, default=20261101)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    rubric_bytes = (DATA / "rubric.json").read_bytes()
    rubric = json.loads(rubric_bytes)
    scenarios = json.loads((DATA / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
    scenarios = [row for row in scenarios if not args.scenario or row["id"] in args.scenario]
    meter = (FlashMeter(args.max_calls) if args.provider == "deepseek"
             else CapturingMeter(args.model, args.budget_usd, args.reasoning))

    def new_client():
        if args.provider == "deepseek":
            return OpenAICompatibleChatClient(api_key=os.environ[args.api_key_env], model=args.model,
                                              base_url=DEFAULT_DEEPSEEK_EXPRESSION_BASE_URL, timeout_seconds=60,
                                              transport=meter, json_response=True, max_tokens=4096)
        return OpenAIResponsesClient(api_key=os.environ[args.api_key_env], model=args.model,
                                     timeout_seconds=60, transport=meter)

    report = {"rubric_version": rubric["rubric_version"], "rubric_sha256": hashlib.sha256(rubric_bytes).hexdigest(),
              "model": args.model, "reasoning": args.reasoning, "work_plugins": "off",
              "human_review": "not_run", "ai_judge": "not_run", "runs": {}}
    args.output.mkdir(parents=True, exist_ok=True)
    report_path = args.output / "raw-results.json"
    labels = ["persona_v1"] + (["baseline_no_persona_file"] if args.with_baseline else [])
    original = persona_module._read_persona_config
    for label in labels:
        if label.startswith("baseline"):
            persona_module._read_persona_config = lambda *_: (None, "")
        results = []
        for scenario in scenarios:
            if meter.spent >= meter.budget:
                report["stopped"] = "budget"
                break
            try:
                results.append(run_scenario(app, scenario, new_client, meter))
            except BudgetExceeded:
                report["stopped"] = "budget"
                break
            report["runs"][label] = {"results": results}
            report["usage"] = {"calls": meter.calls, "input_tokens": meter.input_tokens,
                               "output_tokens": meter.output_tokens, "reasoning_tokens": meter.reasoning_tokens,
                               "estimated_cost_usd": round(meter.spent, 4) if args.provider == "openai" else "not_priced"}
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
            print(label, scenario["id"], results[-1]["model_status"], meter.calls, flush=True)
        persona_module._read_persona_config = original
    if args.judge:
        client = new_client()
        report["ai_judge"] = {"status": "completed", "note": "AI 辅助，未经人工校准，不算人工评审",
                              "scores": judge(report["runs"]["persona_v1"]["results"], rubric, client, meter)}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    write_blind_sheets(report, args.output, args.seed)
    print(json.dumps(report.get("usage"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
