"""Evidence chip, undo and proactive deferral in the real window."""

import time

from guanghe_companion.app import CompanionWindow
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController
from PySide6.QtWidgets import QApplication


def _window(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    window = CompanionWindow(controller=controller)
    window.show()
    return app, window, controller


def _say(app, window, text):
    window.dialogue_input.setText(text)
    window._handle_dialogue_submit()
    deadline = time.monotonic() + 10
    while not window.dialogue_input.isEnabled() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)


def test_small_talk_shows_no_memory_state(monkeypatch, tmp_path):
    app, window, _ = _window(monkeypatch, tmp_path)
    _say(app, window, "今天天气不错")
    assert window.memory_evidence_button.isHidden()
    window.close()


def test_new_turn_clears_old_evidence(monkeypatch, tmp_path):
    app, window, controller = _window(monkeypatch, tmp_path)
    controller.memory_album_controller.capture_turn_evidence()
    _say(app, window, "今天天气不错")
    assert window.memory_evidence_button.isHidden()
    window.close()


def test_recall_shows_evidence_and_opening_it_lists_sources(monkeypatch, tmp_path):
    app, window, controller = _window(monkeypatch, tmp_path)
    controller.memory_album_controller.remember_explicit("我喜欢喝乌龙茶", now=int(controller.now))
    _say(app, window, "今天天气不错")
    controller.story_runtime.memory.retrieve("我喜欢喝什么", now=int(controller.now))
    controller.memory_album_controller.capture_turn_evidence()
    window._show_turn_evidence()
    assert "有依据" in window.memory_evidence_button.text()
    window.memory_evidence_button.click()
    assert window.memory_album_page.memory_claim_list.count() == 1
    window.close()


def test_unknown_recall_is_not_an_alarm(monkeypatch, tmp_path):
    app, window, controller = _window(monkeypatch, tmp_path)
    controller.story_runtime.memory.retrieve("我的牙医叫什么名字", now=int(controller.now))
    controller.memory_album_controller.capture_turn_evidence()
    window._show_turn_evidence()
    assert "暂时没找到依据" in window.memory_evidence_button.text()
    assert "不代表你没说过" in window.memory_evidence_button.toolTip()
    window.close()


def test_casual_chat_with_fallback_route_shows_no_memory_state(monkeypatch, tmp_path):
    app, window, controller = _window(monkeypatch, tmp_path)
    for text in ("猫和狗你选哪个？说个理由", "不想说", "我今天又买了一个键盘，第五个了"):
        result = controller.story_runtime.memory.retrieve(text, now=int(controller.now))
        assert result.trace.status in {"unknown", "not_needed"}
        controller.memory_album_controller.capture_turn_evidence()
        window._show_turn_evidence()
        assert window.memory_evidence_button.isHidden()
    window.close()


def test_undo_withdraws_an_automatic_memory(monkeypatch, tmp_path):
    app, window, controller = _window(monkeypatch, tmp_path)
    _say(app, window, "我喜欢乌龙茶")
    assert not window.memory_undo_button.isHidden()
    window.memory_undo_button.click()
    assert not [m for m in controller.story_runtime.memory.store.load_memories() if not m.deleted]
    assert window.memory_undo_button.isHidden() and window.memory_receipt_button.isHidden()
    window.close()


def test_defer_is_not_counted_as_rejection(monkeypatch, tmp_path):
    from guanghe_companion.proactive_companion import (PROACTIVE_DEFERRED_UNTIL_KEY,
                                                       PROACTIVE_REJECTION_COOLDOWN_KEY)
    app, window, controller = _window(monkeypatch, tmp_path)
    controller.defer_proactive_request(3600)
    assert controller._last_proactive_at[PROACTIVE_DEFERRED_UNTIL_KEY] == int(controller.now) + 3600
    assert PROACTIVE_REJECTION_COOLDOWN_KEY not in controller._last_proactive_at
    window.close()


def test_committed_memory_signal_captures_evidence_before_empty_query_snapshots(monkeypatch, tmp_path):
    app, window, controller = _window(monkeypatch, tmp_path)
    memory = controller.story_runtime.memory
    memory.retrieve("我的牙医叫什么名字", now=int(controller.now))
    window.desktop_dialogue.memory_committed.emit(None)
    memory.retrieve("", now=int(controller.now))
    window._show_turn_evidence()
    assert "暂时没找到依据" in window.memory_evidence_button.text()
    window.close()
