"""Small reusable UI building blocks: cards, section headers, color picker."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Card(QFrame):
    """A rounded panel with an optional title + hint, then arbitrary content."""

    def __init__(self, title: str = "", hint: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(18, 16, 18, 16)
        self._outer.setSpacing(10)

        if title:
            lbl = QLabel(title)
            lbl.setObjectName("CardTitle")
            self._outer.addWidget(lbl)
        if hint:
            h = QLabel(hint)
            h.setObjectName("CardHint")
            h.setWordWrap(True)
            self._outer.addWidget(h)

    def body(self) -> QVBoxLayout:
        return self._outer

    def add(self, widget) -> None:
        self._outer.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._outer.addLayout(layout)


class PageHeader(QWidget):
    """Big title + subtitle for the top of a page."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        lay.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("PageSub")
            s.setWordWrap(True)
            lay.addWidget(s)


class ColorButton(QPushButton):
    """A swatch button that opens a color picker; emits ``colorChanged``."""

    colorChanged = pyqtSignal(tuple)

    def __init__(self, color: tuple[int, int, int] = (255, 255, 255), parent=None):
        super().__init__(parent)
        self._color = tuple(color)
        self.setFixedSize(46, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._pick)
        self._refresh()

    def color(self) -> tuple[int, int, int]:
        return self._color

    def set_color(self, color: tuple[int, int, int]) -> None:
        self._color = tuple(int(x) for x in color)
        self._refresh()

    def _refresh(self) -> None:
        r, g, b = self._color
        border = "#ffffff" if (r + g + b) < 200 else "#00000044"
        self.setStyleSheet(
            f"background: rgb({r},{g},{b}); border: 1px solid {border}; border-radius: 7px;"
        )

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(*self._color), self, "Choose channel color")
        if c.isValid():
            self.set_color((c.red(), c.green(), c.blue()))
            self.colorChanged.emit(self._color)


def hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #2c3140; max-height: 1px;")
    return line


def row(*widgets, stretch_last: bool = False, spacing: int = 8) -> QHBoxLayout:
    """Compose a horizontal layout from widgets/(widget, stretch) tuples."""
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    for w in widgets:
        if isinstance(w, tuple):
            lay.addWidget(w[0], w[1])
        elif isinstance(w, int):
            lay.addSpacing(w)
        else:
            lay.addWidget(w)
    if stretch_last:
        lay.addStretch(1)
    return lay
