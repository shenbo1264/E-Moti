from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.expression_clients import OpenAICompatibleChatClient, OpenAIResponsesClient, _default_transport
from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.expression_settings import ExpressionSettingsStore
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def load_dataset(path: Path, selected: list[str]) -> tuple[dict, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("kind") != "synthetic_frozen_holdout" or payload.get("version") != 1:
        raise ValueError("unsupported holdout dataset")
    cases = payload["cases"]
    ids = [case["id"] for case in cases]
    if not cases or len(ids) != len(set(ids)):
        raise ValueError("holdout cases must be nonempty with unique ids")
    if set(selected) - set(ids):
        raise ValueError("unknown case ids")
    return payload, [case for case in cases if not selected or case["id"] in selected]


def open_controller(root: Path, character_id: str = "xingxi_pixel_pet"):
    return PluginEnabledCompanionController(
        user_data_root=root, character_id=character_id,
        ai_expressor=ShinsekaiAIExpressor(enabled=False),
        expression_settings_store=ExpressionSettingsStore(root / "disabled-expression.json"),
    )


def build_case(case: dict, root: Path) -> dict:
    controller = open_controller(root)
    aliases = {}
    try:
        for index, step in enumerate(case["steps"], 1):
            controller.now = index * 100
            album = controller.memory_album_controller
            epoch = controller.story_runtime.memory.store.context_epoch
            operation = step["op"]
            if operation == "remember":
                before = {row.memory_id for row in controller.story_runtime.memory.store.load_memories()}
                album.remember_explicit(step["text"], now=controller.now, expected_epoch=epoch)
                aliases[step["id"]] = next(row.memory_id for row in controller.story_runtime.memory.store.load_memories() if row.memory_id not in before)
            elif operation == "correct":
                album.correct(aliases[step["id"]], title="用户更新的事实", summary=step["text"], now=controller.now, expected_epoch=epoch)
            elif operation == "forget":
                album.forget(aliases[step["id"]], now=controller.now, expected_epoch=epoch)
            elif operation == "consolidate":
                controller.story_runtime.memory.consolidate(now=controller.now)
            elif operation == "chat":
                controller.submit_dialogue_request(DialogueRequest(text=step["text"], source="holdout"), include_ai_expression=False)
            elif operation == "reopen":
                character_id = controller.state.character_id
                controller.close()
                controller = open_controller(root, character_id)
            elif operation == "switch":
                controller.switch_character(step["character_id"], include_ai_expression=False)
            else:
                raise ValueError(f"unknown holdout operation: {operation}")
        controller.now = 10000
        controller._current_player_message = case["query"]
        started = time.perf_counter()
        recalled = controller.story_runtime.memory.recall(case["query"], now=controller.now, top_k=4)
        context = controller.get_expression_context()
        current = ExpressionRequest.from_snapshot(controller.get_typed_snapshot(), context=context)
        # 两组都排除非记忆变量，避免角色包工具提示或上次本地反馈成为混杂因素。
        current = replace(current, feedback="", delta_text="", perception_summary="",
                          tool_results=(), plugin_context={})
        # 消融实验移除所有历史证据通道，保留同一人格、当前问题与表达预算。
        no_memory = replace(current, emotional_memory={}, recent_memory=(), recent_dialogue=(),
                            long_term_memory=())
        prompts = {"current_memory": controller.ai_expressor.build_prompt(current),
                   "no_memory": controller.ai_expressor.build_prompt(no_memory)}
        latency = (time.perf_counter() - started) * 1000
        required = case.get("required", [])
        forbidden = case.get("forbidden", [])
        retrieved_text = "\n".join(row.summary for row in recalled)
        return {
            "id": case["id"], "category": case["category"], "query": case["query"],
            "rubric": case.get("rubric", "依据有效事实作答；无证据时说明未知。"),
            "retrieved": [{"memory_id": row.memory_id, "summary": row.summary} for row in recalled],
            "retrieval_checks": [{"fragment": value, "passed": value in retrieved_text} for value in required],
            "prompt_checks": [{"fragment": value, "passed": value in prompts["current_memory"], "kind": "delivery"} for value in required]
                + [{"fragment": value, "passed": value not in prompts["current_memory"], "kind": "no_leak"} for value in forbidden],
            "context_and_prompt_latency_ms": latency,
            "persona_equal_between_arms": current.persona == no_memory.persona,
            "arms": {name: {"prompt": prompt, "model_status": "not_run"} for name, prompt in prompts.items()},
        }
    finally:
        controller.close()


class MeteredTransport:
    def __init__(self):
        self.usage = None
        self.response_model = None
        self.response_id = None

    def __call__(self, request, timeout):
        raw = _default_transport(request, timeout)
        payload = json.loads(raw)
        self.usage = payload.get("usage")
        self.response_model = payload.get("model")
        self.response_id = payload.get("id")
        return raw


def run_live(result: dict, case: dict, args) -> None:
    for arm in result["arms"].values():
        meter = MeteredTransport()
        client_type = OpenAIResponsesClient if args.api_style == "responses" else OpenAICompatibleChatClient
        kwargs = {"api_key": os.environ[args.api_key_env], "model": args.model,
                  "base_url": args.base_url, "timeout_seconds": args.timeout, "transport": meter}
        if args.api_style == "chat_completions":
            kwargs["max_tokens"] = 512
        started = time.perf_counter()
        with client_type(**kwargs) as client:
            answer = client(arm["prompt"])
        arm.update({"model_status": "completed", "raw_answer": answer,
                    "response_model": meter.response_model, "response_id": meter.response_id,
                    "provider_usage": meter.usage if meter.usage is not None else "not_reported",
                    "complete_response_latency_ms": (time.perf_counter() - started) * 1000,
                    "first_token_latency_ms": "not_measured_nonstreaming",
                    "answer_literal_checks": [{"fragment": value, "present": value in answer} for value in case.get("required", [])],
                    "forbidden_literal_hits": [value for value in case.get("forbidden", []) if value in answer],
                    "answer_correctness": "pending_blind_review", "persona_behavior": "pending_blind_review"})


def rate(checks: list[dict]) -> dict:
    return {"numerator": sum(row["passed"] for row in checks), "denominator": len(checks)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Frozen synthetic multi-session holdout; model calls require --live.")
    parser.add_argument("--dataset", type=Path, default=ROOT / "tests/fixtures/memory_holdout.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--api-style", choices=["responses", "chat_completions"], default="chat_completions")
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--api-key-env", default="EMOTI_HOLDOUT_API_KEY")
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args(argv)
    try:
        dataset, cases = load_dataset(args.dataset, args.case)
        if args.live and (not args.base_url or not args.model or not os.environ.get(args.api_key_env)):
            raise ValueError("--live requires --base-url, --model and the named API-key environment variable")
        if not 0 < args.timeout <= 60:
            raise ValueError("timeout must be in (0, 60]")
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))
    scratch = ROOT / "artifacts/codex_handoff/holdout"
    scratch.mkdir(parents=True, exist_ok=True)
    report = {"dataset_kind": dataset["kind"], "dataset_version": dataset["version"],
              "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
              "created_at": datetime.now(timezone.utc).isoformat(),
              "model_execution": "requested" if args.live else "not_run",
              "model_requested": args.model, "semantic_enhancement": "not_run", "results": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        with tempfile.TemporaryDirectory(dir=scratch, prefix="case-") as directory:
            result = build_case(case, Path(directory))
        report["results"].append(result)
        if args.live:
            try:
                run_live(result, case, args)
            except Exception as exc:
                # 实验失败需留下已完成样本；不重试计费请求，不将错误当作回答。
                result["model_error"] = {"type": type(exc).__name__, "reason": getattr(exc, "public_reason", "request_failed")}
                report["model_execution"] = "failed"
                args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                raise
    rows = report["results"]
    prompt_checks = [check for row in rows for check in row["prompt_checks"]]
    report["summary"] = {
        "cases": len(rows), "retrieval_hits": rate([check for row in rows for check in row["retrieval_checks"]]),
        "prompt_delivery": rate([check for check in prompt_checks if check["kind"] == "delivery"]),
        "prompt_no_leak": rate([check for check in prompt_checks if check["kind"] == "no_leak"]),
        "answer_correctness": "pending_blind_review" if args.live else "not_run",
        "persona_behavior": "pending_blind_review" if args.live else "not_run",
        "provider_usage": "per_response" if args.live else "not_run",
        "model_latency": "per_response" if args.live else "not_run",
        "answer_forgetting_leakage": "literal_hits_require_semantic_review" if args.live else "not_run",
    }
    if args.live:
        report["model_execution"] = "completed"
    report["local_contract_passed"] = all(check["passed"] for check in prompt_checks)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=True))
    return 0 if report["local_contract_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
