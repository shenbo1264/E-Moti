from __future__ import annotations

"""Desktop page that lets the user opt in to the phone host and manage paired devices."""

from pathlib import Path
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from .mobile_link_view_model import device_rows, invitation_view, link_status_view

DEFAULT_HOST_PORT = 8765
CREDENTIALS_FILENAME = "host-devices.sqlite3"

CONNECTION_HELP = (
    "连接方式：\n"
    "· 安卓模拟器：在 App 中填写 http://10.0.2.2:{port}\n"
    "· USB 连接的真机：电脑运行 adb reverse tcp:{port} tcp:{port}，App 中填写 http://127.0.0.1:{port}\n"
    "局域网 Wi-Fi 直连需要可信 TLS 证书，当前版本未开放。"
)


def _host_modules():
    try:
        from .host_auth import DeviceCredentials
        from .host_runtime import HostServer
        from .host_service import CompanionHost
        from .plugin_enabled_controller import PluginEnabledCompanionController
    except ImportError:
        return None
    return DeviceCredentials, HostServer, CompanionHost, PluginEnabledCompanionController


class MobileLinkPanel(QWidget):
    def __init__(self, controller, *, data_root: Path | None, port: int = DEFAULT_HOST_PORT,
                 on_snapshot=None, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.data_root = Path(data_root) if data_root is not None else None
        self.port = port
        self._on_snapshot = on_snapshot
        self._modules = _host_modules()
        self._host = None
        self._server = None
        self._invitation = None
        self._invitation_created_at = None
        self.state = self._initial_state()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        link_card = QGroupBox("手机连接")
        link_layout = QVBoxLayout(link_card)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        buttons = QHBoxLayout()
        self.start_button = QPushButton("开启手机连接")
        self.stop_button = QPushButton("关闭")
        self.start_button.clicked.connect(self.start_link)
        self.stop_button.clicked.connect(self.stop_link)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        buttons.addStretch(1)
        self.help_label = QLabel()
        self.help_label.setWordWrap(True)
        self.help_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        link_layout.addWidget(self.status_label)
        link_layout.addLayout(buttons)
        link_layout.addWidget(self.help_label)
        layout.addWidget(link_card)

        invite_card = QGroupBox("配对新手机")
        invite_layout = QVBoxLayout(invite_card)
        invite_buttons = QHBoxLayout()
        self.invite_button = QPushButton("生成邀请码")
        self.copy_invitation_button = QPushButton("复制")
        self.invite_button.clicked.connect(self.create_invitation)
        self.copy_invitation_button.clicked.connect(self._copy_invitation)
        invite_buttons.addWidget(self.invite_button)
        invite_buttons.addWidget(self.copy_invitation_button)
        invite_buttons.addStretch(1)
        self.invitation_code_label = QLabel()
        self.invitation_code_label.setObjectName("InvitationCode")
        self.invitation_code_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.invitation_code_label.setWordWrap(True)
        self.invitation_status_label = QLabel()
        invite_layout.addLayout(invite_buttons)
        invite_layout.addWidget(self.invitation_code_label)
        invite_layout.addWidget(self.invitation_status_label)
        layout.addWidget(invite_card)

        devices_card = QGroupBox("已配对设备")
        devices_layout = QVBoxLayout(devices_card)
        self.devices_list = QListWidget()
        self.devices_list.currentItemChanged.connect(lambda *_: self._update_controls())
        device_buttons = QHBoxLayout()
        self.refresh_devices_button = QPushButton("刷新")
        self.revoke_button = QPushButton("撤销此设备")
        self.refresh_devices_button.clicked.connect(self.refresh_devices)
        self.revoke_button.clicked.connect(lambda: self.revoke_selected())
        device_buttons.addWidget(self.refresh_devices_button)
        device_buttons.addWidget(self.revoke_button)
        device_buttons.addStretch(1)
        self.devices_empty_label = QLabel("还没有配对的手机。开启连接并生成邀请码后，在手机 App 中输入即可。")
        self.devices_empty_label.setWordWrap(True)
        devices_layout.addWidget(self.devices_empty_label)
        devices_layout.addWidget(self.devices_list, stretch=1)
        devices_layout.addLayout(device_buttons)
        layout.addWidget(devices_card, stretch=1)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(200)
        self._poll_timer.timeout.connect(self._poll_server)
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._update_invitation)
        self.refresh_devices()
        self._update_controls()

    def _initial_state(self) -> str:
        if self.data_root is None:
            return "unsupported"
        if self._modules is None:
            return "missing_dependency"
        if not isinstance(self.controller, self._modules[3]):
            return "unsupported"
        return "stopped"

    def _credentials(self, *, create: bool):
        if self._modules is None or self.data_root is None:
            return None
        path = self.data_root / CREDENTIALS_FILENAME
        if not create and not path.exists():
            return None
        return self._modules[0](path)

    def start_link(self) -> None:
        if self.state not in {"stopped", "failed"}:
            return
        _, host_server, companion_host, _ = self._modules
        self._host = companion_host(self.controller, self._credentials(create=True))
        if self._on_snapshot is not None:
            self._host.snapshot_changed.connect(self._on_snapshot)
        self._server = host_server(self._host, bind="127.0.0.1", port=self.port)
        self._server.start()
        self.state = "starting"
        self._poll_timer.start()
        self._update_controls()

    def stop_link(self) -> None:
        if self._server is not None:
            self._server.stop()
            self._server.thread.join(timeout=4)
        self._release_host()
        if self.state in {"starting", "running"}:
            self.state = "stopped"
        self._update_controls()

    def _release_host(self) -> None:
        self._poll_timer.stop()
        self._clear_invitation()
        if self._host is not None:
            self._host.close()
        self._host = None
        self._server = None

    def _poll_server(self) -> None:
        if self._server is None:
            return
        alive = self._server.thread.is_alive()
        if alive and self._server.server.started:
            if self.state != "running":
                self.state = "running"
                self._update_controls()
            return
        if not alive:
            self._release_host()
            self.state = "failed"
            self._update_controls()

    def create_invitation(self) -> None:
        if self.state != "running" or self._host is None:
            return
        self._invitation = self._host.create_invitation()
        self._invitation_created_at = time.time()
        self._countdown_timer.start()
        self._update_invitation()

    def _clear_invitation(self) -> None:
        self._invitation = None
        self._invitation_created_at = None
        self._countdown_timer.stop()
        self._update_invitation()

    def _update_invitation(self) -> None:
        view = invitation_view(self._invitation, created_at=self._invitation_created_at, now=time.time())
        if view["expired"]:
            self._invitation = None
            self._countdown_timer.stop()
            self.refresh_devices()
        self.invitation_code_label.setText(view["code"])
        self.invitation_status_label.setText(view["text"])
        self.copy_invitation_button.setEnabled(bool(view["code"]))

    def _copy_invitation(self) -> None:
        if self._invitation:
            QApplication.clipboard().setText(self._invitation)

    def refresh_devices(self) -> None:
        selected = self._selected_device_id()
        self.devices_list.clear()
        credentials = self._credentials(create=False)
        owner = getattr(getattr(getattr(self.controller, "story_runtime", None), "memory", None), "owner_id", None)
        devices = credentials.list_devices(owner_id=owner) if credentials is not None and owner else []
        for row in device_rows(devices, now=time.time()):
            item = QListWidgetItem(row["title"])
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.devices_list.addItem(item)
            if row["device_id"] == selected:
                self.devices_list.setCurrentItem(item)
        self.devices_empty_label.setVisible(not devices)
        self._update_controls()

    def _selected_row(self):
        item = self.devices_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _selected_device_id(self):
        row = self._selected_row() if hasattr(self, "devices_list") else None
        return row["device_id"] if row else None

    def revoke_selected(self, *, confirm: bool = True) -> None:
        row = self._selected_row()
        if not row or not row["can_revoke"]:
            return
        if confirm and QMessageBox.question(
            self, "撤销设备", f"撤销后这台手机需要重新配对。确定撤销 {row['title']}？"
        ) != QMessageBox.StandardButton.Yes:
            return
        if self._host is not None:
            self._host.revoke_device(row["device_id"])
        else:
            self._credentials(create=True).revoke(row["device_id"])
        self.refresh_devices()

    def _update_controls(self) -> None:
        view = link_status_view(self.state, port=self.port)
        self.status_label.setText(view["text"])
        self.help_label.setText(CONNECTION_HELP.format(port=self.port))
        self.start_button.setEnabled(view["can_start"])
        self.stop_button.setEnabled(view["can_stop"])
        self.invite_button.setEnabled(view["can_invite"])
        row = self._selected_row()
        self.revoke_button.setEnabled(bool(row and row["can_revoke"]))
        self.refresh_devices_button.setEnabled(self.state not in {"unsupported", "missing_dependency"})

    def close_link(self) -> None:
        self.stop_link()
