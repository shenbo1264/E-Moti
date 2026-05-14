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


def make_controller(tmp_path):
    from guanghe_companion.controller import CompanionController

    return CompanionController(save_path=tmp_path / "save.json", auto_load=False)


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
