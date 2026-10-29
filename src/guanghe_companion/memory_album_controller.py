from __future__ import annotations

"""Application-facing controller for the player-visible Starshard Memory Album."""

from dataclasses import replace
import time
from typing import Callable

from .companion_story_runtime import CompanionStoryRuntime
from .emotional_memory import MAX_MEMORY_TEXT_LENGTH, MAX_MEMORY_TITLE_LENGTH
from .memory_album_view_model import build_memory_album


class MemoryAlbumStaleError(ValueError):
    """The displayed revision no longer grants permission to replay an edit."""


class MemoryAlbumController:
    def __init__(self, story: CompanionStoryRuntime, on_invalidated: Callable[[], None] | None = None) -> None:
        self.story = story
        self.on_invalidated = on_invalidated

    def snapshot(self, *, now: int | None = None) -> dict[str, object]:
        timestamp = self._now(now)
        for _attempt in range(3):
            epoch = self.story.memory.store.context_epoch
            sections = build_memory_album(
                self.story.memory.store.load_memories(),
                self.story.memory.valid_chapters(now=timestamp),
            )
            pending = [
                {
                    "pending_id": pending_id,
                    "title": candidate.title,
                    "summary": candidate.summary,
                    "source": candidate.source,
                    "source_ids": list(candidate.source_ids),
                    "occurred_at": candidate.occurred_at,
                }
                for pending_id, candidate in list(self.story.memory.pending_candidates.items())
                if candidate.character_id == self.story.memory.character_id
                and candidate.owner_id == self.story.memory.owner_id
            ]
            if epoch == self.story.memory.store.context_epoch:
                break
        else:
            raise MemoryAlbumStaleError("stale memory album snapshot; refresh")
        return {
            "title": "星屑回忆册",
            "subtitle": "记住、珍藏、纠正或忘记你们共同留下的片段。",
            "character_id": self.story.memory.character_id,
            "context_epoch": epoch,
            "sections": [section.to_dict() for section in sections],
            "pending_confirmation_count": len(pending),
            "pending_candidates": pending,
        }

    def pin(self, memory_id: str, pinned: bool = True, *, now: int = 0,
            expected_epoch: int | None = None) -> dict[str, object]:
        epoch = self._require_epoch(expected_epoch)
        memory = self._memory(memory_id)
        self.story.memory.store.upsert_memory(
            replace(memory, pinned=bool(pinned), updated_at=max(memory.updated_at, int(now))),
            expected_epoch=epoch,
        )
        return self.snapshot(now=now)

    def forget(self, memory_id: str, *, now: int, expected_epoch: int | None = None) -> dict[str, object]:
        epoch = self._require_epoch(expected_epoch)
        if self.story.memory.forget(memory_id, now=now, expected_epoch=epoch) is None:
            raise KeyError(f"memory not found: {memory_id}")
        self._notify_invalidated()
        return self.snapshot(now=now)

    def correct(self, memory_id: str, *, title: str, summary: str, now: int,
                expected_epoch: int | None = None) -> dict[str, object]:
        epoch = self._require_epoch(expected_epoch)
        previous = self._memory(memory_id)
        self._check_text(summary or previous.summary, title=title or previous.title)
        self.story.memory.correct(
            memory_id,
            title=title or previous.title,
            summary=summary or previous.summary,
            now=now,
            expected_epoch=epoch,
        )
        self._notify_invalidated()
        return self.snapshot(now=now)

    def remember_explicit(self, text: str, *, now: int, expected_epoch: int | None = None) -> dict[str, object]:
        """The album's accepted user-authored form proposes and confirms a fact."""
        epoch = self._require_epoch(expected_epoch)
        self._check_text(text)
        pending_id = self.story.memory.propose_explicit_user_memory(f"请记住：{text.strip()}", now=now)
        if pending_id is None:
            raise ValueError("memory content is required")
        try:
            self._require_epoch(epoch)
            self.story.memory.confirm_candidate(pending_id, now=now)
        except (ValueError, KeyError):
            self.story.memory.reject_candidate(pending_id)
            raise
        return self.snapshot(now=now)

    def confirm_pending(self, pending_id: str, *, now: int,
                        expected_epoch: int | None = None) -> dict[str, object]:
        self._require_epoch(expected_epoch)
        try:
            self.story.memory.confirm_candidate(pending_id, now=now)
        except ValueError as exc:
            if "stale" in str(exc):
                raise MemoryAlbumStaleError("stale memory proposal; refresh and submit again") from exc
            raise
        return self.snapshot(now=now)

    def reject_pending(self, pending_id: str, *, expected_epoch: int | None = None) -> dict[str, object]:
        self._require_epoch(expected_epoch)
        self.story.memory.reject_candidate(pending_id)
        return self.snapshot()

    def source_details(self, card_id: str, *, now: int | None = None,
                       expected_epoch: int | None = None) -> dict[str, object]:
        epoch = self._require_epoch(expected_epoch)
        timestamp = self._now(now)
        memory = next(
            (
                row
                for row in self.story.memory.store.load_memories()
                if row.memory_id == card_id and not row.deleted
            ),
            None,
        )
        if memory is not None:
            details = {
                "memory_id": memory.memory_id,
                "title": memory.title,
                "summary": memory.summary,
                "source": memory.source,
                "source_ids": list(memory.source_ids),
                "occurred_at": memory.occurred_at,
                "updated_at": memory.updated_at,
                "version": memory.version,
                "confidence": memory.confidence,
                "valid_from": memory.valid_from,
                "valid_until": memory.valid_until,
                "scope": memory.scope,
                "active": memory.is_active(now=timestamp, scope=memory.scope),
                "user_confirmed": memory.user_confirmed,
                "supersedes": memory.supersedes,
            }
            self._require_epoch(epoch)
            return details
        chapter = next(
            (row for row in self.story.memory.valid_chapters(now=timestamp) if row.chapter_id == card_id),
            None,
        )
        if chapter is None:
            raise KeyError(f"memory card not found: {card_id}")
        memories = {
            row.memory_id: row
            for row in self.story.memory.store.load_memories()
            if not row.deleted
        }
        details = {
            "chapter_id": chapter.chapter_id,
            "title": chapter.title,
            "summary": chapter.summary,
            "created_at": chapter.created_at,
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
        self._require_epoch(epoch)
        return details

    def _memory(self, memory_id: str):
        memory = next((row for row in self.story.memory.store.load_memories() if row.memory_id == memory_id and not row.deleted), None)
        if memory is None:
            raise KeyError(f"memory not found: {memory_id}")
        return memory

    def _require_epoch(self, expected_epoch: int | None) -> int:
        current = self.story.memory.store.context_epoch
        if expected_epoch is not None and expected_epoch != current:
            raise MemoryAlbumStaleError("stale memory album; refresh before editing")
        return current

    def _notify_invalidated(self) -> None:
        if self.on_invalidated is not None:
            self.on_invalidated()

    def _now(self, value: int | None) -> int:
        if value is not None:
            return max(0, int(value))
        latest = max((row.updated_at for row in self.story.memory.store.load_memories()), default=0)
        # Preserve the demo's logical clock; real saves still expire while idle.
        return int(time.time()) if latest >= 946_684_800 else latest

    @staticmethod
    def _check_text(summary: str, *, title: str = "") -> None:
        if not summary.strip() or len(summary) > MAX_MEMORY_TEXT_LENGTH or len(title) > MAX_MEMORY_TITLE_LENGTH:
            raise ValueError("memory content or title is empty/too long")
