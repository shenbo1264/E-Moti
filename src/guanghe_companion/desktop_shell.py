from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtWidgets import QApplication


class DesktopWindow(Protocol):
    def pos(self) -> QPoint:
        ...

    def size(self) -> QSize:
        ...

    def width(self) -> int:
        ...

    def height(self) -> int:
        ...

    def frameGeometry(self) -> QRect:
        ...

    def move(self, target: QPoint) -> None:
        ...


@dataclass(slots=True)
class DesktopShell:
    window: DesktopWindow
    available_geometry_provider: Callable[[], QRect] | None = None
    dock_threshold_px: int = 32

    def move_by(self, delta: QPoint, *, enabled: bool) -> None:
        if not enabled:
            return
        self.window.move(self.clamp_position(self.window.pos() + delta))

    def clamp_position(self, target: QPoint) -> QPoint:
        bounds = self.available_geometry()
        max_x = max(bounds.left(), bounds.right() - self.window.width() + 1)
        max_y = max(bounds.top(), bounds.bottom() - self.window.height() + 1)
        x = min(max(target.x(), bounds.left()), max_x)
        y = min(max(target.y(), bounds.top()), max_y)
        return QPoint(x, y)

    def dock_position(self, target: QPoint) -> QPoint:
        clamped = self.clamp_position(target)
        bounds = self.available_geometry()
        max_x = max(bounds.left(), bounds.right() - self.window.width() + 1)
        max_y = max(bounds.top(), bounds.bottom() - self.window.height() + 1)

        x = clamped.x()
        if x - bounds.left() <= self.dock_threshold_px:
            x = bounds.left()
        elif max_x - x <= self.dock_threshold_px:
            x = max_x

        y = clamped.y()
        if y - bounds.top() <= self.dock_threshold_px:
            y = bounds.top()
        elif max_y - y <= self.dock_threshold_px:
            y = max_y

        return QPoint(x, y)

    def available_geometry(self) -> QRect:
        if self.available_geometry_provider is not None:
            return self.available_geometry_provider()
        screen = QApplication.screenAt(self.window.frameGeometry().center()) or QApplication.primaryScreen()
        if screen is None:
            return QRect(self.window.pos(), self.window.size())
        return screen.availableGeometry()
