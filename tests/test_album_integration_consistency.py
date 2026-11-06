from PySide6.QtWidgets import QApplication

from guanghe_companion.app import CompanionWindow
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def test_album_queries_validate_sources_without_recording_a_conversation(tmp_path):
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    try:
        memory, album = controller.story_runtime.memory, controller.memory_album_controller
        row = memory.remember(kind="玩家希望被记住", title="饮品", summary="我喜欢喝白茶",
            source="explicit_user_request", now=int(controller.now))
        before = memory.store.load_memories()[0].to_dict()
        result = album.ask("我喜欢喝什么")
        assert result["status"] == "sufficient"
        expanded = album.expand({row.memory_id: row.evidence_fingerprint()},
                                expected_epoch=result["context_epoch"])
        assert expanded["status"] == "sufficient"
        assert memory.store.load_memories()[0].to_dict() == before
        album.forget(row.memory_id, expected_epoch=result["context_epoch"])
        stale = album.expand({row.memory_id: row.evidence_fingerprint()},
                             expected_epoch=result["context_epoch"])
        assert stale["status"] == "unavailable"
        assert not stale["cards"] and not stale["spans"]
    finally:
        controller.close()


def test_snapshot_revocation_clears_album_sources_and_cross_character_receipts(tmp_path):
    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    window = CompanionWindow(controller=controller)
    try:
        memory, album = controller.story_runtime.memory, controller.memory_album_controller
        row = memory.remember(kind="玩家希望被记住", title="饮品", summary="我喜欢喝白茶",
            source="explicit_user_request", now=int(controller.now))
        page = window.memory_album_page
        page.refresh_memory_album()
        memory.retrieve("我喜欢喝什么", now=int(controller.now))
        album.capture_turn_evidence()
        page.show_turn_evidence()
        page.memory_action_buttons[3].click()
        assert page.memory_claim_list.count() == 1
        assert "白茶" in page.memory_source_view.toPlainText()
        album.forget(row.memory_id, expected_epoch=memory.store.context_epoch)
        window._apply_snapshot(controller.get_snapshot())
        assert page.memory_claim_list.count() == 0
        assert "白茶" not in page.memory_source_view.toPlainText()
        assert all("白茶" not in page.memory_list.item(i).text() for i in range(page.memory_list.count()))
        window.memory_receipt_button.setText("旧角色记下了")
        window.memory_receipt_button.show()
        window.memory_undo_button.show()
        window._last_saved_memory_ids = (row.memory_id,)
        window._apply_snapshot(controller.switch_character("original_oc", include_ai_expression=False))
        assert window.memory_receipt_button.isHidden() and window.memory_undo_button.isHidden()
        assert not window._last_saved_memory_ids
    finally:
        window.close()
        controller.close()
        app.processEvents()


def test_album_query_delivery_is_queued_and_withdrawal_discards_old_results(tmp_path):
    from guanghe_companion.memory_album_query import MemoryAlbumQueryService
    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    service = MemoryAlbumQueryService(lambda: controller.memory_album_controller)
    received, failed = [], []
    service.completed.connect(received.append)
    service.failed.connect(failed.append)
    try:
        memory = controller.story_runtime.memory
        row = memory.remember(kind="玩家希望被记住", title="饮品", summary="我喜欢喝白茶",
            source="explicit_user_request", now=int(controller.now))
        service.submit("我喜欢喝什么")
        assert not received
        controller.memory_album_controller.forget(row.memory_id, expected_epoch=memory.store.context_epoch)
        app.processEvents()
        assert not received and failed
        service.submit("我喜欢喝什么")
        app.processEvents()
        assert received[-1]["status"] == "unknown" and received[-1]["claims"] == []
        received.clear()
        service.submit("我喜欢喝什么")
        controller.switch_character("original_oc", include_ai_expression=False)
        app.processEvents()
        assert not received
        service.submit("我喜欢喝什么")
        service.close()
        app.processEvents()
        assert not received
    finally:
        service.close()
        controller.close()
