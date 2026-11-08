from time import monotonic

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from guanghe_companion.memory_album_qt import create_memory_album_widget
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


@pytest.fixture
def album_widget(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    controller.now = 200_000
    album = controller.memory_album_controller
    album.remember_explicit("我喜欢喝乌龙茶")
    album.remember_explicit("我住在杭州")
    memories = controller.story_runtime.memory.store.load_memories()
    tea = next(row for row in memories if "乌龙茶" in row.summary)
    address = next(row for row in memories if "杭州" in row.summary)
    album.pin(address.memory_id, True)
    widget = create_memory_album_widget(controller)
    try:
        yield app, controller, widget, tea, address
    finally:
        if widget.memory_edit_dialog is not None:
            widget.memory_edit_dialog.reject()
        widget.close_memory_query()
        widget.close()
        controller.close()
        app.processEvents()


def current_id(widget):
    item = widget.memory_list.currentItem()
    return item.data(Qt.ItemDataRole.UserRole) if item is not None else None


def select_id(widget, memory_id):
    for index in range(widget.memory_list.count()):
        item = widget.memory_list.item(index)
        if item.data(Qt.ItemDataRole.UserRole) == memory_id:
            widget.memory_list.setCurrentItem(item)
            return
    pytest.fail("expected real memory card missing")


def ask(app, widget, text):
    widget.memory_ask_input.setText(text)
    widget.memory_ask_button.click()
    deadline = monotonic() + 5
    while not widget.memory_ask_button.isEnabled() and monotonic() < deadline:
        app.processEvents()
        QTest.qWait(1)
    assert widget.memory_ask_button.isEnabled()


def click_claim(widget, memory_id):
    for index in range(widget.memory_claim_list.count()):
        item = widget.memory_claim_list.item(index)
        if item.data(Qt.ItemDataRole.UserRole + 1)["memory_id"] == memory_id:
            widget.memory_claim_list.itemClicked.emit(item)
            return
    pytest.fail("expected source claim missing")


def test_expanded_source_selects_the_same_edit_target(album_widget):
    app, controller, widget, tea, address = album_widget
    assert current_id(widget) == address.memory_id
    ask(app, widget, "我喜欢喝什么")
    assert widget.memory_claim_list.count() == 1
    click_claim(widget, tea.memory_id)
    assert "乌龙茶" in widget.memory_source_view.toPlainText()
    assert current_id(widget) == tea.memory_id
    widget.memory_action_buttons[1].click()
    assert widget.memory_edit_dialog.summary_input.toPlainText() == "我喜欢喝乌龙茶"
    widget.memory_edit_dialog.reject()
    assert next(row for row in controller.story_runtime.memory.store.load_memories()
                if row.memory_id == address.memory_id).summary == "我住在杭州"


def test_changing_list_selection_clears_the_previous_source(album_widget):
    _, _, widget, tea, address = album_widget
    select_id(widget, address.memory_id)
    widget.memory_action_buttons[3].click()
    assert "杭州" in widget.memory_source_view.toPlainText()
    select_id(widget, tea.memory_id)
    assert "杭州" not in widget.memory_source_view.toPlainText()
    widget.memory_action_buttons[3].click()
    assert "乌龙茶" in widget.memory_source_view.toPlainText()
    assert "杭州" not in widget.memory_source_view.toPlainText()


def test_multiple_query_sources_disable_edits_until_one_source_is_selected(album_widget):
    app, _, widget, tea, address = album_widget
    widget.memory_action_buttons[3].click()
    assert "杭州" in widget.memory_source_view.toPlainText()
    ask(app, widget, "我喜欢喝什么？我住在哪里？")
    assert widget.memory_claim_list.count() == 2
    assert current_id(widget) is None
    assert widget.memory_source_view.toPlainText() == ""
    assert all(not button.isEnabled() for button in widget.memory_action_buttons)
    click_claim(widget, tea.memory_id)
    assert current_id(widget) == tea.memory_id
    assert widget.memory_action_buttons[1].isEnabled()
    assert widget.memory_action_buttons[2].isEnabled()
    assert "乌龙茶" in widget.memory_source_view.toPlainText()
    assert "杭州" not in widget.memory_source_view.toPlainText()
