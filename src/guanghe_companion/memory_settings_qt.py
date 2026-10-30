from __future__ import annotations

"""Chat memory mode and semantic recall controls shown above the memory album."""

import json
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QCheckBox, QGridLayout, QGroupBox, QLabel
from .ui_controls import CompanionComboBox as QComboBox

from .memory_settings_view_model import CHAT_MEMORY_MODES, MODE_HELP, semantic_status_text

SETTINGS_FILENAME = "memory_ui_settings.json"


class MemorySettingsPanel(QGroupBox):
    def __init__(self, controller, *, data_root: Path | None, on_changed=None, parent=None) -> None:
        super().__init__("记忆设置", parent)
        self.controller = controller
        self.data_root = Path(data_root) if data_root is not None else None
        self._on_changed = on_changed
        self._warmup = None
        self._syncing = False
        layout = QGridLayout(self)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)
        self.mode_combo = QComboBox()
        self.mode_combo.setAccessibleName("聊天记忆方式")
        mode_label = QLabel("聊天记忆方式")
        mode_label.setBuddy(self.mode_combo)
        for mode, label in CHAT_MEMORY_MODES:
            self.mode_combo.addItem(label, mode)
        self.mode_help_label = QLabel()
        self.mode_help_label.setWordWrap(True)
        self.mode_help_label.setProperty("role", "secondary")
        self.semantic_check = QCheckBox("语义召回（本机模型）")
        self.semantic_status_label = QLabel()
        self.semantic_status_label.setWordWrap(True)
        self.semantic_status_label.setProperty("role", "secondary")
        layout.addWidget(mode_label, 0, 0)
        layout.addWidget(self.mode_combo, 0, 1)
        layout.addWidget(self.mode_help_label, 1, 0, 1, 2)
        layout.addWidget(self.semantic_check, 2, 0)
        layout.addWidget(self.semantic_status_label, 2, 1)
        layout.setColumnStretch(1, 1)
        self.mode_combo.currentIndexChanged.connect(self._mode_selected)
        self.semantic_check.toggled.connect(self._semantic_toggled)
        self._poll = QTimer(self)
        self._poll.setInterval(250)
        self._poll.timeout.connect(self._check_warmup)
        self.refresh()
        if self._saved_semantic_enabled():
            self._start_semantic(local_files_only=True)

    def refresh(self) -> None:
        status = self.controller.get_chat_memory_status()
        self._syncing = True
        self.mode_combo.setCurrentIndex(self.mode_combo.findData(status["mode"]))
        self.semantic_check.setChecked(bool(status["semantic"].get("enabled")))
        self._syncing = False
        self.mode_help_label.setText(MODE_HELP[status["mode"]])
        self.semantic_status_label.setText(semantic_status_text(status["semantic"]))

    def _mode_selected(self) -> None:
        if self._syncing:
            return
        self.controller.set_chat_memory_mode(self.mode_combo.currentData())
        self.refresh()
        if callable(self._on_changed):
            self._on_changed()

    def _semantic_toggled(self, checked: bool) -> None:
        if self._syncing:
            return
        self._save_semantic_enabled(checked)
        if checked:
            self._start_semantic(local_files_only=False)
        else:
            self._warmup = None
            self._poll.stop()
            self.controller.disable_semantic_memory()
            self.refresh()

    def _start_semantic(self, *, local_files_only: bool) -> None:
        if self.data_root is None:
            return
        try:
            self._warmup = self.controller.enable_semantic_memory(
                cache_dir=self.data_root / "semantic_cache", local_files_only=local_files_only)
        except ImportError:
            self._semantic_failed("缺少语义组件，请运行 pip install -e \".[semantic]\"")
            return
        self.semantic_status_label.setText(semantic_status_text({"enabled": True, "state": "loading"}))
        self._poll.start()

    def _check_warmup(self) -> None:
        if self._warmup is None or not self._warmup.done():
            return
        future, self._warmup = self._warmup, None
        self._poll.stop()
        error = future.exception()
        if error is None:
            self.refresh()
            return
        self._semantic_failed(str(error) or type(error).__name__)

    def _semantic_failed(self, reason: str) -> None:
        self.controller.disable_semantic_memory()
        self.refresh()
        self.semantic_status_label.setText(f"语义召回未能开启：{reason}。目前按字面匹配。")

    def _settings_path(self) -> Path | None:
        return self.data_root / SETTINGS_FILENAME if self.data_root is not None else None

    def _saved_semantic_enabled(self) -> bool:
        path = self._settings_path()
        if path is None or not path.exists():
            return False
        try:
            return bool(json.loads(path.read_text(encoding="utf-8")).get("semantic_enabled"))
        except (OSError, ValueError, AttributeError):
            return False

    def _save_semantic_enabled(self, enabled: bool) -> None:
        path = self._settings_path()
        if path is not None:
            path.write_text(json.dumps({"semantic_enabled": enabled}), encoding="utf-8")
