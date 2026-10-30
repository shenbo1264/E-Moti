import socket
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from guanghe_companion.mobile_link_view_model import (
    device_rows,
    invitation_view,
    link_status_view,
)


def test_invitation_view_counts_down_and_expires():
    view = invitation_view("a" * 43, created_at=100, now=160)
    assert view["code"] == "a" * 43
    assert view["remaining_seconds"] == 240
    assert view["expired"] is False
    assert "4:00" in view["text"]
    expired = invitation_view("a" * 43, created_at=100, now=400)
    assert expired["expired"] is True
    assert expired["code"] == ""
    assert "已过期" in expired["text"]
    assert invitation_view(None, created_at=None, now=0)["code"] == ""


def test_device_rows_describe_status_and_only_active_can_revoke():
    rows = device_rows([
        {"device_id": "d1", "name": "Xiaomi 15", "status": "active", "paired_at": 0, "expires_at": 30 * 86400},
        {"device_id": "d2", "name": "old", "status": "revoked", "paired_at": 0, "expires_at": 30 * 86400},
        {"device_id": "d3", "name": "older", "status": "expired", "paired_at": 0, "expires_at": 10},
    ], now=86400)
    assert [row["can_revoke"] for row in rows] == [True, False, False]
    assert "Xiaomi 15" in rows[0]["title"] and "29 天后到期" in rows[0]["title"]
    assert "已撤销" in rows[1]["title"]
    assert "已过期" in rows[2]["title"]


@pytest.mark.parametrize("state, enabled, running", [
    ("unsupported", False, False),
    ("missing_dependency", False, False),
    ("stopped", True, False),
    ("starting", False, True),
    ("running", False, True),
    ("failed", True, False),
])
def test_link_status_view_states(state, enabled, running):
    view = link_status_view(state, port=8765)
    assert view["can_start"] is enabled
    assert view["can_stop"] is running
    assert view["can_invite"] is (state == "running")
    assert view["text"]


def test_link_status_running_names_local_address_and_no_observation():
    text = link_status_view("running", port=8765)["text"]
    assert "127.0.0.1:8765" in text


def _free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def _wait(app, predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    return predicate()


def _pump(app, future):
    assert _wait(app, future.done)
    return future.result()


def test_panel_unsupported_controller_keeps_link_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from guanghe_companion.controller import CompanionController
    from guanghe_companion.mobile_link_qt import MobileLinkPanel

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    panel = MobileLinkPanel(controller, data_root=tmp_path)
    assert panel.state == "unsupported"
    assert panel.start_button.isEnabled() is False
    assert panel.invite_button.isEnabled() is False
    panel.close_link()
    controller.close()


def test_panel_real_host_pair_list_and_revoke(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    httpx = pytest.importorskip("httpx")
    pytest.importorskip("fastapi")
    from PySide6.QtWidgets import QApplication
    from guanghe_companion.mobile_link_qt import MobileLinkPanel
    from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController

    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    snapshots = []
    port = _free_port()
    panel = MobileLinkPanel(controller, data_root=tmp_path, port=port, on_snapshot=snapshots.append)
    assert panel.state == "stopped"
    assert panel.invite_button.isEnabled() is False
    panel.start_button.click()
    assert _wait(app, lambda: panel.state == "running")
    assert panel.invite_button.isEnabled() is True
    assert panel.start_button.isEnabled() is False
    panel.invite_button.click()
    code = panel.invitation_code_label.text()
    assert len(code) >= 32
    assert panel.devices_list.count() == 0
    try:
        with ThreadPoolExecutor(1) as worker, httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
            paired = _pump(app, worker.submit(client.post, "/v1/pair",
                                              json={"invitation": code, "device_name": "test-phone"}))
            assert paired.status_code == 200
            token = paired.json()["access_token"]
            client.headers["Authorization"] = "Bearer " + token
            assert _pump(app, worker.submit(client.get, "/v1/session")).status_code == 200
            panel.refresh_devices()
            assert panel.devices_list.count() == 1
            assert "test-phone" in panel.devices_list.item(0).text()
            panel.devices_list.setCurrentRow(0)
            assert panel.revoke_button.isEnabled() is True
            panel.revoke_selected(confirm=False)
            assert "已撤销" in panel.devices_list.item(0).text()
            assert _pump(app, worker.submit(client.get, "/v1/session")).status_code == 401
    finally:
        panel.stop_button.click()
        assert _wait(app, lambda: panel.state == "stopped")
        panel.close_link()
        controller.close()
    assert panel.invitation_code_label.text() == ""


def test_panel_reports_port_in_use(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("fastapi")
    from PySide6.QtWidgets import QApplication
    from guanghe_companion.mobile_link_qt import MobileLinkPanel
    from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController

    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    with socket.socket() as blocker:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            blocker.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        panel = MobileLinkPanel(controller, data_root=tmp_path, port=blocker.getsockname()[1])
        panel.start_button.click()
        assert _wait(app, lambda: panel.state == "failed")
    assert "启动失败" in panel.status_label.text()
    assert panel.start_button.isEnabled() is True
    panel.close_link()
    controller.close()
