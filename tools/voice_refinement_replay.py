from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from companion_flash_eval import Meter
from guanghe_companion.expression_clients import client_config_from_settings
from guanghe_companion.expression_refinement import review_rules
from guanghe_companion.expression_settings import ExpressionSettingsStore


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sources():
    teacher_path = "docs/modernization/evidence/teacher-correction-20261030/after.json"
    teacher = load(teacher_path)["stages"][0]["calls"][-1]
    payload = json.loads(teacher["messages"][-1]["content"])
    payload["draft"] = {"type": "speech", "speech": json.loads(teacher["answer"])["speech"]}
    yield {"id": "abrupt_name", "source": teacher_path, "source_kind": "actual_final_answer_rechecked",
           "source_stage": "correction", "payload": payload}

    blame_path = "docs/modernization/evidence/community-voice-20261030/accepted-final.json"
    row = next(r for r in load(blame_path)["results"] if r["id"] == "holdout_corrected_plan")
    for index, call in enumerate(row["calls"]):
        if "那宁波就当是我随口猜错了" in call["messages"][-1]["content"]:
            payload = json.loads(call["messages"][-1]["content"])
            yield {"id": "unsupported_self_blame", "source": blame_path, "source_kind": "actual_review_input",
                   "source_case": row["id"], "source_call": index, "payload": payload}
            break
    else:
        raise ValueError("真实自责草稿记录缺失")

    advice_path = "docs/modernization/evidence/voice-ui-followup-20261030/voice-after.json"
    row = next(r for r in load(advice_path)["results"] if r["id"] == "persona_game")
    for index, call in enumerate(row["calls"]):
        if "要不先歇一歇" in call["answer"]:
            # 旧记录没有结构化审阅证据，保留完整原请求，不重建或补造情境。
            payload = {"evidence": {"original_generation_prompt": call["messages"][-1]["content"]},
                       "draft": json.loads(call["answer"])}
            yield {"id": "unsolicited_rest_advice", "source": advice_path, "source_kind": "actual_draft_with_complete_original_prompt",
                   "source_case": row["id"], "source_call": index, "payload": payload}
            break
    else:
        raise ValueError("真实多余建议草稿记录缺失")


def main():
    parser = argparse.ArgumentParser(description="以相同真实历史草稿和证据对照旧新审阅规则")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", default="1f681e4")
    args = parser.parse_args()
    previous = subprocess.check_output(["git", "show", f"{args.baseline}:src/guanghe_companion/expression_refinement.py"],
                                       cwd=ROOT, text=True, encoding="utf-8")
    assignment = next(n for n in ast.parse(previous).body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "_REVIEW" for t in n.targets))
    old_rules = "\n".join(ast.literal_eval(assignment.value))
    settings = ExpressionSettingsStore(Path(os.environ["LOCALAPPDATA"]) / "E-Moti/expression_settings.json").load()
    if settings.model != "deepseek-flash":
        raise ValueError("需要应用的 deepseek-flash 配置")
    meter = Meter()
    client = client_config_from_settings(settings).client
    if client is None:
        raise ValueError("应用未配置模型凭据")
    client.transport = meter
    report = {"model": settings.model, "kind": "controlled_historical_draft_replay",
              "old_rules_revision": subprocess.check_output(["git", "rev-parse", args.baseline], cwd=ROOT, text=True).strip(),
              "results": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for row in sources():
            prompt = json.dumps(row["payload"], ensure_ascii=False, separators=(",", ":"))
            row["runs"] = []
            for label, rules in (("before", old_rules), ("after", review_rules())):
                first = len(meter.case_calls)
                answer = client.complete(prompt, system_prompt=rules)
                row["runs"].append({"label": label, "answer": answer, "calls": meter.case_calls[first:]})
                print(row["id"], label, answer, flush=True)
            report["results"].append(row)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
