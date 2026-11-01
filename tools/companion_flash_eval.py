from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
from PySide6.QtWidgets import QApplication


class Meter:
    def __init__(self):
        self.case_calls = []

    def __call__(self, request, timeout):
        from guanghe_companion.expression_clients import _default_transport

        body = json.loads(request.data)
        started = time.perf_counter()
        raw = _default_transport(request, timeout)
        response = json.loads(raw)
        self.case_calls.append({
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "usage": response.get("usage"), "model": response.get("model"),
            "messages": body.get("messages"),
            "response_format": body.get("response_format"), "max_tokens": body.get("max_tokens"),
            "answer": response["choices"][0]["message"].get("content"),
        })
        return raw


def main():
    parser = argparse.ArgumentParser(description="用应用当前 Flash 配置复测合成陪伴样本，保存真实输出，不记录密钥。")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo / "src"))
    from companion_live_eval import run_case
    from guanghe_companion.expression_clients import client_config_from_settings
    from guanghe_companion.expression_settings import ExpressionSettingsStore

    settings = ExpressionSettingsStore(
        Path(os.environ["LOCALAPPDATA"]) / "E-Moti/expression_settings.json"
    ).load()
    if settings.model != "deepseek-flash":
        raise ValueError("应用模型必须为用户指定的 deepseek-flash")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = ROOT / "artifacts/codex_handoff/persona-refinement/temp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(temporary_root)
    meter = Meter()

    def new_client():
        client = client_config_from_settings(settings).client
        if client is None:
            raise ValueError("应用模型未启用或缺少凭据")
        client.transport = meter
        return client

    cases = json.loads(args.dataset.read_text(encoding="utf-8"))["cases"]
    if args.case:
        cases = [case for case in cases if case["id"] in args.case]
    app = QApplication.instance() or QApplication([])
    report = {
        "model": settings.model, "timeout_seconds": settings.timeout_seconds,
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.repo, text=True).strip(),
        "working_changes": subprocess.check_output(["git", "diff", "--name-only"], cwd=args.repo, text=True).splitlines(),
        "dataset": args.dataset.name, "results": [],
    }
    for case in cases:
        started = time.perf_counter()
        row = run_case(app, case, new_client, meter, ROOT / "artifacts/codex_handoff/embedding-models")
        row["case_elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        report["results"].append(row)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(case["id"], row["model_status"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
