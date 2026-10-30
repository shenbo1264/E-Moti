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
from .emotional_memory_reflection import MemoryRecollection, is_chat_interest, is_shared_experience
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
        recorded = record_companion_events(self.memory, events, now=now)
        if recorded:
            self.memory.consolidate(now=now, shared_only=True)
        return recorded

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
        memory = self.memory.record_event(domain_event, now=now)
        if memory is not None:
            self.memory.consolidate(now=now, shared_only=True)
        return memory

    def _shared_memories(self, *, now: int) -> tuple[EmotionalMemoryEntry, ...]:
        return tuple(memory for memory in self.memory.store.load_memories()
                     if memory.is_active(now=now) and is_shared_experience(memory))

    def relationship_development(self, *, now: int) -> dict[str, object]:
        epoch = self.memory.store.context_epoch
        memories = sorted(self._shared_memories(now=now), key=lambda entry: entry.occurred_at, reverse=True)[:6]
        if epoch != self.memory.store.context_epoch:
            memories = []
            epoch = self.memory.store.context_epoch
        # 一个宿主事件可能形成多种记忆，不能把同一事件累计成多次共同经历。
        sources = {source for memory in memories for source in memory.source_ids}
        count = len(sources)
        return {
            "shared_moment_count": count,
            "expression_stage": "familiar_shared_moments" if count >= 3 else "first_shared_moments" if count else "getting_acquainted",
            "expression_hint": ("可以更自然地提起有来源的共同经历，保持角色原有风格。" if count >= 3
                                else "轻轻提起已经发生的共同片段，不假定已经很亲密。" if count
                                else "尚无可引用的共同经历，保持自然好奇，不虚构共同过去。"),
            "source_memory_ids": [memory.memory_id for memory in memories],
            "source_fingerprints": {memory.memory_id: memory.evidence_fingerprint() for memory in memories},
            "context_epoch": epoch,
        }

    def memory_recollection(self, *, now: int,
                           last_proactive_at: Mapping[str, int] | None = None) -> MemoryRecollection | None:
        emitted = last_proactive_at or {}
        epoch = self.memory.store.context_epoch
        memories = sorted((memory for memory in self.memory.store.load_memories()
                           if memory.is_active(now=now) and (is_shared_experience(memory) or is_chat_interest(memory))),
                          key=lambda row: (is_chat_interest(row), row.occurred_at, row.importance), reverse=True)
        if epoch != self.memory.store.context_epoch:
            return None
        for memory in memories:
            key = f"memory_recollection:{memory.memory_id}"
            if now - memory.occurred_at < 300 or (key in emitted and now - emitted[key] < 86400):
                continue
            return MemoryRecollection(memory.memory_id, memory.character_id, memory.evidence_fingerprint(),
                                      epoch, memory.summary, memory.valid_until,
                                      str(memory.metadata["fact_value"]) if is_chat_interest(memory) else "")
        return None

    def is_recollection_current(self, candidate: MemoryRecollection, *, now: int) -> bool:
        return (candidate.character_id == self.memory.character_id
                and candidate.context_epoch == self.memory.store.context_epoch
                and any(memory.memory_id == candidate.memory_id and memory.evidence_fingerprint() == candidate.fingerprint
                        for memory in self.memory.store.load_memories() if memory.is_active(now=now)
                        and (is_shared_experience(memory) or is_chat_interest(memory))))

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
    def build_memory_album(self, *, now: int | None = None) -> tuple[MemoryAlbumSection, ...]:
        """Return a game-facing album model for the PySide6 memory page."""

        if now is None:
            now = max((entry.updated_at for entry in self.memory.store.load_memories()), default=0)
        return build_memory_album(
            self.memory.store.load_memories(),
            self.memory.valid_chapters(now=now),
        )
