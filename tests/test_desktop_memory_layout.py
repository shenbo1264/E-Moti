import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from guanghe_companion.app import CompanionWindow
from guanghe_companion.chat_memory import ChatMemoryResult
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


@pytest.mark.parametrize('status', ['clarify', 'pending', 'forgotten'])
def test_memory_receipt_fits_desktop_and_keeps_full_detail(tmp_path, status):
    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    window = CompanionWindow(controller=controller, desktop_mode=True)
    window.show()
    detail = '这条没能确认要记或要忘什么，可以说得更具体，或在回忆册里操作。'
    controller.last_chat_memory_result = ChatMemoryResult(status, detail)
    window._handle_dialogue_finished(controller.get_snapshot())
    app.processEvents()
    receipt = window.memory_receipt_button
    assert receipt.fontMetrics().horizontalAdvance(receipt.text()) + 16 <= receipt.width()
    assert detail in receipt.toolTip()
    for widget in (window.desktop_feedback_label, window.dialogue_bar, receipt):
        origin = widget.mapTo(window, QPoint(0, 0))
        assert origin.y() >= 0
        assert origin.y() + widget.height() <= window.height()
    window.close()
    app.processEvents()


def test_pending_memory_does_not_squeeze_chat_input(tmp_path):
    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    controller.set_chat_memory_mode('review')
    controller.chat_memory.process('我喜欢茉莉茶', now=0)
    window = CompanionWindow(controller=controller, desktop_mode=True)
    window.show()
    app.processEvents()
    assert window.memory_pending_button.isVisible()
    assert window.dialogue_input.width() >= 100
    window.close()
    app.processEvents()
