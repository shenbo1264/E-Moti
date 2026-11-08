from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from PySide6.QtWidgets import QApplication

from companion_live_eval import BudgetExceeded, open_controller, turn
from eval_ondemand_generation import RecordingTransport, redact
from guanghe_companion import persona as persona_module
from guanghe_companion.desktop_dialogue_service import DesktopDialogueService
from guanghe_companion.expression_clients import MAX_OPENAI_RESPONSE_BYTES, _default_transport, client_config_from_settings
from guanghe_companion.expression_settings import ExpressionSettingsStore, provider_api_style

DATA = ROOT / "docs" / "modernization" / "persona-behavior"


class FlashMeter(RecordingTransport):
    def __init__(self, max_calls: int, api_style: str = "chat", journal_path: Path | None = None, secret: str = ""):
        super().__init__(delegate=_default_transport, api_style=api_style, max_output_tokens=4096)
        self.max_calls = max_calls
        self.journal_path, self.secret = journal_path, secret

    def __call__(self, request, timeout):
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"call cap {self.max_calls} reached")
        try:
            return super().__call__(request, timeout)
        except Exception as exc:
            record = self.records[-1]
            record["error_type"] = type(exc).__name__
            if isinstance(exc, HTTPError):
                record["http_status"] = exc.code
                record["raw_response_text"] = exc.read(MAX_OPENAI_RESPONSE_BYTES).decode("utf-8", errors="replace")
            raise
        finally:
            if self.journal_path is not None:
                # 每次实际请求立即保存，避免后续窗口/场景清理错误丢失已付费的原始证据。
                pending = self.journal_path.with_suffix(".pending")
                pending.write_text(json.dumps(redact({"calls": self.records}, self.secret), ensure_ascii=False, indent=1), encoding="utf-8")
                pending.replace(self.journal_path)


def measured_usage(meter):
    result = {"calls": meter.calls, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0,
              "estimated_cost_usd": "not_priced", "transport_latency_ms": 0.0}
    for call in meter.records:
        usage = call.get("provider_response", {}).get("usage") or {}
        result["input_tokens"] += usage.get("prompt_tokens", usage.get("input_tokens", 0))
        result["output_tokens"] += usage.get("completion_tokens", usage.get("output_tokens", 0))
        details = usage.get("completion_tokens_details", usage.get("output_tokens_details")) or {}
        result["reasoning_tokens"] += details.get("reasoning_tokens", 0)
        result["transport_latency_ms"] += call.get("transport_latency_ms", 0.0)
    return result


def run_scenario(app, scenario: dict, new_client, meter: FlashMeter, archive_root: Path) -> dict:
    start = len(meter.records)
    archive_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="emoti-persona-", dir=archive_root) as temp:
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
                call_start = len(meter.records)
                row = turn(app, controller, service, text)
                service.memory_committed.disconnect(capture)
                row["retrieval_status"] = statuses[-1] if statuses else "not_run"
                row["provider_call_indices"] = list(range(call_start, len(meter.records)))
                row["model_status"] = ("failed" if row.get("error") or row.get("fallback") else
                                       "completed" if row["provider_call_indices"] else "not_run")
                turns.append(row)
            persona = controller._persona_payload
            # 事实抽取调用本来就不带人格，只检查表达调用。
            calls = meter.records[start:]
            prompts = [json.dumps(call["wire_payload"], ensure_ascii=False) for call in calls]
            expression = [prompt for prompt in prompts if "player_message" in prompt]
            return {"id": scenario["id"], "dimensions": scenario["dimensions"], "seed": scenario.get("seed", []), "turns": turns,
                    "persona_hash": persona["config_hash"], "persona_source": persona["source"],
                    "persona_in_prompt": bool(expression) and all(persona["identity_version"] in p for p in expression),
                    "model_status": "completed" if calls and not any(
                        row.get("error") or row.get("fallback") for row in turns) else "failed" if calls else "not_run",
                    "calls": calls}
        finally:
            service.close()
            controller.close()


def judge(scenarios: list[dict], rubric: dict, client, meter: FlashMeter) -> list[dict]:
    """AI-assisted scoring. It widens coverage; it is not a human review."""
    rules = json.dumps(rubric["dimensions"], ensure_ascii=False)
    scored = []
    for row in scenarios:
        if meter.calls >= meter.max_calls:
            scored.append({"id": row["id"], "status": "not_run", "reason": "budget"})
            continue
        dialogue = [{"user": t["text"], "reply": t.get("reply")} for t in row["turns"]]
        prompt = ("你是中文对话评审。严格按评分表给这段桌面伙伴对话打分，0/1/2 或 na，并为每个非 2 分引用原句说明。"
                  "只输出 JSON：{\"scores\":{维度id:{\"score\":..,\"quote\":..,\"why\":..}}}。\n"
                  f"评分表：{rules}\n只需要评这些维度：{row['dimensions']}\n对话：{json.dumps(dialogue, ensure_ascii=False)}")
        try:
            start = len(meter.records)
            scored.append({"id": row["id"], "status": "completed", "raw": client(prompt), "calls": meter.records[start:]})
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="通过桌面对话链采集真实人格行为与完整 provider 证据")
    parser.add_argument("--app-settings", type=Path, required=True)
    parser.add_argument("--max-calls", type=int, default=400)
    parser.add_argument("--scenario", action="append", default=[])
    parser.add_argument("--with-baseline", action="store_true", help="same-code persona.json configuration ablation, not old-code comparison")
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--seed", type=int, default=20261101)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.max_calls < 1:
        parser.error("--max-calls must be positive")
    if not args.app_settings.is_file():
        parser.error("application settings file is missing")
    if not args.output.resolve().is_relative_to(ROOT):
        parser.error("output and temporary archives must stay inside this project")
    if (args.output / "raw-results.json").exists() or (args.output / "provider-calls.json").exists():
        parser.error("output already contains evidence; select a new directory")
    args.output.mkdir(parents=True, exist_ok=True)
    settings = ExpressionSettingsStore(args.app_settings).load()
    if not settings.enabled:
        parser.error("application model configuration is disabled")
    app = QApplication.instance() or QApplication([])
    rubric_bytes = (DATA / "rubric.json").read_bytes()
    rubric = json.loads(rubric_bytes)
    scenarios = json.loads((DATA / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
    unknown = set(args.scenario) - {row["id"] for row in scenarios}
    if unknown:
        parser.error("unknown scenario ids: " + ", ".join(sorted(unknown)))
    scenarios = [row for row in scenarios if not args.scenario or row["id"] in args.scenario]
    style = "responses" if provider_api_style(settings.provider) == "responses" else "chat"
    meter = FlashMeter(args.max_calls, api_style=style, journal_path=args.output / "provider-calls.json", secret=settings.api_key)

    def new_client():
        client = client_config_from_settings(settings).client
        if client is None:
            raise ValueError("application settings do not provide an enabled model client")
        client.transport = meter
        return client

    report = {"rubric_version": rubric["rubric_version"], "rubric_sha256": hashlib.sha256(rubric_bytes).hexdigest(),
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "model": settings.model, "work_plugins": "off",
              "provider": {"requested_model": settings.model, "base_url": settings.base_url,
                           "api_style": style, "credential_source": "app_settings", "transport": "real_http",
                           "timeout_seconds": settings.timeout_seconds, "max_calls": args.max_calls},
              "comparison": "same-code persona configuration ablation; not historical code or independent unseen sample",
              "selected_scenarios": [row["id"] for row in scenarios],
              "human_review": "not_run", "ai_judge": "not_run", "runs": {}}
    args.output.mkdir(parents=True, exist_ok=True)
    report_path = args.output / "raw-results.json"
    labels = ["persona_v1"] + (["baseline_no_persona_file"] if args.with_baseline else [])
    original = persona_module._read_persona_config
    try:
        for label in labels:
            persona_module._read_persona_config = (lambda *_: (None, "")) if label.startswith("baseline") else original
            results = []
            report["runs"][label] = {"results": results}
            for scenario in scenarios:
                if meter.calls >= meter.max_calls:
                    report["stopped"] = "budget"
                    results.append({"id": scenario["id"], "dimensions": scenario["dimensions"],
                                    "turns": [], "calls": [], "model_status": "not_run", "reason": "budget"})
                else:
                    results.append(run_scenario(app, scenario, new_client, meter, args.output / "temporary-archives"))
                report["usage"] = measured_usage(meter)
                report_path.write_text(json.dumps(redact(report, settings.api_key), ensure_ascii=False, indent=1), encoding="utf-8")
                print(label, scenario["id"], results[-1]["model_status"], meter.calls, flush=True)
    finally:
        persona_module._read_persona_config = original
    if args.judge:
        client = new_client()
        try:
            report["ai_judge"] = {"status": "completed", "note": "AI 辅助，未经人工校准，不算人工评审",
                                  "scores": judge(report["runs"]["persona_v1"]["results"], rubric, client, meter)}
        finally:
            client.close()
    report["usage"] = measured_usage(meter)
    report_path.write_text(json.dumps(redact(report, settings.api_key), ensure_ascii=False, indent=1), encoding="utf-8")
    write_blind_sheets(report, args.output, args.seed)
    print(json.dumps(report.get("usage"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
