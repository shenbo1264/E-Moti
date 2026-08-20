from __future__ import annotations

from guanghe_companion.emotional_memory_policy import EmotionalMemoryPolicy


def test_relationship_unlock_is_pinned_high_importance_memory() -> None:
    policy = EmotionalMemoryPolicy()
    candidate = policy.from_event(
        {
            "event_type": "relationship",
            "event_id": "evt-1",
            "payload": {
                "unlock_id": "unlock_shared_ritual",
                "message": "我们有自己的小默契了。",
            },
        },
        character_id="xingxi_pixel_pet",
        now=100,
    )

    assert candidate is not None
    assert candidate.pinned is True
    assert candidate.importance > 0.9
    assert candidate.kind == "关系里程碑"


def test_first_gift_becomes_keepsake_memory() -> None:
    policy = EmotionalMemoryPolicy()
    candidate = policy.from_event(
        {
            "event_type": "inventory",
            "payload": {
                "action": "gift",
                "item_id": "warm_milk",
                "item_name": "热牛奶",
                "first_time": True,
            },
        },
        character_id="xingxi_pixel_pet",
        now=100,
    )

    assert candidate is not None
    assert candidate.kind == "赠礼"
    assert "第一次" in candidate.tags
    assert candidate.pinned is True


def test_routine_touch_is_not_promoted_without_first_or_milestone() -> None:
    policy = EmotionalMemoryPolicy()
    candidate = policy.from_event(
        {
            "event_type": "memory",
            "payload": {
                "kind": "互动",
                "summary": "轻触：她轻轻回应。",
                "motion": "TouchHead",
            },
        },
        character_id="xingxi_pixel_pet",
        now=100,
    )

    assert candidate is None


def test_raw_screen_summary_is_never_persisted() -> None:
    policy = EmotionalMemoryPolicy()
    candidate = policy.from_event(
        {
            "event_type": "proactive",
            "payload": {
                "summary": "屏幕显示用户正在写某个私密文档",
                "completed": True,
                "user_accepted": True,
                "contains_screen_content": True,
            },
        },
        character_id="xingxi_pixel_pet",
        now=100,
    )

    assert candidate is None


def test_only_completed_confirmed_companion_skill_can_be_memory() -> None:
    policy = EmotionalMemoryPolicy()
    candidate = policy.from_event(
        {
            "event_type": "proactive",
            "payload": {
                "summary": "星汐陪你安静休息了五分钟。",
                "skill_id": "rest_timer",
                "completed": True,
                "user_accepted": True,
                "contains_screen_content": False,
            },
        },
        character_id="xingxi_pixel_pet",
        now=100,
    )

    assert candidate is not None
    assert candidate.kind == "主动陪伴"
    assert candidate.source == "confirmed_companion_skill"


def test_explicit_user_request_requires_confirmation() -> None:
    policy = EmotionalMemoryPolicy()
    candidate = policy.explicit_user_memory(
        "请记住：我不喜欢突然弹出声音",
        character_id="xingxi_pixel_pet",
        now=100,
    )

    assert candidate is not None
    assert candidate.requires_user_confirmation is True
    assert candidate.summary == "我不喜欢突然弹出声音"
