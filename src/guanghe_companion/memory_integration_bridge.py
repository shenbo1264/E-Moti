from __future__ import annotations

from collections.abc import Iterable, Mapping

from .emotional_memory import MemoryContextBundle
from .emotional_memory_service import EmotionalMemoryService
from .focus_companion_runtime import FocusSkillEvent


def record_companion_events(
    service: EmotionalMemoryService,
    events: Iterable[object],
    *,
    now: int,
) -> list[str]:
    """Record one settled domain-event batch after game-state mutation."""

    return [memory.memory_id for memory in service.record_event_bundle(events, now=now)]


def enrich_ai_context_with_memory(
    context: Mapping[str, object],
    bundle: MemoryContextBundle,
) -> dict[str, object]:
    """Add memory V2 as read-only expression context."""

    next_context = dict(context)
    next_context["emotional_memory"] = bundle.to_prompt_payload()
    return next_context


def confirmed_companion_skill_event(
    *,
    summary: str,
    skill_id: str,
    event_id: str,
) -> dict[str, object]:
    """Create the only proactive shape eligible for long-term memory.

    Raw screen/perception content is deliberately absent. Only a completed,
    user-confirmed shared moment is written.
    """

    return {
        "event_type": "proactive",
        "event_id": event_id,
        "speech": summary,
        "payload": {
            "summary": summary,
            "skill_id": skill_id,
            "completed": True,
            "user_accepted": True,
            "contains_screen_content": False,
        },
    }


def confirmed_focus_skill_event(event: FocusSkillEvent, *, event_id: str) -> dict[str, object] | None:
    """Translate a completed Focus Skill into a memory-safe domain event."""

    if event.event_type != "focus_break_completed" or event.memory_draft is None:
        return None
    summary = str(event.memory_draft.get("summary", "")).strip()
    if not summary:
        return None
    return confirmed_companion_skill_event(
        summary=summary,
        skill_id=str(event.payload.get("skill_id", "local_break_timer")),
        event_id=event_id,
    )
