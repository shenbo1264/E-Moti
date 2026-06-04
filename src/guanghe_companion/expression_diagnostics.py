from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from .ai_expressor import ExpressionRequest, fetch_provider_model_ids
from .events import CompanionEvent, EventValidator
from .expression_settings import (
    ExpressionSettings,
    normalize_expression_settings,
    provider_api_key_required,
)
from .models import CompanionState
from .snapshot import CompanionSnapshot


class ExpressionExpressor(Protocol):
    enabled: bool
    last_fallback_reason: str

    def express(self, snapshot: ExpressionRequest, effect: str | None = None) -> list[dict[str, str]]:
        ...


ModelFetcher = Callable[..., tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class ExpressionProviderDiagnosticResult:
    ok: bool
    stage: str
    reason: str
    provider: str
    model: str
    base_url: str
    timeout_seconds: float
    speech: str = ""
    effect: str = ""
    fallback_reason: str = ""

    def to_public_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "stage": self.stage,
            "reason": self.reason,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "timeout_seconds": self.timeout_seconds,
            "speech": self.speech,
            "effect": self.effect,
            "fallback_reason": self.fallback_reason,
        }


class ExpressionDiagnosticsService:
    def __init__(
        self,
        *,
        settings: ExpressionSettings,
        expressor: ExpressionExpressor,
        state_provider: Callable[[], CompanionState],
        snapshot_provider: Callable[[], CompanionSnapshot],
        context_provider: Callable[[], Mapping[str, object]],
        choices_provider: Callable[[], tuple[str, ...]],
        model_fetcher: ModelFetcher = fetch_provider_model_ids,
    ) -> None:
        self.settings = settings
        self.expressor = expressor
        self.state_provider = state_provider
        self.snapshot_provider = snapshot_provider
        self.context_provider = context_provider
        self.choices_provider = choices_provider
        self.model_fetcher = model_fetcher

    def test_provider(self) -> ExpressionProviderDiagnosticResult:
        settings_issue = self._settings_diagnostic_issue()
        if settings_issue:
            return self._result(ok=False, stage="settings", reason=settings_issue)

        request = ExpressionRequest.from_snapshot(
            self.snapshot_provider(),
            context=self.context_provider(),
        )
        try:
            expressed_events = self.expressor.express(request, effect="ATTENTION")
        except Exception:
            return self._result(ok=False, stage="provider_call", reason="provider_error")

        state = self.state_provider()
        validated_events = EventValidator(state).validate(
            events=expressed_events,
            fallback_feedback=request.feedback,
            choices=list(self.choices_provider()),
        )
        speech_event = next(
            (
                event
                for event in validated_events
                if event.event_type == "speech" and event.character_name == state.character_name
            ),
            None,
        )
        fallback_reason = str(getattr(self.expressor, "last_fallback_reason", "") or "")
        is_local_fallback = _is_local_fallback_expression(validated_events, request.feedback)
        if speech_event is None:
            reason = fallback_reason or "invalid_event"
            return self._result(ok=False, stage=expression_diagnostic_stage(reason), reason=reason)
        reason = "" if not fallback_reason and not is_local_fallback else fallback_reason or "local_fallback"
        return self._result(
            ok=not reason,
            stage=expression_diagnostic_stage(reason),
            reason=reason,
            speech=speech_event.speech,
            effect=speech_event.effect,
        )

    def fetch_models(
        self,
        settings: ExpressionSettings | Mapping[str, object] | None = None,
    ) -> tuple[str, ...]:
        normalized = (
            self.settings
            if settings is None
            else settings
            if isinstance(settings, ExpressionSettings)
            else normalize_expression_settings(settings)
        )
        return self.model_fetcher(
            provider=normalized.provider,
            base_url=normalized.base_url,
            api_key=normalized.api_key,
            timeout_seconds=normalized.timeout_seconds,
        )

    def _settings_diagnostic_issue(self) -> str:
        if (
            self.settings.enabled
            and provider_api_key_required(self.settings.provider)
            and not self.settings.api_key
        ):
            return "missing_api_key"
        expressor_enabled = getattr(self.expressor, "enabled", None)
        if not self.settings.enabled and expressor_enabled is False:
            return "disabled"
        if self.settings.enabled and expressor_enabled is False:
            return "disabled"
        return ""

    def _result(
        self,
        *,
        ok: bool,
        stage: str,
        reason: str,
        speech: str = "",
        effect: str = "",
    ) -> ExpressionProviderDiagnosticResult:
        return ExpressionProviderDiagnosticResult(
            ok=ok,
            stage=stage,
            reason=reason,
            provider=self.settings.provider,
            model=self.settings.model,
            base_url=self.settings.base_url,
            timeout_seconds=self.settings.timeout_seconds,
            speech=speech,
            effect=effect,
            fallback_reason=reason,
        )


def _is_local_fallback_expression(events: list[CompanionEvent], feedback: str) -> bool:
    return [event.event_type for event in events] == ["speech", "stat", "choice"] and events[0].speech == feedback


def expression_diagnostic_stage(reason: str) -> str:
    if not reason:
        return "event_validation"
    if reason in {"disabled", "missing_api_key", "invalid_prompt"}:
        return "settings"
    if reason in {"timeout", "provider_error", "closed"}:
        return "provider_call"
    if reason in {
        "invalid_response_text",
        "invalid_response_json",
        "invalid_payload",
        "invalid_response_bytes",
        "invalid_response_size",
        "invalid_response_encoding",
        "invalid_response_shape",
    }:
        return "provider_parse"
    return "event_validation"
