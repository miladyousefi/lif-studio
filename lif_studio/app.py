"""Application bootstrap."""

from __future__ import annotations

import sys


def run() -> int:
    from PyQt6.QtWidgets import QApplication

    from .config import AppConfig
    from .ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("LIF Studio")
    window = MainWindow(AppConfig.load())
    window.show()
    return app.exec()
