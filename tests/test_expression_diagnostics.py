import guanghe_companion.expression_diagnostics as diagnostics_module
from guanghe_companion.ai_expressor import ExpressionRequest, ShinsekaiAIExpressor
from guanghe_companion.engine import create_initial_state
from guanghe_companion.events import build_typed_fallback_events
from guanghe_companion.expression_settings import normalize_expression_settings
from guanghe_companion.snapshot import SnapshotBuilder, SnapshotContextFactory


def _snapshot(state, events=None):
    actions = [{"label": "Touch"}, {"label": "Rest"}]
    builder_input = SnapshotContextFactory(
        state=state,
        character_title="Desktop companion",
        character_description="Local original character",
        current_motion="Default",
        motion_caption="Idle",
        feedback="local feedback",
        delta_text="no change",
        allowed=True,
        tick_count=0,
        events=events or build_typed_fallback_events(state, "local feedback", ["Touch", "Rest"], effect="ATTENTION"),
        actions=actions,
        shop_items=[],
        inventory_items=[],
        item_feedback_icon=None,
        proactive_feedback=None,
    ).build_input()
    return SnapshotBuilder(builder_input).build()


def test_expression_diagnostics_service_success_does_not_mutate_growth_state():
    service_cls = getattr(diagnostics_module, "ExpressionDiagnosticsService", None)
    assert service_cls is not None

    class FakeExpressor:
        enabled = True
        last_fallback_reason = ""

        def __init__(self):
            self.requests = []

        def express(self, request, effect=None):
            self.requests.append((request, effect))
            return [
                {
                    "character_name": request.character_name,
                    "speech": "LLM connected",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    state = create_initial_state(now=0)
    before_inventory = dict(state.inventory)
    expressor = FakeExpressor()
    service = service_cls(
        settings=normalize_expression_settings({"enabled": True, "api_key": "test-key"}),
        expressor=expressor,
        state_provider=lambda: state,
        snapshot_provider=lambda: _snapshot(state),
        context_provider=lambda: {"perception_summary": "readonly"},
        choices_provider=lambda: ("Touch", "Rest"),
    )

    result = service.test_provider().to_public_dict()

    assert result["ok"] is True
    assert result["stage"] == "event_validation"
    assert result["reason"] == ""
    assert result["speech"] == "LLM connected"
    assert result["effect"] == "ATTENTION"
    assert "api_key" not in result
    assert isinstance(expressor.requests[0][0], ExpressionRequest)
    assert expressor.requests[0][1] == "ATTENTION"
    assert state.inventory == before_inventory
    assert state.memory_log == []
    assert state.unlocks == []


def test_expression_diagnostics_service_reports_missing_key_before_provider_call():
    service_cls = getattr(diagnostics_module, "ExpressionDiagnosticsService", None)
    assert service_cls is not None

    class FailingIfCalledExpressor:
        enabled = False

        def express(self, request, effect=None):
            raise AssertionError("missing key should stop before provider call")

    state = create_initial_state(now=0)
    service = service_cls(
        settings=normalize_expression_settings(
            {
                "enabled": True,
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "base_url": "https://api.deepseek.com",
                "api_key": "",
            }
        ),
        expressor=FailingIfCalledExpressor(),
        state_provider=lambda: state,
        snapshot_provider=lambda: _snapshot(state),
        context_provider=lambda: {},
        choices_provider=lambda: ("Touch", "Rest"),
    )

    result = service.test_provider().to_public_dict()

    assert result["ok"] is False
    assert result["stage"] == "settings"
    assert result["reason"] == "missing_api_key"
    assert result["provider"] == "deepseek"
    assert result["model"] == "deepseek-v4-flash"
    assert result["base_url"] == "https://api.deepseek.com"
    assert "api_key" not in result


def test_expression_diagnostics_service_reports_event_validation_failure_for_overreach():
    service_cls = getattr(diagnostics_module, "ExpressionDiagnosticsService", None)
    assert service_cls is not None

    state = create_initial_state(now=0)
    expressor = ShinsekaiAIExpressor(
        llm_client=lambda prompt: '[{"type":"speech","speech":"try write","effect":"ATTENTION","coins":999}]'
    )
    service = service_cls(
        settings=normalize_expression_settings({"enabled": True, "api_key": "test-key"}),
        expressor=expressor,
        state_provider=lambda: state,
        snapshot_provider=lambda: _snapshot(state),
        context_provider=lambda: {},
        choices_provider=lambda: ("Touch", "Rest"),
    )

    result = service.test_provider().to_public_dict()

    assert result["ok"] is False
    assert result["stage"] == "event_validation"
    assert result["reason"] == "unsafe_event"
    assert result["fallback_reason"] == "unsafe_event"
    assert result["speech"] == "local feedback"
    assert state.coins == 20


def test_expression_diagnostics_service_fetch_models_delegates_to_injected_fetcher():
    service_cls = getattr(diagnostics_module, "ExpressionDiagnosticsService", None)
    assert service_cls is not None
    captured = {}

    def fake_model_fetcher(*, provider, base_url, api_key, timeout_seconds):
        captured.update(
            {
                "provider": provider,
                "base_url": base_url,
                "api_key": api_key,
                "timeout_seconds": timeout_seconds,
            }
        )
        return ("deepseek-v4-flash", "deepseek-v4-pro")

    state = create_initial_state(now=0)
    service = service_cls(
        settings=normalize_expression_settings({}),
        expressor=object(),
        state_provider=lambda: state,
        snapshot_provider=lambda: _snapshot(state),
        context_provider=lambda: {},
        choices_provider=lambda: ("Touch", "Rest"),
        model_fetcher=fake_model_fetcher,
    )

    models = service.fetch_models(
        {
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key": "test-key",
            "timeout_seconds": "0.5",
        }
    )

    assert models == ("deepseek-v4-flash", "deepseek-v4-pro")
    assert captured == {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com",
        "api_key": "test-key",
        "timeout_seconds": 0.5,
    }
