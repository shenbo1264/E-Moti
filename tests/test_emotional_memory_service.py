from __future__ import annotations

from pathlib import Path

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_integration_bridge import (
    confirmed_companion_skill_event,
    enrich_ai_context_with_memory,
    record_companion_events,
)


def _service(tmp_path: Path, character_id: str = "xingxi_pixel_pet") -> EmotionalMemoryService:
    return EmotionalMemoryService(root=tmp_path, character_id=character_id)


def test_service_records_eligible_event(tmp_path: Path) -> None:
    service = _service(tmp_path)
    memory = service.record_event(
        {
            "event_type": "inventory",
            "payload": {
                "action": "gift",
                "item_id": "warm_milk",
                "item_name": "热牛奶",
                "first_time": True,
            },
        },
        now=100,
    )

    assert memory is not None
    assert service.store.load_memories()[0].title == "第一次热牛奶"


def test_explicit_memory_waits_for_user_confirmation(tmp_path: Path) -> None:
    service = _service(tmp_path)
    pending_id = service.propose_explicit_user_memory("你要记得：我喜欢安静的早晨", now=100)

    assert pending_id is not None
    assert service.store.load_memories() == ()

    confirmed = service.confirm_candidate(pending_id, now=110)
    assert confirmed.user_confirmed is True
    assert confirmed.pinned is True
    assert service.store.load_memories()[0].summary == "我喜欢安静的早晨"


def test_rejected_candidate_is_not_stored(tmp_path: Path) -> None:
    service = _service(tmp_path)
    pending_id = service.propose_explicit_user_memory("帮我记住：不要夜间提醒", now=100)

    assert pending_id is not None
    assert service.reject_candidate(pending_id) is True
    assert service.store.load_memories() == ()


def test_context_retrieves_relevant_memory_not_just_latest(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.remember(
        kind="赠礼",
        title="第一次热牛奶",
        summary="你送给星汐一杯热牛奶。",
        source="test",
        now=1,
        importance=0.95,
        pinned=True,
        tags=("第一次", "热牛奶"),
    )
    service.remember(
        kind="互动",
        title="今天摸了摸头",
        summary="一次普通互动。",
        source="test",
        now=1_000,
        importance=0.4,
    )

    context = service.build_context("还记得热牛奶吗", now=2_000)

    assert context.memories[0].title == "第一次热牛奶"


def test_chapter_is_source_grounded(tmp_path: Path) -> None:
    service = _service(tmp_path)
    for index, title in enumerate(("第一次热牛奶", "第一次共同学习", "解锁共同日常"), start=1):
        service.remember(
            kind="关系里程碑" if index == 3 else "共同日常",
            title=title,
            summary=f"发生了：{title}",
            source="test",
            now=index * 100,
            importance=0.8,
            pinned=index == 3,
            tags=("第一次", "共同日常"),
        )

    chapter = service.consolidate(now=1_000)

    assert chapter is not None
    assert len(chapter.source_memory_ids) == 3
    existing = {entry.memory_id for entry in service.store.load_memories()}
    assert set(chapter.source_memory_ids) <= existing


def test_bond_profile_is_small_always_visible_context(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.update_bond_profile(
        now=100,
        player_alias="申博",
        relationship_stage="熟悉的陪伴",
        new_preference="喜欢安静的早晨",
        new_boundary="夜间不要主动出声",
        new_ritual="忙完后一起喝热牛奶",
    )

    context = service.build_context("今天早上做什么", now=200)
    payload = context.to_prompt_payload()

    assert payload["bond_profile"]["player_alias"] == "申博"
    assert "喜欢安静的早晨" in payload["bond_profile"]["stable_preferences"]
    assert "夜间不要主动出声" in payload["bond_profile"]["boundaries"]


def test_superseded_preference_is_preserved_as_deleted_history(tmp_path: Path) -> None:
    service = _service(tmp_path)
    old = service.remember(
        kind="玩家希望被记住",
        title="饮品偏好",
        summary="喜欢咖啡",
        source="explicit_user_request",
        now=100,
        pinned=True,
    )
    new = service.remember(
        kind="玩家希望被记住",
        title="饮品偏好更新",
        summary="现在更喜欢热牛奶",
        source="explicit_user_request",
        now=200,
        pinned=True,
        supersedes=old.memory_id,
    )

    entries = {entry.memory_id: entry for entry in service.store.load_memories()}
    assert entries[old.memory_id].deleted is True
    assert entries[new.memory_id].supersedes == old.memory_id


def test_confirmed_skill_memory_does_not_store_screen_content(tmp_path: Path) -> None:
    service = _service(tmp_path)
    event = confirmed_companion_skill_event(
        summary="星汐陪你安静休息了五分钟。",
        skill_id="rest_timer",
        event_id="skill-1",
    )

    memory_ids = record_companion_events(service, [event], now=100)

    assert len(memory_ids) == 1
    memory = service.store.load_memories()[0]
    assert "屏幕" not in memory.summary
    assert memory.metadata["skill_id"] == "rest_timer"


def test_enrich_context_is_read_only_addition(tmp_path: Path) -> None:
    service = _service(tmp_path)
    bundle = service.build_context("你好", now=100)
    original = {"recent_dialogue": []}

    enriched = enrich_ai_context_with_memory(original, bundle)

    assert original == {"recent_dialogue": []}
    assert "emotional_memory" in enriched


def test_album_groups_memories_as_game_content(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.record_event(
        {
            "event_type": "inventory",
            "payload": {
                "action": "gift",
                "item_id": "warm_milk",
                "item_name": "热牛奶",
                "first_time": True,
            },
        },
        now=100,
    )

    album = service.album()

    assert album["第一次"]
    assert album["礼物与纪念"]
