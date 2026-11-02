import time

from PySide6.QtWidgets import QApplication

from guanghe_companion.host_auth import DeviceCredentials
from guanghe_companion.host_service import CompanionHost
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def call(host, token, action, **payload):
    future = host.submit(token, action, payload)
    deadline = time.monotonic() + 5
    while not future.done() and time.monotonic() < deadline:
        QApplication.instance().processEvents()
        time.sleep(.001)
    return future.result(timeout=.1)


def message(host, token, request_id, text):
    session = call(host, token, "session")
    result = call(host, token, "message", session_id=session["session_id"],
                  expected_epoch=session["context_epoch"], expected_revision=session["revision"],
                  request_id=request_id, text=text)
    deadline = time.monotonic() + 5
    while result["status"] == "running" and time.monotonic() < deadline:
        result = call(host, token, "message_result", request_id=request_id)
        time.sleep(.001)
    return session, result


def test_host_uses_desktop_memory_pipeline_and_distinguishes_own_committed_version(tmp_path):
    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    credentials = DeviceCredentials(tmp_path / "devices.sqlite3")
    host = CompanionHost(controller, credentials)
    token = credentials.pair(host.create_invitation(), device_name="test-phone")["access_token"]
    try:
        _, first = message(host, token, "fact", "我的室友叫林岚")
        assert first["status"] == "completed"
        session, corrected = message(host, token, "correction", "记错了，我的室友叫林溪")
        assert corrected["status"] == "completed"
        assert corrected["input_version"] == session["revision"]
        assert corrected["committed_version"] > corrected["input_version"]
        assert corrected["context_epoch"] > session["context_epoch"]
        rows = controller.story_runtime.memory.store.load_memories()
        assert any("林溪" in row.summary and not row.deleted for row in rows)
        assert not any("林岚" in row.summary and not row.deleted for row in rows)
        assert call(host, token, "message_result", request_id="fact")["status"] == "stale"
        assert host._dialogue.controller is controller
    finally:
        host.close()
        controller.close()
