from __future__ import annotations

from guanghe_companion.expression_provider_diagnostics import (
    diagnose_expression_provider_settings,
)
from guanghe_companion.expression_settings import normalize_expression_settings


def test_diagnostics_reports_disabled_provider_without_secret() -> None:
    settings = normalize_expression_settings({"enabled": False, "api_key": "sk-secret"})

    report = diagnose_expression_provider_settings(settings)

    assert report.ok is False
    assert report.status == "disabled"
    assert "expression provider is disabled" in report.reasons
    assert "sk-secret" not in report.to_public_dict().__repr__()


def test_diagnostics_accepts_deepseek_openai_compatible_settings() -> None:
    settings = normalize_expression_settings(
        {
            "enabled": True,
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-secret",
            "timeout_seconds": 45,
        }
    )

    report = diagnose_expression_provider_settings(settings)

    assert report.ok is True
    assert report.status == "ready"
    assert report.provider == "deepseek"
    assert report.model == "deepseek-v4-flash"
    assert "sk-secret" not in str(report.to_public_dict())


def test_diagnostics_rejects_enabled_provider_without_key() -> None:
    settings = normalize_expression_settings(
        {
            "enabled": True,
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "api_key": "",
        }
    )

    report = diagnose_expression_provider_settings(settings)

    assert report.ok is False
    assert report.status == "missing_api_key"
    assert "api key is missing" in report.reasons
