class FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in tuple(self._callbacks):
            callback(*args)


class FakeSystemTrayIcon:
    class ActivationReason:
        Trigger = object()
        DoubleClick = object()

    class MessageIcon:
        Information = object()

    available = True
    instances = []

    def __init__(self, icon=None, parent=None):
        self.icon = icon
        self.parent = parent
        self.context_menu = None
        self.tool_tip = ""
        self.visible = False
        self.messages = []
        self.activated = FakeSignal()
        self.__class__.instances.append(self)

    @classmethod
    def isSystemTrayAvailable(cls):
        return cls.available

    def setToolTip(self, text):
        self.tool_tip = text

    def setContextMenu(self, menu):
        self.context_menu = menu

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def showMessage(self, title, message, icon=None, msecs=0):
        self.messages.append((title, message, icon, msecs))


class FakeApplication:
    def __init__(self):
        self.quit_on_last_window_closed = True
        self.set_values = []
        self.quit_calls = 0

    def quitOnLastWindowClosed(self):
        return self.quit_on_last_window_closed

    def setQuitOnLastWindowClosed(self, value):
        self.set_values.append(value)
        self.quit_on_last_window_closed = value

    def quit(self):
        self.quit_calls += 1


def test_tray_controller_sets_up_menu_hides_restores_and_quits(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QWidget

    from guanghe_companion.tray_controller import TrayController

    app = QApplication.instance() or QApplication([])
    fake_app = FakeApplication()
    parent = QWidget()
    calls = []
    FakeSystemTrayIcon.instances = []
    FakeSystemTrayIcon.available = True
    controller = TrayController(
        parent=parent,
        tray_icon_class=FakeSystemTrayIcon,
        icon_provider=QIcon,
        show_control_panel=lambda: calls.append("show-panel"),
        show_desktop_pet=lambda: calls.append("show-pet"),
        hide_window=lambda: calls.append("hide-window"),
        close_window=lambda: calls.append("close-window"),
        application_provider=lambda: fake_app,
    )

    controller.setup(owns_controller=True)

    tray_icon = FakeSystemTrayIcon.instances[-1]
    assert tray_icon.visible is True
    assert tray_icon.tool_tip == "星汐 E-Moti"
    assert fake_app.set_values == [False]
    labels_to_actions = {
        action.text(): action
        for action in tray_icon.context_menu.actions()
        if not action.isSeparator()
    }
    assert set(labels_to_actions) == {"显示控制面板", "显示/进入桌宠模式", "隐藏到托盘", "退出"}

    tray_icon.activated.emit(FakeSystemTrayIcon.ActivationReason.Trigger)
    labels_to_actions["显示/进入桌宠模式"].trigger()
    labels_to_actions["隐藏到托盘"].trigger()
    labels_to_actions["隐藏到托盘"].trigger()

    assert calls == ["show-panel", "show-pet", "hide-window", "hide-window"]
    assert len(tray_icon.messages) == 1
    assert controller.should_hide_to_tray() is True

    labels_to_actions["退出"].trigger()

    assert controller.should_hide_to_tray() is False
    assert calls[-1] == "close-window"
    assert fake_app.quit_calls == 1
    assert tray_icon.visible is True

    controller.cleanup()
    controller.restore_quit_on_last_window_closed()

    assert tray_icon.visible is False
    assert fake_app.set_values == [False, True]
    parent.close()
    app.processEvents()


def test_tray_controller_skips_setup_when_child_window_or_tray_unavailable(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QWidget

    from guanghe_companion.tray_controller import TrayController

    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    FakeSystemTrayIcon.instances = []
    FakeSystemTrayIcon.available = True
    controller = TrayController(
        parent=parent,
        tray_icon_class=FakeSystemTrayIcon,
        icon_provider=QIcon,
        show_control_panel=lambda: None,
        show_desktop_pet=lambda: None,
        hide_window=lambda: None,
        close_window=lambda: None,
    )

    controller.setup(owns_controller=False)
    assert FakeSystemTrayIcon.instances == []

    FakeSystemTrayIcon.available = False
    controller.setup(owns_controller=True)
    assert FakeSystemTrayIcon.instances == []
    parent.close()
    app.processEvents()
