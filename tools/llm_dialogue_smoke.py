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
    provider_api_key_required,
    provider_api_style,
)
from guanghe_companion.llm_smoke import DEFAULT_LLM_CONVERSATION_SCENARIOS, run_llm_dialogue_smoke


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an LLM dialogue smoke check with a temporary save directory.")
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--api-key-env", default="")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--min-expression-actions", type=int, default=4)
    parser.add_argument("--min-motion-actions", type=int, default=3)
    parser.add_argument("--min-speech-chars", type=int, default=8)
    parser.add_argument("--max-speech-chars", type=int, default=80)
    parser.add_argument("--prompt", action="append", default=[])
    parser.add_argument("--report", default="", help="Optional UTF-8 JSON report path.")
    parser.add_argument("--dry-run", action="store_true", help="Print sanitized provider settings without API calls.")
    return parser.parse_args(argv)


def _api_key_from_env(provider: str, api_key_env: str, env: dict[str, str]) -> str:
    if api_key_env:
        return env.get(api_key_env, "")
    if provider == "deepseek" and env.get("DEEPSEEK_API_KEY"):
        return env["DEEPSEEK_API_KEY"]
    return env.get("E_MOTI_LLM_API_KEY", "")


def _emit_payload(payload: dict[str, object], report_path: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
    print(text)


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
    if args.dry_run:
        missing_key = provider_api_key_required(provider) and not settings["api_key"]
        payload = {
            "ok": not missing_key,
            "reason": "missing_api_key" if missing_key else "",
            "dry_run": True,
            "would_call_api": False,
            "provider": provider,
            "model": settings["model"],
            "base_url": settings["base_url"],
            "api_style": provider_api_style(provider),
            "api_key_set": bool(settings["api_key"]),
            "timeout_seconds": settings["timeout_seconds"],
            "scenario_version": DEFAULT_LLM_CONVERSATION_SCENARIOS.version,
            "scenario_count": len(DEFAULT_LLM_CONVERSATION_SCENARIOS.scenarios),
            "scenario_ids": [
                scenario.scenario_id for scenario in DEFAULT_LLM_CONVERSATION_SCENARIOS.scenarios
            ],
        }
        _emit_payload(payload, args.report)
        return 1 if missing_key else 0
    prompts = tuple(args.prompt) if args.prompt else None
    report = run_llm_dialogue_smoke(
        settings,
        prompts=prompts,
        min_expression_actions=args.min_expression_actions,
        min_motion_actions=args.min_motion_actions,
        min_speech_chars=args.min_speech_chars,
        max_speech_chars=args.max_speech_chars,
    )
    _emit_payload(report.to_public_dict(), args.report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
