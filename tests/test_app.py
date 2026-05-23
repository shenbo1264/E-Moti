import time


def make_window(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt
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


def test_sprite_drag_uses_global_cursor_delta_when_window_moves(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import SpriteInteractionLabel

    app = QApplication.instance() or QApplication([])
    drag_deltas = []
    label = SpriteInteractionLabel(
        on_click=lambda: None,
        on_drag=lambda: None,
        on_drag_move=drag_deltas.append,
    )
    label.show()
    app.processEvents()

    label.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            QPointF(100, 100),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    label.mouseMoveEvent(
        QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(10, 10),
            QPointF(124, 100),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    assert drag_deltas == [QPoint(24, 0)]

    label.close()
    app.processEvents()


def test_companion_window_character_panel_omits_obsolete_placeholder_copy(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    text = window.character_label.text()

    assert "星汐" in text
    assert "程序化占位" not in text
    assert "后续可直接替换" not in text
    assert "正式角色包资产" not in text

    window.close()
    app.processEvents()


def test_companion_window_title_positions_xingxi_as_desktop_companion(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert window.windowTitle() == "星汐 E-Moti 桌面伴侣"

    window.close()
    app.processEvents()


def test_application_style_uses_fusion_and_chinese_font(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import configure_application_style

    app = QApplication.instance() or QApplication([])

    assert configure_application_style(app) is True
    assert app.font().family() in {"Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Arial"}
    assert "QGroupBox" in app.styleSheet()
    assert "font-family" in app.styleSheet()


def test_control_panel_presents_desktop_pet_as_primary_launch(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert window.launcher_title_label.text() == "星汐 E-Moti"
    assert "桌宠模式" in window.launcher_subtitle_label.text()
    assert window.enter_desktop_mode_button.text() == "进入桌宠模式"
    assert window.enter_desktop_mode_button.objectName() == "PrimaryLaunchButton"

    window.close()
    app.processEvents()


def test_control_panel_launches_separate_desktop_pet_window(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    window.enter_desktop_mode_button.click()
    app.processEvents()

    pet_window = window.desktop_pet_window
    assert window.desktop_mode is False
    assert window.status_card.isVisibleTo(window)
    assert pet_window is not window
    assert pet_window.desktop_mode is True
    assert pet_window.sprite_label.isVisibleTo(pet_window)
    assert not pet_window.tick_timer.isActive()

    pet_window.close()
    app.processEvents()

    assert window.desktop_pet_window is None

    window.close()
    app.processEvents()


def test_control_panel_uses_readable_chinese_status_labels(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert [label.text() for label in window.stat_name_labels] == ["专注", "能量", "稳定", "心情", "信任"]
    assert "金币" in window.resources_label.text()
    assert "coins" not in window.resources_label.text()
    assert "level" not in window.resources_label.text()

    window.close()
    app.processEvents()


def test_control_panel_has_settings_center_navigation(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert window.navigation_hint_label.text() == "控制中心"
    assert [button.text() for button in window.navigation_buttons] == [
        "总览",
        "互动",
        "背包",
        "感知与搜索",
        "隐私",
        "LLM表达",
        "表达规则",
        "语音",
    ]

    window.close()
    app.processEvents()


def test_control_panel_navigation_switches_right_hand_pages(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert window.content_stack.currentIndex() == 0
    assert window.hero_card.isVisibleTo(window)

    window.navigation_buttons[2].click()
    app.processEvents()

    assert window.content_stack.currentIndex() == 2
    assert window.shop_card.isVisibleTo(window)
    assert window.inventory_card.isVisibleTo(window)
    assert not window.hero_card.isVisibleTo(window)

    window.navigation_buttons[3].click()
    app.processEvents()

    assert window.content_stack.currentIndex() == 3
    assert window.perception_search_page.isVisibleTo(window)
    assert not window.shop_card.isVisibleTo(window)

    window.navigation_buttons[4].click()
    app.processEvents()

    assert window.content_stack.currentIndex() == 4
    assert window.perception_card.isVisibleTo(window)
    assert not window.shop_card.isVisibleTo(window)

    window.close()
    app.processEvents()


def test_window_event_panel_uses_presentational_summary_not_raw_json(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    window._handle_action("touch")
    app.processEvents()
    text = window.events_label.text()

    assert "{" not in text
    assert "}" not in text
    assert "星汐" in text
    assert "状态" in text
    assert "可选动作" in text

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
    assert bool(flags & Qt.WindowType.NoDropShadowWindowHint)
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.hero_card.isVisibleTo(window)
    assert window.status_card.isHidden()
    assert window.feedback_card.isHidden()
    assert window.actions_card.isHidden()
    assert window.shop_card.isHidden()
    assert window.inventory_card.isHidden()
    assert window.screen_observation_settings_card.isHidden()
    assert window.web_search_settings_card.isHidden()
    assert window.expression_settings_card.isHidden()
    assert window.expression_rule_card.isHidden()
    assert window.voice_settings_card.isHidden()

    window.close()
    app.processEvents()


def test_desktop_mode_shows_sprite_with_dialogue_controls_after_layout(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()

    assert window.width() <= 360
    assert window.height() <= 430
    assert window.hero_card.title() == ""
    assert window.root_widget.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.hero_card.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.sprite_label.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert "border: none" in window.hero_card.styleSheet()
    assert "background: transparent" in window.sprite_label.styleSheet()
    assert window.sprite_label.isVisibleTo(window)
    assert window.sprite_label.pixmap() is not None
    assert not window.sprite_label.pixmap().isNull()
    assert window.mask().isEmpty()
    assert not window.character_label.isVisibleTo(window)
    assert not window.desktop_feedback_label.isVisibleTo(window)
    assert window.dialogue_input.isVisibleTo(window)
    assert window.dialogue_send_button.isVisibleTo(window)

    window.close()
    app.processEvents()


def test_desktop_pet_has_dialogue_input_and_send_button(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()

    assert window.dialogue_input.placeholderText() == "和星汐说点什么"
    assert window.dialogue_send_button.text() == "发送"
    assert window.dialogue_input.isVisibleTo(window)
    assert window.dialogue_send_button.isVisibleTo(window)

    window.close()
    app.processEvents()


def test_desktop_pet_dialogue_send_shows_xingxi_response_without_growth_settlement(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()
    before = window.controller.get_typed_snapshot()

    window.dialogue_input.setText("今天陪我一会儿")
    window.dialogue_send_button.click()
    app.processEvents()

    after = window.controller.get_typed_snapshot()
    assert window.dialogue_input.text() == ""
    assert window.desktop_feedback_label.isVisibleTo(window)
    assert "今天陪我一会儿" in window.desktop_feedback_label.text()
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_desktop_mode_context_menu_status_panel_shows_feedback(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication, QMessageBox

    from guanghe_companion.app import CompanionWindow

    captured = {}

    def fake_information(parent, title, message):
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(QMessageBox, "information", fake_information)
    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()

    menu = window._build_desktop_context_menu()
    menu.actions()[0].trigger()
    app.processEvents()

    assert captured["title"] == "状态面板"
    assert "模式" in captured["message"]
    assert "能量 65" in captured["message"]
    assert "心情 58" in captured["message"]
    assert "信任 5" in captured["message"]
    assert "{" not in captured["message"]
    assert "STAT" not in captured["message"]
    assert "CHOICE" not in captured["message"]

    window.close()
    app.processEvents()


def test_desktop_mode_feedback_overlay_updates_after_sprite_touch(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()

    QTest.mouseClick(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(24, 24))
    app.processEvents()
    text = window._format_desktop_status_panel(window.controller.get_snapshot())

    assert "模式：Calm" in text
    assert "靠近回应" in text
    assert "靠近我的方式" in text
    assert window.controller.get_snapshot()["motion"] == "TouchHead"

    window.close()
    app.processEvents()


def test_desktop_mode_context_menu_returns_to_control_panel(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()

    menu = window._build_desktop_context_menu()
    labels = [action.text() for action in menu.actions() if not action.isSeparator()]

    assert labels == ["状态面板", "对话历史", "清屏", "复制对话", "回放上一句", "回溯上一轮", "返回控制面板", "退出"]

    labels_to_actions = {action.text(): action for action in menu.actions() if not action.isSeparator()}
    labels_to_actions["返回控制面板"].trigger()
    app.processEvents()
    flags = window.windowFlags()

    assert window.desktop_mode is False
    assert not bool(flags & Qt.WindowType.FramelessWindowHint)
    assert not bool(flags & Qt.WindowType.WindowStaysOnTopHint)
    assert not window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.launcher_card.isVisibleTo(window)
    assert window.sidebar_card.isVisibleTo(window)
    assert window.content_stack.currentIndex() == 0
    assert window.status_card.isVisibleTo(window)
    assert window.feedback_card.isVisibleTo(window)
    assert not window.actions_card.isVisibleTo(window)
    assert not window.demo_card.isVisibleTo(window)
    assert not window.perception_card.isVisibleTo(window)
    assert not window.shop_card.isVisibleTo(window)
    assert not window.inventory_card.isVisibleTo(window)
    assert not window.expression_settings_card.isVisibleTo(window)
    assert not window.expression_rule_card.isVisibleTo(window)
    assert not window.voice_settings_card.isVisibleTo(window)
    assert window.character_label.isVisibleTo(window)
    assert window.desktop_feedback_label.isHidden()
    assert window.mask().isEmpty()
    assert window.controller.get_snapshot()["motion"] == "Default"

    window.close()
    app.processEvents()


def test_desktop_mode_sprite_right_click_opens_context_menu(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    captured = {}

    def fake_show_desktop_context_menu(global_pos):
        captured["global_pos"] = global_pos

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window._show_desktop_context_menu = fake_show_desktop_context_menu
    window.show()
    app.processEvents()

    window.sprite_label.customContextMenuRequested.emit(QPoint(18, 18))
    app.processEvents()

    assert isinstance(captured["global_pos"], QPoint)

    window.close()
    app.processEvents()


def test_desktop_mode_context_menu_exit_closes_window_and_controller(monkeypatch, tmp_path):
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
    window = CompanionWindow(controller=controller, desktop_mode=True)
    window.show()
    app.processEvents()

    menu = window._build_desktop_context_menu()
    labels_to_actions = {action.text(): action for action in menu.actions() if not action.isSeparator()}
    labels_to_actions["退出"].trigger()
    app.processEvents()

    assert not window.isVisible()
    assert controller.close_calls == 1


def test_desktop_pet_history_menu_shows_copies_replays_reverts_and_clears_dialogue(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication, QMessageBox

    from guanghe_companion.app import CompanionWindow

    captured_messages = []

    def fake_information(parent, title, message):
        captured_messages.append((title, message))

    monkeypatch.setattr(QMessageBox, "information", fake_information)
    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()

    window.dialogue_input.setText("第一句")
    window.dialogue_send_button.click()
    window.dialogue_input.setText("第二句")
    window.dialogue_send_button.click()
    app.processEvents()

    menu = window._build_desktop_context_menu()
    labels_to_actions = {action.text(): action for action in menu.actions() if not action.isSeparator()}

    labels_to_actions["对话历史"].trigger()
    app.processEvents()
    assert captured_messages[-1][0] == "对话历史"
    assert "你：第一句" in captured_messages[-1][1]
    assert "星汐：" in captured_messages[-1][1]
    assert "{" not in captured_messages[-1][1]

    labels_to_actions["复制对话"].trigger()
    app.processEvents()
    assert "你：第二句" in QApplication.clipboard().text()

    labels_to_actions["回放上一句"].trigger()
    app.processEvents()
    assert "第二句" in window.desktop_feedback_label.text()

    labels_to_actions["回溯上一轮"].trigger()
    app.processEvents()
    assert "第一句" in window.desktop_feedback_label.text()

    labels_to_actions["清屏"].trigger()
    app.processEvents()
    assert window.controller.get_snapshot()["dialogue_history"] == []
    assert "清屏" in window.controller.get_snapshot()["feedback"]

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


def test_dragging_sprite_area_moves_desktop_pet_window(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.move(100, 100)
    window.show()
    app.processEvents()
    original_pos = window.pos()

    QTest.mousePress(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(24, 24))
    QTest.mouseMove(window.sprite_label, pos=QPoint(84, 54))
    QTest.mouseRelease(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(84, 54))
    app.processEvents()

    moved_pos = window.pos()
    snapshot = window.controller.get_snapshot()

    assert moved_pos.x() > original_pos.x()
    assert moved_pos.y() > original_pos.y()
    assert snapshot["motion"] == "Raised"

    window.close()
    app.processEvents()


def test_dragging_desktop_pet_window_stays_inside_available_screen(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QPoint, QRect, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.resize(120, 100)
    window._desktop_available_geometry = lambda: QRect(0, 0, 300, 260)
    window.move(150, 140)
    window.show()
    app.processEvents()

    QTest.mousePress(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(24, 24))
    QTest.mouseMove(window.sprite_label, pos=QPoint(320, 320))
    QTest.mouseRelease(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(320, 320))
    app.processEvents()

    moved_pos = window.pos()
    snapshot = window.controller.get_snapshot()

    assert moved_pos.x() <= 180
    assert moved_pos.y() <= 160
    assert moved_pos.x() >= 0
    assert moved_pos.y() >= 0
    assert snapshot["motion"] == "Raised"

    window.close()
    app.processEvents()


def test_desktop_pet_drag_release_docks_to_near_left_edge(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window._desktop_available_geometry = lambda: QRect(0, 0, 1000, 800)
    window.show()
    app.processEvents()
    window.move(24, 140)
    app.processEvents()

    window._handle_action("drag")
    app.processEvents()
    snapshot = window.controller.get_snapshot()

    assert window.pos().x() == 0
    assert window.pos().y() == 140
    assert snapshot["motion"] == "Raised"

    window.close()
    app.processEvents()


def test_desktop_pet_drag_release_docks_to_near_right_edge(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window._desktop_available_geometry = lambda: QRect(0, 0, 1000, 800)
    window.show()
    app.processEvents()
    docked_x = window._clamp_desktop_position(QPoint(10_000, 140)).x()
    window.move(docked_x - 24, 140)
    app.processEvents()

    window._handle_action("drag")
    app.processEvents()
    snapshot = window.controller.get_snapshot()

    assert window.pos().x() == docked_x
    assert window.pos().y() == 140
    assert snapshot["motion"] == "Raised"

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

    window.navigation_buttons[4].click()
    app.processEvents()

    assert window.perception_card.isVisibleTo(window)
    assert window.observe_screen_button.isEnabled()
    assert "屏幕感知：关闭" in window.perception_status_label.text()
    assert "默认不会读取屏幕" in window.perception_privacy_label.text()
    assert "不会自动截图" in window.perception_privacy_label.text()

    window.close()
    app.processEvents()


def test_capability_pages_have_safe_defaults(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    nav_labels = [button.text() for button in window.navigation_buttons]

    assert "感知与搜索" in nav_labels
    assert "语音" in nav_labels
    assert window.screen_observation_enabled_check.isChecked() is False
    assert window.screen_observation_auto_check.isChecked() is False
    assert window.web_search_enabled_check.isChecked() is False
    assert window.tts_enabled_check.isChecked() is False
    assert window.asr_enabled_check.isChecked() is False
    assert "不会自动点击" in window.perception_privacy_label.text()

    window.close()
    app.processEvents()


def test_capability_ui_save_round_trips_to_controller(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)
    before = window.controller.get_typed_snapshot()

    window.screen_observation_enabled_check.setChecked(True)
    window.web_search_enabled_check.setChecked(True)
    window.tts_enabled_check.setChecked(True)
    window.asr_enabled_check.setChecked(True)
    window.capability_save_button.click()
    app.processEvents()

    settings = window.controller.get_capability_settings()
    after = window.controller.get_typed_snapshot()
    assert settings.screen_observation.enabled is True
    assert settings.web_search.enabled is True
    assert settings.tts.enabled is True
    assert settings.asr.enabled is True
    assert "已保存" in window.capability_feedback_label.text()
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_screen_observation_button_updates_readonly_context_without_growth_mutation(monkeypatch, tmp_path):
    from guanghe_companion.screen_observation import ScreenObservationResult

    app, window = make_window(monkeypatch, tmp_path)
    before = window.controller.get_typed_snapshot()

    class FakeObservationService:
        def __init__(self):
            self.settings = []

        def observe(self, settings):
            self.settings.append(settings)
            return ScreenObservationResult(True, "屏幕观察完成", "看到 IDE 和测试结果")

    fake_service = FakeObservationService()
    window.screen_observation_service = fake_service
    window.screen_observation_enabled_check.setChecked(True)
    window.screen_observation_model_input.setText("vision-test")
    window.screen_observation_base_url_input.setText("https://vision.example.test/v1")
    window.screen_observation_api_key_input.setText("secret")

    window.screen_observation_run_button.click()
    app.processEvents()

    context = window.controller._expression_context()
    after = window.controller.get_typed_snapshot()
    assert fake_service.settings[0].enabled is True
    assert context["perception_summary"] == "看到 IDE 和测试结果"
    assert "屏幕观察完成" in window.screen_observation_status_label.text()
    assert "看到 IDE 和测试结果" in window.screen_observation_status_label.text()
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_screen_observation_auto_timer_tracks_saved_settings(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    window.screen_observation_enabled_check.setChecked(True)
    window.screen_observation_auto_check.setChecked(True)
    window.screen_observation_interval_input.setValue(10)
    window.capability_save_button.click()
    app.processEvents()

    assert window.screen_observation_timer.isActive()
    assert window.screen_observation_timer.interval() == 10_000

    window.screen_observation_auto_check.setChecked(False)
    window.capability_save_button.click()
    app.processEvents()

    assert not window.screen_observation_timer.isActive()

    window.close()
    app.processEvents()


def test_expression_settings_page_shows_required_fields_and_saves_local_config(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication, QLineEdit

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))
    window.show()
    app.processEvents()

    window.navigation_buttons[5].click()
    app.processEvents()

    assert window.expression_settings_card.isVisibleTo(window)
    assert window.expression_settings_card.title() == "LLM 表达接入"
    assert window.expression_enabled_checkbox.text() == "启用 LLM 表达增强"
    assert window.expression_provider_label.text() == "服务商"
    assert window.expression_model_label.text() == "模型 ID"
    assert window.expression_base_url_label.text() == "Base URL"
    assert window.expression_api_key_label.text() == "API Key"
    assert window.expression_timeout_label.text() == "超时（秒）"
    assert window.expression_provider_combo.currentText() == "openai"
    assert window.expression_model_input.text()
    assert window.expression_model_input.placeholderText() == "例如 gpt-5.5"
    assert window.expression_base_url_input.text().startswith("https://")
    assert window.expression_base_url_input.placeholderText() == "OpenAI-compatible Base URL 或完整 endpoint"
    assert window.expression_api_key_input.echoMode() == QLineEdit.EchoMode.Password
    assert window.expression_api_key_input.placeholderText() == "粘贴 API Key"
    assert window.expression_timeout_input.value() == 2.0
    assert window.expression_timeout_input.maximum() == 60.0
    assert window.expression_test_button.text() == "测试 LLM 回应"
    assert window.expression_settings_status_label.text() == "LLM 表达：关闭"

    window.expression_enabled_checkbox.setChecked(True)
    window.expression_model_input.setText("demo-model")
    window.expression_base_url_input.setText("https://example.test/v1/responses")
    window.expression_api_key_input.setText("test-key")
    window.expression_timeout_input.setValue(0.5)
    window.expression_save_button.click()
    app.processEvents()

    settings = window.controller.get_expression_settings()
    assert settings["enabled"] is True
    assert settings["provider"] == "openai"
    assert settings["model"] == "demo-model"
    assert settings["base_url"] == "https://example.test/v1/responses"
    assert settings["api_key_set"] is True
    assert settings["timeout_seconds"] == 0.5
    assert window.expression_settings_status_label.text() == "LLM 表达设置已保存"

    window.close()
    app.processEvents()


def test_expression_settings_test_button_saves_and_tests_llm_without_mutating_state(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    import guanghe_companion.controller as controller_module
    from guanghe_companion.app import CompanionWindow

    class FakeExpressor:
        def __init__(self):
            self.last_fallback_reason = None
            self.requests = []

        def close(self):
            pass

        def express(self, snapshot, effect=None):
            self.requests.append((snapshot, effect))
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "LLM 连接成功",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    created = []

    def fake_build_default_ai_expressor(*, settings=None):
        fake = FakeExpressor()
        created.append((settings, fake))
        return fake

    monkeypatch.setattr(controller_module, "build_default_ai_expressor", fake_build_default_ai_expressor)

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))
    window.show()
    app.processEvents()

    window.navigation_buttons[5].click()
    app.processEvents()
    before = window.controller.get_typed_snapshot()

    window.expression_enabled_checkbox.setChecked(True)
    window.expression_model_input.setText("demo-model")
    window.expression_base_url_input.setText("https://example.test/v1/responses")
    window.expression_api_key_input.setText("test-key")
    window.expression_timeout_input.setValue(0.5)
    window.expression_test_button.click()
    app.processEvents()

    after = window.controller.get_typed_snapshot()
    settings, fake = created[-1]
    assert settings.enabled is True
    assert settings.model == "demo-model"
    assert settings.base_url == "https://example.test/v1/responses"
    assert settings.api_key == "test-key"
    assert fake.requests
    assert "LLM 测试通过" in window.expression_settings_status_label.text()
    assert "LLM 连接成功" in window.expression_settings_status_label.text()
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.unlocks == before.unlocks
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_expression_settings_fetches_provider_model_list_without_saving_or_mutating_state(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    captured = {}
    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))

    def fake_fetch_expression_models(settings):
        captured.update(settings)
        return ("deepseek-v4-flash", "deepseek-v4-pro")

    window.controller.fetch_expression_models = fake_fetch_expression_models
    window.show()
    app.processEvents()

    window.navigation_buttons[5].click()
    app.processEvents()
    before = window.controller.get_typed_snapshot()

    provider_items = [window.expression_provider_combo.itemText(index) for index in range(window.expression_provider_combo.count())]
    assert provider_items == ["openai", "deepseek", "openrouter", "custom"]
    assert not window.expression_model_list_combo.isVisibleTo(window)

    window.expression_provider_combo.setCurrentText("deepseek")
    app.processEvents()

    assert window.expression_model_input.text() == "deepseek-v4-flash"
    assert window.expression_base_url_input.text() == "https://api.deepseek.com"

    window.expression_api_key_input.setText("test-key")
    window.expression_model_fetch_button.click()
    app.processEvents()

    after = window.controller.get_typed_snapshot()
    assert captured["provider"] == "deepseek"
    assert captured["base_url"] == "https://api.deepseek.com"
    assert captured["api_key"] == "test-key"
    assert window.expression_model_list_combo.isVisibleTo(window)
    assert window.expression_model_list_combo.count() == 2
    assert window.expression_model_list_combo.itemText(1) == "deepseek-v4-pro"
    assert window.expression_model_input.text() == "deepseek-v4-flash"

    window.expression_model_list_combo.setCurrentIndex(1)
    app.processEvents()

    assert window.expression_model_input.text() == "deepseek-v4-pro"
    assert "获取到 2 个模型" in window.expression_settings_status_label.text()
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_expression_rule_preview_page_is_readonly_and_copyable(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))
    window.show()
    app.processEvents()
    before = window.controller.get_typed_snapshot()

    window.navigation_buttons[6].click()
    app.processEvents()

    preview = window.expression_rule_preview_text.toPlainText()
    assert window.expression_rule_card.isVisibleTo(window)
    assert window.expression_rule_preview_text.isReadOnly()
    assert "AI 只能生成表达事件" in preview
    assert "不能修改状态数值" in preview
    assert "背包" in preview
    assert "星汐" in preview

    window.expression_rule_copy_button.click()
    app.processEvents()

    assert QApplication.clipboard().text() == preview
    assert "已复制" in window.expression_rule_status_label.text()
    assert window.controller.get_typed_snapshot().stats == before.stats
    assert window.controller.get_typed_snapshot().inventory == before.inventory
    assert window.controller.get_typed_snapshot().memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_voice_settings_page_marks_tts_and_asr_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))
    window.show()
    app.processEvents()
    before = window.controller.get_typed_snapshot()

    window.navigation_buttons[7].click()
    app.processEvents()

    assert window.voice_settings_card.isVisibleTo(window)
    assert "TTS 暂未启用" in window.voice_status_label.text()
    assert "ASR 暂未启用" in window.voice_status_label.text()
    assert window.voice_tts_provider_label.text() == "tts_provider: disabled"
    assert window.voice_asr_provider_label.text() == "asr_provider: disabled"
    assert not window.voice_tts_enable_button.isEnabled()
    assert not window.voice_asr_enable_button.isEnabled()
    assert window.controller.get_typed_snapshot().stats == before.stats
    assert window.controller.get_typed_snapshot().inventory == before.inventory
    assert window.controller.get_typed_snapshot().memory_log == before.memory_log

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


def test_window_close_ignores_controller_close_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    class BrokenCloseController(CompanionController):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.close_calls = 0

        def close(self):
            self.close_calls += 1
            raise RuntimeError("controller close failed")

    app = QApplication.instance() or QApplication([])
    controller = BrokenCloseController(save_path=tmp_path / "save.json", auto_load=False)
    original_provider = controller.expression_context_provider
    window = CompanionWindow(controller=controller)
    window._manual_perception_summary = "manual context"

    window.closeEvent(QCloseEvent())
    app.processEvents()

    assert controller.close_calls == 1
    assert window._manual_perception_summary == ""
    assert controller.expression_context_provider is original_provider


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
