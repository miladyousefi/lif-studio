"""Viewer page: open a folder and navigate it as a tree; view TIFFs with zoom."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from PyQt6.QtCore import Qt, QDir, QModelIndex
from PyQt6.QtGui import QFileSystemModel, QImage, QPixmap
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from .widgets import Card, PageHeader, row


class ImageCanvas(QScrollArea):
    """Scrollable image area with mouse-wheel and button zoom."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._label = QLabel("Open a folder, then click an image")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("background:#0c0d12; color:#5b6675;")
        self.setWidget(self._label)
        self.setWidgetResizable(True)
        self._pixmap: QPixmap | None = None
        self._zoom = 1.0

    def load(self, path: Path) -> bool:
        try:
            img = Image.open(path).convert("RGB")
        except Exception as e:
            self._label.setText(f"Could not open image:\n{e}")
            self._pixmap = None
            return False
        arr = np.ascontiguousarray(np.array(img))
        h, w = arr.shape[:2]
        qimg = QImage(arr.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        self._pixmap = QPixmap.fromImage(qimg)
        self._zoom = 1.0
        self._render()
        return True

    def _render(self) -> None:
        if self._pixmap is None:
            return
        scaled = self._pixmap.scaledToWidth(
            max(1, int(self._pixmap.width() * self._zoom)),
            Qt.TransformationMode.SmoothTransformation,
        )
        self._label.setPixmap(scaled)
        self._label.resize(scaled.size())

    def zoom_in(self):
        self._zoom = min(10.0, self._zoom * 1.2)
        self._render()

    def zoom_out(self):
        self._zoom = max(0.1, self._zoom / 1.2)
        self._render()

    def fit(self):
        if self._pixmap and self._pixmap.width():
            self._zoom = self.viewport().width() / self._pixmap.width()
            self._render()

    def wheelEvent(self, event):
        self.zoom_in() if event.angleDelta().y() > 0 else self.zoom_out()
        event.accept()


class ViewerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)
        root.addWidget(
            PageHeader("Viewer", "Open a folder and browse it as a tree — expand folders, click a TIFF.")
        )

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, 1)

        # ---- left: folder tree ----
        left = Card("Folders")
        self.path_label = QLabel("No folder open")
        self.path_label.setObjectName("Hint")
        self.path_label.setWordWrap(True)
        left.add(self.path_label)

        self.model = QFileSystemModel()
        self.model.setNameFilters(["*.tif", "*.tiff", "*.png", "*.jpg", "*.jpeg"])
        self.model.setNameFilterDisables(False)  # hide non-matching files (keep folders)
        self.model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(False)
        for col in (1, 2, 3):           # hide size/type/date columns, keep Name
            self.tree.hideColumn(col)
        self.tree.setMinimumWidth(280)
        self.tree.clicked.connect(self._on_tree_clicked)
        self.tree.doubleClicked.connect(self._on_tree_clicked)
        left.add(self.tree)

        open_btn = QPushButton("Open folder…")
        open_btn.clicked.connect(self.open_folder)
        left.add(open_btn)
        left.setMaximumWidth(340)
        body.addWidget(left)

        # ---- right: image + zoom controls ----
        right = QVBoxLayout()
        right.setSpacing(10)
        self.canvas = ImageCanvas()
        right.addWidget(self.canvas, 1)
        zin, zout, fit, full = (QPushButton(t) for t in ("＋ Zoom", "－ Zoom", "Fit", "Fullscreen"))
        zin.clicked.connect(self.canvas.zoom_in)
        zout.clicked.connect(self.canvas.zoom_out)
        fit.clicked.connect(self.canvas.fit)
        full.clicked.connect(self._fullscreen)
        self.current_label = QLabel("")
        self.current_label.setObjectName("Hint")
        right.addLayout(row(zin, zout, fit, full, (self.current_label, 1)))
        body.addLayout(right, 1)

    def open_folder(self, folder: str | None = None) -> None:
        if not folder:
            folder = QFileDialog.getExistingDirectory(self, "Select image folder")
        if not folder:
            return
        self.path_label.setText(folder)
        self.model.setRootPath(folder)
        self.tree.setRootIndex(self.model.index(folder))
        self.tree.expandToDepth(0)

    def _on_tree_clicked(self, index: QModelIndex) -> None:
        path = Path(self.model.filePath(index))
        if path.is_file():
            if self.canvas.load(path):
                self.current_label.setText(path.name)

    def _fullscreen(self) -> None:
        if self.canvas.isFullScreen():
            self.canvas.showNormal()
        else:
            self.canvas.setWindowFlag(Qt.WindowType.Window, True)
            self.canvas.showFullScreen()
