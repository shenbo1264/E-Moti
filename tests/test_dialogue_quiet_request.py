import time
from dataclasses import replace

import pytest
from PySide6.QtCore import QCoreApplication

from guanghe_companion.capability_settings import ProactiveCompanionSettings
from guanghe_companion.desktop_dialogue_service import DesktopDialogueService
from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController
from guanghe_companion.proactive_companion import ProactiveCompanionService, rejection_cooldown_seconds


def assert_quiet(controller):
    assert controller.last_feedback == "好，我先安静待着。"
    assert controller._last_proactive_at["__rejection__"] == controller.now
    assert controller._last_proactive_at["__global__"] == controller.now
    assert controller.dialogue_history[-1].text == "好，我先安静待着。"
    settings = ProactiveCompanionSettings(enabled=True, quiet_hours_enabled=False)
    controller.state.charge = 10
    cooldown = rejection_cooldown_seconds(settings)
    for elapsed, expected in [(cooldown - 1, False), (cooldown, True)]:
        feedback = ProactiveCompanionService(
            state=controller.state, previous_state=replace(controller.state),
            now=int(controller.now) + elapsed, settings=settings,
            last_proactive_at=controller._last_proactive_at, daily_counts={},
        ).select_feedback()
        assert (feedback is not None) is expected


@pytest.mark.parametrize("text", ["别烦我，先别说话了。", "先别说话了", "请让我安静一会儿。", "暂时别打扰我", "星汐，先安静一会儿吧。", "你能先别说话了吗？"])
def test_direct_quiet_request_uses_local_ack_and_existing_cooldown(tmp_path, text):
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        controller.now = 120
        controller.submit_dialogue_request(DialogueRequest(text), include_ai_expression=True)
        assert_quiet(controller)
        assert controller.last_chat_memory_result.status == "ignored"
    finally:
        controller.close()
    reopened = PluginEnabledCompanionController(user_data_root=tmp_path)
    try:
        assert reopened._last_proactive_at["__rejection__"] == 120
    finally:
        reopened.close()


def test_actual_qt_service_commits_local_quiet_ticket_without_expression(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    service = DesktopDialogueService(controller)
    snapshots = []
    service.snapshot_changed.connect(snapshots.append)
    try:
        future = service.submit(DialogueRequest("别烦我，先别说话了。"), include_ai_expression=True)
        assert not future.done()
        deadline = time.monotonic() + 5
        while not future.done() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.001)
        assert future.result(timeout=0)
        assert len(snapshots) == 1
        assert_quiet(controller)
        assert controller._host_dialogue_ticket is None
        assert not controller._desktop_dialogue_pending
    finally:
        service.close()
        controller.close()


def test_host_ticket_for_quiet_request_has_no_model_request(tmp_path):
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        ticket = controller.prepare_host_dialogue(DialogueRequest("先别说话了"), include_ai_expression=True)
        assert ticket.expression_request is None
        controller.complete_host_dialogue(ticket)
        assert_quiet(controller)
    finally:
        controller.close()


@pytest.mark.parametrize("text", [
    "如果我说别烦我，先别说话了，你会怎么办？",
    "他说：别烦我，先别说话了。",
    "‘别烦我，先别说话了。’这句话是不是很凶？",
    "把‘先别说话了’翻译成英文", "我没有让你先别说话了", "先别说话了是什么意思？",
])
def test_quoted_hypothetical_and_non_command_text_does_not_set_quiet_cooldown(tmp_path, text):
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        controller.submit_dialogue_request(DialogueRequest(text))
        assert "__rejection__" not in controller._last_proactive_at
        assert controller.last_feedback != "好，我先安静待着。"
    finally:
        controller.close()
