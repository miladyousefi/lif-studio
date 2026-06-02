"""QThread worker that runs the (pure) exporter off the UI thread."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from ..analysis import AnalysisResult, analyze_lif
from ..config import AnalysisConfig, AppConfig
from ..exporter import ExportResult, export_lif


class ExportWorker(QObject):
    progress = pyqtSignal(int, int)   # done, total
    log = pyqtSignal(str)
    finished = pyqtSignal(object)     # ExportResult
    failed = pyqtSignal(str)

    def __init__(self, lif_path: Path, cfg: AppConfig, custom_dir: Optional[str] = None):
        super().__init__()
        self.lif_path = lif_path
        self.cfg = cfg
        self.custom_dir = custom_dir
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            result: ExportResult = export_lif(
                self.lif_path,
                self.cfg,
                custom_dir=self.custom_dir,
                progress_cb=lambda d, t: self.progress.emit(d, t),
                log_cb=lambda m: self.log.emit(m),
                cancel_cb=lambda: self._cancel,
            )
            self.finished.emit(result)
        except Exception as e:  # surface engine-level failures to the UI
            self.failed.emit(str(e))


class AnalysisWorker(QObject):
    progress = pyqtSignal(int, int)
    log = pyqtSignal(str)
    finished = pyqtSignal(object)   # AnalysisResult
    failed = pyqtSignal(str)

    def __init__(self, lif_path: Path, acfg: AnalysisConfig):
        super().__init__()
        self.lif_path = lif_path
        self.acfg = acfg
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            result: AnalysisResult = analyze_lif(
                self.lif_path,
                self.acfg,
                progress_cb=lambda d, t: self.progress.emit(d, t),
                log_cb=lambda m: self.log.emit(m),
                cancel_cb=lambda: self._cancel,
            )
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))
