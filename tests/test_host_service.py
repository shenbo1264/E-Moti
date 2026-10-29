import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from PySide6.QtWidgets import QApplication

from guanghe_companion.host_auth import DeviceCredentials
from guanghe_companion.host_service import CompanionHost, HostError
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


@pytest.fixture
def host(tmp_path):
    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    auth = DeviceCredentials(tmp_path / "devices.sqlite3")
    service = CompanionHost(controller, auth)
    invitation = service.create_invitation()
    token = auth.pair(invitation, device_name="phone")["access_token"]
    yield service, token, app
    service.close()
    controller.close()


def call(host, token, action, **payload):
    future = host.submit(token, action, payload)
    app = QApplication.instance()
    deadline = time.monotonic() + 5
    while not future.done() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)
    return future.result(timeout=0.1)


def test_authenticated_memory_and_idempotency(host):
    service, token, _ = host
    session = call(service, token, "session")
    body = dict(session_id=session["session_id"], expected_epoch=session["context_epoch"],
                request_id="remember-1", operation="remember", text="我喜欢紫苏冰饮")
    first = call(service, token, "memory_edit", **body)
    assert call(service, token, "memory_edit", **body) == first
    rows = service.controller.story_runtime.memory.store.load_memories()
    assert len([r for r in rows if not r.deleted]) == 1
    with pytest.raises(HostError, match="request_id"):
        call(service, token, "memory_edit", **{**body, "text": "我喜欢别的饮料"})
    memory_id = next(r.memory_id for r in rows if not r.deleted)
    call(service, token, "memory_edit", **{**body, "request_id": "forget-1", "operation": "forget", "memory_id": memory_id})
    with pytest.raises(HostError, match="stale"):
        call(service, token, "memory_edit", **body)
    assert call(service, token, "session")["context_epoch"] > session["context_epoch"]


def test_owner_mapping_revoke_and_restart_session(host):
    service, token, _ = host
    session = call(service, token, "session")
    with pytest.raises(HostError, match="session"):
        call(service, token, "message", session_id="old-process", expected_epoch=0, request_id="x", text="你好")
    service.revoke_device(service.credentials.authenticate(token).device_id)
    with pytest.raises(HostError, match="credential"):
        call(service, token, "session")


def test_message_runs_through_real_controller_and_owner_thread(host):
    service, token, app = host
    session = call(service, token, "session")
    with ThreadPoolExecutor(1) as executor:
        submitted = executor.submit(service.submit, token, "message", {
            "session_id": session["session_id"], "expected_epoch": session["context_epoch"],
            "request_id": "hello", "text": "你好"}).result()
    while not submitted.done():
        app.processEvents()
    accepted = submitted.result()
    assert accepted["status"] in {"running", "completed"}
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = call(service, token, "message_result", request_id="hello")
        if result["status"] != "running":
            break
        time.sleep(0.01)
    assert result["status"] == "completed"
    assert result["events"]
    assert service.controller.dialogue_history[-1].context_epoch == session["context_epoch"]
    assert "dialogue_history" not in call(service, token, "session")
