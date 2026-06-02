"""Types & Colors editor.

Left: the list of image types (add / remove / enable).
Right: the selected type's keywords, output folder, and a dynamic table of
channels — each channel maps a source index to an RGB color with a min/max
intensity window. This is where all the per-type configurability lives.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig, ChannelConfig, ImageTypeConfig, NAMED_COLORS
from .widgets import Card, ColorButton, PageHeader, hline, row


class TypesPage(QWidget):
    config_changed = pyqtSignal()

    # table columns
    COL_ON, COL_IDX, COL_NAME, COL_COLOR, COL_MIN, COL_MAX = range(6)

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._current: ImageTypeConfig | None = None
        self._loading = False
        self._build()
        self._reload_list()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)
        root.addWidget(
            PageHeader(
                "Types & Colors",
                "Define each image type, the keyword that identifies it, and how "
                "its channels are colored. Settings are saved automatically.",
            )
        )

        split = QHBoxLayout()
        split.setSpacing(16)
        root.addLayout(split, 1)

        # ---- left: type list ----
        left = Card("Image types")
        self.type_list = QListWidget()
        self.type_list.currentRowChanged.connect(self._on_select)
        left.add(self.type_list)
        add_btn = QPushButton("＋ Add type")
        add_btn.clicked.connect(self._add_type)
        self.del_btn = QPushButton("Remove")
        self.del_btn.setObjectName("Danger")
        self.del_btn.clicked.connect(self._remove_type)
        left.add_layout(row(add_btn, self.del_btn))
        left.setMaximumWidth(280)
        split.addWidget(left)

        # ---- right: detail editor ----
        self.detail = Card("Type settings")
        self.enabled_cb = QCheckBox("Enabled (include this type when exporting)")
        self.enabled_cb.toggled.connect(self._on_field_changed)
        self.detail.add(self.enabled_cb)

        self.name_edit = QLineEdit()
        self.name_edit.textEdited.connect(self._on_field_changed)
        self.detail.add(QLabel("Name"))
        self.detail.add(self.name_edit)

        self.kw_edit = QLineEdit()
        self.kw_edit.setPlaceholderText("Comma-separated, e.g. AQP4   or   C5-9, C5_9")
        self.kw_edit.textEdited.connect(self._on_field_changed)
        self.detail.add(QLabel("Keywords (matched in the image name)"))
        self.detail.add(self.kw_edit)

        self.subdir_edit = QLineEdit()
        self.subdir_edit.setPlaceholderText("Output subfolder (defaults to the type name)")
        self.subdir_edit.textEdited.connect(self._on_field_changed)
        self.detail.add(QLabel("Output subfolder"))
        self.detail.add(self.subdir_edit)

        self.detail.add(hline())
        self.detail.add(QLabel("Channels → colors"))
        hint = QLabel(
            "Each row tints one source channel. Channels add together "
            "(green + blue → cyan). Min/Max set the brightness window (0–255)."
        )
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        self.detail.add(hint)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["On", "Source ch", "Label", "Color", "Min", "Max"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        for col in (self.COL_ON, self.COL_IDX, self.COL_COLOR, self.COL_MIN, self.COL_MAX):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.detail.add(self.table)

        add_ch = QPushButton("＋ Add channel")
        add_ch.clicked.connect(self._add_channel)
        self.del_ch = QPushButton("Remove last channel")
        self.del_ch.clicked.connect(self._remove_channel)
        self.detail.add_layout(row(add_ch, self.del_ch, stretch_last=True))

        split.addWidget(self.detail, 1)

    # ------------------------------------------------------------- list ops
    def _reload_list(self, select_row: int = 0) -> None:
        self._loading = True
        self.type_list.clear()
        for t in self.cfg.types:
            item = QListWidgetItem(("● " if t.enabled else "○ ") + t.name)
            self.type_list.addItem(item)
        self._loading = False
        if self.cfg.types:
            self.type_list.setCurrentRow(min(select_row, len(self.cfg.types) - 1))
        else:
            self._current = None
            self._set_detail_enabled(False)

    def _on_select(self, rowidx: int) -> None:
        if self._loading or rowidx < 0 or rowidx >= len(self.cfg.types):
            return
        self._current = self.cfg.types[rowidx]
        self._load_detail()

    def _add_type(self) -> None:
        n = len(self.cfg.types) + 1
        self.cfg.types.append(
            ImageTypeConfig(name=f"Type {n}", keywords=[], output_subdir=f"Type{n}")
        )
        self._reload_list(select_row=len(self.cfg.types) - 1)
        self._emit_changed()

    def _remove_type(self) -> None:
        rowidx = self.type_list.currentRow()
        if rowidx < 0 or rowidx >= len(self.cfg.types):
            return
        name = self.cfg.types[rowidx].name
        if (
            QMessageBox.question(self, "Remove type", f"Remove '{name}'?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        del self.cfg.types[rowidx]
        self._reload_list(select_row=max(0, rowidx - 1))
        self._emit_changed()

    # ----------------------------------------------------------- detail ops
    def _set_detail_enabled(self, on: bool) -> None:
        self.detail.setEnabled(on)

    def _load_detail(self) -> None:
        t = self._current
        if t is None:
            self._set_detail_enabled(False)
            return
        self._set_detail_enabled(True)
        self._loading = True
        self.enabled_cb.setChecked(t.enabled)
        self.name_edit.setText(t.name)
        self.kw_edit.setText(", ".join(t.keywords))
        self.subdir_edit.setText(t.output_subdir)
        self._rebuild_table()
        self._loading = False

    def _on_field_changed(self, *_a) -> None:
        if self._loading or self._current is None:
            return
        t = self._current
        t.enabled = self.enabled_cb.isChecked()
        t.name = self.name_edit.text().strip() or t.name
        t.keywords = [k.strip() for k in self.kw_edit.text().split(",") if k.strip()]
        t.output_subdir = self.subdir_edit.text().strip()
        # keep the list label in sync without losing selection
        item = self.type_list.currentItem()
        if item:
            item.setText(("● " if t.enabled else "○ ") + t.name)
        self._emit_changed()

    # -------------------------------------------------------- channel table
    def _rebuild_table(self) -> None:
        t = self._current
        self.table.setRowCount(0)
        if t is None:
            return
        for ch in t.channels:
            self._append_channel_row(ch)

    def _append_channel_row(self, ch: ChannelConfig) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)

        on = QCheckBox()
        on.setChecked(ch.enabled)
        on.toggled.connect(lambda v, c=ch: self._set_ch(c, "enabled", v))
        self._center(self.table, r, self.COL_ON, on)

        idx = QSpinBox()
        idx.setRange(0, 31)
        idx.setValue(ch.index)
        idx.valueChanged.connect(lambda v, c=ch: self._set_ch(c, "index", v))
        self.table.setCellWidget(r, self.COL_IDX, idx)

        name = QLineEdit(ch.name)
        name.setPlaceholderText(f"Channel {ch.index}")
        name.textEdited.connect(lambda v, c=ch: self._set_ch(c, "name", v))
        self.table.setCellWidget(r, self.COL_NAME, name)

        color = ColorButton(ch.color)
        color.colorChanged.connect(lambda v, c=ch: self._set_ch(c, "color", v))
        self._center(self.table, r, self.COL_COLOR, color)

        cmin = QSpinBox()
        cmin.setRange(0, 255)
        cmin.setValue(ch.min_intensity)
        cmin.valueChanged.connect(lambda v, c=ch: self._set_ch(c, "min_intensity", v))
        self.table.setCellWidget(r, self.COL_MIN, cmin)

        cmax = QSpinBox()
        cmax.setRange(0, 255)
        cmax.setValue(ch.max_intensity)
        cmax.valueChanged.connect(lambda v, c=ch: self._set_ch(c, "max_intensity", v))
        self.table.setCellWidget(r, self.COL_MAX, cmax)

    @staticmethod
    def _center(table: QTableWidget, r: int, c: int, w: QWidget) -> None:
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(w)
        table.setCellWidget(r, c, wrap)

    def _set_ch(self, ch: ChannelConfig, attr: str, value) -> None:
        if self._loading:
            return
        setattr(ch, attr, value)
        self._emit_changed()

    def _add_channel(self) -> None:
        if self._current is None:
            return
        next_idx = len(self._current.channels)
        palette = list(NAMED_COLORS.values())
        ch = ChannelConfig(
            index=next_idx,
            name=f"Channel {next_idx}",
            color=palette[next_idx % len(palette)],
        )
        self._current.channels.append(ch)
        self._append_channel_row(ch)
        self._emit_changed()

    def _remove_channel(self) -> None:
        if self._current is None or not self._current.channels:
            return
        self._current.channels.pop()
        self.table.removeRow(self.table.rowCount() - 1)
        self._emit_changed()

    # ------------------------------------------------------------- signals
    def _emit_changed(self) -> None:
        self.config_changed.emit()
