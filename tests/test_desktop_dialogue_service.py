import time
import pytest
from concurrent.futures import Future

from PySide6.QtCore import QCoreApplication

from guanghe_companion.desktop_dialogue_service import DesktopDialogueService
from guanghe_companion.controller import HostDialogueBusyError, HostDialogueStaleError
from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def pump(app, future):
    deadline = time.monotonic() + 5
    while not future.done() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)
    return future.result(timeout=0)


def test_desktop_async_chat_uses_same_memory_authority(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    service = DesktopDialogueService(controller)
    try:
        result = pump(app, service.submit(DialogueRequest("我喜欢乌龙茶"), include_ai_expression=False))
        assert result
        assert any("乌龙茶" in m.summary for m in controller.story_runtime.memory.store.load_memories())
        pump(app, service.submit(DialogueRequest("别再记我的饮料偏好了"), include_ai_expression=False))
        assert not any(not m.deleted for m in controller.story_runtime.memory.store.load_memories())
        assert controller.last_chat_memory_result.status == "forgotten"
    finally:
        service.close()
        controller.close()


def test_cancelled_queued_desktop_input_is_not_written(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    service = DesktopDialogueService(controller)
    try:
        future = service.submit(DialogueRequest("我喜欢红茶"), include_ai_expression=False)
        service.cancel()
        app.processEvents()
        assert future.cancelled()
        assert not controller.story_runtime.memory.store.load_memories()
    finally:
        service.close()
        controller.close()


def test_cancel_during_embedding_releases_slot_and_ignores_old_callback(tmp_path, monkeypatch):
    app = QCoreApplication.instance() or QCoreApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    service = DesktopDialogueService(controller)
    old_prepare, new_prepare = Future(), Future()
    old_prepare.set_running_or_notify_cancel()
    preparations = iter((old_prepare, new_prepare))
    monkeypatch.setattr(controller, "prepare_semantic_recall", lambda request: next(preparations))
    try:
        old_result = service.submit(DialogueRequest("我喜欢红茶"), include_ai_expression=False)
        service.cancel()
        assert old_result.cancelled()
        assert service._active is None
        assert not controller._desktop_dialogue_pending
        new_result = service.submit(DialogueRequest("我喜欢绿茶"), include_ai_expression=False)
        # A running ONNX batch can finish after cancellation. Its delivery
        # must not start the new request before the new preparation is ready.
        old_prepare.set_result(None)
        app.processEvents()
        assert not new_result.done()
        assert not controller.story_runtime.memory.store.load_memories()
        new_prepare.set_result(None)
        pump(app, new_result)
        summaries = [m.summary for m in controller.story_runtime.memory.store.load_memories() if not m.deleted]
        assert any("绿茶" in text for text in summaries)
        assert not any("红茶" in text for text in summaries)
    finally:
        service.close()
        controller.close()


def test_pending_preparation_blocks_other_dialogue_entry_and_revocation_fences_result(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    service = DesktopDialogueService(controller)
    try:
        controller.submit_dialogue_request(DialogueRequest("我喜欢红茶"))
        memory_id = controller.last_chat_memory_result.memory_ids[0]
        future = service.submit(DialogueRequest("我住在上海"), include_ai_expression=False)
        with pytest.raises(HostDialogueBusyError):
            controller.submit_dialogue_request(DialogueRequest("我住在北京"))
        controller.memory_album_controller.forget(memory_id, now=0)
        with pytest.raises(HostDialogueStaleError):
            pump(app, future)
        assert not any(not row.deleted for row in controller.story_runtime.memory.store.load_memories())
        pump(app, service.submit(DialogueRequest("我住在南京"), include_ai_expression=False))
    finally:
        service.close()
        controller.close()


def test_cancelled_future_cannot_commit_an_already_computed_expression(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    service = DesktopDialogueService(controller)
    try:
        ticket = controller.prepare_host_dialogue(DialogueRequest("你好"))
        work = Future()
        work.set_result(ticket.expressor.express(ticket.expression_request, effect="ATTENTION"))
        cancelled = Future()
        cancelled.cancel()
        service._active = {"ticket": ticket, "result": cancelled}
        service._deliver(("complete", work))
        assert not controller.dialogue_history
        assert controller._host_dialogue_ticket is None
    finally:
        service.close()
        controller.close()


def test_first_input_after_memory_expiry_is_processed(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    service = DesktopDialogueService(controller)
    try:
        controller.story_runtime.memory.remember(kind="用户自述", title="短期安排", summary="今晚看电影",
            source="explicit_user_request", now=0, valid_until=5)
        controller.now = 10
        pump(app, service.submit(DialogueRequest("你好"), include_ai_expression=False))
        assert controller.dialogue_history
    finally:
        service.close()
        controller.close()


def test_expiry_during_extraction_cannot_resume_with_stale_context(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    service = DesktopDialogueService(controller)
    try:
        memory = controller.story_runtime.memory
        memory.remember(kind="用户自述", title="短期安排", summary="周末去爬山",
                        source="explicit_user_request", now=0, valid_until=5)
        envelope = controller.chat_memory_extraction.prepare("我家有一只狗", now=0,
            mode=controller.chat_memory.mode, generation=controller.host_context_generation)
        result = Future()
        service._active = {"result": result, "request": DialogueRequest("我家有一只狗"),
            "include_ai": False, "generation": controller.host_context_generation,
            "character": controller.state.character_id, "epoch": controller._dialogue_context_epoch(),
            "ticket": None, "extraction": envelope, "extractor": controller.chat_memory_extraction}
        controller.now = 10
        work = Future()
        work.set_result(())
        service._deliver(("extracted", work))
        with pytest.raises(HostDialogueStaleError):
            result.result()
        assert not controller.dialogue_history
        assert service._active is None
    finally:
        service.close()
        controller.close()


def test_live_evidence_expiry_invalidates_inflight_expression(tmp_path):
    from guanghe_companion.retrieval_contract import ExternalStateEvidence
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        controller.now = 10
        memory = controller.story_runtime.memory
        memory.external_state_readers["relay"] = lambda intent, now: ExternalStateEvidence(
            "relay", "构建已完成", 10, 11, "relay:job:7:v4", controller.state.character_id)
        ticket = controller.prepare_host_dialogue(DialogueRequest("Relay 的任务完成了吗？"))
        assert ticket.expression_request.emotional_memory["external_state"]
        assert controller._expression_context_is_current(ticket.expression_request)
        epoch = memory.store.current_context_epoch(now=10)
        controller.now = 11
        assert memory.store.current_context_epoch(now=11) == epoch  # no local fact changed
        assert not controller._expression_context_is_current(ticket.expression_request)
    finally:
        controller.close()
