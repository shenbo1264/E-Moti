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

from guanghe_companion.expression_settings import (
    provider_default_base_url,
    provider_default_model,
)
from guanghe_companion.llm_smoke import DEFAULT_LLM_SMOKE_PROMPTS, run_llm_dialogue_smoke


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an LLM dialogue smoke check with a temporary save directory.")
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--api-key-env", default="")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--prompt", action="append", default=[])
    return parser.parse_args(argv)


def _api_key_from_env(provider: str, api_key_env: str, env: dict[str, str]) -> str:
    if api_key_env:
        return env.get(api_key_env, "")
    if provider == "deepseek" and env.get("DEEPSEEK_API_KEY"):
        return env["DEEPSEEK_API_KEY"]
    return env.get("E_MOTI_LLM_API_KEY", "")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    provider = str(args.provider).strip().lower()
    settings = {
        "enabled": True,
        "provider": provider,
        "model": args.model or provider_default_model(provider),
        "base_url": args.base_url or provider_default_base_url(provider),
        "api_key": _api_key_from_env(provider, args.api_key_env, os.environ),
        "timeout_seconds": args.timeout_seconds,
    }
    prompts = tuple(args.prompt) if args.prompt else DEFAULT_LLM_SMOKE_PROMPTS
    report = run_llm_dialogue_smoke(settings, prompts=prompts)
    print(json.dumps(report.to_public_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
