"""Analysis page: configurable quantitative analysis of raw LIF channels.

Layout:
  • Source card        — choose the LIF
  • Parameters card    — every hyperparameter, each with a tooltip guide
  • Run / Cancel / CSV / Method & formulas
  • Output tabs        — Results · By type · Charts · Histogram
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..analysis import aggregate, compare_groups, group_rows, numeric_columns
from ..config import (
    AppConfig,
    BG_GAUSSIAN,
    BG_MEDIAN,
    BG_NONE,
    BG_ROLLING,
    THRESH_MANUAL,
    THRESH_MEAN_STD,
    THRESH_OTSU,
    THRESH_PERCENTILE,
    Z_FIRST,
    Z_MAX,
    Z_MEAN,
)
from ..docs import ANALYSIS_MD
from .charts import BarChart, BoxPlot, ScatterPlot
from .histogram import HistogramWidget
from .widgets import Card, PageHeader, row
from .workers import AnalysisWorker


class AnalysisPage(QWidget):
    config_changed = pyqtSignal()

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.acfg = cfg.analysis
        self.lif_path: Optional[Path] = None
        self._result = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[AnalysisWorker] = None
        self._loading = False
        self._build()
        self._sync_from_config()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)
        root.addWidget(
            PageHeader(
                "Analysis",
                "Quantify raw LIF channels — intensity, % area, objects, colocalization. "
                "Hover any parameter for guidance, or open Method & formulas.",
            )
        )

        # ---- source ----
        src = Card("LIF file")
        self.file_label = QLabel("No file selected")
        self.file_label.setObjectName("Hint")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        src.add_layout(row((self.file_label, 1), browse))
        root.addWidget(src)

        # ---- parameters ----
        params = Card("Parameters", "Hover each field for a short guide.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        r = 0

        self.z_combo = QComboBox()
        for label, data in [("Max", Z_MAX), ("Mean", Z_MEAN), ("First", Z_FIRST)]:
            self.z_combo.addItem(f"{label} projection", data)
        self.z_combo.setToolTip(
            "How to collapse a Z-stack:\n"
            "• Max — brightest value (best for puncta; matches LAS X max projection)\n"
            "• Mean — average (reduces noise for diffuse signal)\n"
            "• First — only the first slice")
        grid.addWidget(self._lbl("Z-stack", self.z_combo.toolTip()), r, 0)
        grid.addWidget(self.z_combo, r, 1)

        self.thr_combo = QComboBox()
        for label, data in [
            ("Otsu (auto)", THRESH_OTSU), ("Manual", THRESH_MANUAL),
            ("Percentile", THRESH_PERCENTILE), ("Mean + k·std", THRESH_MEAN_STD),
        ]:
            self.thr_combo.addItem(label, data)
        self.thr_combo.setToolTip(
            "Threshold separating signal from background. Feeds % area, object\n"
            "count and Manders coloc.\n"
            "• Otsu — automatic, good for clear bright objects\n"
            "• Manual — fixed value (use to keep a batch comparable)\n"
            "• Percentile — keep the top (100−p)% brightest pixels\n"
            "• Mean+k·std — threshold at mean + k·std")
        self.thr_combo.currentIndexChanged.connect(self._on_thr_method)
        grid.addWidget(self._lbl("Threshold method", self.thr_combo.toolTip()), r, 2)
        grid.addWidget(self.thr_combo, r, 3)
        r += 1

        self.manual_spin = QDoubleSpinBox()
        self.manual_spin.setRange(0, 65535)
        self.manual_spin.setDecimals(1)
        self.manual_spin.setToolTip("Absolute intensity threshold (used when method = Manual).")
        grid.addWidget(self._lbl("Manual threshold", self.manual_spin.toolTip()), r, 0)
        grid.addWidget(self.manual_spin, r, 1)

        self.pct_spin = QDoubleSpinBox()
        self.pct_spin.setRange(0, 100)
        self.pct_spin.setSuffix(" %")
        self.pct_spin.setToolTip("Percentile p (used when method = Percentile). Threshold = the p-th percentile of pixel intensities.")
        grid.addWidget(self._lbl("Percentile", self.pct_spin.toolTip()), r, 2)
        grid.addWidget(self.pct_spin, r, 3)
        r += 1

        self.k_spin = QDoubleSpinBox()
        self.k_spin.setRange(0, 10)
        self.k_spin.setSingleStep(0.5)
        self.k_spin.setToolTip("k (used when method = Mean + k·std). Threshold = mean + k·std.")
        grid.addWidget(self._lbl("Std multiplier (k)", self.k_spin.toolTip()), r, 0)
        grid.addWidget(self.k_spin, r, 1)

        self.minsize_spin = QSpinBox()
        self.minsize_spin.setRange(0, 1000000)
        self.minsize_spin.setSuffix(" px")
        self.minsize_spin.setToolTip("Objects smaller than this (in pixels) are discarded when counting. Raise it to reject noise specks.")
        grid.addWidget(self._lbl("Min object size", self.minsize_spin.toolTip()), r, 2)
        grid.addWidget(self.minsize_spin, r, 3)
        r += 1

        self.bg_method = QComboBox()
        for label, data in [
            ("None", BG_NONE), ("Gaussian", BG_GAUSSIAN),
            ("Rolling-ball", BG_ROLLING), ("Median", BG_MEDIAN),
        ]:
            self.bg_method.addItem(label, data)
        self.bg_method.setToolTip(
            "Subtract a slowly-varying background before measuring.\n"
            "• Gaussian — remove smooth shading (σ = size)\n"
            "• Rolling-ball — remove uneven illumination (radius = size)\n"
            "• Median — robust to bright outliers (window = size)")
        self.bg_method.currentIndexChanged.connect(self._on_field_changed)
        grid.addWidget(self._lbl("Background method", self.bg_method.toolTip()), r, 0)
        grid.addWidget(self.bg_method, r, 1)

        self.bg_spin = QDoubleSpinBox()
        self.bg_spin.setRange(0, 500)
        self.bg_spin.setSingleStep(1.0)
        self.bg_spin.setToolTip("Background size: σ for Gaussian, radius/window for rolling-ball/median. Pick a few × your object size. 0 = off.")
        grid.addWidget(self._lbl("Background size", self.bg_spin.toolTip()), r, 2)
        grid.addWidget(self.bg_spin, r, 3)
        r += 1

        self.coloc_a = QSpinBox()
        self.coloc_a.setRange(0, 31)
        self.coloc_a.setToolTip("First channel for colocalization (A).")
        self.coloc_b = QSpinBox()
        self.coloc_b.setRange(0, 31)
        self.coloc_b.setToolTip("Second channel for colocalization (B).")
        ab = QWidget()
        ab_l = QHBoxLayout(ab)
        ab_l.setContentsMargins(0, 0, 0, 0)
        ab_l.addWidget(self.coloc_a)
        ab_l.addWidget(self.coloc_b)
        grid.addWidget(self._lbl("Coloc channels A / B", "Channel pair used for Pearson / Manders / overlap."), r, 0)
        grid.addWidget(ab, r, 1)
        params.add_layout(grid)

        self.cb_intensity = QCheckBox("Intensity stats")
        self.cb_intensity.setToolTip("Mean, median, std, integrated density, p95, CV, skew, kurtosis.")
        self.cb_area = QCheckBox("% positive area")
        self.cb_area.setToolTip("Fraction of pixels above the threshold.")
        self.cb_objects = QCheckBox("Object count")
        self.cb_objects.setToolTip("Connected components above the threshold, min-size filtered.")
        self.cb_coloc = QCheckBox("Colocalization")
        self.cb_coloc.setToolTip("Pearson r, Manders M1/M2, overlap coefficient for channels A/B.")
        params.add_layout(
            row(self.cb_intensity, self.cb_area, self.cb_objects, self.cb_coloc, stretch_last=True)
        )
        root.addWidget(params)

        for w in (self.z_combo, self.thr_combo, self.bg_method):
            w.currentIndexChanged.connect(self._on_field_changed)
        for w in (self.manual_spin, self.pct_spin, self.k_spin, self.bg_spin):
            w.valueChanged.connect(self._on_field_changed)
        for w in (self.minsize_spin, self.coloc_a, self.coloc_b):
            w.valueChanged.connect(self._on_field_changed)
        for w in (self.cb_intensity, self.cb_area, self.cb_objects, self.cb_coloc):
            w.toggled.connect(self._on_field_changed)

        # ---- run row ----
        self.run_btn = QPushButton("Run Analysis")
        self.run_btn.setObjectName("Primary")
        self.run_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("Danger")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel)
        self.csv_btn = QPushButton("Export CSV…")
        self.csv_btn.setEnabled(False)
        self.csv_btn.clicked.connect(self._export_csv)
        self.docs_btn = QPushButton("Method && formulas")
        self.docs_btn.clicked.connect(self._show_docs)
        root.addLayout(
            row(self.run_btn, self.cancel_btn, self.csv_btn, self.docs_btn, stretch_last=True)
        )

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        # ---- output tabs ----
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_results_tab(), "Results")
        self.tabs.addTab(self._build_bytype_tab(), "By type")
        self.tabs.addTab(self._build_charts_tab(), "Charts")
        self.tabs.addTab(self._build_histogram_tab(), "Histogram")
        root.addWidget(self.tabs, 1)

        # ---- log ----
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("Analysis log…")
        self.console.setMinimumHeight(80)
        self.console.setMaximumHeight(130)
        root.addWidget(self.console)

    def _lbl(self, text: str, tip: str = "") -> QLabel:
        lbl = QLabel(text)
        if tip:
            lbl.setToolTip(tip)
        return lbl

    # ---- tab builders ----
    def _build_results_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        self.table = QTableWidget(0, 0)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(240)
        self.table.currentCellChanged.connect(self._on_row_changed)
        lay.addWidget(self.table)
        return w

    def _build_bytype_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(8)
        self.bytype_metric = QComboBox()
        self.bytype_metric.currentIndexChanged.connect(self._update_bytype)
        lay.addLayout(row(QLabel("Metric:"), (self.bytype_metric, 0), stretch_last=True))
        self.bytype_table = QTableWidget(0, 0)
        self.bytype_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bytype_table.setMaximumHeight(170)
        lay.addWidget(self.bytype_table)
        self.compare_label = QLabel("")
        self.compare_label.setObjectName("Hint")
        self.compare_label.setWordWrap(True)
        lay.addWidget(self.compare_label)
        self.bar_chart = BarChart(self.cfg.theme)
        lay.addWidget(self.bar_chart, 1)
        return w

    def _build_charts_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(8)
        self.box_metric = QComboBox()
        self.box_metric.currentIndexChanged.connect(self._update_charts)
        lay.addLayout(row(QLabel("Distribution metric:"), (self.box_metric, 0), stretch_last=True))
        self.box_plot = BoxPlot(self.cfg.theme)
        lay.addWidget(self.box_plot, 1)
        self.scatter_x = QComboBox()
        self.scatter_y = QComboBox()
        self.scatter_x.currentIndexChanged.connect(self._update_charts)
        self.scatter_y.currentIndexChanged.connect(self._update_charts)
        lay.addLayout(row(QLabel("Scatter  X:"), (self.scatter_x, 0),
                          QLabel("Y:"), (self.scatter_y, 0), stretch_last=True))
        self.scatter = ScatterPlot(self.cfg.theme)
        lay.addWidget(self.scatter, 1)
        return w

    def _build_histogram_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(8)
        hint = QLabel("Select a row in the Results tab, then a channel here.")
        hint.setObjectName("Hint")
        lay.addWidget(hint)
        self.hist_channel = QComboBox()
        self.hist_channel.currentIndexChanged.connect(self._update_histogram)
        lay.addLayout(row(QLabel("Channel:"), (self.hist_channel, 0), stretch_last=True))
        self.histogram = HistogramWidget(self.cfg.theme)
        lay.addWidget(self.histogram, 1)
        return w

    # --------------------------------------------------------------- config
    def _sync_from_config(self) -> None:
        self._loading = True
        a = self.acfg
        self.z_combo.setCurrentIndex(max(0, self.z_combo.findData(a.z_projection)))
        self.thr_combo.setCurrentIndex(max(0, self.thr_combo.findData(a.threshold_method)))
        self.manual_spin.setValue(a.manual_threshold)
        self.pct_spin.setValue(a.percentile)
        self.k_spin.setValue(a.std_k)
        self.minsize_spin.setValue(a.min_object_size)
        self.bg_method.setCurrentIndex(max(0, self.bg_method.findData(a.background_method)))
        self.bg_spin.setValue(a.background_sigma)
        self.coloc_a.setValue(a.coloc_channel_a)
        self.coloc_b.setValue(a.coloc_channel_b)
        self.cb_intensity.setChecked(a.do_intensity)
        self.cb_area.setChecked(a.do_area)
        self.cb_objects.setChecked(a.do_objects)
        self.cb_coloc.setChecked(a.do_coloc)
        self._loading = False
        self._update_param_enabled()

    def _on_thr_method(self, _i: int) -> None:
        self._update_param_enabled()

    def _update_param_enabled(self) -> None:
        m = self.thr_combo.currentData()
        self.manual_spin.setEnabled(m == THRESH_MANUAL)
        self.pct_spin.setEnabled(m == THRESH_PERCENTILE)
        self.k_spin.setEnabled(m == THRESH_MEAN_STD)
        self.bg_spin.setEnabled(self.bg_method.currentData() != BG_NONE)

    def _on_field_changed(self, *_a) -> None:
        if self._loading:
            return
        a = self.acfg
        a.z_projection = self.z_combo.currentData()
        a.threshold_method = self.thr_combo.currentData()
        a.manual_threshold = self.manual_spin.value()
        a.percentile = self.pct_spin.value()
        a.std_k = self.k_spin.value()
        a.min_object_size = self.minsize_spin.value()
        a.background_method = self.bg_method.currentData()
        a.background_sigma = self.bg_spin.value()
        a.coloc_channel_a = self.coloc_a.value()
        a.coloc_channel_b = self.coloc_b.value()
        a.do_intensity = self.cb_intensity.isChecked()
        a.do_area = self.cb_area.isChecked()
        a.do_objects = self.cb_objects.isChecked()
        a.do_coloc = self.cb_coloc.isChecked()
        self._update_param_enabled()
        self.config_changed.emit()

    # ----------------------------------------------------------- file/share
    def set_lif(self, path) -> None:
        if path:
            self.lif_path = Path(path)
            self.file_label.setText(self.lif_path.name)

    def _browse(self) -> None:
        start = str(self.lif_path.parent) if self.lif_path else str(Path.cwd())
        path, _ = QFileDialog.getOpenFileName(
            self, "Open LIF file", start, "LIF files (*.lif);;All files (*)"
        )
        if path:
            self.set_lif(path)

    # ------------------------------------------------------------- running
    def _start(self) -> None:
        if not self.lif_path or not self.lif_path.exists():
            QMessageBox.warning(self, "No file", "Choose a .lif file to analyze first.")
            return
        self.console.clear()
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.run_btn.setEnabled(False)
        self.csv_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)

        self._thread = QThread()
        self._worker = AnalysisWorker(self.lif_path, self.acfg)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self.console.appendPlainText)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _on_progress(self, done: int, total: int) -> None:
        if self.progress.maximum() == 0 and total:
            self.progress.setRange(0, total)
        self.progress.setValue(done)

    def _teardown(self) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        self.run_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.progress.setVisible(False)

    def _cancel(self) -> None:
        if self._worker:
            self._worker.cancel()

    def _on_failed(self, msg: str) -> None:
        self._teardown()
        QMessageBox.critical(self, "Analysis failed", msg)

    def _on_finished(self, result) -> None:
        self._teardown()
        self._result = result
        self._fill_table(result)
        self._populate_metric_combos()
        self.csv_btn.setEnabled(bool(result.rows))

    # -------------------------------------------------------------- helpers
    def _type_of(self, image_name: str) -> str:
        t = self.cfg.match_type(image_name)
        return t.name if t else "Other"

    def _populate_metric_combos(self) -> None:
        self._loading = True
        metrics = numeric_columns(self._result.rows) if self._result else []
        for combo in (self.bytype_metric, self.box_metric, self.scatter_x, self.scatter_y):
            combo.clear()
            combo.addItems(metrics)
        # sensible scatter defaults: first two channel means if present
        if metrics:
            for i, name in enumerate(("ch0_mean", "ch1_mean")):
                idx = self.scatter_x.findText(name) if i == 0 else self.scatter_y.findText(name)
                if idx >= 0:
                    (self.scatter_x if i == 0 else self.scatter_y).setCurrentIndex(idx)
        self._loading = False
        self._update_bytype()
        self._update_charts()

    # -------------------------------------------------------------- results
    def _fill_table(self, result) -> None:
        cols = result.columns
        self.table.clear()
        self.table.setColumnCount(len(cols))
        self.table.setRowCount(len(result.rows))
        self.table.setHorizontalHeaderLabels([c.replace("_", " ") for c in cols])
        for ri, rowd in enumerate(result.rows):
            for ci, key in enumerate(cols):
                v = rowd.get(key, "")
                if isinstance(v, float):
                    v = f"{v:.3f}"
                self.table.setItem(ri, ci, QTableWidgetItem(str(v)))
        self.table.resizeColumnsToContents()
        if result.rows:
            self.table.selectRow(0)

    # --------------------------------------------------------------- by type
    def _update_bytype(self, *_a) -> None:
        if self._loading or not self._result or not self._result.rows:
            return
        metric = self.bytype_metric.currentText()
        if not metric:
            return
        groups = group_rows(self._result.rows, lambda r: self._type_of(r["image"]))
        names = list(groups.keys())
        cols = ["type", "n", "mean", "std", "sem", "median"]
        self.bytype_table.setColumnCount(len(cols))
        self.bytype_table.setHorizontalHeaderLabels(cols)
        self.bytype_table.setRowCount(len(names))
        bar_cats, bar_vals, bar_errs = [], [], []
        for ri, name in enumerate(names):
            agg = aggregate(groups[name], metric)
            vals = [name, agg["n"], agg["mean"], agg["std"], agg["sem"], agg["median"]]
            for ci, v in enumerate(vals):
                txt = f"{v:.3f}" if isinstance(v, float) else str(v)
                self.bytype_table.setItem(ri, ci, QTableWidgetItem(txt))
            bar_cats.append(f"{name} (n={agg['n']})")
            bar_vals.append(agg["mean"])
            bar_errs.append(agg["sem"])
        self.bytype_table.resizeColumnsToContents()
        self.bar_chart.set_data(bar_cats, bar_vals, bar_errs, title=f"{metric}  (mean ± SEM)")

        # compare the two largest groups
        ordered = sorted(names, key=lambda n: len(groups[n]), reverse=True)
        if len(ordered) >= 2:
            a, b = ordered[0], ordered[1]
            cmp = compare_groups(groups[a], groups[b], metric)
            if "welch_p" in cmp:
                import math

                def fmt_p(x):
                    return "n/a" if (x is None or math.isnan(x)) else f"{x:.4g}"

                wt = cmp["welch_t"]
                wt_s = "n/a" if math.isnan(wt) else f"{wt:.3f}"
                self.compare_label.setText(
                    f"{a} (n={cmp['n_a']}) vs {b} (n={cmp['n_b']}) — "
                    f"Welch t={wt_s}, p={fmt_p(cmp['welch_p'])}   |   "
                    f"Mann–Whitney U={cmp['mannwhitney_u']:.0f}, p={fmt_p(cmp['mannwhitney_p'])}"
                )
            else:
                self.compare_label.setText(f"{a} vs {b}: need ≥2 values per group for a test.")
        else:
            self.compare_label.setText("Need ≥2 types present to compare.")

    # --------------------------------------------------------------- charts
    def _update_charts(self, *_a) -> None:
        if self._loading or not self._result or not self._result.rows:
            return
        groups = group_rows(self._result.rows, lambda r: self._type_of(r["image"]))
        # box plot
        bm = self.box_metric.currentText()
        if bm:
            data = {
                name: [r[bm] for r in rows if isinstance(r.get(bm), (int, float))]
                for name, rows in groups.items()
            }
            self.box_plot.set_data(data, title=f"{bm} by type")
        # scatter
        xm, ym = self.scatter_x.currentText(), self.scatter_y.currentText()
        if xm and ym:
            series = {}
            for name, rows in groups.items():
                xs = [r[xm] for r in rows if isinstance(r.get(xm), (int, float))
                      and isinstance(r.get(ym), (int, float))]
                ys = [r[ym] for r in rows if isinstance(r.get(xm), (int, float))
                      and isinstance(r.get(ym), (int, float))]
                if xs:
                    series[name] = (xs, ys)
            self.scatter.set_data(series, xlabel=xm, ylabel=ym, title=f"{ym} vs {xm}")

    # ------------------------------------------------------------ histogram
    def _on_row_changed(self, cur_row: int, *_a) -> None:
        if not self._result or cur_row < 0 or cur_row >= len(self._result.histograms):
            return
        hist = self._result.histograms[cur_row]
        self._loading = True
        self.hist_channel.clear()
        for ci in sorted(hist.keys()):
            self.hist_channel.addItem(f"Channel {ci}", ci)
        self._loading = False
        self._update_histogram()

    def _update_histogram(self, *_a) -> None:
        if self._loading or not self._result:
            return
        cur = self.table.currentRow()
        ci = self.hist_channel.currentData()
        if cur < 0 or ci is None or cur >= len(self._result.histograms):
            return
        h = self._result.histograms[cur].get(ci)
        if not h:
            return
        colors = [(40, 180, 99), (59, 108, 240), (224, 72, 61)]
        self.histogram.set_data(
            h["counts"], h["edges"], threshold=h.get("threshold"),
            color=colors[ci % len(colors)],
            title=f"{self._result.rows[cur]['image']} — channel {ci}",
        )

    # ---------------------------------------------------------------- misc
    def _export_csv(self) -> None:
        if not self._result or not self._result.rows:
            return
        default = str((self.lif_path.parent if self.lif_path else Path.cwd())
                      / f"{self.lif_path.stem if self.lif_path else 'analysis'}_analysis.csv")
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", default, "CSV files (*.csv)")
        if not path:
            return
        try:
            import csv

            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=self._result.columns)
                w.writeheader()
                for r in self._result.rows:
                    w.writerow({k: r.get(k, "") for k in self._result.columns})
            QMessageBox.information(self, "Saved", f"Wrote {len(self._result.rows)} rows to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "CSV export failed", str(e))

    def _show_docs(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Analysis — Method & formulas")
        dlg.resize(760, 640)
        lay = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(ANALYSIS_MD)
        lay.addWidget(browser)
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        lay.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dlg.exec()

    def apply_theme(self, theme: str) -> None:
        for chart in (self.histogram, self.bar_chart, self.box_plot, self.scatter):
            chart.set_theme(theme)
