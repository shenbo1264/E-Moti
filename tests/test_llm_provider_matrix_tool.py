from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "llm_provider_matrix.py"


def test_llm_provider_matrix_dry_run_reports_missing_and_configured_providers(tmp_path: Path) -> None:
    report = tmp_path / "matrix.json"
    markdown = tmp_path / "matrix.md"

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--dry-run",
            "--report",
            str(report),
            "--markdown",
            str(markdown),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={},
    )

    assert result.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    statuses = {item["provider"]: item["status"] for item in payload["providers"]}
    assert payload["ok"] is False
    assert payload["dry_run"] is True
    assert statuses["deepseek"] == "missing_api_key"
    assert statuses["openrouter"] == "missing_api_key"
    assert statuses["ollama"] == "not_configured"
    assert statuses["lmstudio"] == "not_configured"
    assert statuses["custom"] == "not_configured"
    assert "sk-" not in result.stdout
    assert "### Provider Matrix" in markdown.read_text(encoding="utf-8")


def test_llm_provider_matrix_live_classifies_fetch_errors_without_secret() -> None:
    from tools.llm_provider_matrix import build_provider_matrix

    def fake_fetcher(*, provider, base_url, api_key, timeout_seconds):
        if provider == "deepseek":
            raise RuntimeError("unexpected generic failure")
        if provider == "openrouter":
            from guanghe_companion.expression_clients import LLMProviderError

            raise LLMProviderError("model list fetch failed: http_429", public_reason="http_429")
        if provider == "ollama":
            from guanghe_companion.expression_clients import LLMProviderError

            raise LLMProviderError("model list fetch failed: network_error", public_reason="network_error")
        return ("model-a",)

    payload = build_provider_matrix(
        env={
            "DEEPSEEK_API_KEY": "sk-secret",
            "OPENROUTER_API_KEY": "sk-openrouter",
            "E_MOTI_LLM_API_KEY": "custom-secret",
        },
        dry_run=False,
        model_fetcher=fake_fetcher,
    )

    statuses = {item["provider"]: item["status"] for item in payload["providers"]}
    assert statuses["deepseek"] == "not_configured"
    assert statuses["openrouter"] == "quota_or_rate_limited"
    assert statuses["ollama"] == "not_configured"
    assert statuses["lmstudio"] == "ready"
    assert statuses["custom"] == "ready"
    assert "sk-secret" not in str(payload)
