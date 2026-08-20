from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .emotional_memory import (
    CoreBondProfile,
    EmotionalMemoryEntry,
    MemoryChapter,
    make_memory_id,
)


class MemoryReflectionService:
    """Source-grounded consolidation for relationship chapters.

    The default implementation is deterministic. A future LLM writer may polish
    the prose, but it must preserve the same source ids and may not introduce a
    fact that cannot be traced to a stored memory.
    """

    def should_consolidate(self, memories: Iterable[EmotionalMemoryEntry]) -> bool:
        significant = [
            memory
            for memory in memories
            if not memory.deleted and (memory.importance >= 0.68 or memory.pinned)
        ]
        return len(significant) >= 3

    def build_chapter(
        self,
        memories: Iterable[EmotionalMemoryEntry],
        *,
        character_id: str,
        now: int,
    ) -> MemoryChapter | None:
        significant = sorted(
            (
                memory
                for memory in memories
                if not memory.deleted and (memory.importance >= 0.60 or memory.pinned)
            ),
            key=lambda memory: (memory.occurred_at, memory.importance),
        )[-6:]
        if len(significant) < 2:
            return None
        source_ids = tuple(memory.memory_id for memory in significant)
        title = _chapter_title(significant)
        summary = _chapter_summary(significant)
        return MemoryChapter(
            chapter_id=make_memory_id(character_id, "chapter", now, *source_ids),
            character_id=character_id,
            title=title,
            summary=summary,
            source_memory_ids=source_ids,
            created_at=max(0, int(now)),
            tags=("关系章节", *tuple(dict.fromkeys(tag for memory in significant for tag in memory.tags))[:4]),
        )

    def update_bond_profile(
        self,
        profile: CoreBondProfile,
        *,
        player_alias: str | None = None,
        relationship_stage: str | None = None,
        new_preference: str | None = None,
        new_boundary: str | None = None,
        new_ritual: str | None = None,
        active_story_thread: str | None = None,
        now: int,
    ) -> CoreBondProfile:
        return replace(
            profile,
            player_alias=player_alias if player_alias is not None else profile.player_alias,
            relationship_stage=(
                relationship_stage if relationship_stage is not None else profile.relationship_stage
            ),
            stable_preferences=_append_unique(profile.stable_preferences, new_preference, limit=12),
            boundaries=_append_unique(profile.boundaries, new_boundary, limit=12),
            shared_rituals=_append_unique(profile.shared_rituals, new_ritual, limit=8),
            active_story_threads=_append_unique(
                profile.active_story_threads,
                active_story_thread,
                limit=8,
            ),
            updated_at=max(0, int(now)),
        )


def _append_unique(values: tuple[str, ...], item: str | None, *, limit: int) -> tuple[str, ...]:
    if not item:
        return values[:limit]
    normalized = " ".join(item.strip().split())
    if not normalized:
        return values[:limit]
    return tuple([normalized, *(value for value in values if value != normalized)][:limit])


def _chapter_title(memories: list[EmotionalMemoryEntry]) -> str:
    tags = {tag for memory in memories for tag in memory.tags}
    if "第一次" in tags and "共同日常" in tags:
        return "我们的第一份小默契"
    if any(memory.kind == "关系里程碑" for memory in memories):
        return "从初识到熟悉的陪伴"
    if any(memory.kind in {"赠礼", "投喂"} for memory in memories):
        return "被好好收下的小心意"
    return "星汐记住的这一小段日子"


def _chapter_summary(memories: list[EmotionalMemoryEntry]) -> str:
    fragments = [memory.title for memory in memories[:4]]
    if len(fragments) == 1:
        return f"这一章从“{fragments[0]}”开始。"
    body = "、".join(f"“{fragment}”" for fragment in fragments[:-1])
    return f"这一章里留下了{body}，还有“{fragments[-1]}”。这些瞬间一起组成了你们正在形成的共同日常。"
