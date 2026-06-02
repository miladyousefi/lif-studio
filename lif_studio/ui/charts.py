"""Lightweight charts drawn with QPainter (no matplotlib dependency).

Provides three widgets used by the Analysis page:
  • BarChart    — one bar per category, optional error bars (mean ± SEM)
  • ScatterPlot — x/y points, optionally colored by group
  • BoxPlot     — box-and-whisker per group (quartiles + whiskers + outliers)
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from .style import palette

# A pleasant categorical palette (reused across charts).
SERIES_COLORS = [
    (59, 108, 240), (40, 180, 99), (224, 72, 61), (155, 89, 217),
    (240, 160, 40), (0, 178, 178), (220, 80, 160), (120, 120, 120),
]


class _ChartBase(QWidget):
    def __init__(self, theme: str = "light", parent=None):
        super().__init__(parent)
        self._theme = theme
        self.setMinimumHeight(240)
        self._title = ""

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self.update()

    # shared helpers -----------------------------------------------------
    def _begin(self, p: QPainter):
        c = palette(self._theme)
        p.fillRect(self.rect(), QColor(c["input"]))
        return c

    def _empty(self, p: QPainter, c: dict, msg="No data"):
        p.setPen(QColor(c["text_dim"]))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)
        p.end()

    @staticmethod
    def _nice_plot_rect(w, h, left=54, right=14, top=26, bottom=46) -> QRectF:
        return QRectF(left, top, max(10, w - left - right), max(10, h - top - bottom))

    def _draw_axes(self, p, c, plot, ymin, ymax, ylabel=""):
        p.setPen(QPen(QColor(c["border_strong"]), 1))
        p.drawLine(int(plot.left()), int(plot.top()), int(plot.left()), int(plot.bottom()))
        p.drawLine(int(plot.left()), int(plot.bottom()), int(plot.right()), int(plot.bottom()))
        # y ticks
        p.setPen(QColor(c["text_dim"]))
        for i in range(5):
            frac = i / 4
            yv = ymin + (ymax - ymin) * frac
            y = plot.bottom() - frac * plot.height()
            p.setPen(QPen(QColor(c["border"]), 1, Qt.PenStyle.DotLine))
            p.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
            p.setPen(QColor(c["text_dim"]))
            p.drawText(QRectF(0, y - 8, plot.left() - 6, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, _fmt(yv))
        if self._title:
            p.setPen(QColor(c["text"]))
            p.drawText(QRectF(0, 4, self.width(), 18), Qt.AlignmentFlag.AlignCenter, self._title)


def _fmt(v: float) -> str:
    av = abs(v)
    if av != 0 and (av < 0.01 or av >= 1e5):
        return f"{v:.1e}"
    if av >= 100:
        return f"{v:.0f}"
    return f"{v:.2f}"


class BarChart(_ChartBase):
    def __init__(self, theme="light", parent=None):
        super().__init__(theme, parent)
        self._cats: list[str] = []
        self._vals: list[float] = []
        self._errs: list[float] = []

    def set_data(self, categories, values, errors=None, title=""):
        self._cats = list(categories)
        self._vals = [float(v) for v in values]
        self._errs = [float(e) for e in (errors or [0] * len(self._vals))]
        self._title = title
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        c = self._begin(p)
        if not self._vals:
            return self._empty(p, c)
        plot = self._nice_plot_rect(self.width(), self.height())
        top_val = max((v + e) for v, e in zip(self._vals, self._errs)) or 1.0
        ymax = top_val * 1.15
        self._draw_axes(p, c, plot, 0.0, ymax)

        n = len(self._vals)
        slot = plot.width() / n
        bw = slot * 0.55
        fm = QFontMetrics(p.font())
        for i, (cat, val, err) in enumerate(zip(self._cats, self._vals, self._errs)):
            x = plot.left() + slot * i + (slot - bw) / 2
            bh = (val / ymax) * plot.height()
            color = SERIES_COLORS[i % len(SERIES_COLORS)]
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(*color))
            p.drawRoundedRect(QRectF(x, plot.bottom() - bh, bw, bh), 3, 3)
            # error bar
            if err > 0:
                ex = x + bw / 2
                y0 = plot.bottom() - ((val + err) / ymax) * plot.height()
                y1 = plot.bottom() - ((val - err) / ymax) * plot.height()
                p.setPen(QPen(QColor(c["text"]), 1.4))
                p.drawLine(int(ex), int(y0), int(ex), int(y1))
                p.drawLine(int(ex - 4), int(y0), int(ex + 4), int(y0))
                p.drawLine(int(ex - 4), int(y1), int(ex + 4), int(y1))
            # category label (elided)
            p.setPen(QColor(c["text_dim"]))
            label = fm.elidedText(str(cat), Qt.TextElideMode.ElideRight, int(slot))
            p.drawText(QRectF(plot.left() + slot * i, plot.bottom() + 4, slot, 18),
                       Qt.AlignmentFlag.AlignCenter, label)
        p.end()


class ScatterPlot(_ChartBase):
    def __init__(self, theme="light", parent=None):
        super().__init__(theme, parent)
        self._series: dict[str, tuple] = {}  # name -> (x_array, y_array)
        self._xlabel = self._ylabel = ""

    def set_data(self, series: dict, xlabel="", ylabel="", title=""):
        self._series = {k: (np.asarray(v[0], float), np.asarray(v[1], float))
                        for k, v in series.items() if len(v[0])}
        self._xlabel, self._ylabel, self._title = xlabel, ylabel, title
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        c = self._begin(p)
        if not self._series:
            return self._empty(p, c)
        allx = np.concatenate([s[0] for s in self._series.values()])
        ally = np.concatenate([s[1] for s in self._series.values()])
        xmin, xmax = float(allx.min()), float(allx.max())
        ymin, ymax = float(ally.min()), float(ally.max())
        if xmax <= xmin:
            xmax = xmin + 1
        if ymax <= ymin:
            ymax = ymin + 1
        plot = self._nice_plot_rect(self.width(), self.height())
        self._draw_axes(p, c, plot, ymin, ymax)

        def px(x): return plot.left() + (x - xmin) / (xmax - xmin) * plot.width()
        def py(y): return plot.bottom() - (y - ymin) / (ymax - ymin) * plot.height()

        for i, (name, (xs, ys)) in enumerate(self._series.items()):
            color = QColor(*SERIES_COLORS[i % len(SERIES_COLORS)])
            color.setAlpha(190)
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            for x, y in zip(xs, ys):
                p.drawEllipse(QPointF(px(x), py(y)), 3.2, 3.2)
        # axis titles + legend
        p.setPen(QColor(c["text_dim"]))
        p.drawText(QRectF(plot.left(), plot.bottom() + 22, plot.width(), 16),
                   Qt.AlignmentFlag.AlignCenter, self._xlabel)
        self._legend(p, c, plot)
        p.end()

    def _legend(self, p, c, plot):
        x = plot.right() - 130
        y = plot.top() + 6
        for i, name in enumerate(self._series):
            p.setBrush(QColor(*SERIES_COLORS[i % len(SERIES_COLORS)]))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(x, y + i * 16 + 5), 4, 4)
            p.setPen(QColor(c["text_dim"]))
            p.drawText(QRectF(x + 10, y + i * 16, 120, 14), Qt.AlignmentFlag.AlignLeft, str(name))


class BoxPlot(_ChartBase):
    def __init__(self, theme="light", parent=None):
        super().__init__(theme, parent)
        self._groups: dict[str, np.ndarray] = {}

    def set_data(self, groups: dict, title=""):
        self._groups = {k: np.asarray(v, float) for k, v in groups.items() if len(v)}
        self._title = title
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        c = self._begin(p)
        if not self._groups:
            return self._empty(p, c)
        allv = np.concatenate(list(self._groups.values()))
        ymin, ymax = float(allv.min()), float(allv.max())
        if ymax <= ymin:
            ymax = ymin + 1
        pad = (ymax - ymin) * 0.08
        ymin -= pad
        ymax += pad
        plot = self._nice_plot_rect(self.width(), self.height())
        self._draw_axes(p, c, plot, ymin, ymax)

        def py(y): return plot.bottom() - (y - ymin) / (ymax - ymin) * plot.height()
        n = len(self._groups)
        slot = plot.width() / n
        bw = slot * 0.5
        fm = QFontMetrics(p.font())
        for i, (name, v) in enumerate(self._groups.items()):
            q1, med, q3 = np.percentile(v, [25, 50, 75])
            iqr = q3 - q1
            lo = max(float(v.min()), q1 - 1.5 * iqr)
            hi = min(float(v.max()), q3 + 1.5 * iqr)
            cx = plot.left() + slot * i + slot / 2
            color = QColor(*SERIES_COLORS[i % len(SERIES_COLORS)])
            # whiskers
            p.setPen(QPen(QColor(c["text_dim"]), 1.3))
            p.drawLine(int(cx), int(py(lo)), int(cx), int(py(hi)))
            p.drawLine(int(cx - bw / 4), int(py(lo)), int(cx + bw / 4), int(py(lo)))
            p.drawLine(int(cx - bw / 4), int(py(hi)), int(cx + bw / 4), int(py(hi)))
            # box
            box = QRectF(cx - bw / 2, py(q3), bw, py(q1) - py(q3))
            fill = QColor(color)
            fill.setAlpha(70)
            p.setBrush(fill)
            p.setPen(QPen(color, 1.6))
            p.drawRect(box)
            # median
            p.setPen(QPen(color, 2))
            p.drawLine(int(cx - bw / 2), int(py(med)), int(cx + bw / 2), int(py(med)))
            # label
            p.setPen(QColor(c["text_dim"]))
            label = fm.elidedText(str(name), Qt.TextElideMode.ElideRight, int(slot))
            p.drawText(QRectF(plot.left() + slot * i, plot.bottom() + 4, slot, 18),
                       Qt.AlignmentFlag.AlignCenter, label)
        p.end()
