from __future__ import annotations

"""Small integration facade used by E-Moti's controller/UI layer.

It keeps game-state settlement outside this module. The host passes already
validated domain events in, receives read-only memory context out, and may feed
completed Focus Skill events back as shared moments.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .emotional_memory import EmotionalMemoryEntry, MemoryContextBundle
from .emotional_memory_service import EmotionalMemoryService
from .focus_companion import FocusCompanionSettings
from .focus_companion_runtime import (
    FocusCompanionCoordinator,
    FocusCompanionStateStore,
    FocusSkillEvent,
)
from .memory_album_view_model import MemoryAlbumSection, build_memory_album
from .memory_integration_bridge import (
    confirmed_focus_skill_event,
    enrich_ai_context_with_memory,
    record_companion_events,
)


@dataclass(slots=True)
class CompanionStoryRuntime:
    memory: EmotionalMemoryService
    focus: FocusCompanionCoordinator

    @classmethod
    def create(
        cls,
        *,
        user_data_root: Path | str,
        character_id: str,
        focus_settings: FocusCompanionSettings | None = None,
    ) -> "CompanionStoryRuntime":
        root = Path(user_data_root)
        return cls(
            memory=EmotionalMemoryService(root=root, character_id=character_id),
            focus=FocusCompanionCoordinator(
                focus_settings,
                state_store=FocusCompanionStateStore(
                    root / "characters" / character_id / "focus_companion_state.json"
                ),
            ),
        )

    def record_settled_events(self, events: Iterable[object], *, now: int) -> list[str]:
        return record_companion_events(self.memory, events, now=now)

    def record_focus_completion(
        self,
        event: FocusSkillEvent,
        *,
        now: int,
        event_id: str,
    ) -> EmotionalMemoryEntry | None:
        domain_event = confirmed_focus_skill_event(event, event_id=event_id)
        if domain_event is None:
            return None
        return self.memory.record_event(domain_event, now=now)

    def build_expression_context(
        self,
        base_context: Mapping[str, object],
        *,
        query: str,
        now: int,
        relationship_stage: str,
    ) -> tuple[dict[str, object], MemoryContextBundle]:
        bundle = self.memory.build_context(
            query,
            now=now,
            relationship_stage=relationship_stage,
            top_k=4,
        )
        return enrich_ai_context_with_memory(base_context, bundle), bundle
    def build_memory_album(self) -> tuple[MemoryAlbumSection, ...]:
        """Return a game-facing album model for the PySide6 memory page."""

        return build_memory_album(
            self.memory.store.load_memories(),
            self.memory.store.load_chapters(),
        )

