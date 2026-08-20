from pathlib import Path
from dataclasses import replace
import inspect
import pytest
import guanghe_companion.plugin_enabled_controller as module
from guanghe_companion.focus_companion import ActivityKind, ActivitySample


def test_drop_in_controller_class_is_defined():
    assert hasattr(module,'PluginEnabledCompanionController')


def test_drop_in_controller_exposes_expected_app_hooks():
    cls=module.PluginEnabledCompanionController
    for name in ('bind_plugin_capabilities','get_focus_companion_view_model','_build_actions','_expression_context'):
        assert hasattr(cls,name)


def test_drop_in_controller_starts_and_stops_with_full_upstream(tmp_path):
    controller = module.PluginEnabledCompanionController(
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )

    try:
        assert controller.plugin_boot_report.loaded_plugin_ids
        assert any(action["action_id"] == "touch" for action in controller.get_snapshot()["actions"])
    finally:
        controller.close()


def test_plugin_center_app_imports_lazily():
    import guanghe_companion.plugin_center_app as app
    assert callable(app.main)


def test_focus_poll_is_opt_in_and_does_not_mutate_growth(tmp_path):
    controller = module.PluginEnabledCompanionController(
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    baseline = controller.get_typed_snapshot()

    class Reader:
        def sample(self, *, observed_at=None):
            return ActivitySample(
                observed_at=float(observed_at or 0),
                kind=ActivityKind.CODING,
                app_label="code.exe",
                source="test",
            )

    controller._focus_activity_reader = Reader()
    try:
        assert controller.poll_focus_companion(now=10_000) == []
        controller.set_focus_companion_enabled(True)
        controller.story_runtime.focus.update_settings(
            replace(controller.story_runtime.focus.settings, threshold_minutes=5)
        )
        for offset in range(0, 330, 30):
            events = controller.poll_focus_companion(now=20_000 + offset)
        assert events and events[0]["type"] == "focus_break_offer"
        after = controller.get_typed_snapshot()
        assert after.stats == baseline.stats
        assert after.inventory == baseline.inventory
        assert after.relationship_stage == baseline.relationship_stage
    finally:
        controller.close()


def test_completed_focus_break_becomes_shared_memory(tmp_path):
    controller = module.PluginEnabledCompanionController(
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    try:
        controller.inject_demo_focus(focused_minutes=52, now=30_000)
        controller.confirm_focus_break(now=30_001, duration_seconds_override=1)
        events = controller.tick_focus_companion(now=30_003)
        assert events and events[0]["type"] == "focus_break_completed"
        assert any(
            row.source == "confirmed_companion_skill"
            for row in controller.story_runtime.memory.store.load_memories()
        )
    finally:
        controller.close()


def test_host_expression_provider_uses_current_prompt_client(tmp_path):
    controller = module.PluginEnabledCompanionController(
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    controller.ai_expressor.llm_client = lambda prompt: f"provider:{prompt}"
    controller.bind_plugin_capabilities(expression_provider=controller.generate_plugin_expression)
    try:
        provider = controller.plugin_subsystem.runtime.resolve_service("emoti.llm.expression")
        assert provider.generate("hello") == "provider:hello"
        assert controller.plugin_center.set_enabled("emoti.bundled.stargazing", True).ok
        provider = controller.plugin_subsystem.runtime.resolve_service("emoti.llm.expression")
        assert provider.generate("after-reload") == "provider:after-reload"
    finally:
        controller.close()


def test_stargazing_lifecycle_runs_through_formal_controller(tmp_path):
    controller = module.PluginEnabledCompanionController(
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    try:
        assert not any(row["action_id"] == "stargazing.watch" for row in controller.get_snapshot()["actions"])
        assert controller.plugin_center.set_enabled("emoti.bundled.stargazing", True).ok
        assert any(row["action_id"] == "stargazing.watch" for row in controller.get_snapshot()["actions"])

        controller.perform_action("stargazing.watch", include_ai_expression=False)
        controller.perform_action("stargazing.watch", include_ai_expression=False)
        memories = [
            row
            for row in controller.story_runtime.memory.store.load_memories()
            if row.title == "第一次一起看星星"
        ]
        assert len(memories) == 1
        assert memories[0].metadata["count"] == 2

        assert controller.plugin_center.set_enabled("emoti.bundled.stargazing", False).ok
        assert not any(row["action_id"] == "stargazing.watch" for row in controller.get_snapshot()["actions"])
        assert any(
            row.title == "第一次一起看星星"
            for row in controller.story_runtime.memory.store.load_memories()
        )
    finally:
        controller.close()
