from __future__ import annotations

"""Standalone launcher for E-Moti Plugin Center."""

import sys


def main(argv: list[str] | None = None) -> int:
    try:
        from PySide6.QtWidgets import QApplication, QMainWindow
    except ImportError as exc:
        raise RuntimeError("PySide6 is required to launch Plugin Center") from exc
    from .plugin_center_qt import create_plugin_center_widget
    from .plugin_enabled_controller import PluginEnabledCompanionController

    args = sys.argv if argv is None else argv
    app = QApplication.instance() or QApplication(args)
    controller = PluginEnabledCompanionController()
    window = QMainWindow()
    window.setWindowTitle("E-Moti 插件中心")
    window.resize(980, 680)
    window.setCentralWidget(create_plugin_center_widget(controller))
    window.show()
    exit_code = app.exec()
    controller.close()
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
