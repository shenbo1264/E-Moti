import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from guanghe_companion.expression_clients import client_config_from_settings
from guanghe_companion.expression_settings import ExpressionSettingsStore
from persona_behavior_eval import FlashMeter, measured_usage


def run(args):
    settings = ExpressionSettingsStore(args.app_settings).load()
    if settings.model != "deepseek-flash":
        raise ValueError("requires the configured Flash model")
    args.output.mkdir(parents=True, exist_ok=False)
    meter = FlashMeter(len(args.input), api_style="chat",
        journal_path=args.output / "provider-calls.json", secret=settings.api_key)
    client = client_config_from_settings(settings).client
    if client is None:
        raise ValueError("model client unavailable")
    client.transport = meter
    rows = []
    try:
        for path in args.input:
            original = json.loads(path.read_text(encoding="utf-8"))["calls"][-1]
            wire = original["wire_payload"]
            messages = wire["messages"]
            if [m["role"] for m in messages] != ["system", "user"]:
                raise ValueError("requires the original two-message extraction request")
            row = {"input": str(path), "before_finish_reason": original["provider_response"]["choices"][0]["finish_reason"],
                "before_usage": original["provider_response"].get("usage"), "status": "running"}
            rows.append(row)
            try:
                raw = client.complete(messages[1]["content"], system_prompt=messages[0]["content"],
                    reasoning_effort="none")
                value = json.loads(raw)
                row.update(status="completed", raw_output=raw,
                    proposals_shape_valid=isinstance(value, dict) and isinstance(value.get("proposals"), list))
            except Exception as exc:
                row.update(status="failed", error_type=type(exc).__name__)
            (args.output / "results.json").write_text(json.dumps({"rows": rows, "usage": measured_usage(meter),
                "scope": "same-input format comparison only; no memory writes or semantic acceptance"},
                ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--app-settings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())
