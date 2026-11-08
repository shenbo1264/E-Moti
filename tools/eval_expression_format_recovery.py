from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.expression_parser import ExpressionPayloadError, parse_shinsekai_object_stream
from guanghe_companion.expression_request import ExpressionRequest
from eval_ondemand_generation import recorded_app_client, redact


def historical_expressor(commit):
    source = subprocess.check_output(["git", "show", f"{commit}:src/guanghe_companion/expression_expressor.py"], cwd=ROOT)
    module = ModuleType("guanghe_companion._format_recovery_baseline")
    module.__package__ = "guanghe_companion"
    exec(compile(source, f"git:{commit}/expression_expressor.py", "exec"), module.__dict__)
    return module.ShinsekaiAIExpressor, hashlib.sha256(source).hexdigest()


def schema_status(text):
    try:
        return "valid" if parse_shinsekai_object_stream(text, None) else "invalid"
    except ExpressionPayloadError as exc:
        return exc.reason


def main():
    parser = argparse.ArgumentParser(description="真实表达链前后复测；历史失败回放与全新 HTTP 调用分开报告")
    parser.add_argument("--app-settings", type=Path, required=True)
    parser.add_argument("--baseline", default="2db87399c5ce070cce4919415a820d98362eec6e")
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "artifacts/codex_handoff/memory-upgrade/sealed-sixth-first")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    old_class, old_digest = historical_expressor(args.baseline)
    fixtures = {}
    for method in ("routed", "layered"):
        report = json.loads((args.evidence_dir / f"{method}-300.json").read_text(encoding="utf-8"))
        fixtures.update({(method, row["query_id"]): row for row in report["rows"]})
    failures = json.loads((args.evidence_dir / "generation-failures.json").read_text(encoding="utf-8"))
    jobs = [("recorded_failure_replay", row["method"], row["query_id"], row) for row in failures]
    jobs += [("fresh_http", method, query_id, None) for method, query_id in (
        ("routed", "v6_tour_q3"), ("layered", "v6_stars_q3"),
        ("routed", "v6_stars_q6"), ("routed", "v6_stars_q8"),
    )]
    output = {"scope": "seen-case regression; not independent generalization or human persona acceptance",
        "baseline_commit": args.baseline, "baseline_expressor_sha256": old_digest,
        "current_expressor_sha256": hashlib.sha256((ROOT / "src/guanghe_companion/expression_expressor.py").read_bytes()).hexdigest(),
        "rows": []}
    for label, klass in (("before", old_class), ("after", ShinsekaiAIExpressor)):
        for mode, method, query_id, failure in jobs:
            client, meter, provider, key = recorded_app_client(args.app_settings, max_requests=2)
            saved = fixtures[method, query_id]
            expression_request = ExpressionRequest(**saved["actual_expression_request"])
            replayed = []
            if failure:
                def replay_first(request, timeout):
                    if not replayed:
                        replayed.append({"origin": "recorded_provider_response", "wire_payload": json.loads(request.data),
                            "historical_wire_payload": failure["wire_payload"],
                            "provider_response": failure["provider_response"]})
                        return failure["raw_response_text"].encode("utf-8")
                    return meter(request, timeout)
                client.transport = replay_first
            started = perf_counter()
            with klass(llm_client=client, timeout_seconds=client.timeout_seconds) as expressor:
                events = expressor.express(expression_request)
                fallback = expressor.last_fallback_reason
            calls = replayed + meter.records
            draft = calls[0].get("provider_response", {}).get("choices", [{}])[0].get("message", {}).get("content", "") if calls else ""
            row = {"phase": label, "mode": mode, "method": method, "query_id": query_id,
                "query": expression_request.player_message, "provider": provider,
                "actual_requests": meter.calls, "replayed_requests": len(replayed),
                "raw_draft": draft, "raw_schema_status": schema_status(draft),
                "fallback_reason": fallback, "events": events, "calls": calls,
                "latency_ms": (perf_counter() - started) * 1000,
                "final_speech": "\n".join(event["speech"] for event in events if event.get("character_name") == expression_request.character_name),
                "answer_review": "pending_review"}
            output["rows"].append(redact(row, key))
            output["actual_requests"] = sum(item["actual_requests"] for item in output["rows"])
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
            print(label, mode, query_id, "requests", meter.calls, "fallback", fallback, flush=True)


if __name__ == "__main__":
    main()
