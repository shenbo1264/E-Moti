import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QPushButton

from guanghe_companion.app import CompanionWindow
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


@pytest.mark.parametrize('height', [600, 760])
def test_control_panel_bottom_actions_are_reachable_at_normal_size(tmp_path, height):
    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    window = CompanionWindow(controller=controller)
    try:
        window.resize(1180, height)
        window.show()
        window.content_stack.setCurrentWidget(window.memory_album_page)
        app.processEvents()
        assert window.height() <= height
        scroll = window.control_panel_scroll
        buttons = window.memory_album_page.findChildren(QPushButton)
        bottom_button = max(buttons, key=lambda button: button.mapTo(window.memory_album_page, QPoint()).y())
        scroll.ensureWidgetVisible(bottom_button)
        app.processEvents()
        bottom = bottom_button.mapTo(scroll.viewport(), QPoint(0, bottom_button.height()))
        assert 0 < bottom.y() <= scroll.viewport().height()
    finally:
        window.close()
        controller.close()
        app.processEvents()


def test_standalone_desktop_returns_to_scrollable_control_panel(tmp_path):
    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    window = CompanionWindow(controller=controller, desktop_mode=True)
    try:
        window.show()
        app.processEvents()
        assert window.width() == 260
        window._return_to_control_panel()
        window.resize(1180, 600)
        window.content_stack.setCurrentWidget(window.memory_album_page)
        app.processEvents()
        assert window.height() <= 600
        assert window.control_panel_scroll.isVisible()
    finally:
        window.close()
        controller.close()
        app.processEvents()
