from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QWidget


@dataclass(slots=True)
class TrayController:
    parent: QWidget
    tray_icon_class: type
    icon_provider: Callable[[], QIcon]
    show_control_panel: Callable[[], None]
    show_desktop_pet: Callable[[], None]
    hide_window: Callable[[], None]
    close_window: Callable[[], None]
    application_provider: Callable[[], Any | None] = QApplication.instance

    tray_icon: Any | None = None
    force_exit: bool = False
    close_message_shown: bool = False
    previous_quit_on_last_window_closed: bool | None = None
    owns_controller: bool = False

    def setup(self, *, owns_controller: bool) -> None:
        self.owns_controller = owns_controller
        if not owns_controller:
            return
        try:
            if not self.tray_icon_class.isSystemTrayAvailable():
                return
        except Exception:
            return

        tray_icon = self.tray_icon_class(self.icon_provider(), self.parent)
        tray_icon.setToolTip("星汐 E-Moti")
        tray_icon.setContextMenu(self._build_menu())
        tray_icon.activated.connect(self.handle_activated)
        tray_icon.show()
        self.tray_icon = tray_icon

        app = self.application_provider()
        if app is not None and self.previous_quit_on_last_window_closed is None:
            self.previous_quit_on_last_window_closed = app.quitOnLastWindowClosed()
            app.setQuitOnLastWindowClosed(False)

    def cleanup(self) -> None:
        tray_icon = self.tray_icon
        if tray_icon is None:
            return
        tray_icon.hide()
        self.tray_icon = None

    def should_hide_to_tray(self) -> bool:
        return self.tray_icon is not None and not self.force_exit

    def hide_to_tray(self) -> None:
        if self.tray_icon is None or self.force_exit:
            return
        self.hide_window()
        if self.close_message_shown:
            return
        self.close_message_shown = True
        try:
            self.tray_icon.showMessage(
                "星汐 E-Moti",
                "星汐已隐藏到托盘，可从托盘菜单恢复或退出。",
                self.tray_icon_class.MessageIcon.Information,
                2500,
            )
        except Exception:
            pass

    def handle_activated(self, reason: object) -> None:
        if reason in (
            self.tray_icon_class.ActivationReason.Trigger,
            self.tray_icon_class.ActivationReason.DoubleClick,
        ):
            self.show_control_panel()

    def request_quit(self) -> None:
        self.force_exit = True
        self.close_window()
        if self.owns_controller:
            app = self.application_provider()
            if app is not None:
                app.quit()

    def restore_quit_on_last_window_closed(self) -> None:
        app = self.application_provider()
        if app is not None and self.previous_quit_on_last_window_closed is not None:
            app.setQuitOnLastWindowClosed(self.previous_quit_on_last_window_closed)
            self.previous_quit_on_last_window_closed = None

    def _build_menu(self) -> QMenu:
        menu = QMenu(self.parent)
        show_panel_action = QAction("显示控制面板", self.parent)
        show_panel_action.triggered.connect(self.show_control_panel)
        show_pet_action = QAction("显示/进入桌宠模式", self.parent)
        show_pet_action.triggered.connect(self.show_desktop_pet)
        hide_action = QAction("隐藏到托盘", self.parent)
        hide_action.triggered.connect(self.hide_to_tray)
        exit_action = QAction("退出", self.parent)
        exit_action.triggered.connect(self.request_quit)
        menu.addAction(show_panel_action)
        menu.addAction(show_pet_action)
        menu.addAction(hide_action)
        menu.addSeparator()
        menu.addAction(exit_action)
        return menu
