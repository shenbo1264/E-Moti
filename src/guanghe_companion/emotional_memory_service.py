from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from .emotional_memory import (
    MAX_SOURCE_IDS,
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
        semantic_retriever: Callable[[str, tuple[EmotionalMemoryEntry, ...]], Mapping[str, float]] | None = None,
    ) -> None:
        self.store = EmotionalMemoryStore(root=root, character_id=character_id, owner_id=owner_id)
        self.character_id = character_id
        self.owner_id = owner_id
        self.policy = policy or EmotionalMemoryPolicy()
        self.reflection = reflection or MemoryReflectionService()
        self.semantic_retriever = semantic_retriever

    @property
    def pending_candidates(self) -> dict[str, MemoryCandidate]:
        return {key: MemoryCandidate(
            character_id=entry.character_id, owner_id=entry.owner_id, kind=entry.kind,
            title=entry.title, summary=entry.summary, source=entry.source, occurred_at=entry.occurred_at,
            source_ids=entry.source_ids, tags=entry.tags, emotion=entry.emotion,
            importance=entry.importance, relationship_delta=entry.relationship_delta, pinned=entry.pinned,
            requires_user_confirmation=requires_confirmation, metadata=dict(entry.metadata),
        ) for key, (entry, requires_confirmation, _epoch) in self.store.load_pending_candidates().items()}

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
            self.propose_candidate(candidate, pending_id=pending_id, expected_epoch=self.store.context_epoch)
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
        # 每次明确的新陈述是独立来源；相同逻辑时刻重述也不是旧记录重放。
        candidate = replace(candidate, source_ids=(f"explicit_statement:{uuid4().hex}",))
        pending_id = candidate.to_memory(now=now).memory_id
        return self.propose_candidate(candidate, pending_id=pending_id, expected_epoch=self.store.context_epoch)

    def confirm_candidate(self, pending_id: str, *, now: int) -> EmotionalMemoryEntry:
        entry = self.store.confirm_pending_candidate(pending_id, now=now)
        self.promote_sourced_alias(entry, now=now)
        return entry

    def promote_sourced_alias(self, entry: EmotionalMemoryEntry, *, now: int) -> None:
        if entry.metadata.get("fact_domain") != "称呼" or entry.metadata.get("speaker") != "user":
            return
        alias = entry.metadata.get("fact_value")
        if not isinstance(alias, str) or not alias or _canonical_profile_value("player_alias", alias) != alias:
            raise ValueError("nickname fact must contain a valid literal alias")
        current = {m.memory_id: m for m in self.store.load_memories() if m.is_active(now=now)}
        actual = current.get(entry.memory_id)
        if actual is None or actual.evidence_fingerprint() != entry.evidence_fingerprint():
            raise ValueError("nickname promotion requires current evidence")
        profile = self.store.load_profile()
        previous_sources = set(profile.evidence.get(f"player_alias:{profile.player_alias}", {}))
        previous_sources.update(m.memory_id for m in current.values()
                                if m.metadata.get("profile_field") == "player_alias")
        # 旧称呼的事实与派生来源一起退役，沿用已有 epoch 传播和历史屏障。
        for memory_id in previous_sources - {entry.memory_id}:
            self.forget(memory_id, now=now, expected_epoch=self.store.context_epoch)
        self.update_bond_profile(player_alias=alias, source_memory_ids=(entry.memory_id,),
                                 now=now, expected_epoch=self.store.context_epoch)

    def propose_candidate(self, candidate: MemoryCandidate, *, pending_id: str,
                          expected_epoch: int, now: int | None = None) -> str:
        """Host-only proposal boundary; a model/provider cannot confirm itself."""
        if candidate.character_id != self.character_id or candidate.owner_id != self.owner_id:
            raise ValueError("candidate belongs to another character or owner")
        references = candidate.metadata.get("source_memory_ids", [])
        if (not isinstance(references, (list, tuple)) or len(references) > 16
                or any(not isinstance(key, str) or not key for key in references)):
            raise ValueError("invalid memory candidate source references")
        recorded_at = candidate.occurred_at if now is None else now
        return self.store.save_pending_candidate(pending_id, candidate.to_memory(now=recorded_at),
            requires_user_confirmation=candidate.requires_user_confirmation, expected_epoch=expected_epoch)

    def reject_candidate(self, pending_id: str, *, revoke_context: bool = False) -> bool:
        return self.store.reject_pending_candidate(pending_id, revoke_context=revoke_context)

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
        source_ids: tuple[str, ...] = (),
        scope: str = "companion",
        confidence: float = 1.0,
        valid_from: int = 0,
        valid_until: int = 0,
        expected_epoch: int | None = None,
        preserve_occurred_at: bool = True,
    ) -> EmotionalMemoryEntry:
        if source in {"model", "assistant", "llm", "llm_generated", "assistant_generated", "model_generated"} and not user_confirmed:
            raise ValueError("model output is not evidence of a user fact or completed event")
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
            source_ids=source_ids,
        )
        memory = replace(candidate.to_memory(now=now, user_confirmed=user_confirmed),
                         scope=scope, confidence=confidence, valid_from=valid_from, valid_until=valid_until)
        if supersedes:
            return self.store.replace_memory(supersedes, memory, now=now, expected_epoch=expected_epoch,
                                             preserve_occurred_at=preserve_occurred_at)
        return self.store.upsert_memory(memory, expected_epoch=expected_epoch)

    def correct(self, memory_id: str, *, title: str, summary: str, now: int,
                expected_epoch: int | None = None, source_ids: tuple[str, ...] = (),
                metadata: Mapping[str, object] | None = None) -> EmotionalMemoryEntry:
        epoch = self.store.context_epoch if expected_epoch is None else expected_epoch
        previous = next((entry for entry in self.store.load_memories()
                         if entry.memory_id == memory_id and not entry.deleted), None)
        if previous is None:
            raise KeyError(f"active memory not found: {memory_id}")
        combined_sources = tuple(dict.fromkeys((*previous.source_ids, *source_ids)))
        if len(combined_sources) > MAX_SOURCE_IDS:
            raise ValueError("correction source references exceed the supported limit")
        return self.remember(kind=previous.kind, title=title, summary=summary,
            source="user_correction", now=now, importance=previous.importance,
            tags=previous.tags, pinned=previous.pinned, user_confirmed=True,
            supersedes=memory_id, metadata={**previous.metadata, **dict(metadata or {}), "corrected_by_user": True},
            source_ids=combined_sources, scope=previous.scope, confidence=1.0,
            valid_from=previous.valid_from, valid_until=previous.valid_until, expected_epoch=epoch)

    def recall(
        self,
        query: str,
        *,
        now: int,
        relationship_stage: str | None = None,
        top_k: int = 4,
        scope: str = "companion",
    ) -> tuple[EmotionalMemoryEntry, ...]:
        self.store.expire_memories(now=now)
        profile = self.store.load_profile()
        stage = relationship_stage or profile.relationship_stage
        existing = tuple(memory for memory in self.store.load_memories()
                         if memory.is_active(now=now, scope=scope))
        semantic_scores = {}
        if self.semantic_retriever is not None:
            try:
                supplied = self.semantic_retriever(query, existing)
                if isinstance(supplied, Mapping):
                    semantic_scores = supplied
            except Exception:
                # Optional retrieval failures must not prevent local companionship.
                semantic_scores = {}
        ranked = rank_memories(
            existing,
            query,
            now=now,
            relationship_stage=stage,
            top_k=top_k,
            semantic_scores=semantic_scores,
            scope=scope,
        )
        if not ranked:
            return ()
        return self.store.touch_memories((memory.memory_id for memory, _ in ranked), now=now)

    def build_context(
        self,
        query: str,
        *,
        now: int,
        relationship_stage: str | None = None,
        top_k: int = 4,
    ) -> MemoryContextBundle:
        self.store.expire_memories(now=now)
        # A writer may revoke a source while retrieval is running. Never emit
        # a bundle assembled across two different revocation generations.
        for _attempt in range(3):
            epoch = self.store.context_epoch
            profile = self.valid_profile(now=now)
            if relationship_stage is not None:
                profile = replace(profile, relationship_stage=relationship_stage)
            memories = self.recall(query, now=now, relationship_stage=profile.relationship_stage, top_k=top_k)
            chapter = self.latest_chapter(now=now)
            if chapter is not None and not set(chapter.source_memory_ids).intersection(m.memory_id for m in memories):
                chapter = None
            if epoch == self.store.context_epoch:
                return MemoryContextBundle(profile, memories, chapter, context_epoch=epoch)
        return MemoryContextBundle(CoreBondProfile(self.character_id, self.owner_id),
                                   context_epoch=self.store.context_epoch)

    def valid_profile(self, *, now: int) -> CoreBondProfile:
        profile = self.store.load_profile()
        entries = {entry.memory_id: entry for entry in self.store.load_memories()
                   if entry.is_active(now=now)}
        def valid(field: str, value: str) -> bool:
            refs = profile.evidence.get(f"{field}:{value}", {})
            return bool(refs) and all(key in entries and entries[key].evidence_fingerprint() == fingerprint
                                      for key, fingerprint in refs.items())
        fields = {name: tuple(value for value in getattr(profile, name) if valid(name, value))
                  for name in ("stable_preferences", "boundaries", "shared_rituals", "active_story_threads")}
        alias = profile.player_alias if valid("player_alias", profile.player_alias) else ""
        # The model needs only the active view. Keep lineage in the store and source inspector.
        return replace(profile, player_alias=alias, evidence={}, **fields)

    def valid_chapters(self, *, now: int) -> tuple[MemoryChapter, ...]:
        entries = {entry.memory_id: entry for entry in self.store.load_memories() if entry.is_active(now=now)}
        return tuple(chapter for chapter in self.store.load_chapters() if chapter.source_memory_ids and all(
            key in entries and chapter.source_fingerprints.get(key) == entries[key].evidence_fingerprint()
            for key in chapter.source_memory_ids))

    def consolidate(self, *, now: int, shared_only: bool = False) -> MemoryChapter | None:
        epoch = self.store.context_epoch
        memories = tuple(entry for entry in self.store.load_memories() if entry.is_active(now=now))
        if shared_only:
            from .emotional_memory_reflection import is_shared_experience
            memories = tuple(entry for entry in memories if is_shared_experience(entry))
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
                for item in self.valid_chapters(now=now)
                if frozenset(item.source_memory_ids) == source_set
            ),
            None,
        )
        if existing is not None:
            return existing
        return self.store.upsert_chapter(chapter, expected_epoch=epoch)

    def latest_chapter(self, *, now: int | None = None) -> MemoryChapter | None:
        if now is None:
            now = max((entry.updated_at for entry in self.store.load_memories()), default=0)
        chapters = sorted(self.valid_chapters(now=now), key=lambda chapter: chapter.created_at, reverse=True)
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
        source_memory_ids: tuple[str, ...] = (),
        expected_epoch: int | None = None,
    ) -> CoreBondProfile:
        epoch = self.store.context_epoch if expected_epoch is None else expected_epoch
        old_profile = self.store.load_profile()
        bindings = dict(old_profile.evidence)
        updates = {field: _canonical_profile_value(field, value) for field, value in {
            "player_alias": player_alias, "stable_preferences": new_preference,
            "boundaries": new_boundary, "shared_rituals": new_ritual,
            "active_story_threads": active_story_thread,
        }.items()}
        for field, value in updates.items():
            if not value:
                continue
            entries = [entry for entry in self.store.load_memories() if entry.is_active(now=now)]
            sources = [entry for entry in entries if entry.memory_id in source_memory_ids] if source_memory_ids else [
                entry for entry in entries if entry.summary == value]
            if source_memory_ids and len(sources) != len(set(source_memory_ids)):
                raise ValueError("profile requires current, same-scope evidence")
            if not sources:
                # This API is a trusted user edit, never a model extraction path.
                sources = [self.remember(kind="玩家希望被记住", title="你确认的一条个人信息",
                    summary=value, source="profile_edit", now=now, tags=("关于你",), user_confirmed=True)]
            bindings[f"{field}:{value}"] = {entry.memory_id: entry.evidence_fingerprint() for entry in sources}
        profile = self.reflection.update_bond_profile(
            old_profile,
            player_alias=updates["player_alias"],
            relationship_stage=relationship_stage,
            new_preference=updates["stable_preferences"],
            new_boundary=updates["boundaries"],
            new_ritual=updates["shared_rituals"],
            active_story_thread=updates["active_story_threads"],
            now=now,
        )
        profile = CoreBondProfile.from_dict(replace(profile, evidence=bindings).to_dict())
        self.store.save_profile(profile, expected_epoch=epoch)
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

    def forget(self, memory_id: str, *, now: int, expected_epoch: int | None = None) -> EmotionalMemoryEntry | None:
        return self.store.forget_memory(memory_id, now=now, expected_epoch=expected_epoch)

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
        expected_epoch: int | None = None,
    ) -> EmotionalMemoryEntry | None:
        memory = self.store.upsert_memory(candidate.to_memory(now=now, user_confirmed=user_confirmed),
                                          expected_epoch=expected_epoch)
        return None if memory.deleted else memory

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


def _canonical_profile_value(field: str, value: str | None) -> str | None:
    """Bind evidence to exactly the representation that survives persistence."""
    if value is None:
        return None
    payload = {field: value if field == "player_alias" else [value]}
    normalized = getattr(CoreBondProfile.from_dict(payload), field)
    return normalized if isinstance(normalized, str) else next(iter(normalized), "")


def _clean(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\n", " ").replace("\r", " ").strip().split())[:240]
