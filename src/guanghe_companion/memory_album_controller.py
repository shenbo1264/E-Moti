from __future__ import annotations

"""Application-facing controller for the player-visible Starshard Memory Album."""

from dataclasses import replace
from typing import Mapping

from .companion_story_runtime import CompanionStoryRuntime


class MemoryAlbumController:
    def __init__(self, story: CompanionStoryRuntime) -> None:
        self.story = story

    def snapshot(self) -> dict[str, object]:
        sections = self.story.build_memory_album()
        return {
            "title": "星屑回忆册",
            "subtitle": "珍藏、纠正或忘记你和星汐共同留下的片段。",
            "sections": [section.to_dict() for section in sections],
            "pending_confirmation_count": len(self.story.memory.pending_candidates),
        }

    def pin(self, memory_id: str, pinned: bool = True, *, now: int = 0) -> dict[str, object]:
        memory = self._memory(memory_id)
        self.story.memory.store.update_memory(replace(memory, pinned=bool(pinned), updated_at=max(memory.updated_at, int(now))))
        return self.snapshot()

    def forget(self, memory_id: str, *, now: int) -> dict[str, object]:
        if self.story.memory.forget(memory_id, now=now) is None:
            raise KeyError(f"memory not found: {memory_id}")
        return self.snapshot()

    def correct(self, memory_id: str, *, title: str, summary: str, now: int) -> dict[str, object]:
        previous = self._memory(memory_id)
        self.story.memory.remember(
            kind=previous.kind,
            title=title or previous.title,
            summary=summary or previous.summary,
            source="user_correction",
            now=now,
            importance=previous.importance,
            tags=previous.tags,
            pinned=previous.pinned,
            user_confirmed=True,
            supersedes=previous.memory_id,
            metadata={**previous.metadata, "corrected_by_user": True},
        )
        return self.snapshot()

    def confirm_pending(self, pending_id: str, *, now: int) -> dict[str, object]:
        self.story.memory.confirm_candidate(pending_id, now=now)
        return self.snapshot()

    def reject_pending(self, pending_id: str) -> dict[str, object]:
        self.story.memory.reject_candidate(pending_id)
        return self.snapshot()

    def source_details(self, card_id: str) -> dict[str, object]:
        memory = next(
            (
                row
                for row in self.story.memory.store.load_memories()
                if row.memory_id == card_id and not row.deleted
            ),
            None,
        )
        if memory is not None:
            return {
                "memory_id": memory.memory_id,
                "title": memory.title,
                "source": memory.source,
                "source_ids": list(memory.source_ids),
                "occurred_at": memory.occurred_at,
                "user_confirmed": memory.user_confirmed,
                "supersedes": memory.supersedes,
            }
        chapter = next(
            (row for row in self.story.memory.store.load_chapters() if row.chapter_id == card_id),
            None,
        )
        if chapter is None:
            raise KeyError(f"memory card not found: {card_id}")
        memories = {
            row.memory_id: row
            for row in self.story.memory.store.load_memories()
            if not row.deleted
        }
        return {
            "chapter_id": chapter.chapter_id,
            "title": chapter.title,
            "source_memories": [
                {
                    "memory_id": memory_id,
                    "title": memories[memory_id].title,
                    "source": memories[memory_id].source,
                }
                for memory_id in chapter.source_memory_ids
                if memory_id in memories
            ],
        }

    def _memory(self, memory_id: str):
        memory = next((row for row in self.story.memory.store.load_memories() if row.memory_id == memory_id and not row.deleted), None)
        if memory is None:
            raise KeyError(f"memory not found: {memory_id}")
        return memory
