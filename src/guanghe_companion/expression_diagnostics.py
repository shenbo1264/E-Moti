from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from .ai_expressor import ExpressionRequest
from .expression_clients import fetch_provider_model_ids
from .events import CompanionEvent, EventValidator
from .expression_settings import (
    ExpressionSettings,
    normalize_expression_settings,
    provider_api_key_required,
)
from .models import CompanionState
from .snapshot import CompanionSnapshot
from .interaction_intents import InteractionIntent
from .visual_actions import VisualAction


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
    visual_actions: tuple[dict[str, object], ...] = ()
    interaction_intents: tuple[dict[str, object], ...] = ()
    state_mutation_check: dict[str, object] | None = None

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
            "visual_actions": [dict(action) for action in self.visual_actions],
            "interaction_intents": [dict(intent) for intent in self.interaction_intents],
            "state_mutation_check": self.state_mutation_check or {"ok": True, "changed_fields": []},
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

        state_before = self.state_provider()
        guard_before = _state_guard_snapshot(state_before)
        request = ExpressionRequest.from_snapshot(
            self.snapshot_provider(),
            context=self.context_provider(),
        )
        try:
            expressed_events = self.expressor.express(request, effect="ATTENTION")
        except Exception:
            return self._result(ok=False, stage="provider_call", reason="provider_error")

        state = self.state_provider()
        state_mutation_check = _state_mutation_check(guard_before, _state_guard_snapshot(state))
        visual_actions = _public_visual_actions(getattr(self.expressor, "last_visual_actions", ()))
        interaction_intents = _public_interaction_intents(getattr(self.expressor, "last_interaction_intents", ()))
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
        if state_mutation_check["ok"] is False:
            return self._result(
                ok=False,
                stage="state_guard",
                reason="state_mutated",
                speech=speech_event.speech if speech_event is not None else "",
                effect=speech_event.effect if speech_event is not None else "",
                visual_actions=visual_actions,
                interaction_intents=interaction_intents,
                state_mutation_check=state_mutation_check,
            )
        if speech_event is None:
            reason = fallback_reason or "invalid_event"
            return self._result(
                ok=False,
                stage=expression_diagnostic_stage(reason),
                reason=reason,
                visual_actions=visual_actions,
                interaction_intents=interaction_intents,
                state_mutation_check=state_mutation_check,
            )
        reason = "" if not fallback_reason and not is_local_fallback else fallback_reason or "local_fallback"
        return self._result(
            ok=not reason,
            stage=expression_diagnostic_stage(reason),
            reason=reason,
            speech=speech_event.speech,
            effect=speech_event.effect,
            visual_actions=visual_actions,
            interaction_intents=interaction_intents,
            state_mutation_check=state_mutation_check,
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
        visual_actions: tuple[dict[str, object], ...] = (),
        interaction_intents: tuple[dict[str, object], ...] = (),
        state_mutation_check: dict[str, object] | None = None,
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
            visual_actions=visual_actions,
            interaction_intents=interaction_intents,
            state_mutation_check=state_mutation_check,
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


def _public_visual_actions(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, tuple) or not all(isinstance(action, VisualAction) for action in value):
        return ()
    return tuple(action.to_dict() for action in value)


def _public_interaction_intents(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, tuple) or not all(isinstance(intent, InteractionIntent) for intent in value):
        return ()
    return tuple(intent.to_dict() for intent in value)


def _state_guard_snapshot(state: CompanionState) -> dict[str, object]:
    return {
        "focus": state.focus,
        "charge": state.charge,
        "stability": state.stability,
        "mood": state.mood,
        "trust": state.trust,
        "exp": state.exp,
        "level": state.level,
        "coins": state.coins,
        "mode": state.mode,
        "resting": state.resting,
        "inventory": deepcopy(state.inventory),
        "unlocks": tuple(state.unlocks),
        "current_goal_id": state.current_goal_id,
        "last_interaction_at": state.last_interaction_at,
        "last_tick_at": state.last_tick_at,
        "last_gift_item_id": state.last_gift_item_id,
        "last_gift_at": state.last_gift_at,
        "same_gift_chain": state.same_gift_chain,
        "study_bonus_exp": state.study_bonus_exp,
        "player_alias": state.player_alias,
        "memory_log": deepcopy(state.memory_log),
    }


def _state_mutation_check(before: Mapping[str, object], after: Mapping[str, object]) -> dict[str, object]:
    changed_fields = sorted(
        key
        for key, value in before.items()
        if after.get(key) != value
    )
    return {
        "ok": not changed_fields,
        "changed_fields": changed_fields,
    }
