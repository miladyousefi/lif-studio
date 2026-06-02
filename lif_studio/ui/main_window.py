"""Main window: sidebar navigation + stacked pages, shared AppConfig."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig
from .analysis_page import AnalysisPage
from .export_page import ExportPage
from .style import stylesheet
from .types_page import TypesPage
from .viewer_page import ViewerPage


class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig | None = None):
        super().__init__()
        self.cfg = cfg or AppConfig.load()
        self.setWindowTitle("LIF Studio")
        self.setMinimumSize(1040, 680)
        self.resize(1180, 780)

        # debounce config writes so rapid edits don't hammer the disk
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._persist)

        self._build()
        self._apply_theme()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.export_page = ExportPage(self.cfg)
        self.types_page = TypesPage(self.cfg)
        self.viewer_page = ViewerPage()
        self.analysis_page = AnalysisPage(self.cfg)
        # Scroll-wrap the form-heavy pages so content never collapses/overlaps.
        self.stack.addWidget(self._scrollable(self.export_page))
        self.stack.addWidget(self._scrollable(self.types_page))
        self.stack.addWidget(self.viewer_page)   # has its own image scroll area
        self.stack.addWidget(self._scrollable(self.analysis_page))
        layout.addWidget(self.stack, 1)

        # keep config saved + summaries fresh
        self.export_page.config_changed.connect(self._schedule_save)
        self.types_page.config_changed.connect(self._on_types_changed)
        self.analysis_page.config_changed.connect(self._schedule_save)
        # picking a LIF on Export shares it with Analysis (no need to pick twice)
        self.export_page.lif_selected.connect(self.analysis_page.set_lif)

        self.statusBar().showMessage("Ready")

    @staticmethod
    def _scrollable(page: QWidget) -> QScrollArea:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setWidget(page)
        return sa

    def _build_sidebar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(216)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 12)
        lay.setSpacing(0)

        brand = QLabel("LIF Studio")
        brand.setObjectName("Brand")
        sub = QLabel("Leica → colored TIFF")
        sub.setObjectName("BrandSub")
        lay.addWidget(brand)
        lay.addWidget(sub)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        # "&&" so Qt shows a literal ampersand instead of a mnemonic underline.
        for i, label in enumerate(
            ["Export", "Types && Colors", "Viewer", "Analysis"]
        ):
            btn = QPushButton(label)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _c, idx=i: self._go(idx))
            self._nav_group.addButton(btn, i)
            lay.addWidget(btn)
        self._nav_group.button(0).setChecked(True)

        lay.addStretch(1)
        self.theme_btn = QPushButton("  Toggle theme")
        self.theme_btn.setObjectName("NavButton")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(self._toggle_theme)
        lay.addWidget(self.theme_btn)
        return bar

    # --------------------------------------------------------------- nav
    def _go(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        if idx == 0:  # refresh the type summary whenever Export is shown
            self.export_page.refresh_summary()

    # ------------------------------------------------------------- config
    def _on_types_changed(self) -> None:
        self.export_page.refresh_summary()
        self._schedule_save()

    def _schedule_save(self) -> None:
        self.statusBar().showMessage("Saving…")
        self._save_timer.start()

    def _persist(self) -> None:
        try:
            self.cfg.save()
            self.statusBar().showMessage("Settings saved", 1500)
        except Exception as e:
            self.statusBar().showMessage(f"Could not save settings: {e}", 4000)

    # -------------------------------------------------------------- theme
    def _apply_theme(self) -> None:
        self.setStyleSheet(stylesheet(self.cfg.theme))

    def _toggle_theme(self) -> None:
        self.cfg.theme = "light" if self.cfg.theme == "dark" else "dark"
        self._apply_theme()
        self.analysis_page.apply_theme(self.cfg.theme)
        self._schedule_save()

    def closeEvent(self, event):
        self._persist()  # flush any pending edits on exit
        super().closeEvent(event)
