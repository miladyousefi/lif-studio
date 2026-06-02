"""Modern flat theme (light default + dark) as a single Qt stylesheet.

Colors live in one palette dict so the whole look can be retuned in one place.
``stylesheet(theme)`` returns the QSS string for the chosen theme.
"""

from __future__ import annotations

LIGHT = {
    "bg": "#f3f5f8",
    "surface": "#ffffff",
    "surface_alt": "#eef1f6",
    "card": "#ffffff",
    "border": "#e3e7ee",
    "border_strong": "#d3d9e2",
    "text": "#1b2230",
    "text_dim": "#6b7686",
    "accent": "#3b6cf0",
    "accent_hi": "#5482f5",
    "accent_press": "#2f57cc",
    "accent_soft": "#eaf0fe",
    "success": "#1f9d63",
    "danger": "#e0483d",
    "input": "#ffffff",
}

DARK = {
    "bg": "#13151b",
    "surface": "#1a1d25",
    "surface_alt": "#222632",
    "card": "#1a1d25",
    "border": "#2a2f3c",
    "border_strong": "#363c4b",
    "text": "#e7e9ef",
    "text_dim": "#98a1b2",
    "accent": "#5b8cff",
    "accent_hi": "#7aa2ff",
    "accent_press": "#456fe0",
    "accent_soft": "#23304d",
    "success": "#3ecf8e",
    "danger": "#ff6b6b",
    "input": "#11131a",
}


def palette(theme: str) -> dict:
    return DARK if theme == "dark" else LIGHT


def stylesheet(theme: str = "light") -> str:
    c = palette(theme)
    return f"""
    * {{
        font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
        font-size: 13px;
        color: {c['text']};
    }}
    QMainWindow, QWidget#Root {{ background: {c['bg']}; }}
    QScrollArea, QAbstractScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}

    /* ---- Sidebar ---- */
    QWidget#Sidebar {{ background: {c['surface']}; border-right: 1px solid {c['border']}; }}
    QLabel#Brand {{ font-size: 17px; font-weight: 700; padding: 22px 20px 2px 20px; }}
    QLabel#BrandSub {{ color: {c['text_dim']}; font-size: 11px; padding: 0 20px 16px 20px; }}
    QPushButton#NavButton {{
        text-align: left; padding: 10px 14px; margin: 2px 12px; border: none;
        border-radius: 9px;
        background: transparent; color: {c['text_dim']}; font-size: 13px; font-weight: 600;
    }}
    QPushButton#NavButton:hover {{ background: {c['surface_alt']}; color: {c['text']}; }}
    QPushButton#NavButton:checked {{ background: {c['accent_soft']}; color: {c['accent']}; }}

    /* ---- Cards ---- */
    QFrame#Card {{
        background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px;
    }}
    QLabel#CardTitle {{ font-size: 14px; font-weight: 700; }}
    QLabel#CardHint, QLabel#Hint {{ color: {c['text_dim']}; font-size: 12px; }}
    QLabel#PageTitle {{ font-size: 21px; font-weight: 700; }}
    QLabel#PageSub {{ color: {c['text_dim']}; font-size: 13px; }}

    /* ---- Buttons (compact, professional) ---- */
    QPushButton {{
        background: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border_strong']};
        border-radius: 8px; padding: 6px 13px; font-weight: 600;
    }}
    QPushButton:hover {{ border-color: {c['accent']}; color: {c['accent']}; }}
    QPushButton:disabled {{ color: {c['text_dim']}; background: {c['surface_alt']}; border-color: {c['border']}; }}
    QPushButton#Primary {{
        background: {c['accent']}; color: #ffffff; border: 1px solid {c['accent']};
        padding: 8px 22px; border-radius: 8px; font-weight: 600;
    }}
    QPushButton#Primary:hover {{ background: {c['accent_hi']}; border-color: {c['accent_hi']}; color: #ffffff; }}
    QPushButton#Primary:pressed {{ background: {c['accent_press']}; }}
    QPushButton#Primary:disabled {{ background: {c['border_strong']}; border-color: {c['border_strong']}; color: {c['surface']}; }}
    QPushButton#Danger {{ border-color: {c['danger']}; color: {c['danger']}; }}
    QPushButton#Danger:hover {{ background: {c['danger']}; color: #ffffff; }}
    QPushButton#Ghost {{ background: transparent; border-color: {c['border']}; }}

    /* ---- Inputs ---- */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
        background: {c['input']}; border: 1px solid {c['border_strong']}; border-radius: 8px;
        padding: 6px 9px; selection-background-color: {c['accent']}; selection-color: #fff;
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {c['accent']};
    }}
    QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
        background: {c['surface_alt']}; color: {c['text_dim']}; border-color: {c['border']};
    }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox QAbstractItemView {{
        background: {c['surface']}; border: 1px solid {c['border_strong']};
        selection-background-color: {c['accent']}; selection-color: #fff; outline: none;
    }}
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 15px; border: none; }}

    /* ---- Lists & tables ---- */
    QListWidget, QTableWidget, QTreeWidget {{
        background: {c['input']}; border: 1px solid {c['border_strong']}; border-radius: 9px;
        outline: none;
    }}
    QListWidget::item {{ padding: 7px 9px; border-radius: 6px; }}
    QListWidget::item:selected, QTableWidget::item:selected {{ background: {c['accent']}; color: #fff; }}
    QListWidget::item:hover {{ background: {c['surface_alt']}; }}
    QHeaderView::section {{
        background: {c['surface_alt']}; color: {c['text_dim']}; border: none;
        padding: 6px; font-weight: 600;
    }}
    QTableWidget {{ gridline-color: {c['border']}; }}

    /* ---- Tabs ---- */
    QTabWidget::pane {{
        background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px;
        top: -1px;
    }}
    QTabBar {{ qproperty-drawBase: 0; background: transparent; }}
    QTabBar::tab {{
        background: transparent; color: {c['text_dim']}; padding: 8px 16px; margin-right: 4px;
        border: none; border-bottom: 2px solid transparent; font-weight: 600;
    }}
    QTabBar::tab:hover {{ color: {c['text']}; }}
    QTabBar::tab:selected {{ color: {c['accent']}; border-bottom: 2px solid {c['accent']}; }}

    /* ---- Tree ---- */
    QTreeView {{
        background: {c['input']}; border: 1px solid {c['border_strong']}; border-radius: 9px;
        outline: none;
    }}
    QTreeView::item {{ padding: 3px 2px; }}
    QTreeView::item:selected {{ background: {c['accent']}; color: #fff; }}
    QTreeView::item:hover {{ background: {c['surface_alt']}; }}

    /* ---- Text browser (docs) ---- */
    QTextBrowser {{ background: {c['input']}; border: 1px solid {c['border_strong']}; border-radius: 9px; padding: 10px; }}

    /* ---- Progress ---- */
    QProgressBar {{
        background: {c['surface_alt']}; border: none; border-radius: 7px; height: 14px;
        text-align: center; color: {c['text']};
    }}
    QProgressBar::chunk {{ background: {c['accent']}; border-radius: 7px; }}

    /* ---- Radio / check ---- */
    QRadioButton, QCheckBox {{ spacing: 9px; padding: 2px 0; }}
    QCheckBox::indicator {{
        width: 16px; height: 16px; border: 1px solid {c['border_strong']};
        border-radius: 5px; background: {c['input']};
    }}
    QCheckBox::indicator:hover {{ border-color: {c['accent']}; }}
    QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; }}
    QRadioButton::indicator {{
        width: 15px; height: 15px; border: 1px solid {c['border_strong']};
        border-radius: 8px; background: {c['input']};
    }}
    QRadioButton::indicator:hover {{ border-color: {c['accent']}; }}
    QRadioButton::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; }}

    /* ---- Misc ---- */
    QStatusBar {{ background: {c['surface']}; color: {c['text_dim']}; border-top: 1px solid {c['border']}; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {c['border_strong']}; border-radius: 5px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {c['text_dim']}; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {c['border_strong']}; border-radius: 5px; min-width: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QToolTip {{ background: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border_strong']}; padding: 5px; }}
    """
