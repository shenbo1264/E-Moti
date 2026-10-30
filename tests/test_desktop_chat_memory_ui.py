import time

import pytest
from PySide6.QtWidgets import QApplication

from guanghe_companion.memory_settings_view_model import (
    memory_receipt,
    semantic_status_text,
    source_details_text,
)


def test_receipt_only_speaks_when_something_happened():
    assert memory_receipt({"status": "ignored", "message": ""}) == ""
    assert memory_receipt(None) == ""
    assert "记下了" in memory_receipt({"status": "saved", "message": ""})
    assert memory_receipt({"status": "forgotten", "message": "已经忘记了"}) == "已经忘记了"


def test_source_text_shows_original_quote_not_raw_json():
    text = source_details_text({"summary": "我喜欢乌龙茶", "source": "user_chat", "user_confirmed": False, "version": 2,
                                "provenance": {"original_quote": "我最近喜欢乌龙茶", "confidence_reason": "明确自述"}})
    assert "你的原话：我最近喜欢乌龙茶" in text
    assert "{" not in text
    assert "来源：普通聊天" in text
    assert "未经你逐条确认" in text


def test_semantic_status_never_claims_ready_when_off():
    assert "未开启" in semantic_status_text({"enabled": False})
    assert "不可用" in semantic_status_text({"enabled": True, "state": "failed", "error": "x"})


def make_window(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController

    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    window = CompanionWindow(controller=controller)
    window.show()
    return app, window, controller


def wait(app, predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    return predicate()


def test_ordinary_chat_goes_through_service_and_shows_receipt(monkeypatch, tmp_path):
    app, window, controller = make_window(monkeypatch, tmp_path)
    window.dialogue_input.setText("我喜欢乌龙茶")
    window._handle_dialogue_submit()
    assert window.dialogue_input.isEnabled() is False
    assert window.dialogue_send_button.text() == "取消"
    assert wait(app, lambda: window.dialogue_input.isEnabled())
    assert window.dialogue_send_button.text() == "发送"
    assert window.dialogue_input.text() == ""
    assert "乌龙茶" in "\n".join(m.summary for m in controller.story_runtime.memory.store.load_memories())
    assert window.memory_receipt_button.isHidden() is False
    assert "记下了" in window.memory_receipt_button.text()
    page = window.memory_album_page
    page.refresh_memory_album()
    page.memory_list.setCurrentRow(1)
    page.memory_action_buttons[3].click()
    assert "你的原话" in page.memory_source_view.toPlainText()
    window.close()
    app.processEvents()


def test_ordinary_small_talk_shows_no_receipt(monkeypatch, tmp_path):
    app, window, _ = make_window(monkeypatch, tmp_path)
    window.dialogue_input.setText("今天天气不错")
    window._handle_dialogue_submit()
    assert wait(app, lambda: window.dialogue_input.isEnabled())
    assert window.memory_receipt_button.isHidden() is True
    window.close()
    app.processEvents()


def test_failure_restores_typed_text(monkeypatch, tmp_path):
    app, window, _ = make_window(monkeypatch, tmp_path)
    window.dialogue_input.setText("你好")
    window._handle_dialogue_submit()
    window._handle_dialogue_failed("连接超时")
    assert window.dialogue_input.isEnabled() is True
    assert window.dialogue_input.text() == "你好"
    assert "连接超时" in window.desktop_feedback_label.text()
    assert wait(app, lambda: window.desktop_dialogue._active is None)
    window.close()
    app.processEvents()


def test_mode_combo_changes_real_mode_and_review_keeps_fact_pending(monkeypatch, tmp_path):
    app, window, controller = make_window(monkeypatch, tmp_path)
    panel = window.memory_settings_panel
    assert panel.mode_combo.currentData() == "auto"
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData("review"))
    assert controller.get_chat_memory_status()["mode"] == "review"
    window.dialogue_input.setText("我喜欢乌龙茶")
    window._handle_dialogue_submit()
    assert wait(app, lambda: window.dialogue_input.isEnabled())
    assert controller.get_chat_memory_status()["pending_count"] == 1
    assert window.memory_pending_button.isHidden() is False
    window.close()
    app.processEvents()


def test_semantic_toggle_failure_is_visible_and_falls_back(monkeypatch, tmp_path):
    app, window, controller = make_window(monkeypatch, tmp_path)
    panel = window.memory_settings_panel

    def fail(**_):
        raise ImportError("fastembed")

    monkeypatch.setattr(controller, "enable_semantic_memory", fail)
    panel.semantic_check.setChecked(True)
    assert "未能开启" in panel.semantic_status_label.text()
    assert panel.semantic_check.isChecked() is False
    window.close()
    app.processEvents()


def test_rejected_extraction_asks_user_instead_of_failing_the_turn(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from guanghe_companion.desktop_dialogue_service import DesktopDialogueService
    from guanghe_companion.dialogue import DialogueRequest
    from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
    from guanghe_companion.expression_settings import ExpressionSettingsStore
    from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController

    app = QApplication.instance() or QApplication([])
    client = lambda prompt: "not json" if "用户事实抽取器" in prompt else '{"speech": "好"}'
    controller = PluginEnabledCompanionController(
        user_data_root=tmp_path, ai_expressor=ShinsekaiAIExpressor(llm_client=client, enabled=True),
        expression_settings_store=ExpressionSettingsStore(tmp_path / "off.json"))
    service = DesktopDialogueService(controller)
    errors = []
    service.failed.connect(errors.append)
    controller.memory_album_controller.remember_explicit(
        "我的猫叫年糕。", now=100, expected_epoch=controller.story_runtime.memory.store.context_epoch)
    future = service.submit(DialogueRequest(text="把我猫的事忘了吧。"), include_ai_expression=True)
    assert wait(app, future.done)
    assert errors == []
    assert controller.get_chat_memory_status()["last_result"]["status"] == "clarify"
    service.close()
    controller.close()
