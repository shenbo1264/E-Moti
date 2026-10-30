import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QPushButton, QStyle, QStyleOptionComboBox

from guanghe_companion.app import CompanionWindow, configure_application_style
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


@pytest.fixture
def window(tmp_path):
    app = QApplication.instance() or QApplication([])
    configure_application_style(app)
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    view = CompanionWindow(controller=controller)
    view.resize(1040, 700)
    view.show()
    app.processEvents()
    yield view
    view.close()
    controller.close()
    app.processEvents()


def test_all_pages_have_current_heading_and_navigation_returns_to_top(window):
    for index, button in enumerate(window.navigation_buttons):
        window.control_panel_scroll.verticalScrollBar().setValue(1000)
        button.click()
        QApplication.processEvents()
        assert window.page_title_label.text() == button.text()
        assert window.content_stack.currentIndex() == index
        assert window.control_panel_scroll.verticalScrollBar().value() == 0
        assert window.content_stack.widget(index).accessibleName() == button.text()
        assert window.control_panel_scroll.horizontalScrollBar().maximum() == 0


def test_plugin_actions_do_not_force_an_extra_wide_page(window):
    window.navigation_buttons[11].click()
    QApplication.processEvents()
    buttons = {b.text(): b for b in window.plugin_center_page.findChildren(QPushButton)}
    assert buttons["启用"].y() != buttons["卸载"].y()
    assert window.plugin_center_page.minimumSizeHint().width() < 760


def test_memory_controls_keep_persistent_labels(window):
    panel = window.memory_settings_panel
    labels = panel.findChildren(QLabel)
    assert any(label.buddy() is panel.mode_combo for label in labels)
    assert panel.mode_combo.accessibleName() == "聊天记忆方式"


def test_combo_preserves_keyboard_selection_and_arrow_space(window):
    combo = window.memory_settings_panel.mode_combo
    window.navigation_buttons[9].click()
    QApplication.processEvents()
    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    arrow = combo.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option, QStyle.SubControl.SC_ComboBoxArrow, combo)
    edit = combo.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option, QStyle.SubControl.SC_ComboBoxEditField, combo)
    assert arrow.width() >= 24
    assert edit.right() < arrow.left()
    rendered = combo.grab().toImage()
    center = arrow.center()
    assert any(rendered.pixelColor(x, y).lightness() < 150
               for x in range(center.x() - 5, center.x() + 6)
               for y in range(center.y() - 5, center.y() + 6))
    # 不改真实设置，只验证同样主题下的原生选择与关闭行为。
    probe = QComboBox(window)
    probe.addItems(["短选项", "中文与 English 混排的较长选项"])
    probe.resize(260, 36)
    probe.show()
    probe.setFocus()
    probe.showPopup()
    QTest.keyClick(probe.view(), Qt.Key.Key_Down)
    QTest.keyClick(probe.view(), Qt.Key.Key_Return)
    assert probe.currentIndex() == 1
    assert not probe.view().isVisible()


def test_navigation_stays_visible_when_content_scrolls(window):
    window.resize(1040, 600)
    window.navigation_buttons[9].click()
    QApplication.processEvents()
    top = window.navigation_buttons[0].mapToGlobal(window.navigation_buttons[0].rect().topLeft())
    window.control_panel_scroll.verticalScrollBar().setValue(10000)
    QApplication.processEvents()
    assert window.navigation_buttons[0].mapToGlobal(window.navigation_buttons[0].rect().topLeft()) == top
    assert window.sidebar_scroll.verticalScrollBar().maximum() > 0
