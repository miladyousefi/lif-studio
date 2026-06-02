"""A lightweight intensity-histogram widget drawn with QPainter (no matplotlib)."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from .style import palette


class HistogramWidget(QWidget):
    """Draws a bar histogram with an optional threshold marker line."""

    def __init__(self, theme: str = "light", parent=None):
        super().__init__(parent)
        self.setMinimumHeight(170)
        self._counts = np.array([])
        self._edges = np.array([])
        self._threshold: float | None = None
        self._bar_color = (59, 108, 240)
        self._title = ""
        self._theme = theme

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self.update()

    def set_data(self, counts, edges, threshold=None, color=(59, 108, 240), title=""):
        self._counts = np.asarray(counts, dtype=np.float64)
        self._edges = np.asarray(edges, dtype=np.float64)
        self._threshold = threshold
        self._bar_color = color
        self._title = title
        self.update()

    def clear(self) -> None:
        self._counts = np.array([])
        self.update()

    def paintEvent(self, _event):
        c = palette(self._theme)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()

        # background
        p.fillRect(self.rect(), QColor(c["input"]))
        pad_l, pad_r, pad_t, pad_b = 8, 8, 22 if self._title else 8, 18
        plot = QRectF(pad_l, pad_t, w - pad_l - pad_r, h - pad_t - pad_b)

        if self._title:
            p.setPen(QColor(c["text_dim"]))
            p.drawText(QRectF(pad_l, 2, w - 16, 18),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._title)

        if self._counts.size == 0 or self._edges.size < 2:
            p.setPen(QColor(c["text_dim"]))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No histogram")
            p.end()
            return

        # log-ish scaling keeps tall background peaks from flattening signal
        counts = np.log1p(self._counts)
        cmax = counts.max() or 1.0
        n = counts.size
        bw = plot.width() / n

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(*self._bar_color))
        for i, v in enumerate(counts):
            bh = (v / cmax) * plot.height()
            p.drawRect(QRectF(plot.left() + i * bw, plot.bottom() - bh, max(1.0, bw), bh))

        # axis baseline
        p.setPen(QPen(QColor(c["border_strong"]), 1))
        p.drawLine(int(plot.left()), int(plot.bottom()), int(plot.right()), int(plot.bottom()))

        # threshold marker
        if self._threshold is not None:
            lo, hi = float(self._edges[0]), float(self._edges[-1])
            if hi > lo:
                x = plot.left() + (self._threshold - lo) / (hi - lo) * plot.width()
                x = min(max(plot.left(), x), plot.right())
                p.setPen(QPen(QColor(c["danger"]), 1, Qt.PenStyle.DashLine))
                p.drawLine(int(x), int(plot.top()), int(x), int(plot.bottom()))
                p.setPen(QColor(c["danger"]))
                p.drawText(QRectF(x + 3, plot.top(), 90, 14),
                           Qt.AlignmentFlag.AlignLeft, f"thr {self._threshold:.0f}")

        # x range labels
        p.setPen(QColor(c["text_dim"]))
        p.drawText(QRectF(plot.left(), plot.bottom() + 2, 80, 14),
                   Qt.AlignmentFlag.AlignLeft, f"{self._edges[0]:.0f}")
        p.drawText(QRectF(plot.right() - 80, plot.bottom() + 2, 80, 14),
                   Qt.AlignmentFlag.AlignRight, f"{self._edges[-1]:.0f}")
        p.end()
