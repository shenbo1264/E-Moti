from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .expression_settings import ExpressionSettings


@dataclass(frozen=True, slots=True)
class ExpressionProviderDiagnosticReport:
    ok: bool
    status: str
    provider: str
    model: str
    base_url: str
    timeout_seconds: float
    reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "timeout_seconds": self.timeout_seconds,
            "reasons": list(self.reasons),
        }


def diagnose_expression_provider_settings(
    settings: ExpressionSettings,
) -> ExpressionProviderDiagnosticReport:
    reasons: list[str] = []
    if not settings.enabled:
        reasons.append("expression provider is disabled")
        return _report(settings, ok=False, status="disabled", reasons=reasons)
    if not settings.api_key.strip():
        reasons.append("api key is missing")
        return _report(settings, ok=False, status="missing_api_key", reasons=reasons)
    if settings.timeout_seconds <= 0:
        reasons.append("timeout_seconds must be positive")
        return _report(settings, ok=False, status="invalid_timeout", reasons=reasons)
    return _report(settings, ok=True, status="ready", reasons=reasons)


def _report(
    settings: ExpressionSettings,
    *,
    ok: bool,
    status: str,
    reasons: list[str],
) -> ExpressionProviderDiagnosticReport:
    return ExpressionProviderDiagnosticReport(
        ok=ok,
        status=status,
        provider=settings.provider,
        model=settings.model,
        base_url=settings.base_url,
        timeout_seconds=settings.timeout_seconds,
        reasons=tuple(reasons),
    )
