from __future__ import annotations

"""PySide6 Plugin Center built from generic controller/view-model contracts."""

import json
from pathlib import Path


def create_plugin_center_widget(controller: object, on_changed=None, parent: object | None = None):
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QFileDialog,
            QApplication,
            QHBoxLayout,
            QLabel,
            QListWidget,
            QListWidgetItem,
            QMessageBox,
            QPushButton,
            QSplitter,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PySide6 is required for the plugin center") from exc
    if QApplication.instance() is None:
        raise RuntimeError("PySide6 QApplication is required for the plugin center")

    center = getattr(controller, "plugin_center_controller", controller)
    if not callable(getattr(center, "snapshot", None)):
        raise RuntimeError("PySide6 plugin center requires a compatible controller")
    widget = QWidget(parent)
    root = QVBoxLayout(widget)
    title = QLabel("E-Moti 插件中心")
    hint = QLabel("插件可扩展互动、记忆、角色表达和本地能力。启用第三方插件前，请查看权限和审计结果。")
    hint.setWordWrap(True)
    trust_notice = QLabel("同进程 Python 插件属于可信代码；只启用你了解来源并审阅过权限的插件。")
    trust_notice.setWordWrap(True)
    root.addWidget(title); root.addWidget(hint); root.addWidget(trust_notice)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    plugin_list = QListWidget()
    detail = QTextEdit(); detail.setReadOnly(True)
    splitter.addWidget(plugin_list); splitter.addWidget(detail); splitter.setStretchFactor(1, 1)
    root.addWidget(splitter, stretch=1)

    settings_editor = QTextEdit(); settings_editor.setPlaceholderText("插件设置 JSON 对象")
    settings_editor.setMaximumHeight(130)
    root.addWidget(settings_editor)
    panels = QTextEdit()
    panels.setReadOnly(True)
    panels.setMaximumHeight(150)
    panels.setPlaceholderText("当前没有插件提供页面内容。")
    root.addWidget(panels)
    buttons = QHBoxLayout()
    enable = QPushButton("启用")
    disable = QPushButton("停用")
    save_settings = QPushButton("保存设置")
    refresh_button = QPushButton("刷新")
    install_button = QPushButton("安装插件包")
    uninstall_button = QPushButton("卸载")
    clear_data = QPushButton("清除数据")
    clear_quarantine = QPushButton("解除隔离")
    action_buttons = (enable, disable, save_settings, refresh_button, install_button, uninstall_button, clear_data, clear_quarantine)
    for button in action_buttons:
        buttons.addWidget(button)
    root.addLayout(buttons)

    cache: dict[str, dict[str, object]] = {}

    def selected_id() -> str:
        item = plugin_list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def show_selected(*_args: object) -> None:
        plugin_id = selected_id()
        row = cache.get(plugin_id)
        if row is None:
            detail.clear(); settings_editor.clear(); return
        detail.setPlainText(json.dumps(row, ensure_ascii=False, indent=2))
        settings_editor.setPlainText(json.dumps(row.get("effective_settings", {}), ensure_ascii=False, indent=2))
        uninstall_button.setEnabled(row.get("source_kind") == "installed")

    def refresh() -> None:
        previous = selected_id()
        snapshot = center.snapshot()
        cache.clear(); plugin_list.clear()
        for row in snapshot.get("plugins", []):
            if not isinstance(row, dict):
                continue
            plugin_id = str(row.get("plugin_id", ""))
            cache[plugin_id] = row
            state = "启用" if row.get("enabled") else "停用"
            if row.get("quarantined"):
                state = "已隔离"
            item = QListWidgetItem(f"{row.get('name', plugin_id)}  ·  {state}")
            item.setData(Qt.ItemDataRole.UserRole, plugin_id)
            plugin_list.addItem(item)
            if plugin_id == previous:
                plugin_list.setCurrentItem(item)
        if plugin_list.currentItem() is None and plugin_list.count():
            plugin_list.setCurrentRow(0)
        show_selected()
        panel_rows = center.panel_models()
        panels.setPlainText(json.dumps(panel_rows, ensure_ascii=False, indent=2) if panel_rows else "")

    def operate(method: str, *args: object) -> None:
        plugin_id = selected_id()
        if not plugin_id:
            return
        result = getattr(center, method)(plugin_id, *args)
        if not result.ok:
            QMessageBox.warning(widget, "插件操作失败", result.message)
        refresh()
        if callable(on_changed):
            on_changed()

    def save() -> None:
        plugin_id = selected_id()
        if not plugin_id:
            return
        try:
            payload = json.loads(settings_editor.toPlainText() or "{}")
            if not isinstance(payload, dict):
                raise ValueError("设置必须是 JSON 对象")
        except (json.JSONDecodeError, ValueError) as exc:
            QMessageBox.warning(widget, "设置格式错误", str(exc)); return
        result = center.set_settings(plugin_id, payload)
        if not result.ok:
            QMessageBox.warning(widget, "保存失败", result.message)
        refresh()
        if callable(on_changed):
            on_changed()

    def install() -> None:
        path, _ = QFileDialog.getOpenFileName(widget, "选择 E-Moti 插件包", "", "ZIP (*.zip)")
        if not path:
            return
        result = center.install(Path(path))
        if not result.ok:
            QMessageBox.warning(widget, "安装失败", result.message)
        refresh()

    plugin_list.currentItemChanged.connect(show_selected)
    enable.clicked.connect(lambda: operate("set_enabled", True))
    disable.clicked.connect(lambda: operate("set_enabled", False))
    clear_quarantine.clicked.connect(lambda: operate("clear_quarantine"))
    clear_data.clicked.connect(lambda: operate("clear_data"))
    uninstall_button.clicked.connect(lambda: operate("uninstall"))
    save_settings.clicked.connect(save)
    refresh_button.clicked.connect(refresh)
    install_button.clicked.connect(install)
    refresh()
    widget.plugin_list = plugin_list  # type: ignore[attr-defined]
    widget.plugin_detail = detail  # type: ignore[attr-defined]
    widget.plugin_settings_editor = settings_editor  # type: ignore[attr-defined]
    widget.plugin_panels = panels  # type: ignore[attr-defined]
    widget.plugin_trust_notice = trust_notice  # type: ignore[attr-defined]
    widget.plugin_action_buttons = action_buttons  # type: ignore[attr-defined]
    widget.refresh_plugins = refresh  # type: ignore[attr-defined]
    return widget
