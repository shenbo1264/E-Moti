from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from guanghe_companion.emotional_memory import (
    CoreBondProfile,
    EmotionalMemoryEntry,
    EmotionalMemoryStore,
    EmotionalSignal,
    make_memory_id,
)
from guanghe_companion.emotional_memory_retrieval import (
    lexical_similarity,
    memory_strength,
    rank_memories,
)


def _memory(
    *,
    title: str,
    summary: str,
    occurred_at: int,
    importance: float = 0.6,
    emotion: float = 0.4,
    character_id: str = "xingxi_pixel_pet",
    pinned: bool = False,
    tags: tuple[str, ...] = (),
) -> EmotionalMemoryEntry:
    return EmotionalMemoryEntry(
        memory_id=make_memory_id(character_id, title, occurred_at),
        character_id=character_id,
        owner_id="local_user",
        kind="共同日常",
        title=title,
        summary=summary,
        source="test",
        occurred_at=occurred_at,
        created_at=occurred_at,
        updated_at=occurred_at,
        emotion=EmotionalSignal("开心", 0.6, emotion),
        importance=importance,
        pinned=pinned,
        tags=tags,
    )


def test_store_roundtrip_and_character_isolation(tmp_path: Path) -> None:
    xingxi = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    other = EmotionalMemoryStore(tmp_path, "other_pet")
    entry = _memory(title="第一次热牛奶", summary="你送了热牛奶", occurred_at=10)

    xingxi.save_memories([entry])

    assert xingxi.load_memories() == (entry.normalized(),)
    assert other.load_memories() == ()


def test_profile_roundtrip(tmp_path: Path) -> None:
    store = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    profile = CoreBondProfile(
        character_id="xingxi_pixel_pet",
        player_alias="申博",
        relationship_stage="共同日常",
        shared_rituals=("忙完后一起喝热牛奶",),
        updated_at=100,
    )

    store.save_profile(profile)

    assert store.load_profile() == profile


def test_lexical_similarity_supports_chinese_bigrams() -> None:
    assert lexical_similarity("热牛奶", "第一次收到热牛奶") > 0.4
    assert lexical_similarity("热牛奶", "今天一起写代码") < 0.1


def test_relevant_older_memory_can_beat_irrelevant_recent_memory() -> None:
    old_relevant = _memory(
        title="第一次热牛奶",
        summary="你送给星汐一杯热牛奶",
        occurred_at=0,
        importance=0.9,
        emotion=0.8,
        pinned=True,
    )
    recent_irrelevant = _memory(
        title="今天摸了摸头",
        summary="一次普通的轻触",
        occurred_at=30 * 86_400,
        importance=0.4,
    )

    ranked = rank_memories(
        [recent_irrelevant, old_relevant],
        "还记得那杯热牛奶吗",
        now=31 * 86_400,
        top_k=2,
    )

    assert ranked[0][0].memory_id == old_relevant.memory_id


def test_pinned_memory_resists_decay() -> None:
    now = 365 * 86_400
    normal = _memory(title="普通一天", summary="普通互动", occurred_at=0, importance=0.8)
    pinned = replace(normal, memory_id="pinned", pinned=True)

    assert memory_strength(pinned, now=now) > memory_strength(normal, now=now)


def test_forget_marks_memory_deleted_without_erasing_provenance(tmp_path: Path) -> None:
    store = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    entry = _memory(title="想忘记的事", summary="用户希望删除", occurred_at=10)
    store.save_memories([entry])

    forgotten = store.forget_memory(entry.memory_id, now=50)

    assert forgotten is not None
    assert forgotten.deleted is True
    assert store.load_memories()[0].memory_id == entry.memory_id
