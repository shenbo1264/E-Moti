from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path

from .emotional_memory import (
    CoreBondProfile,
    EmotionalMemoryEntry,
    EmotionalMemoryStore,
    MemoryChapter,
    MemoryContextBundle,
)
from .emotional_memory_policy import EmotionalMemoryPolicy, MemoryCandidate
from .emotional_memory_reflection import MemoryReflectionService
from .emotional_memory_retrieval import rank_memories


class EmotionalMemoryService:
    """Character-scoped emotional memory with deterministic write policy."""

    def __init__(
        self,
        *,
        root: Path | str,
        character_id: str,
        owner_id: str = "local_user",
        policy: EmotionalMemoryPolicy | None = None,
        reflection: MemoryReflectionService | None = None,
    ) -> None:
        self.store = EmotionalMemoryStore(root=root, character_id=character_id, owner_id=owner_id)
        self.character_id = character_id
        self.owner_id = owner_id
        self.policy = policy or EmotionalMemoryPolicy()
        self.reflection = reflection or MemoryReflectionService()
        self.pending_candidates: dict[str, MemoryCandidate] = {}

    def record_event(self, event: object, *, now: int) -> EmotionalMemoryEntry | None:
        normalized_event = self._annotate_firsts(event)
        candidate = self.policy.from_event(
            normalized_event,
            character_id=self.character_id,
            owner_id=self.owner_id,
            now=now,
        )
        if candidate is None:
            return None
        if candidate.requires_user_confirmation:
            pending_id = candidate.to_memory(now=now).memory_id
            self.pending_candidates[pending_id] = candidate
            return None
        return self._persist_candidate(candidate, now=now, user_confirmed=False)

    def record_event_bundle(self, events: Iterable[object], *, now: int) -> tuple[EmotionalMemoryEntry, ...]:
        """Record one settled domain-event batch without duplicate memories.

        E-Moti's current inventory flow can emit both an ``inventory`` event and
        a generic ``memory`` event. Inventory is the authoritative source for
        feed/gift memories, while relationship is the authoritative source for
        unlock milestones. This method coalesces that bundle before writing.
        """

        rows = list(events)
        has_inventory = any(_event_type(event) == "inventory" for event in rows)
        has_relationship = any(_event_type(event) == "relationship" for event in rows)
        memories: list[EmotionalMemoryEntry] = []
        for event in rows:
            if _event_type(event) == "memory":
                payload = _event_payload(event)
                kind = _clean(payload.get("kind"))
                if has_inventory and kind in {"赠礼", "投喂", "使用"}:
                    continue
                if has_relationship and kind == "关系解锁":
                    continue
            memory = self.record_event(event, now=now)
            if memory is not None and memory.memory_id not in {item.memory_id for item in memories}:
                memories.append(memory)
        return tuple(memories)

    def propose_explicit_user_memory(self, text: str, *, now: int) -> str | None:
        candidate = self.policy.explicit_user_memory(
            text,
            character_id=self.character_id,
            owner_id=self.owner_id,
            now=now,
        )
        if candidate is None:
            return None
        pending_id = candidate.to_memory(now=now).memory_id
        self.pending_candidates[pending_id] = candidate
        return pending_id

    def confirm_candidate(self, pending_id: str, *, now: int) -> EmotionalMemoryEntry:
        candidate = self.pending_candidates.pop(pending_id)
        return self._persist_candidate(candidate, now=now, user_confirmed=True)

    def reject_candidate(self, pending_id: str) -> bool:
        return self.pending_candidates.pop(pending_id, None) is not None

    def remember(
        self,
        *,
        kind: str,
        title: str,
        summary: str,
        source: str,
        now: int,
        importance: float = 0.7,
        tags: tuple[str, ...] = (),
        pinned: bool = False,
        user_confirmed: bool = True,
        supersedes: str = "",
        metadata: Mapping[str, object] | None = None,
    ) -> EmotionalMemoryEntry:
        candidate = MemoryCandidate(
            character_id=self.character_id,
            owner_id=self.owner_id,
            kind=kind,
            title=title,
            summary=summary,
            source=source,
            occurred_at=now,
            tags=tags,
            importance=importance,
            pinned=pinned,
            metadata=dict(metadata or {}),
        )
        memory = candidate.to_memory(now=now, user_confirmed=user_confirmed)
        if supersedes:
            memory = replace(memory, supersedes=supersedes)
            previous = next(
                (entry for entry in self.store.load_memories() if entry.memory_id == supersedes),
                None,
            )
            if previous is not None:
                self.store.update_memory(replace(previous, deleted=True, updated_at=now))
        return self.store.upsert_memory(memory)

    def recall(
        self,
        query: str,
        *,
        now: int,
        relationship_stage: str | None = None,
        top_k: int = 4,
    ) -> tuple[EmotionalMemoryEntry, ...]:
        profile = self.store.load_profile()
        stage = relationship_stage or profile.relationship_stage
        existing = self.store.load_memories()
        ranked = rank_memories(
            existing,
            query,
            now=now,
            relationship_stage=stage,
            top_k=top_k,
        )
        if not ranked:
            return ()
        results: list[EmotionalMemoryEntry] = []
        all_memories = {memory.memory_id: memory for memory in existing}
        for memory, _score in ranked:
            touched = memory.touch(now)
            all_memories[touched.memory_id] = touched
            results.append(touched)
        self.store.save_memories(all_memories.values())
        return tuple(results)

    def build_context(
        self,
        query: str,
        *,
        now: int,
        relationship_stage: str | None = None,
        top_k: int = 4,
    ) -> MemoryContextBundle:
        profile = self.store.load_profile()
        if relationship_stage is not None and relationship_stage != profile.relationship_stage:
            profile = replace(profile, relationship_stage=relationship_stage, updated_at=now)
            self.store.save_profile(profile)
        memories = self.recall(
            query,
            now=now,
            relationship_stage=profile.relationship_stage,
            top_k=top_k,
        )
        return MemoryContextBundle(
            bond_profile=profile,
            memories=memories,
            chapter=self.latest_chapter(),
        )

    def consolidate(self, *, now: int) -> MemoryChapter | None:
        memories = self.store.load_memories()
        if not self.reflection.should_consolidate(memories):
            return None
        chapter = self.reflection.build_chapter(memories, character_id=self.character_id, now=now)
        if chapter is None:
            return None
        # Re-running consolidation over the same evidence should not create an
        # endless stack of identical chapters.
        source_set = frozenset(chapter.source_memory_ids)
        existing = next(
            (
                item
                for item in self.store.load_chapters()
                if frozenset(item.source_memory_ids) == source_set
            ),
            None,
        )
        if existing is not None:
            return existing
        return self.store.upsert_chapter(chapter)

    def latest_chapter(self) -> MemoryChapter | None:
        chapters = sorted(self.store.load_chapters(), key=lambda chapter: chapter.created_at, reverse=True)
        return chapters[0] if chapters else None

    def update_bond_profile(
        self,
        *,
        now: int,
        player_alias: str | None = None,
        relationship_stage: str | None = None,
        new_preference: str | None = None,
        new_boundary: str | None = None,
        new_ritual: str | None = None,
        active_story_thread: str | None = None,
    ) -> CoreBondProfile:
        profile = self.reflection.update_bond_profile(
            self.store.load_profile(),
            player_alias=player_alias,
            relationship_stage=relationship_stage,
            new_preference=new_preference,
            new_boundary=new_boundary,
            new_ritual=new_ritual,
            active_story_thread=active_story_thread,
            now=now,
        )
        self.store.save_profile(profile)
        return profile

    def reinforce(self, memory_id: str, *, now: int, amount: float = 0.08) -> EmotionalMemoryEntry | None:
        entries = list(self.store.load_memories())
        updated: EmotionalMemoryEntry | None = None
        next_entries: list[EmotionalMemoryEntry] = []
        for entry in entries:
            if entry.memory_id == memory_id:
                updated = replace(
                    entry,
                    importance=min(1.0, entry.importance + max(0.0, amount)),
                    access_count=entry.access_count + 1,
                    last_accessed_at=now,
                    updated_at=now,
                )
                next_entries.append(updated)
            else:
                next_entries.append(entry)
        if updated is not None:
            self.store.save_memories(next_entries)
        return updated

    def forget(self, memory_id: str, *, now: int) -> EmotionalMemoryEntry | None:
        return self.store.forget_memory(memory_id, now=now)

    def album(self) -> dict[str, tuple[EmotionalMemoryEntry, ...]]:
        visible = [memory for memory in self.store.load_memories() if not memory.deleted]
        groups: dict[str, list[EmotionalMemoryEntry]] = {
            "第一次": [],
            "小默契": [],
            "礼物与纪念": [],
            "共同日常": [],
            "关于你": [],
        }
        for memory in visible:
            if "第一次" in memory.tags:
                groups["第一次"].append(memory)
            if memory.kind == "关系里程碑" or {"共同日常", "小默契"} & set(memory.tags):
                groups["小默契"].append(memory)
            if memory.kind in {"赠礼", "投喂"}:
                groups["礼物与纪念"].append(memory)
            if memory.kind in {"互动", "共同学习", "主动陪伴", "玩耍"}:
                groups["共同日常"].append(memory)
            if memory.kind == "玩家希望被记住" or "关于你" in memory.tags:
                groups["关于你"].append(memory)
        return {
            name: tuple(sorted(items, key=lambda item: item.occurred_at, reverse=True))
            for name, items in groups.items()
        }

    def _persist_candidate(
        self,
        candidate: MemoryCandidate,
        *,
        now: int,
        user_confirmed: bool,
    ) -> EmotionalMemoryEntry:
        return self.store.upsert_memory(candidate.to_memory(now=now, user_confirmed=user_confirmed))

    def _annotate_firsts(self, event: object) -> object:
        row = _event_to_mapping(event)
        if not row:
            return event
        payload = dict(row.get("payload") or {})
        if row.get("event_type") == "inventory" and "first_time" not in payload:
            action = _clean(payload.get("action"))
            item_id = _clean(payload.get("item_id"))
            if action in {"feed", "gift"} and item_id:
                payload["first_time"] = not any(
                    not memory.deleted
                    and memory.metadata.get("action") == action
                    and memory.metadata.get("item_id") == item_id
                    for memory in self.store.load_memories()
                )
        if row.get("event_type") == "memory":
            kind = _clean(payload.get("kind"))
            motion = _clean(payload.get("motion"))
            if kind == "互动":
                kind = {
                    "Study": "共同学习",
                    "Play": "玩耍",
                    "Comfort": "安抚",
                    "Sleep": "休息",
                }.get(motion, kind)
                payload["kind"] = kind
            if "first_time" not in payload and kind and kind not in {"互动", "赠礼", "投喂", "使用"}:
                payload["first_time"] = not any(
                    not memory.deleted and memory.kind == kind
                    for memory in self.store.load_memories()
                )
        return {**row, "payload": payload}


def _event_to_mapping(event: object) -> dict[str, object]:
    if isinstance(event, Mapping):
        return dict(event)
    event_type = getattr(event, "event_type", None)
    if not isinstance(event_type, str):
        return {}
    payload = getattr(event, "payload", {})
    return {
        "event_type": event_type,
        "event_id": getattr(event, "event_id", ""),
        "speech": getattr(event, "speech", ""),
        "payload": dict(payload) if isinstance(payload, Mapping) else {},
    }


def _event_type(event: object) -> str:
    return str(_event_to_mapping(event).get("event_type", ""))


def _event_payload(event: object) -> dict[str, object]:
    payload = _event_to_mapping(event).get("payload")
    return dict(payload) if isinstance(payload, Mapping) else {}


def _clean(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\n", " ").replace("\r", " ").strip().split())[:240]
