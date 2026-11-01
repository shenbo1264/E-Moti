from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from companion_flash_eval import Meter
from guanghe_companion.expression_clients import client_config_from_settings
from guanghe_companion.expression_refinement import review_rules
from guanghe_companion.expression_settings import ExpressionSettingsStore


def main():
    parser = argparse.ArgumentParser(description="对同一真实感谢代写错误回答回放旧新审阅规则")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = "docs/modernization/evidence/voice-followup-20261031/final.json"
    recorded = json.loads((ROOT / source).read_text(encoding="utf-8"))
    case = next(row for row in recorded["results"] if row["id"] == "help_control")
    original_review = case["calls"][-1]
    payload = json.loads(original_review["messages"][-1]["content"])
    speech = json.loads(original_review["answer"])["speech"]
    # 使用实际交付过的失败回答，不捏造模型草稿或缺失情境。
    payload["draft"] = {"type": "speech", "speech": speech}
    old_rules = next(m["content"] for m in original_review["messages"] if m["role"] == "system")
    settings = ExpressionSettingsStore(Path(os.environ["LOCALAPPDATA"]) / "E-Moti/expression_settings.json").load()
    if settings.model != "deepseek-flash":
        raise ValueError("需要应用的 deepseek-flash 配置")
    client = client_config_from_settings(settings).client
    if client is None:
        raise ValueError("应用未配置模型凭据")
    meter = Meter()
    client.transport = meter
    report = {"model": settings.model, "source": source, "source_case": "help_control",
              "source_kind": "actual_final_answer_rechecked", "original_speech": speech,
              "payload": payload, "runs": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for label, rules in (("before", old_rules), ("after", review_rules())):
            start = len(meter.case_calls)
            answer = client.complete(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), system_prompt=rules)
            report["runs"].append({"label": label, "answer": answer, "calls": meter.case_calls[start:]})
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(label, answer, flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
