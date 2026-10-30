from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def test_rejection_and_source_cooldown_survive_restart(tmp_path):
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        controller.now = 400
        controller._last_proactive_at["memory_recollection:source"] = 390
        controller._proactive_daily_counts["day:0"] = 2
        controller.last_proactive_feedback = {"kind": "memory_recollection"}
        controller.reject_proactive_request()
        expected = dict(controller._last_proactive_at)
    finally:
        controller.close()
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    try:
        assert controller.now >= 400
        assert controller._last_proactive_at == expected
        assert controller._proactive_daily_counts["day:0"] == 2
    finally:
        controller.close()
