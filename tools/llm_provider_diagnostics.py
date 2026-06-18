from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.expression_provider_diagnostics import (
    diagnose_expression_provider_settings,
)
from guanghe_companion.expression_settings import normalize_expression_settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check LLM expression provider settings without printing secrets."
    )
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--base-url", default="https://api.deepseek.com")
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    settings = normalize_expression_settings(
        {
            "enabled": True,
            "provider": args.provider,
            "model": args.model,
            "base_url": args.base_url,
            "api_key": os.environ.get(args.api_key_env, ""),
            "timeout_seconds": args.timeout_seconds,
        }
    )
    report = diagnose_expression_provider_settings(settings).to_public_dict()
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
