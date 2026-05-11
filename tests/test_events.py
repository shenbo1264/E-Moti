from guanghe_companion.controller import CompanionController
from guanghe_companion.events import build_fallback_events, validate_events
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
