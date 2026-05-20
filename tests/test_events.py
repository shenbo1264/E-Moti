import guanghe_companion.events as events_module
from guanghe_companion.controller import CompanionController
from guanghe_companion.events import (
    CompanionEvent,
    EVENT_PAYLOAD_FIELDS,
    EventBuilder,
    EventContext,
    EventValidator,
    build_fallback_events,
    build_typed_fallback_events,
    validate_events,
)
from guanghe_companion.models import CompanionState


def make_state() -> CompanionState:
    controller = CompanionController(auto_load=False)
    return controller.state


def test_build_fallback_events_returns_character_stat_and_choice_rows():
    state = make_state()
    events = build_fallback_events(
        state=state,
        feedback="信号有点乱，但我还在。先做一个简单动作吧。",
        choices=["轻触", "投喂", "安抚", "休息"],
        effect="DISAPPOINTED",
    )

    assert len(events) == 3
    assert events[0]["character_name"] == state.character_name
    assert events[0]["effect"] == "DISAPPOINTED"
    assert events[1]["character_name"] == "STAT"
    assert "专注 72" in events[1]["speech"]
    assert events[2]["character_name"] == "CHOICE"
    assert "轻触 / 投喂 / 安抚 / 休息" in events[2]["speech"]


def test_build_typed_fallback_events_returns_stable_event_types_and_legacy_rows():
    state = make_state()

    events = build_typed_fallback_events(
        state=state,
        feedback="信号有点乱，但我还在。",
        choices=["轻触", "安抚"],
        effect="ATTENTION",
    )

    assert [event.event_type for event in events] == ["speech", "stat", "choice"]
    assert all(isinstance(event, CompanionEvent) for event in events)
    assert [event.to_legacy_dict() for event in events] == build_fallback_events(
        state=state,
        feedback="信号有点乱，但我还在。",
        choices=["轻触", "安抚"],
        effect="ATTENTION",
    )


def test_event_builder_creates_local_stat_and_choice_events_with_payload_anchors():
    state = make_state()
    builder = EventBuilder(state)

    events = builder.fallback_events(
        feedback="信号稳定。",
        choices=["轻触", "共同学习"],
        effect="ATTENTION",
    )

    stat_event = events[1]
    choice_event = events[2]
    assert [event.event_type for event in events] == ["speech", "stat", "choice"]
    assert stat_event.payload["stats"] == {
        "focus": 72,
        "charge": 65,
        "stability": 78,
        "mood": 58,
        "trust": 5,
    }
    assert choice_event.payload["choices"] == ["轻触", "共同学习"]


def test_event_payload_schema_covers_stage_one_event_types():
    assert EVENT_PAYLOAD_FIELDS == {
        "speech": frozenset(),
        "stat": frozenset({"stats"}),
        "choice": frozenset({"choices"}),
        "motion": frozenset({"motion", "reason"}),
        "memory": frozenset({"kind", "summary", "motion"}),
        "relationship": frozenset({"stage", "unlock_id", "message"}),
        "inventory": frozenset({"item_id", "action", "item_name", "icon_path"}),
        "proactive": frozenset({"kind", "summary"}),
        "system": frozenset({"code", "message"}),
    }


def test_event_builder_creates_stage_one_typed_events_with_fixed_payloads():
    state = make_state()
    builder = EventBuilder(state)

    built_events = [
        builder.motion_event(motion="TouchHead", reason="轻触后切换动作"),
        builder.memory_event(kind="互动", summary="轻触：她靠近了一点", motion="TouchHead"),
        builder.relationship_event(stage="熟悉的陪伴", unlock_id="unlock_first_nickname", message="第一次主动称呼解锁了。"),
        builder.inventory_event(item_id="warm_milk", action="feed", item_name="热牛奶", icon_path="icons/warm_milk.png"),
        builder.proactive_event(kind="low_charge", summary="能量有点低时主动陪伴。"),
        builder.system_event(code="save_ok", message="存档已保存。"),
    ]

    assert [event.event_type for event in built_events] == [
        "motion",
        "memory",
        "relationship",
        "inventory",
        "proactive",
        "system",
    ]
    for event in built_events:
        assert EVENT_PAYLOAD_FIELDS[event.event_type].issubset(event.payload.keys())


def test_event_builder_groups_action_domain_events():
    state = make_state()
    builder = EventBuilder(state)

    events = builder.action_domain_events(
        motion="TouchHead",
        feedback="我听见你靠近了。",
        effect="ATTENTION",
        memory_kind="互动",
        memory_summary="轻触：我听见你靠近了。",
        relationship_unlocks=[
            {
                "stage": "熟悉的陪伴",
                "unlock_id": "unlock_first_nickname",
                "message": "第一次主动称呼解锁了。",
            }
        ],
    )

    assert [event.event_type for event in events] == ["motion", "memory", "relationship"]
    assert events[0].payload == {"motion": "TouchHead", "reason": "我听见你靠近了。"}
    assert events[1].payload == {"kind": "互动", "summary": "轻触：我听见你靠近了。", "motion": "TouchHead"}
    assert events[2].payload["unlock_id"] == "unlock_first_nickname"


def test_event_builder_groups_inventory_domain_events():
    state = make_state()
    builder = EventBuilder(state)

    events = builder.inventory_domain_events(
        motion="Eat",
        feedback="投喂了热牛奶。",
        effect="ATTENTION",
        item_id="warm_milk",
        action="feed",
        item_name="热牛奶",
        icon_path="icons/warm_milk.png",
        memory_kind="投喂",
        memory_summary="投喂了热牛奶：charge +12",
    )

    assert [event.event_type for event in events] == ["motion", "inventory", "memory"]
    assert events[1].payload["item_id"] == "warm_milk"
    assert events[1].payload["action"] == "feed"
    assert events[2].payload["kind"] == "投喂"


def test_event_builder_groups_proactive_domain_events():
    state = make_state()
    builder = EventBuilder(state)

    events = builder.proactive_domain_events(
        motion="Tick",
        feedback="能量有点低了。",
        effect="ATTENTION",
        proactive_kind="low_charge",
        proactive_summary="能量有点低时主动陪伴：能量有点低了。",
    )

    assert [event.event_type for event in events] == ["motion", "proactive", "memory"]
    assert events[1].payload["kind"] == "low_charge"
    assert events[2].payload == {
        "kind": "主动陪伴",
        "summary": "能量有点低时主动陪伴：能量有点低了。",
        "motion": "Tick",
    }


def test_event_validator_accepts_typed_events_only_when_required_payload_fields_exist():
    state = make_state()
    validator = EventValidator(state)
    builder = EventBuilder(state)
    valid_event = builder.motion_event(motion="TouchHead", reason="轻触后切换动作")
    invalid_event = CompanionEvent(
        event_type="motion",
        character_name="MOTION",
        speech="切换动作",
        payload={"motion": "TouchHead"},
    )

    assert validator.validate_typed([valid_event], fallback_feedback="fallback", choices=["轻触"]) == [valid_event]

    fallback = validator.validate_typed([invalid_event], fallback_feedback="字段缺失，切回本地反馈。", choices=["轻触"])

    assert [event.event_type for event in fallback] == ["speech", "stat", "choice"]
    assert fallback[0].speech == "字段缺失，切回本地反馈。"


def test_event_context_builds_ai_expressor_compatible_snapshot():
    state = make_state()
    actions = [{"action_id": "touch", "label": "轻触", "motion": "TouchHead", "enabled": True}]

    context = EventContext(
        state=state,
        motion="TouchHead",
        feedback="我听见你靠近了。",
        delta_text="mood +4",
        goal="信任达到 20",
        actions=actions,
    )

    assert context.to_expressor_dict() == {
        "character_name": state.character_name,
        "mode": "Calm",
        "motion": "TouchHead",
        "focus": 72,
        "charge": 65,
        "stability": 78,
        "mood": 58,
        "trust": 5,
        "feedback": "我听见你靠近了。",
        "delta_text": "mood +4",
        "goal": "信任达到 20",
        "actions": actions,
        "memory_log": [],
    }


def test_action_event_effect_keeps_controller_effect_mapping():
    assert events_module.action_event_effect("touch", allowed=True, mode="Calm") == "ATTENTION"
    assert events_module.action_event_effect("study", allowed=True, mode="Calm") == "ATTENTION"
    assert events_module.action_event_effect("drag", allowed=True, mode="Calm") == "SWITCH"
    assert events_module.action_event_effect("study", allowed=False, mode="Calm") == "DISAPPOINTED"
    assert events_module.action_event_effect("touch", allowed=False, mode="Overload") == "OVERLOAD"


def test_event_validator_returns_typed_events_and_falls_back_for_invalid_rows():
    state = make_state()
    validator = EventValidator(state)
    good_events = [
        {"character_name": state.character_name, "speech": "我听见你靠近了。", "sprite": "1", "effect": "ATTENTION"},
        {"character_name": "STAT", "speech": "专注 72 / 能量 65 / 稳定 78 / 心情 58 / 信任 5", "sprite": "-1", "effect": ""},
    ]

    validated = validator.validate(good_events, fallback_feedback="fallback", choices=["轻触"])
    fallback = validator.validate(
        [{"character_name": "HACK", "speech": "x", "sprite": "1", "effect": "ATTENTION"}],
        fallback_feedback="校验失败，切回本地反馈。",
        choices=["轻触"],
    )

    assert [event.event_type for event in validated] == ["speech", "stat"]
    assert all(isinstance(event, CompanionEvent) for event in validated)
    assert [event.event_type for event in fallback] == ["speech", "stat", "choice"]
    assert fallback[0].speech == "校验失败，切回本地反馈。"
    assert fallback[0].effect == "DISAPPOINTED"


def test_validate_events_replaces_invalid_rows_with_fallback():
    state = make_state()
    bad_events = [
        {"character_name": "HACK", "speech": "x" * 200, "sprite": "99", "effect": "BOOM"},
    ]

    validated = validate_events(
        state=state,
        events=bad_events,
        fallback_feedback="校验失败，切回本地反馈。",
        choices=["轻触", "共同学习"],
    )

    assert len(validated) == 3
    assert validated[0]["character_name"] == state.character_name
    assert validated[0]["speech"] == "校验失败，切回本地反馈。"
    assert validated[2]["character_name"] == "CHOICE"


def test_validate_events_falls_back_for_non_string_adapter_fields():
    state = make_state()
    bad_events = [
        {"character_name": state.character_name, "speech": "ok", "sprite": 1, "effect": "ATTENTION"},
    ]

    validated = validate_events(
        state=state,
        events=bad_events,
        fallback_feedback="adapter field invalid; local fallback",
        choices=["杞昏Е"],
    )

    assert len(validated) == 3
    assert validated[0]["character_name"] == state.character_name
    assert validated[0]["speech"] == "adapter field invalid; local fallback"
    assert validated[0]["effect"] == "DISAPPOINTED"


def test_validate_events_keeps_compliant_rows():
    state = make_state()
    good_events = [
        {"character_name": state.character_name, "speech": "我听见你靠近了。", "sprite": "1", "effect": "ATTENTION"},
        {"character_name": "STAT", "speech": "专注 72 / 能量 65 / 稳定 78 / 心情 58 / 信任 5", "sprite": "-1", "effect": ""},
    ]

    validated = validate_events(
        state=state,
        events=good_events,
        fallback_feedback="fallback",
        choices=["轻触"],
    )

    assert validated == good_events
