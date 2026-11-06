from __future__ import annotations

"""Application-facing controller for the player-visible Starshard Memory Album."""

from dataclasses import replace
import time
from typing import Callable

from .companion_story_runtime import CompanionStoryRuntime
from .emotional_memory import MAX_MEMORY_TEXT_LENGTH, MAX_MEMORY_TITLE_LENGTH
from .memory_album_view_model import build_memory_album
from .memory_evidence_view_model import present_evidence
from .memory_ledger_view_model import build_memory_ledger
from .memory_source_spans import resolve_source_spans


class MemoryAlbumStaleError(ValueError):
    """The displayed revision no longer grants permission to replay an edit."""


def _missing(trace) -> tuple[str, ...]:
    return tuple(detail for decision in trace.decisions for detail in decision.missing_details)


class MemoryAlbumController:
    def __init__(self, story: CompanionStoryRuntime, on_invalidated: Callable[[], None] | None = None,
                 clock: Callable[[], int] | None = None) -> None:
        self.story = story
        self.on_invalidated = on_invalidated
        self.clock = clock
        self._turn_trace = None

    def current_time(self) -> int:
        return self._now(None)

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
            "ledger": build_memory_ledger(self.story.memory.store.load_memories(), now=timestamp,
                                          time_basis=self.story.memory.time_basis,
                                          timezone_name=self.story.memory.timezone_name, pending=pending),
            "pending_confirmation_count": len(pending),
            "pending_candidates": pending,
        }

    def pin(self, memory_id: str, pinned: bool = True, *, now: int | None = None,
            expected_epoch: int | None = None) -> dict[str, object]:
        epoch = self._require_epoch(expected_epoch)
        timestamp = self._now(now)
        memory = self._memory(memory_id)
        self.story.memory.store.upsert_memory(
            replace(memory, pinned=bool(pinned), updated_at=max(memory.updated_at, timestamp)),
            expected_epoch=epoch,
        )
        return self.snapshot(now=timestamp)

    def forget(self, memory_id: str, *, now: int | None = None,
               expected_epoch: int | None = None) -> dict[str, object]:
        epoch = self._require_epoch(expected_epoch)
        now = self._now(now)
        if self.story.memory.forget(memory_id, now=now, expected_epoch=epoch) is None:
            raise KeyError(f"memory not found: {memory_id}")
        self._notify_invalidated()
        return self.snapshot(now=now)

    def purge(self, memory_id: str, *, now: int | None = None,
              expected_epoch: int | None = None) -> dict[str, object]:
        """Remove the body of a whole revision chain; see memory_lifecycle.purge_memory."""
        epoch = self._require_epoch(expected_epoch)
        now = self._now(now)
        if not self.story.memory.purge(memory_id, now=now, expected_epoch=epoch):
            raise KeyError(f"memory not found: {memory_id}")
        self._notify_invalidated()
        return self.snapshot(now=now)

    def change(self, memory_id: str, *, title: str, summary: str, now: int | None = None,
               expected_epoch: int | None = None) -> dict[str, object]:
        """Reality moved on: the old fact stays as legitimate history."""
        epoch = self._require_epoch(expected_epoch)
        now = self._now(now)
        previous = self._memory(memory_id)
        self._check_text(summary or previous.summary, title=title or previous.title)
        self.story.memory.change(memory_id, title=title or previous.title, summary=summary or previous.summary,
                                 now=now, effective_at=now, expected_epoch=epoch)
        self._notify_invalidated()
        return self.snapshot(now=now)

    def ask(self, query: str, *, now: int | None = None, history=()) -> dict[str, object]:
        """L1 overview for one question. It runs the production retrieval path."""
        timestamp = self._now(now)
        memory = self.story.memory
        turn_trace = memory.last_retrieval_trace
        try:
            result = memory.retrieve(query, now=timestamp, history=history, record_access=False)
        finally:
            memory.last_retrieval_trace = turn_trace
        claims = {row.memory_id: self._claim(row) for row in result.bundle.memories}
        return {"status": result.trace.status, "presentation": present_evidence(result.trace.status,
                                                                               missing=_missing(result.trace)),
                "semantic_status": result.trace.semantic_status, "claims": list(claims.values()),
                "context_epoch": result.bundle.context_epoch}

    def expand(self, bindings: dict[str, str], *, expected_epoch: int,
               now: int | None = None) -> dict[str, object]:
        """L2 current memory cards, re-read from the authority on every click."""
        timestamp = self._now(now)
        memory = self.story.memory
        turn_trace = memory.last_retrieval_trace
        try:
            result = memory.expand_sources(bindings, expected_epoch=expected_epoch, now=timestamp, record_access=False)
        finally:
            memory.last_retrieval_trace = turn_trace
        status = result.trace.status
        cards = [{"memory_id": row.memory_id, "title": row.title, "summary": row.summary, "source": row.source,
                  "version": row.version} for row in result.bundle.memories]
        return {"status": status, "presentation": present_evidence(status), "cards": cards,
                "spans": list(result.bundle.source_spans),
                "note": "这里是当前有效的记忆卡，不是完整聊天原文。"}

    def clear_turn_evidence(self) -> None:
        """A new turn must not inherit the previous turn's evidence."""
        self._turn_trace = None

    def capture_turn_evidence(self) -> None:
        """Call once a turn's memory is prepared: later snapshots retrieve with an empty query."""
        self._turn_trace = self.story.memory.last_retrieval_trace

    def turn_evidence(self, *, now: int | None = None) -> dict[str, object]:
        """Evidence behind the last reply, or nothing if it has since been revoked."""
        trace = self._turn_trace
        status = getattr(trace, "status", "not_needed")
        # 宽泛兜底路由查不到东西是普通聊天的常态，不是用户在问回忆。
        casual = status == "unknown" and not set(trace.route if trace else ()) - {"chat", "bounded"}
        if trace is None or status == "not_needed" or casual:
            return {"status": "not_needed", "presentation": None, "claims": [], "context_epoch": None}
        epoch = self.story.memory.store.context_epoch
        if trace.context_epoch != epoch:
            return {"status": "unavailable", "presentation": present_evidence("unavailable"),
                    "claims": [], "context_epoch": epoch}
        timestamp = self._now(now)
        selected = set(trace.selected_memory_ids)
        claims = [self._claim(row) for row in self.story.memory.store.load_memories()
                  if row.memory_id in selected and row.is_active(now=timestamp, scope=row.scope)]
        return {"status": status, "presentation": present_evidence(status, missing=_missing(trace)),
                "claims": claims, "context_epoch": epoch}

    @staticmethod
    def _claim(row) -> dict[str, object]:
        return {"memory_id": row.memory_id, "fingerprint": row.evidence_fingerprint(), "text": row.summary,
                "title": row.title, "source": row.source}

    def correct(self, memory_id: str, *, title: str, summary: str, now: int | None = None,
                expected_epoch: int | None = None) -> dict[str, object]:
        epoch = self._require_epoch(expected_epoch)
        now = self._now(now)
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

    def remember_explicit(self, text: str, *, now: int | None = None,
                          expected_epoch: int | None = None) -> dict[str, object]:
        """The album's accepted user-authored form proposes and confirms a fact."""
        epoch = self._require_epoch(expected_epoch)
        now = self._now(now)
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

    def confirm_pending(self, pending_id: str, *, now: int | None = None,
                        expected_epoch: int | None = None) -> dict[str, object]:
        epoch = self._require_epoch(expected_epoch)
        now = self._now(now)
        try:
            entry = self.story.memory.confirm_candidate(pending_id, now=now)
        except ValueError as exc:
            if "stale" in str(exc):
                raise MemoryAlbumStaleError("stale memory proposal; refresh and submit again") from exc
            raise
        if entry.source == "user_chat" and str(entry.metadata.get("fact_slot", "")).startswith("preference:"):
            self.story.memory.update_bond_profile(new_preference=entry.summary,
                source_memory_ids=(entry.memory_id,), now=now,
                expected_epoch=self.story.memory.store.context_epoch)
        if epoch != self.story.memory.store.context_epoch:
            self._notify_invalidated()
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
            resolved = resolve_source_spans(self.story.memory.store,
                {memory.memory_id: memory.evidence_fingerprint()}, expected_epoch=epoch, now=timestamp, scope=memory.scope)
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
                "provenance": {key: memory.metadata[key] for key in (
                    "message_id", "speaker", "scene", "recorded_at", "confidence_reason",
                    "fact_domain", "fact_slot") if key in memory.metadata},
                "source_expansion": resolved,
            }
            if resolved["spans"]:
                details["provenance"]["original_quote"] = resolved["spans"][0]["text"]
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
        if self.clock is not None:
            return max(0, int(self.clock()))
        latest =max((row.updated_at for row in self.story.memory.store.load_memories()), default=0)
        return int(time.time()) if self.story.memory.time_basis == "unix" else latest

    @staticmethod
    def _check_text(summary: str, *, title: str = "") -> None:
        if not summary.strip() or len(summary) > MAX_MEMORY_TEXT_LENGTH or len(title) > MAX_MEMORY_TITLE_LENGTH:
            raise ValueError("memory content or title is empty/too long")
