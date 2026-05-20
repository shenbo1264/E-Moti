import time


def make_window(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    controller = make_controller(tmp_path)
    window = CompanionWindow(controller=controller)
    window.show()
    app.processEvents()
    return app, window


def make_controller(tmp_path, ai_expressor=None):
    from guanghe_companion.controller import CompanionController

    return CompanionController(save_path=tmp_path / "save.json", auto_load=False, ai_expressor=ai_expressor)


def test_companion_window_character_panel_omits_obsolete_placeholder_copy(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    text = window.character_label.text()

    assert "星汐" in text
    assert "程序化占位" not in text
    assert "后续可直接替换" not in text
    assert "正式角色包资产" not in text

    window.close()
    app.processEvents()


def test_desktop_mode_uses_pet_window_chrome_and_hides_control_panels(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)

    flags = window.windowFlags()

    assert bool(flags & Qt.WindowType.FramelessWindowHint)
    assert bool(flags & Qt.WindowType.WindowStaysOnTopHint)
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.hero_card.isVisibleTo(window)
    assert window.status_card.isHidden()
    assert window.feedback_card.isHidden()
    assert window.actions_card.isHidden()
    assert window.shop_card.isHidden()
    assert window.inventory_card.isHidden()

    window.close()
    app.processEvents()


def test_should_use_desktop_mode_accepts_pet_mode_alias():
    from guanghe_companion.app import should_use_desktop_mode

    assert should_use_desktop_mode(["demo", "--desktop-mode"]) is True
    assert should_use_desktop_mode(["demo", "--pet-mode"]) is True
    assert should_use_desktop_mode(["demo"]) is False


def test_clicking_sprite_area_performs_touch_action(monkeypatch, tmp_path):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    app, window = make_window(monkeypatch, tmp_path)

    QTest.mouseClick(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(24, 24))
    app.processEvents()
    snapshot = window.controller.get_snapshot()

    assert snapshot["motion"] == "TouchHead"
    assert snapshot["mood"] == 62
    assert "靠近" in snapshot["feedback"]

    window.close()
    app.processEvents()


def test_window_action_handler_does_not_wait_for_slow_llm_expression(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    class SlowExpressor:
        def __init__(self):
            self.calls = 0

        def express(self, snapshot, effect=None):
            self.calls += 1
            time.sleep(0.25)
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "late LLM speech",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    app = QApplication.instance() or QApplication([])
    slow_expressor = SlowExpressor()
    window = CompanionWindow(controller=make_controller(tmp_path, ai_expressor=slow_expressor))
    window.show()
    app.processEvents()
    slow_expressor.calls = 0

    started_at = time.monotonic()
    window._handle_action("touch")
    elapsed = time.monotonic() - started_at
    app.processEvents()

    snapshot = window.controller.get_snapshot()
    assert elapsed < 0.1
    assert slow_expressor.calls == 0
    assert snapshot["motion"] == "TouchHead"
    assert snapshot["mood"] == 62
    assert snapshot["events"][0]["speech"] == snapshot["feedback"]
    assert snapshot["events"][0]["speech"] != "late LLM speech"

    window.close()
    app.processEvents()


def test_window_action_button_signal_does_not_wait_for_slow_llm_expression(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    class SlowExpressor:
        def __init__(self):
            self.calls = 0

        def express(self, snapshot, effect=None):
            self.calls += 1
            time.sleep(0.25)
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "late button LLM speech",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    app = QApplication.instance() or QApplication([])
    slow_expressor = SlowExpressor()
    window = CompanionWindow(controller=make_controller(tmp_path, ai_expressor=slow_expressor))
    window.show()
    app.processEvents()
    slow_expressor.calls = 0

    started_at = time.monotonic()
    window.action_buttons["touch"].click()
    elapsed = time.monotonic() - started_at
    app.processEvents()

    snapshot = window.controller.get_snapshot()
    assert elapsed < 0.1
    assert slow_expressor.calls == 0
    assert snapshot["motion"] == "TouchHead"
    assert snapshot["mood"] == 62
    assert snapshot["events"][0]["speech"] == snapshot["feedback"]
    assert snapshot["events"][0]["speech"] != "late button LLM speech"

    window.close()
    app.processEvents()


def test_window_secondary_controls_do_not_wait_for_slow_llm_expression(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    class SlowExpressor:
        def __init__(self):
            self.calls = 0

        def express(self, snapshot, effect=None):
            self.calls += 1
            time.sleep(0.25)
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "late secondary LLM speech",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    app = QApplication.instance() or QApplication([])
    slow_expressor = SlowExpressor()
    controller = make_controller(tmp_path, ai_expressor=slow_expressor)
    controller.state.coins = 120
    window = CompanionWindow(controller=controller)
    window.show()
    app.processEvents()
    slow_expressor.calls = 0

    window.shop_list.setCurrentRow(0)
    started_at = time.monotonic()
    window._handle_buy()
    buy_elapsed = time.monotonic() - started_at
    app.processEvents()

    window.inventory_list.setCurrentRow(0)
    started_at = time.monotonic()
    window._handle_inventory_usage("feed")
    feed_elapsed = time.monotonic() - started_at
    app.processEvents()

    started_at = time.monotonic()
    window._handle_tick()
    tick_elapsed = time.monotonic() - started_at
    app.processEvents()

    started_at = time.monotonic()
    window._handle_demo_reset()
    reset_elapsed = time.monotonic() - started_at
    app.processEvents()

    started_at = time.monotonic()
    window._handle_demo_proactive("low_charge")
    proactive_elapsed = time.monotonic() - started_at
    app.processEvents()

    snapshot = window.controller.get_snapshot()
    assert max(buy_elapsed, feed_elapsed, tick_elapsed, reset_elapsed, proactive_elapsed) < 0.1
    assert slow_expressor.calls == 0
    assert snapshot["proactive_feedback"]["kind"] == "low_charge"
    assert snapshot["events"][0]["speech"] == snapshot["feedback"]
    assert snapshot["events"][0]["speech"] != "late secondary LLM speech"

    window.close()
    app.processEvents()


def test_dragging_sprite_area_performs_raised_action(monkeypatch, tmp_path):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    app, window = make_window(monkeypatch, tmp_path)

    QTest.mousePress(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(24, 24))
    QTest.mouseMove(window.sprite_label, pos=QPoint(72, 72))
    QTest.mouseRelease(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(72, 72))
    app.processEvents()
    snapshot = window.controller.get_snapshot()

    assert snapshot["motion"] == "Raised"
    assert "提起" in snapshot["feedback"]

    window.close()
    app.processEvents()


def test_shop_and_inventory_lists_show_item_icons(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    shop_item = window.shop_list.item(0)

    assert shop_item is not None
    assert not shop_item.icon().isNull()

    window.shop_list.setCurrentRow(0)
    window._handle_buy()
    app.processEvents()
    inventory_item = window.inventory_list.item(0)

    assert inventory_item is not None
    assert not inventory_item.icon().isNull()

    window.close()
    app.processEvents()


def test_feeding_item_shows_temporary_icon_feedback(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    window.shop_list.setCurrentRow(0)
    window._handle_buy()
    app.processEvents()
    window.inventory_list.setCurrentRow(0)
    window._handle_inventory_usage("feed")
    app.processEvents()

    assert window.item_feedback_label.isVisible()
    assert window.item_feedback_label.pixmap() is not None
    assert not window.item_feedback_label.pixmap().isNull()

    window.close()
    app.processEvents()


def test_window_shows_relationship_memory_log(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert "暂无回忆" in window.memory_label.text()

    window._handle_action("touch")
    app.processEvents()

    assert "轻触" in window.memory_label.text()
    assert "互动" in window.memory_label.text()

    window.close()
    app.processEvents()


def test_window_shows_relationship_stage_and_next_unlock(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    text = window.relationship_label.text()

    assert "当前关系：初识" in text
    assert "信任达到 20" in text
    assert "学习 KPI" not in text

    window.close()
    app.processEvents()


def test_window_shows_screen_perception_disabled_by_default(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert window.perception_card.isVisibleTo(window)
    assert window.observe_screen_button.isEnabled()
    assert "屏幕感知：关闭" in window.perception_status_label.text()
    assert "默认不会读取屏幕" in window.perception_privacy_label.text()
    assert "不会自动截图" in window.perception_privacy_label.text()

    window.close()
    app.processEvents()


def test_window_manual_screen_perception_trigger_shows_privacy_prompt_and_status(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    captured = {}

    def fake_information(parent, title, message):
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(QMessageBox, "information", fake_information)
    app, window = make_window(monkeypatch, tmp_path)

    window.observe_screen_button.click()
    app.processEvents()

    assert captured["title"] == "屏幕感知隐私提示"
    assert "只在手动触发时运行" in captured["message"]
    assert "本轮不会自动截图" in captured["message"]
    assert "屏幕感知：已手动触发" in window.perception_status_label.text()
    assert "未读取屏幕内容" in window.perception_status_label.text()

    window.close()
    app.processEvents()


def test_window_manual_screen_perception_updates_readonly_expression_context(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda parent, title, message: None)
    app, window = make_window(monkeypatch, tmp_path)

    before_context = window.controller.expression_context_provider()
    window.observe_screen_button.click()
    app.processEvents()
    after_context = window.controller.expression_context_provider()

    assert "perception_summary" not in before_context
    assert after_context["perception_summary"] == "manual screen perception requested; no screen content was read"
    assert "tool_results" in after_context
    assert "screenshot" not in after_context["perception_summary"]
    assert "ocr" not in after_context["perception_summary"].lower()

    window.close()
    app.processEvents()


def test_window_close_clears_manual_screen_perception_context(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda parent, title, message: None)
    app, window = make_window(monkeypatch, tmp_path)

    window.observe_screen_button.click()
    app.processEvents()
    assert window.controller.expression_context_provider()["perception_summary"]

    controller = window.controller
    window.close()
    app.processEvents()

    context_after_close = controller.expression_context_provider()
    assert "perception_summary" not in context_after_close


def test_window_manual_screen_perception_reaches_typed_expression_request(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication, QMessageBox

    from guanghe_companion.ai_expressor import ExpressionRequest
    from guanghe_companion.app import (
        MANUAL_PERCEPTION_NO_SCREEN_SUMMARY,
        CompanionWindow,
    )

    class CapturingExpressor:
        def __init__(self):
            self.requests = []

        def express(self, snapshot, effect=None):
            self.requests.append(snapshot)
            return []

    monkeypatch.setattr(QMessageBox, "information", lambda parent, title, message: None)
    app = QApplication.instance() or QApplication([])
    expressor = CapturingExpressor()
    window = CompanionWindow(controller=make_controller(tmp_path, ai_expressor=expressor))
    window.show()
    app.processEvents()

    window.observe_screen_button.click()
    app.processEvents()
    snapshot = window.controller.perform_action("touch", include_ai_expression=True)

    request = expressor.requests[-1]
    assert isinstance(request, ExpressionRequest)
    assert request.perception_summary == MANUAL_PERCEPTION_NO_SCREEN_SUMMARY
    assert "no screen content was read" in request.perception_summary
    assert "window title:" not in request.perception_summary.lower()
    assert "screenshot" not in request.perception_summary.lower()
    assert "ocr" not in request.perception_summary.lower()
    assert snapshot["mood"] == 62
    assert snapshot["events"][0]["speech"] == snapshot["feedback"]

    window.close()
    app.processEvents()


def test_window_shows_proactive_companionship_feedback(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)
    window.controller.state.charge = 25
    window.controller.state.mood = 60
    window.controller.state.focus = 70
    window.controller.state.stability = 70

    window._handle_tick()
    app.processEvents()

    assert "能量有点低" in window.feedback_label.text()
    assert "主动陪伴" in window.memory_label.text()

    window.close()
    app.processEvents()


def test_window_close_closes_controller(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    class CloseAwareController(CompanionController):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.close_calls = 0

        def close(self):
            if self.close_calls:
                return
            self.close_calls += 1
            super().close()

    app = QApplication.instance() or QApplication([])
    controller = CloseAwareController(save_path=tmp_path / "save.json", auto_load=False)
    window = CompanionWindow(controller=controller)
    window.show()
    app.processEvents()

    window.close()
    app.processEvents()

    assert controller.close_calls == 1


def test_window_demo_buttons_trigger_proactive_companionship(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert "模拟低能量" in window.demo_low_charge_button.text()
    assert "模拟久未互动" in window.demo_quiet_mood_button.text()

    window.demo_low_charge_button.click()
    app.processEvents()

    assert "能量有点低" in window.feedback_label.text()
    assert "主动陪伴" in window.memory_label.text()

    window.close()
    app.processEvents()


def test_window_reset_demo_button_restores_clean_demo_state(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)
    window._handle_action("study")
    window.shop_list.setCurrentRow(0)
    window._handle_buy()
    window._handle_action("rest")
    app.processEvents()
    assert window.controller.get_snapshot()["memory_log"]

    window.demo_reset_button.click()
    app.processEvents()
    snapshot = window.controller.get_snapshot()

    assert "\u91cd\u7f6e\u6f14\u793a\u72b6\u6001" in window.demo_reset_button.text()
    assert snapshot["coins"] == 20
    assert snapshot["trust"] == 5
    assert snapshot["memory_log"] == []
    assert snapshot["resting"] is False

    window.close()
    app.processEvents()


def test_demo_save_cli_flags_select_isolated_demo_save():
    from guanghe_companion.app import should_reset_demo_save, should_use_demo_save

    assert should_use_demo_save(["demo", "--demo-save"]) is True
    assert should_use_demo_save(["demo", "--reset-demo-save"]) is True
    assert should_use_demo_save(["demo"]) is False
    assert should_reset_demo_save(["demo", "--reset-demo-save"]) is True
    assert should_reset_demo_save(["demo", "--demo-save"]) is False


def test_launch_reset_demo_save_uses_local_first_reset(monkeypatch):
    import guanghe_companion.app as app_module

    captured = {}

    class FakeApplication:
        def __init__(self, args):
            captured["app_args"] = args

        @staticmethod
        def instance():
            return None

        def exec(self):
            return 17

    class FakeController:
        def __init__(self, save_path=None):
            captured["save_path"] = save_path

        def reset_demo_state(self, **kwargs):
            captured["reset_kwargs"] = kwargs

    class FakeWindow:
        def __init__(self, controller, desktop_mode=False):
            captured["window_controller"] = controller
            captured["desktop_mode"] = desktop_mode

        def show(self):
            captured["shown"] = True

    monkeypatch.setattr(app_module, "QApplication", FakeApplication)
    monkeypatch.setattr(app_module, "CompanionController", FakeController)
    monkeypatch.setattr(app_module, "CompanionWindow", FakeWindow)

    result = app_module.launch(["demo", "--reset-demo-save"])

    assert result == 17
    assert captured["reset_kwargs"] == {"include_ai_expression": False}
    assert captured["shown"] is True
