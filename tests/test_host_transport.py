from concurrent.futures import ThreadPoolExecutor
import socket
import time

import httpx
import pytest
from PySide6.QtWidgets import QApplication

from guanghe_companion.host_auth import DeviceCredentials
from guanghe_companion.host_runtime import HostServer
from guanghe_companion.host_service import CompanionHost
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController
from guanghe_companion.host_transport import MessageBody
from pydantic import ValidationError


def pump(app, future):
    deadline = time.monotonic() + 10
    while not future.done() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)
    return future.result(timeout=0.1)


def test_real_http_pair_chat_memory_revoke(tmp_path):
    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    host = CompanionHost(controller, DeviceCredentials(tmp_path / "auth.sqlite3"))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = HostServer(host, port=port)
    server.start()
    deadline = time.monotonic() + 5
    while not server.server.started and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    try:
        with ThreadPoolExecutor(1) as worker, httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
            def request(method, path, **kwargs):
                return pump(app, worker.submit(client.request, method, path, **kwargs))
            assert request("GET", "/v1/session").status_code == 401
            invitation = host.create_invitation()
            paired = request("POST", "/v1/pair", json={"invitation": invitation, "device_name": "integration-client"})
            assert paired.status_code == 200
            credentials = paired.json()
            client.headers["Authorization"] = "Bearer " + credentials["access_token"]
            session = request("GET", "/v1/session").json()
            version = {"session_id": session["session_id"], "expected_epoch": session["context_epoch"],
                       "expected_revision": session["revision"]}
            forged = request("POST", "/v1/messages", json={**version, "request_id": "forged", "text": "hi", "owner_id": "someone_else"})
            assert forged.status_code == 422
            response = request("POST", "/v1/messages", json={**version, "request_id": "hello", "text": "你好"})
            assert response.status_code == 202
            for _ in range(100):
                reply = request("GET", "/v1/messages/hello").json()
                if reply["status"] != "running":
                    break
                time.sleep(0.01)
            assert reply["status"] == "completed"
            assert reply["expression_mode"] == "local"
            remembered = request("POST", "/v1/memory", json={**version, "request_id": "fact", "operation": "remember", "text": "我的饮品是紫苏冰饮"})
            assert remembered.status_code == 200
            entry = next(e for e in controller.story_runtime.memory.store.load_memories() if not e.deleted)
            source = request("GET", f"/v1/memory/{entry.memory_id}/source")
            assert source.json()["source"]["user_confirmed"]
            corrected = request("POST", "/v1/memory", json={**version, "request_id": "correct", "operation": "correct",
                "memory_id": entry.memory_id, "text": "我的饮品是桂花茶"})
            assert corrected.status_code == 200
            current = corrected.json()
            version.update(expected_epoch=current["context_epoch"], expected_revision=current["revision"])
            from guanghe_companion.dialogue import DialogueRequest
            ticket = controller.prepare_host_dialogue(DialogueRequest("我的饮品是什么"))
            prompt = ticket.expressor.build_prompt(ticket.expression_request)
            assert "桂花茶" in prompt and "紫苏冰饮" not in prompt
            controller.complete_host_dialogue(ticket, ticket.expressor.express(ticket.expression_request))
            active = next(e for e in controller.story_runtime.memory.store.load_memories() if not e.deleted)
            forget_body = {**version, "request_id": "forget", "operation": "forget", "memory_id": active.memory_id}
            forgotten = request("POST", "/v1/memory", json=forget_body)
            assert forgotten.status_code == 200
            assert request("POST", "/v1/memory", json=forget_body).json() == forgotten.json()
            assert request("GET", "/v1/messages/hello").json()["status"] == "stale"
            assert request("POST", "/v1/messages", json={**version, "request_id": "late", "text": "你好"}).status_code == 409
            events = request("GET", "/v1/events?after=0").json()
            assert events["events"][-1]["clear_cached_content"]
            assert "紫苏冰饮" not in str(events)
            ticket = controller.prepare_host_dialogue(DialogueRequest("我的饮品是什么"))
            assert "桂花茶" not in ticket.expressor.build_prompt(ticket.expression_request)
            controller.complete_host_dialogue(ticket, ticket.expressor.express(ticket.expression_request))
            host.revoke_device(credentials["device_id"])
            assert request("GET", "/v1/memory").status_code == 401
    finally:
        server.stop()
        server.thread.join(timeout=5)
        host.close()
        controller.close()


def test_external_binding_requires_tls(tmp_path):
    with pytest.raises(ValueError, match="TLS"):
        HostServer(None, bind="0.0.0.0")


def test_network_does_not_accept_text_that_domain_would_truncate():
    with pytest.raises(ValidationError):
        MessageBody(session_id="session", expected_epoch=0, expected_revision=1,
                    request_id="long", text="字" * 241)
