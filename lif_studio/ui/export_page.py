"""Export page: pick a LIF, choose where to save, run, watch progress."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ..config import (
    AppConfig,
    SAVE_CUSTOM,
    SAVE_LIBRARY,
    SAVE_NEXT_TO_LIF,
    Z_FIRST,
    Z_MAX,
    Z_MEAN,
)
from ..exporter import ExportResult, resolve_output_root
from .widgets import Card, PageHeader, row
from .workers import ExportWorker


class ExportPage(QWidget):
    config_changed = pyqtSignal()   # ask the app to persist config
    lif_selected = pyqtSignal(object)   # Path — share the chosen LIF with other pages

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.lif_path: Optional[Path] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[ExportWorker] = None
        self._build()
        self._sync_from_config()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        root.addWidget(
            PageHeader("Export", "Convert LIF image series into colored TIFF overlays.")
        )

        # --- source card ---
        src = Card("Source file", "Choose the Leica .lif file to convert.")
        self.file_label = QLabel("No file selected")
        self.file_label.setObjectName("Hint")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_lif)
        src.add_layout(row((self.file_label, 1), browse))
        root.addWidget(src)

        # --- destination card ---
        dest = Card(
            "Save location",
            "Where exports land. By default they're stored next to the .lif "
            "file, organised as <Project>/<type>/. You can override per export.",
        )
        self.rb_next = QRadioButton("Next to the .lif file  (recommended)")
        self.rb_lib = QRadioButton("Fixed library folder")
        self.rb_custom = QRadioButton("Custom folder (choose each export)")
        self._dest_group = QButtonGroup(self)
        for i, rb in enumerate((self.rb_next, self.rb_lib, self.rb_custom)):
            self._dest_group.addButton(rb, i)
            dest.add(rb)
        self._dest_group.idToggled.connect(self._on_dest_toggle)

        self.lib_edit = QLineEdit()
        self.lib_edit.setPlaceholderText("Library base folder, e.g. ~/LIF_Exports")
        self.lib_edit.textChanged.connect(self._on_lib_changed)
        lib_browse = QPushButton("…")
        lib_browse.setFixedWidth(40)
        lib_browse.clicked.connect(self._browse_lib)
        dest.add_layout(row((self.lib_edit, 1), lib_browse))

        self.dest_preview = QLabel("")
        self.dest_preview.setObjectName("Hint")
        self.dest_preview.setWordWrap(True)
        dest.add(self.dest_preview)
        root.addWidget(dest)

        # --- options card ---
        opts = Card("Options")
        self.z_combo = QComboBox()
        self.z_combo.addItem("Max projection", Z_MAX)
        self.z_combo.addItem("Mean projection", Z_MEAN)
        self.z_combo.addItem("First slice", Z_FIRST)
        self.z_combo.currentIndexChanged.connect(self._on_z_changed)
        opts.add_layout(row(QLabel("Z-stack handling:"), (self.z_combo, 0), stretch_last=True))

        self.lif_colors_cb = QCheckBox(
            "Match LAS X — use each channel's stored LUT color + range from the LIF"
        )
        self.lif_colors_cb.setToolTip(
            "On: reproduce the LAS X overlay exactly (recommended).\n"
            "Off: use the colors you set per type in Types & Colors."
        )
        self.lif_colors_cb.toggled.connect(self._on_lif_colors_toggled)
        opts.add(self.lif_colors_cb)

        self.types_summary = QLabel("")
        self.types_summary.setObjectName("Hint")
        self.types_summary.setWordWrap(True)
        opts.add(self.types_summary)
        root.addWidget(opts)

        # --- run (compact, left-aligned — not a full-width banner) ---
        self.run_btn = QPushButton("Start Export")
        self.run_btn.setObjectName("Primary")
        self.run_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("Danger")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel)
        root.addLayout(row(self.run_btn, self.cancel_btn, stretch_last=True))

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        log_label = QLabel("Export log")
        log_label.setObjectName("Hint")
        root.addWidget(log_label)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("Export log will appear here…")
        self.console.setMinimumHeight(150)
        root.addWidget(self.console, 1)

    # ---------------------------------------------------------------- state
    def _sync_from_config(self) -> None:
        mode = self.cfg.save_mode
        self.rb_next.setChecked(mode == SAVE_NEXT_TO_LIF)
        self.rb_lib.setChecked(mode == SAVE_LIBRARY)
        self.rb_custom.setChecked(mode == SAVE_CUSTOM)
        self.lib_edit.setText(self.cfg.library_dir)
        self.lib_edit.setEnabled(mode == SAVE_LIBRARY)
        idx = self.z_combo.findData(self.cfg.z_projection)
        if idx >= 0:
            self.z_combo.setCurrentIndex(idx)
        self.lif_colors_cb.setChecked(self.cfg.use_lif_colors)
        self.refresh_summary()
        self._update_preview()

    def refresh_summary(self) -> None:
        """Re-describe the configured types (called when the editor changes)."""
        parts = []
        for t in self.cfg.types:
            if not t.enabled:
                continue
            chans = ", ".join(
                f"ch{c.index}" for c in t.channels if c.enabled
            ) or "no channels"
            kws = "/".join(t.keywords) or "—"
            parts.append(f"• {t.name}  [{kws}] → {chans} → {t.subdir}/")
        extra = ""
        if self.cfg.export_unmatched:
            extra = f"\n• Unmatched images → {self.cfg.unmatched_subdir}/"
        color_src = (
            "Colors: from the LIF's channel LUTs (matches LAS X)."
            if self.cfg.use_lif_colors
            else "Colors: per-type, as configured in Types & Colors."
        )
        self.types_summary.setText(
            color_src
            + "\n\nActive types:\n"
            + ("\n".join(parts) if parts else "  (none)")
            + extra
        )

    def _update_preview(self) -> None:
        if self.lif_path:
            root = resolve_output_root(self.lif_path, self.cfg)
            self.dest_preview.setText(f"→ {root}{Path('/')}<type>/")
        else:
            self.dest_preview.setText("Select a .lif file to preview the output path.")

    # ------------------------------------------------------------- handlers
    def _browse_lif(self) -> None:
        start = str(self.lif_path.parent) if self.lif_path else str(Path.cwd())
        path, _ = QFileDialog.getOpenFileName(
            self, "Open LIF file", start, "LIF files (*.lif);;All files (*)"
        )
        if path:
            self.lif_path = Path(path)
            self.file_label.setText(self.lif_path.name)
            self.file_label.setObjectName("")  # de-dim
            self._update_preview()
            self.lif_selected.emit(self.lif_path)

    def _on_dest_toggle(self, _id: int, checked: bool) -> None:
        if not checked:
            return
        if self.rb_next.isChecked():
            self.cfg.save_mode = SAVE_NEXT_TO_LIF
        elif self.rb_lib.isChecked():
            self.cfg.save_mode = SAVE_LIBRARY
        else:
            self.cfg.save_mode = SAVE_CUSTOM
        self.lib_edit.setEnabled(self.cfg.save_mode == SAVE_LIBRARY)
        self._update_preview()
        self.config_changed.emit()

    def _on_lib_changed(self, text: str) -> None:
        self.cfg.library_dir = text
        self._update_preview()
        self.config_changed.emit()

    def _browse_lib(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose library folder")
        if folder:
            self.lib_edit.setText(folder)

    def _on_z_changed(self, _idx: int) -> None:
        self.cfg.z_projection = self.z_combo.currentData()
        self.config_changed.emit()

    def _on_lif_colors_toggled(self, on: bool) -> None:
        self.cfg.use_lif_colors = on
        self.refresh_summary()
        self.config_changed.emit()

    # ------------------------------------------------------------- exporting
    def _start(self) -> None:
        if not self.lif_path:
            QMessageBox.warning(self, "No file", "Please choose a .lif file first.")
            return
        if not self.lif_path.exists():
            QMessageBox.critical(self, "Missing", f"File not found:\n{self.lif_path}")
            return

        custom_dir = None
        if self.cfg.save_mode == SAVE_CUSTOM:
            custom_dir = QFileDialog.getExistingDirectory(
                self, "Choose where to save this export"
            )
            if not custom_dir:
                return  # user backed out of the post-pick prompt
        elif self.cfg.save_mode == SAVE_LIBRARY and not self.cfg.library_dir.strip():
            QMessageBox.warning(
                self, "No library folder", "Set a library folder or pick another mode."
            )
            return

        self.console.clear()
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # busy until first progress tick
        self.run_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)

        self._thread = QThread()
        self._worker = ExportWorker(self.lif_path, self.cfg, custom_dir)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._on_log)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _on_progress(self, done: int, total: int) -> None:
        if self.progress.maximum() == 0 and total:
            self.progress.setRange(0, total)
        self.progress.setValue(done)

    def _on_log(self, line: str) -> None:
        self.console.appendPlainText(line)

    def _teardown_thread(self) -> None:
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
            self._on_log("Cancelling…")

    def _on_failed(self, msg: str) -> None:
        self._teardown_thread()
        QMessageBox.critical(self, "Export failed", msg)

    def _on_finished(self, result: ExportResult) -> None:
        self._teardown_thread()
        self._post_export_dialog(result)

    def _post_export_dialog(self, result: ExportResult) -> None:
        """Confirm where images were saved and offer to open/relocate them."""
        by_type = "\n".join(f"   • {k}: {v}" for k, v in result.per_type.items())
        text = (
            f"Exported {result.exported} image(s)"
            f"{(' by type:' + chr(10) + by_type) if by_type else ''}\n"
            f"Skipped: {result.skipped}    Errors: {result.errors}\n\n"
            f"Saved to:\n{result.output_root}"
        )
        box = QMessageBox(self)
        box.setWindowTitle("Export complete")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(text)
        open_btn = box.addButton("Open folder", QMessageBox.ButtonRole.AcceptRole)
        move_btn = box.addButton("Save copy elsewhere…", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Done", QMessageBox.ButtonRole.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked is open_btn and result.output_root:
            self._open_in_file_manager(result.output_root)
        elif clicked is move_btn:
            self._copy_export_elsewhere(result)

    def _copy_export_elsewhere(self, result: ExportResult) -> None:
        import shutil

        dest = QFileDialog.getExistingDirectory(self, "Choose a folder to copy into")
        if not dest or not result.output_root:
            return
        target = Path(dest) / result.output_root.name
        try:
            shutil.copytree(result.output_root, target, dirs_exist_ok=True)
            QMessageBox.information(self, "Copied", f"Copied to:\n{target}")
            self._open_in_file_manager(target)
        except Exception as e:
            QMessageBox.critical(self, "Copy failed", str(e))

    @staticmethod
    def _open_in_file_manager(path: Path) -> None:
        import subprocess
        import sys

        try:
            if sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["explorer", str(path)])
        except Exception:
            pass
