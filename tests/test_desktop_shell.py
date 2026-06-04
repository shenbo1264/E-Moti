def test_desktop_shell_clamps_and_docks_window_inside_available_geometry():
    from PySide6.QtCore import QPoint, QRect, QSize

    from guanghe_companion.desktop_shell import DesktopShell

    class FakeWindow:
        def __init__(self):
            self._pos = QPoint(40, 50)
            self._size = QSize(120, 100)
            self.moves = []

        def pos(self):
            return QPoint(self._pos)

        def size(self):
            return QSize(self._size)

        def width(self):
            return self._size.width()

        def height(self):
            return self._size.height()

        def move(self, target):
            self._pos = QPoint(target)
            self.moves.append(QPoint(target))

    window = FakeWindow()
    shell = DesktopShell(
        window=window,
        available_geometry_provider=lambda: QRect(0, 0, 300, 260),
        dock_threshold_px=32,
    )

    assert shell.clamp_position(QPoint(10_000, -20)) == QPoint(180, 0)
    assert shell.dock_position(QPoint(24, 100)) == QPoint(0, 100)
    assert shell.dock_position(QPoint(170, 100)) == QPoint(180, 100)

    shell.move_by(QPoint(500, 500), enabled=True)

    assert window.moves[-1] == QPoint(180, 160)


def test_desktop_shell_ignores_drag_move_when_disabled():
    from PySide6.QtCore import QPoint, QRect, QSize

    from guanghe_companion.desktop_shell import DesktopShell

    class FakeWindow:
        def __init__(self):
            self._pos = QPoint(40, 50)
            self._size = QSize(120, 100)
            self.moves = []

        def pos(self):
            return QPoint(self._pos)

        def size(self):
            return QSize(self._size)

        def width(self):
            return self._size.width()

        def height(self):
            return self._size.height()

        def move(self, target):
            self.moves.append(QPoint(target))

    window = FakeWindow()
    shell = DesktopShell(window=window, available_geometry_provider=lambda: QRect(0, 0, 300, 260))

    shell.move_by(QPoint(500, 500), enabled=False)

    assert window.moves == []
