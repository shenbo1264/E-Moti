from __future__ import annotations

import copy
import json
from pathlib import Path

from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
from guanghe_companion.focus_companion import ActivityKind, FocusCompanionSettings
from guanghe_companion.legacy_memory_migration import migrate_legacy_entries
from guanghe_companion.release_security import redact_json_file, scan_json_file, scan_json_payload


def _runtime(tmp_path: Path) -> CompanionStoryRuntime:
    return CompanionStoryRuntime.create(
        user_data_root=tmp_path,
        character_id="xingxi_pixel_pet",
        focus_settings=FocusCompanionSettings(
            enabled=True,
            threshold_minutes=50,
            break_minutes=5,
            snooze_minutes=20,
            quiet_hours_enabled=False,
        ),
    )


def test_real_controller_inventory_bundle_creates_only_one_first_memory(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    # Mirrors the current controller's paired inventory + memory domain events.
    events = [
        {
            "event_type": "inventory",
            "speech": "gift: 热牛奶",
            "payload": {
                "item_id": "warm_milk",
                "action": "feed",
                "item_name": "热牛奶",
                "icon_path": "item_icons/warm_milk.png",
            },
        },
        {
            "event_type": "memory",
            "speech": "投喂了 热牛奶",
            "payload": {
                "kind": "投喂",
                "summary": "投喂了 热牛奶：charge +12 / mood +2",
                "motion": "Eat",
            },
        },
    ]

    ids = runtime.record_settled_events(events, now=100)

    assert len(ids) == 1
    memories = runtime.memory.store.load_memories()
    assert len(memories) == 1
    assert memories[0].title == "第一次热牛奶"
    assert memories[0].metadata["item_id"] == "warm_milk"


def test_repeated_routine_gift_stays_out_of_long_term_album(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    event = {
        "event_type": "inventory",
        "payload": {"item_id": "warm_milk", "action": "feed", "item_name": "热牛奶"},
    }
    assert runtime.record_settled_events([event], now=100)
    assert runtime.record_settled_events([event], now=200) == []
    assert len(runtime.memory.store.load_memories()) == 1



def test_first_study_is_promoted_from_current_interaction_event_shape(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    event = {
        "event_type": "memory",
        "payload": {
            "kind": "互动",
            "summary": "共同学习：把这一小段时间记成共同学习吧。",
            "motion": "Study",
        },
    }

    ids = runtime.record_settled_events([event], now=300)

    assert len(ids) == 1
    memory = runtime.memory.store.load_memories()[0]
    assert memory.kind == "共同学习"
    assert "第一次" in memory.tags

def test_unrelated_memory_is_not_forced_into_context(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.memory.remember(
        kind="赠礼",
        title="第一次热牛奶",
        summary="你送给星汐一杯热牛奶。",
        source="test",
        now=1,
        importance=0.95,
        pinned=True,
        tags=("第一次", "热牛奶"),
    )

    _context, bundle = runtime.build_expression_context(
        {}, query="今天想聊聊像素动画的边缘锯齿", now=10_000, relationship_stage="初识"
    )

    assert bundle.memories == ()


def test_focus_completion_becomes_memory_without_mutating_game_state(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    game_state = {
        "focus": 72,
        "charge": 65,
        "stability": 78,
        "mood": 58,
        "trust": 5,
        "coins": 20,
        "inventory": {"warm_milk": 0},
    }
    before = copy.deepcopy(game_state)

    offer = runtime.focus.inject_demo_focus(
        focused_minutes=52,
        kind=ActivityKind.CODING,
        now=10_000,
        pet_stability=game_state["stability"],
        pet_mode="Calm",
    )
    assert offer and offer[0].event_type == "focus_break_offer"
    runtime.focus.confirm_break(now=10_001, duration_seconds_override=2)
    completed = runtime.focus.tick(now=10_004)
    assert completed and completed[0].payload["state_mutation"] is False

    memory = runtime.record_focus_completion(completed[0], now=10_004, event_id="focus-1")

    assert memory is not None
    assert memory.kind == "主动陪伴"
    assert "星汐" in memory.summary
    assert memory.title == "星汐在合适的时候探出了头"
    assert game_state == before


def test_focus_throttle_persists_but_process_names_do_not(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.focus.inject_demo_focus(now=20_000, focused_minutes=52)
    runtime.focus.mute_today(now=20_001)

    state_path = tmp_path / "characters" / "xingxi_pixel_pet" / "focus_companion_state.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))

    assert payload["muted_day_key"]
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    assert "code.exe" not in serialized
    assert "window_title" not in serialized


def test_chapter_consolidation_is_idempotent(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    for index, title in enumerate(("第一次热牛奶", "第一次共同学习", "解锁共同日常"), start=1):
        runtime.memory.remember(
            kind="关系里程碑" if index == 3 else "共同日常",
            title=title,
            summary=f"发生了：{title}",
            source="test",
            now=index * 100,
            importance=0.8,
            pinned=index == 3,
            tags=("第一次", "共同日常"),
        )
    first = runtime.memory.consolidate(now=1_000)
    second = runtime.memory.consolidate(now=2_000)

    assert first is not None
    assert second is not None
    assert first.chapter_id == second.chapter_id
    assert len(runtime.memory.store.load_chapters()) == 1


def test_legacy_migration_skips_operational_project_notes(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    report = migrate_legacy_entries(
        runtime.memory,
        [
            {"key": "course_submission_route", "summary": "课程包怎么演示", "updated_at": "2026-06-24"},
            {
                "key": "relationship:shared_ritual",
                "category": "relationship_unlock",
                "summary": "我们有自己的小默契了。",
                "source": "relationship_unlock",
                "updated_at": 100,
            },
        ],
        now=200,
    )

    assert len(report.migrated_ids) == 1
    assert report.skipped_keys == ("course_submission_route",)


def test_secret_guard_finds_and_redacts_public_config(tmp_path: Path) -> None:
    source = tmp_path / "private.json"
    target = tmp_path / "public.json"
    source.write_text(
        json.dumps(
            {
                "screen_observation": {"vision_api_key": "TEST_SECRET_VALUE_VISION_12345"},
                "expression": {"api_key": "TEST_SECRET_VALUE_EXPRESSION_12345"},
                "asr": {"api_key": "local"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert not scan_json_file(source).ok

    redact_json_file(source, target)

    assert scan_json_file(target).ok
    redacted = json.loads(target.read_text(encoding="utf-8"))
    assert redacted["screen_observation"]["vision_api_key"] == ""
    assert redacted["expression"]["api_key"] == ""
    assert redacted["asr"]["api_key"] == ""


def test_secret_guard_accepts_empty_template() -> None:
    report = scan_json_payload({"api_key": "", "token": "", "provider": "deepseek"})
    assert report.ok


def test_memory_album_view_model_uses_game_language(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.record_settled_events(
        [
            {
                "event_type": "inventory",
                "payload": {
                    "item_id": "warm_milk",
                    "action": "feed",
                    "item_name": "热牛奶",
                },
            },
            {
                "event_type": "relationship",
                "payload": {
                    "stage": "共同日常",
                    "unlock_id": "unlock_shared_ritual",
                    "message": "我们有自己的小默契了。",
                },
            },
        ],
        now=100,
    )

    album = runtime.build_memory_album()
    payload = [section.to_dict() for section in album]
    serialized = json.dumps(payload, ensure_ascii=False)

    assert "第一次" in serialized
    assert "小默契" in serialized
    assert "warm_milk" in serialized
    assert "vector" not in serialized.lower()
    assert "database" not in serialized.lower()
    assert "屏幕截图" not in serialized


def test_offer_public_copy_is_character_facing(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    events = runtime.focus.inject_demo_focus(
        focused_minutes=52,
        kind=ActivityKind.CODING,
        now=30_000,
        pet_stability=78,
        pet_mode="Calm",
    )
    offer = events[0].payload

    assert offer["eyebrow"] == "探头时刻"
    assert offer["title"] == "星汐从桌角探出头"
    assert "决战到天亮" in offer["speech"]
    assert [action["label"] for action in offer["actions"]] == [
        "陪她歇一会儿",
        "再等一会儿",
        "今天先别管我",
    ]
