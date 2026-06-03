"""Application bootstrap."""

from __future__ import annotations

import sys


def run() -> int:
    from PyQt6.QtCore import QLocale
    from PyQt6.QtWidgets import QApplication

    from .config import AppConfig
    from .ui.main_window import MainWindow

    # Force Western (Latin) digits in every spin box / number field. On Windows
    # with a Persian/Arabic system locale, Qt would otherwise render values as
    # ۰۱۲۳ — set the default locale to English (US) *before* any widget exists
    # so all of them inherit it. Use C-style numbers (no thousands separator).
    en = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
    en.setNumberOptions(QLocale.NumberOption.OmitGroupSeparator)
    QLocale.setDefault(en)

    app = QApplication(sys.argv)
    app.setApplicationName("LIF Studio")
    window = MainWindow(AppConfig.load())
    window.show()
    return app.exec()
