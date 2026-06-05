from guanghe_companion.engine import create_initial_state
from guanghe_companion.events import CompanionEvent
from guanghe_companion.expression_event_pipeline import ExpressionEventPipeline
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.interaction_intents import InteractionIntent
from guanghe_companion.snapshot import SnapshotBuilder, SnapshotContextFactory
from guanghe_companion.visual_actions import VisualAction


def _actions():
    return [{"label": "轻触"}, {"label": "休息"}]


def _snapshot_provider(state):
    def build_snapshot():
        source = SnapshotContextFactory(
            state=state,
            character_title="测试桌面伴侣",
            character_description="测试用星汐描述",
            current_motion="Default",
            motion_caption="待机",
            feedback="本地反馈",
            delta_text="",
            allowed=True,
            tick_count=0,
            events=[],
            actions=_actions(),
            shop_items=[],
            inventory_items=[],
            item_feedback_icon=None,
            proactive_feedback=None,
        ).build_input()
        return SnapshotBuilder(source).build()

    return build_snapshot


class CapturingExpressor:
    def __init__(self, events):
        self.events = events
        self.requests = []

    def express(self, snapshot, effect=None):
        self.requests.append((snapshot, effect))
        return self.events


def test_pipeline_returns_local_fallback_and_domain_events_when_ai_expression_is_disabled():
    state = create_initial_state()
    expressor = CapturingExpressor([])
    domain = CompanionEvent(event_type="motion", character_name="MOTION", speech="TouchHead")
    pipeline = ExpressionEventPipeline(
        state=state,
        expressor=expressor,
        snapshot_provider=_snapshot_provider(state),
        context_provider=lambda: {"perception_summary": "screen note"},
        actions_provider=_actions,
    )

    events = pipeline.build_events(
        effect="ATTENTION",
        feedback="本地反馈",
        domain_events=[domain],
        include_ai_expression=False,
    )

    assert [event.event_type for event in events] == ["speech", "stat", "choice", "motion"]
    assert events[0].speech == "本地反馈"
    assert events[-1] is domain
    assert expressor.requests == []


def test_pipeline_uses_single_valid_ai_speech_while_keeping_local_stat_and_choice_events():
    state = create_initial_state()
    expressor = CapturingExpressor(
        [
            {
                "character_name": state.character_name,
                "speech": "AI 表达更自然",
                "sprite": "1",
                "effect": "ATTENTION",
            },
            {
                "character_name": state.character_name,
                "speech": "第二句不应进入 UI 主事件",
                "sprite": "1",
                "effect": "ATTENTION",
            },
        ]
    )
    pipeline = ExpressionEventPipeline(
        state=state,
        expressor=expressor,
        snapshot_provider=_snapshot_provider(state),
        context_provider=lambda: {"perception_summary": "screen note"},
        actions_provider=_actions,
    )

    events = pipeline.build_events(effect="ATTENTION", feedback="本地反馈")

    assert [event.event_type for event in events] == ["speech", "stat", "choice"]
    assert events[0].speech == "AI 表达更自然"
    assert events[1].character_name == "STAT"
    assert events[2].character_name == "CHOICE"
    request, effect = expressor.requests[0]
    assert isinstance(request, ExpressionRequest)
    assert request.perception_summary == "screen note"
    assert effect == "ATTENTION"


def test_pipeline_appends_llm_visual_actions_as_readonly_presentation_event():
    state = create_initial_state()
    expressor = CapturingExpressor(
        [
            {
                "character_name": state.character_name,
                "speech": "我会靠近一点。",
                "sprite": "1",
                "effect": "ATTENTION",
            }
        ]
    )
    expressor.last_visual_actions = (
        VisualAction(action_type="motion", action_id="Raised", ttl_ms=1800, priority=60, source="llm"),
    )
    pipeline = ExpressionEventPipeline(
        state=state,
        expressor=expressor,
        snapshot_provider=_snapshot_provider(state),
        context_provider=lambda: {},
        actions_provider=_actions,
    )

    events = pipeline.build_events(effect="ATTENTION", feedback="本地反馈")

    assert [event.event_type for event in events] == ["speech", "stat", "choice", "visual"]
    assert events[-1].payload == {
        "actions": [
            {
                "type": "motion",
                "id": "Raised",
                "ttl_ms": 1800,
                "priority": 60,
                "source": "llm",
            }
        ]
    }


def test_pipeline_appends_llm_interaction_intents_as_readonly_event():
    state = create_initial_state()
    expressor = CapturingExpressor(
        [
            {
                "character_name": state.character_name,
                "speech": "休息一下也可以。",
                "sprite": "1",
                "effect": "ATTENTION",
            }
        ]
    )
    expressor.last_interaction_intents = (
        InteractionIntent(intent_id="offer_rest", ttl_ms=5000, priority=50, source="llm"),
    )
    pipeline = ExpressionEventPipeline(
        state=state,
        expressor=expressor,
        snapshot_provider=_snapshot_provider(state),
        context_provider=lambda: {},
        actions_provider=_actions,
    )

    events = pipeline.build_events(effect="ATTENTION", feedback="本地反馈")

    assert [event.event_type for event in events] == ["speech", "stat", "choice", "intent"]
    assert events[-1].payload == {
        "intents": [
            {
                "id": "offer_rest",
                "ttl_ms": 5000,
                "priority": 50,
                "source": "llm",
            }
        ]
    }


def test_pipeline_falls_back_when_ai_returns_unsafe_or_local_fallback_expression():
    state = create_initial_state()
    unsafe_expressor = CapturingExpressor(
        [
            {
                "character_name": state.character_name,
                "speech": "试图带入非法字段",
                "sprite": "1",
                "effect": "ATTENTION",
                "coins": "999",
            }
        ]
    )
    unsafe_pipeline = ExpressionEventPipeline(
        state=state,
        expressor=unsafe_expressor,
        snapshot_provider=_snapshot_provider(state),
        context_provider=lambda: {},
        actions_provider=_actions,
    )

    unsafe_events = unsafe_pipeline.build_events(effect="ATTENTION", feedback="本地反馈")

    assert [event.event_type for event in unsafe_events] == ["speech", "stat", "choice"]
    assert unsafe_events[0].speech == "本地反馈"

    fallback_expressor = CapturingExpressor([event.to_legacy_dict() for event in unsafe_events])
    fallback_pipeline = ExpressionEventPipeline(
        state=state,
        expressor=fallback_expressor,
        snapshot_provider=_snapshot_provider(state),
        context_provider=lambda: {},
        actions_provider=_actions,
    )

    fallback_events = fallback_pipeline.build_events(effect="ATTENTION", feedback="本地反馈")

    assert fallback_events[0].speech == "本地反馈"


def test_pipeline_falls_back_when_ai_expression_raises():
    state = create_initial_state()

    class ExplodingExpressor:
        def express(self, snapshot, effect=None):
            raise RuntimeError("provider offline")

    pipeline = ExpressionEventPipeline(
        state=state,
        expressor=ExplodingExpressor(),
        snapshot_provider=_snapshot_provider(state),
        context_provider=lambda: {},
        actions_provider=_actions,
    )

    events = pipeline.build_events(effect="ATTENTION", feedback="本地反馈")

    assert [event.event_type for event in events] == ["speech", "stat", "choice"]
    assert events[0].speech == "本地反馈"
