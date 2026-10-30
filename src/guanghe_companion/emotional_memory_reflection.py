from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from .emotional_memory import (
    CoreBondProfile,
    EmotionalMemoryEntry,
    MemoryChapter,
    make_memory_id,
)


@dataclass(frozen=True, slots=True)
class MemoryRecollection:
    memory_id: str
    character_id: str
    fingerprint: str
    context_epoch: int
    summary: str
    valid_until: int = 0
    interest_topic: str = ""

    @property
    def cooldown_key(self) -> str:
        return f"memory_recollection:{self.memory_id}"


def is_shared_experience(memory: EmotionalMemoryEntry) -> bool:
    if not memory.source_ids:
        return False
    if memory.source == "confirmed_companion_skill":
        return memory.kind == "主动陪伴"
    if memory.source == "relationship_unlock":
        return memory.kind == "关系里程碑"
    return memory.source == "game_event" and memory.kind in {
        "赠礼", "投喂", "互动", "共同学习", "玩耍", "安抚", "休息",
    }


def is_chat_interest(memory: EmotionalMemoryEntry) -> bool:
    metadata = memory.metadata
    value = metadata.get("fact_value")
    return (memory.source in {"user_chat", "user_correction"} and bool(memory.source_ids)
            and metadata.get("speaker") == "user" and metadata.get("scene") == "companion_chat"
            and metadata.get("fact_slot") in {"preference:饮料偏好:like", "preference:个人偏好:like"}
            and isinstance(value, str) and 0 < len(value) <= 40)


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
            if not memory.deleted and (memory.importance >= 0.68 or memory.pinned
                                       or (is_shared_experience(memory) and memory.importance >= 0.60))
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
        summary = _chapter_summary(significant)
        # 章节存储上限为320字；裁剪完整事件并同步来源，避免半句事实失去语义。
        while len(summary) > 320 and len(significant) > 2:
            significant.pop(0)
            summary = _chapter_summary(significant)
        if len(summary) > 320:
            return None
        source_ids = tuple(memory.memory_id for memory in significant)
        title = _chapter_title(significant)
        return MemoryChapter(
            chapter_id=make_memory_id(character_id, "chapter", now, *source_ids),
            character_id=character_id,
            title=title,
            summary=summary,
            source_memory_ids=source_ids,
            created_at=max(0, int(now)),
            tags=("关系章节", *tuple(dict.fromkeys(tag for memory in significant for tag in memory.tags))[:4]),
            source_fingerprints={memory.memory_id: memory.evidence_fingerprint() for memory in significant},
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
    if not all(is_shared_experience(memory) for memory in memories):
        return "这一段保存的记忆"
    tags = {tag for memory in memories for tag in memory.tags}
    if "第一次" in tags and "共同日常" in tags:
        return "我们的第一份小默契"
    if any(memory.kind == "关系里程碑" for memory in memories):
        return "从初识到熟悉的陪伴"
    if any(memory.kind in {"赠礼", "投喂"} for memory in memories):
        return "被好好收下的小心意"
    return "一起留下的这一小段日子"


def _chapter_summary(memories: list[EmotionalMemoryEntry]) -> str:
    period = f"逻辑时间{memories[0].occurred_at}—{memories[-1].occurred_at}秒"
    body = "随后，".join(memory.summary if memory.summary.endswith(("。", "！", "？")) else memory.summary + "。" for memory in memories)
    themes: dict[str, set[tuple[str, ...]]] = {}
    for memory in memories:
        if is_shared_experience(memory):
            themes.setdefault(memory.kind, set()).add(tuple(sorted(memory.source_ids)))
    repeated = "、".join(f"{kind}记录{len(sources)}次" for kind, sources in themes.items() if len(sources) >= 2)
    recurring = f"重复主题：{repeated}。" if repeated else ""
    return f"{period}。{body}{recurring}仅归纳已记录事件。"
