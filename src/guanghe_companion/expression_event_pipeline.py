from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from .events import CompanionEvent, EventValidator, build_typed_fallback_events
from .expression_request import ExpressionRequest
from .models import CompanionState
from .snapshot import CompanionSnapshot
from .visual_actions import VisualAction


class ExpressionEventExpressor(Protocol):
    def express(self, snapshot: ExpressionRequest, effect: str | None = None) -> list[dict[str, str]]:
        ...


SnapshotProvider = Callable[[], CompanionSnapshot]
ExpressionContextProvider = Callable[[], dict[str, object]]
ActionsProvider = Callable[[], list[dict[str, object]]]


@dataclass(slots=True)
class ExpressionEventPipeline:
    state: CompanionState
    expressor: ExpressionEventExpressor
    snapshot_provider: SnapshotProvider
    context_provider: ExpressionContextProvider
    actions_provider: ActionsProvider

    def build_events(
        self,
        effect: str,
        feedback: str,
        domain_events: Iterable[CompanionEvent] | None = None,
        *,
        include_ai_expression: bool = True,
        closed: bool = False,
    ) -> list[CompanionEvent]:
        domain_event_list = list(domain_events or [])
        choices = self._choices()
        fallback_events = build_typed_fallback_events(
            state=self.state,
            feedback=feedback,
            choices=choices,
            effect=effect,
        )
        if closed or not include_ai_expression:
            return fallback_events + domain_event_list

        expression_request = ExpressionRequest.from_snapshot(
            self.snapshot_provider(),
            context=self.context_provider(),
        )
        try:
            expressed_events = self.expressor.express(expression_request, effect=effect)
        except Exception:
            return fallback_events + domain_event_list
        if not expressed_events:
            return fallback_events + domain_event_list
        if expressed_events == [event.to_legacy_dict() for event in fallback_events]:
            return fallback_events + domain_event_list

        validated_events = EventValidator(self.state).validate(
            events=expressed_events,
            fallback_feedback=feedback,
            choices=choices,
        )
        if _is_local_fallback_expression(validated_events, feedback):
            return fallback_events + domain_event_list

        local_context_events = [event for event in fallback_events if event.event_type in {"stat", "choice"}]
        expression_events = [event for event in validated_events if event.event_type == "speech"]
        if not expression_events:
            return fallback_events + domain_event_list
        visual_event = _visual_event_from_actions(getattr(self.expressor, "last_visual_actions", ()))
        visual_events = [visual_event] if visual_event is not None else []
        return expression_events[:1] + local_context_events + visual_events + domain_event_list

    def _choices(self) -> list[str]:
        return [str(entry["label"]) for entry in self.actions_provider()]


def _is_local_fallback_expression(events: list[CompanionEvent], feedback: str) -> bool:
    return [event.event_type for event in events] == ["speech", "stat", "choice"] and events[0].speech == feedback


def _visual_event_from_actions(actions: object) -> CompanionEvent | None:
    if not isinstance(actions, tuple) or not all(isinstance(action, VisualAction) for action in actions):
        return None
    if not actions:
        return None
    return CompanionEvent(
        event_type="visual",
        character_name="VISUAL",
        speech="llm visual action",
        payload={"actions": [action.to_dict() for action in actions]},
    )
