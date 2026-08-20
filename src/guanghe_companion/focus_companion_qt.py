from __future__ import annotations

"""Optional PySide6 widget for the user-confirmed focus companion flow."""

from typing import Callable


def create_focus_companion_widget(controller: object, on_changed=None, parent: object | None = None):
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QCheckBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
    except ImportError as exc:  # pragma: no cover - exercised by contract tests without Qt
        raise RuntimeError("PySide6 is required for the focus companion widget") from exc
    if QApplication.instance() is None:
        raise RuntimeError("PySide6 QApplication is required for the focus companion widget")

    widget = QWidget(parent)
    layout = QVBoxLayout(widget)
    title = QLabel("探头时刻")
    enabled_check = QCheckBox("启用低频探头判断")
    status = QLabel()
    status.setWordWrap(True)
    buttons = QHBoxLayout()
    demo = QPushButton("模拟专注 52 分钟")
    accept = QPushButton("陪她歇一会儿")
    snooze = QPushButton("再等一会儿")
    mute = QPushButton("今天先别管我")
    for button in (demo, accept, snooze, mute):
        buttons.addWidget(button)
    layout.addWidget(title); layout.addWidget(enabled_check); layout.addWidget(status); layout.addLayout(buttons); layout.addStretch(1)

    story = getattr(controller, "story_runtime", None) or getattr(controller, "story", None)
    coordinator = getattr(story, "focus", None)
    if coordinator is None:
        raise RuntimeError("PySide6 focus companion widget requires a compatible controller")

    def refresh() -> None:
        snap = coordinator.snapshot().to_public_dict()
        enabled_check.blockSignals(True)
        enabled_check.setChecked(bool(coordinator.settings.enabled))
        enabled_check.blockSignals(False)
        pending = snap.get("pending_offer") or {}
        timer = snap.get("timer") or {}
        if pending:
            status.setText(str(pending.get("speech", "星汐正在等你的回应。")))
        elif timer.get("active"):
            status.setText(f"正在一起休息，剩余 {timer.get('remaining_seconds', 0)} 秒。")
        else:
            status.setText("星汐会在合适的时候从桌角探头；你随时可以关闭这项功能。")

    def call(method: str, **kwargs: object) -> None:
        try:
            target = getattr(controller, method, None)
            if callable(target):
                target(**kwargs)
            else:
                getattr(coordinator, method)(**kwargs)
        except Exception as exc:
            status.setText(str(exc))
        refresh()
        if callable(on_changed):
            on_changed()

    enabled_check.toggled.connect(lambda checked: call("set_focus_companion_enabled", enabled=checked))
    demo.clicked.connect(lambda: call("inject_demo_focus", focused_minutes=52))
    accept.clicked.connect(lambda: call("confirm_focus_break"))
    snooze.clicked.connect(lambda: call("snooze_focus_break"))
    mute.clicked.connect(lambda: call("mute_focus_break_today"))
    timer = QTimer(widget); timer.timeout.connect(lambda: (getattr(controller, "tick_focus_companion", coordinator.tick)(), refresh())); timer.start(1000)
    widget._emoti_timer = timer  # type: ignore[attr-defined]
    widget.focus_enabled_check = enabled_check  # type: ignore[attr-defined]
    refresh()
    return widget
