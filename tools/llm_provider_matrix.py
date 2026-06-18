from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.expression_clients import LLMProviderError, fetch_provider_model_ids
from guanghe_companion.expression_settings import provider_default_base_url, provider_default_model


ModelFetcher = Callable[..., tuple[str, ...]]

PROVIDER_ENV_VARS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "custom": "E_MOTI_LLM_API_KEY",
}
PROVIDERS = ("deepseek", "openrouter", "ollama", "lmstudio", "custom")


def build_provider_matrix(
    *,
    env: Mapping[str, str] | None = None,
    dry_run: bool,
    timeout_seconds: float = 2.0,
    model_fetcher: ModelFetcher = fetch_provider_model_ids,
) -> dict[str, Any]:
    source = os.environ if env is None else env
    provider_reports = [
        _provider_report(
            provider=provider,
            env=source,
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
            model_fetcher=model_fetcher,
        )
        for provider in PROVIDERS
    ]
    ready_count = sum(1 for item in provider_reports if item["status"] == "ready")
    return {
        "ok": ready_count > 0,
        "dry_run": dry_run,
        "provider_count": len(provider_reports),
        "ready_count": ready_count,
        "providers": provider_reports,
        "next_actions": _next_actions(provider_reports),
    }


def _provider_report(
    *,
    provider: str,
    env: Mapping[str, str],
    dry_run: bool,
    timeout_seconds: float,
    model_fetcher: ModelFetcher,
) -> dict[str, Any]:
    api_key_env = PROVIDER_ENV_VARS.get(provider, "")
    api_key = str(env.get(api_key_env, "")) if api_key_env else ""
    requires_key = provider in {"deepseek", "openrouter"}
    base_url = provider_default_base_url(provider)
    model = provider_default_model(provider)
    if dry_run:
        status = _dry_run_status(provider=provider, api_key=api_key, requires_key=requires_key)
        return _report(
            provider=provider,
            status=status,
            model=model,
            base_url=base_url,
            api_key_env=api_key_env,
            api_key_set=bool(api_key),
            live_tested=False,
            reasons=_dry_run_reasons(provider=provider, status=status),
        )
    if requires_key and not api_key:
        return _report(
            provider=provider,
            status="missing_api_key",
            model=model,
            base_url=base_url,
            api_key_env=api_key_env,
            api_key_set=False,
            live_tested=False,
            reasons=(f"set {api_key_env}",),
        )
    try:
        models = model_fetcher(
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
    except LLMProviderError as exc:
        status = _status_from_public_reason(exc.public_reason)
        return _report(
            provider=provider,
            status=status,
            model=model,
            base_url=base_url,
            api_key_env=api_key_env,
            api_key_set=bool(api_key),
            live_tested=True,
            reasons=(exc.public_reason,),
        )
    except Exception:
        return _report(
            provider=provider,
            status="not_configured",
            model=model,
            base_url=base_url,
            api_key_env=api_key_env,
            api_key_set=bool(api_key),
            live_tested=True,
            reasons=("provider_error",),
        )
    return _report(
        provider=provider,
        status="ready",
        model=model,
        base_url=base_url,
        api_key_env=api_key_env,
        api_key_set=bool(api_key),
        live_tested=True,
        reasons=(),
        model_ids=models[:10],
    )


def _dry_run_status(*, provider: str, api_key: str, requires_key: bool) -> str:
    if requires_key and not api_key:
        return "missing_api_key"
    if provider in {"ollama", "lmstudio"}:
        return "not_configured"
    if provider == "custom" and not api_key:
        return "not_configured"
    return "ready"


def _dry_run_reasons(*, provider: str, status: str) -> tuple[str, ...]:
    if status == "ready":
        return ("configuration present; live check not requested",)
    if status == "missing_api_key":
        return ("required API key environment variable is missing",)
    if provider in {"ollama", "lmstudio"}:
        return ("local server not probed in dry-run mode",)
    return ("provider not configured",)


def _status_from_public_reason(reason: str) -> str:
    if reason in {"http_401", "http_403"}:
        return "auth_failed"
    if reason == "http_429":
        return "quota_or_rate_limited"
    if reason == "timeout":
        return "timeout"
    if reason.startswith("invalid_response") or reason in {"empty_model_list"}:
        return "invalid_response"
    return "not_configured"


def _report(
    *,
    provider: str,
    status: str,
    model: str,
    base_url: str,
    api_key_env: str,
    api_key_set: bool,
    live_tested: bool,
    reasons: tuple[str, ...],
    model_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "provider": provider,
        "status": status,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "api_key_set": api_key_set,
        "live_tested": live_tested,
        "model_ids": list(model_ids),
        "reasons": list(reasons),
    }


def _next_actions(provider_reports: list[dict[str, Any]]) -> list[str]:
    if any(item["status"] == "ready" for item in provider_reports):
        return []
    actions = ["configure at least one LLM provider or start a local OpenAI-compatible server"]
    if any(item["status"] == "missing_api_key" for item in provider_reports):
        actions.append("set the provider API key in the local environment and rerun the matrix")
    return actions


def _markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# LLM Provider Matrix",
        "",
        f"- Dry run: `{str(payload['dry_run']).lower()}`",
        f"- Ready providers: `{payload['ready_count']}` / `{payload['provider_count']}`",
        "",
        "### Provider Matrix",
        "",
        "| Provider | Status | Live tested | API key env | API key set | Reasons |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in payload["providers"]:
        reasons = ", ".join(item["reasons"]) if item["reasons"] else ""
        lines.append(
            "| {provider} | {status} | {live_tested} | {api_key_env} | {api_key_set} | {reasons} |".format(
                provider=item["provider"],
                status=item["status"],
                live_tested=str(item["live_tested"]).lower(),
                api_key_env=item["api_key_env"] or "-",
                api_key_set=str(item["api_key_set"]).lower(),
                reasons=reasons,
            )
        )
    if payload["next_actions"]:
        lines.extend(["", "## Next Actions", ""])
        lines.extend(f"- {action}" for action in payload["next_actions"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize available LLM expression provider routes.")
    parser.add_argument("--dry-run", action="store_true", help="Do not call provider endpoints.")
    parser.add_argument("--timeout-seconds", type=float, default=2.0)
    parser.add_argument("--report", default="")
    parser.add_argument("--markdown", default="")
    args = parser.parse_args(argv)

    payload = build_provider_matrix(dry_run=bool(args.dry_run), timeout_seconds=args.timeout_seconds)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text + "\n", encoding="utf-8")
    if args.markdown:
        markdown_path = Path(args.markdown)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(_markdown(payload), encoding="utf-8")
    print(text)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
