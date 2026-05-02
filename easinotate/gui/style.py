"""Modern dark theme stylesheet for Easinotate."""

# Color palette - inspired by VS Code dark+ / modern design tools
COLORS = {
    "bg":          "#1e1e2e",  # main background
    "bg_alt":      "#181825",  # darker panels
    "bg_elev":     "#252540",  # elevated panels (toolbars, headers)
    "border":      "#313244",
    "border_lt":   "#45475a",
    "text":        "#cdd6f4",
    "text_dim":    "#a6adc8",
    "text_mute":   "#7f849c",
    "accent":      "#89b4fa",  # blue
    "accent_hov":  "#74a8f5",
    "accent_pres": "#5e95e8",
    "success":     "#a6e3a1",
    "warning":     "#f9e2af",
    "danger":      "#f38ba8",
    "selection":   "#414164",
}


def stylesheet() -> str:
    c = COLORS
    return f"""
QMainWindow, QDialog, QWidget {{
    background-color: {c['bg']};
    color: {c['text']};
    font-family: "Segoe UI", "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
    font-size: 10pt;
}}

/* ---------- Menus ---------- */
QMenuBar {{
    background-color: {c['bg_elev']};
    color: {c['text']};
    border-bottom: 1px solid {c['border']};
    padding: 4px;
}}
QMenuBar::item {{
    background-color: transparent;
    padding: 6px 12px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {c['selection']};
}}
QMenu {{
    background-color: {c['bg_elev']};
    color: {c['text']};
    border: 1px solid {c['border']};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 16px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {c['selection']};
}}
QMenu::separator {{
    height: 1px;
    background: {c['border']};
    margin: 4px 8px;
}}

/* ---------- Toolbar ---------- */
QToolBar {{
    background-color: {c['bg_elev']};
    border: none;
    border-bottom: 1px solid {c['border']};
    spacing: 4px;
    padding: 6px;
}}
QToolButton {{
    background-color: transparent;
    color: {c['text']};
    border: 1px solid transparent;
    padding: 6px 12px;
    border-radius: 6px;
    font-weight: 500;
}}
QToolButton:hover {{
    background-color: {c['selection']};
    border-color: {c['border_lt']};
}}
QToolButton:pressed {{
    background-color: {c['accent_pres']};
    color: white;
}}
QToolButton:checked {{
    background-color: {c['accent']};
    color: {c['bg']};
}}

/* ---------- Status bar ---------- */
QStatusBar {{
    background-color: {c['bg_elev']};
    color: {c['text_dim']};
    border-top: 1px solid {c['border']};
}}
QStatusBar::item {{
    border: none;
}}

/* ---------- Buttons ---------- */
QPushButton {{
    background-color: {c['bg_elev']};
    color: {c['text']};
    border: 1px solid {c['border_lt']};
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 500;
    min-height: 18px;
}}
QPushButton:hover {{
    background-color: {c['selection']};
    border-color: {c['accent']};
}}
QPushButton:pressed {{
    background-color: {c['accent_pres']};
    color: white;
}}
QPushButton:disabled {{
    color: {c['text_mute']};
    background-color: {c['bg_alt']};
    border-color: {c['border']};
}}
QPushButton[primary="true"] {{
    background-color: {c['accent']};
    color: {c['bg']};
    border: none;
    font-weight: 600;
}}
QPushButton[primary="true"]:hover {{
    background-color: {c['accent_hov']};
}}
QPushButton[primary="true"]:pressed {{
    background-color: {c['accent_pres']};
}}
QPushButton[danger="true"] {{
    background-color: transparent;
    color: {c['danger']};
    border: 1px solid {c['danger']};
}}
QPushButton[danger="true"]:hover {{
    background-color: {c['danger']};
    color: {c['bg']};
}}

/* ---------- Inputs ---------- */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {c['bg_alt']};
    color: {c['text']};
    border: 1px solid {c['border_lt']};
    padding: 6px 10px;
    border-radius: 6px;
    selection-background-color: {c['accent']};
    selection-color: {c['bg']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {c['accent']};
}}
QLineEdit:disabled, QTextEdit:disabled {{
    color: {c['text_mute']};
    background-color: {c['bg']};
}}

/* ---------- Combo box ---------- */
QComboBox {{
    background-color: {c['bg_alt']};
    color: {c['text']};
    border: 1px solid {c['border_lt']};
    padding: 6px 10px;
    border-radius: 6px;
    min-height: 20px;
}}
QComboBox:focus {{
    border: 1px solid {c['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {c['text_dim']};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {c['bg_elev']};
    border: 1px solid {c['border_lt']};
    selection-background-color: {c['accent']};
    selection-color: {c['bg']};
    outline: none;
    padding: 4px;
}}

/* ---------- Lists & trees ---------- */
QListWidget, QTreeWidget {{
    background-color: {c['bg_alt']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    outline: none;
    padding: 4px;
}}
QListWidget::item, QTreeWidget::item {{
    padding: 8px 8px;
    border-radius: 4px;
    margin: 1px;
}}
QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {c['accent']};
    color: {c['bg']};
}}
QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected {{
    background-color: {c['selection']};
}}

/* ---------- Splitters ---------- */
QSplitter::handle {{
    background-color: {c['border']};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}
QSplitter::handle:hover {{
    background-color: {c['accent']};
}}

/* ---------- Group box ---------- */
QGroupBox {{
    background-color: transparent;
    border: 1px solid {c['border']};
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 12px;
    font-weight: 600;
    color: {c['text_dim']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 12px;
    background-color: {c['bg']};
}}

/* ---------- Labels ---------- */
QLabel[heading="true"] {{
    font-size: 14pt;
    font-weight: 600;
    color: {c['text']};
}}
QLabel[subheading="true"] {{
    font-size: 11pt;
    font-weight: 600;
    color: {c['text_dim']};
}}
QLabel[muted="true"] {{
    color: {c['text_mute']};
    font-size: 9pt;
}}
QLabel[badge="true"] {{
    background-color: {c['accent']};
    color: {c['bg']};
    padding: 2px 8px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 9pt;
}}

/* ---------- Scroll bars ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c['border_lt']};
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['text_mute']};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {c['border_lt']};
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {c['text_mute']};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    background: none;
    border: none;
    width: 0;
    height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

/* ---------- Tabs ---------- */
QTabWidget::pane {{
    border: 1px solid {c['border']};
    border-radius: 6px;
    background-color: {c['bg_alt']};
}}
QTabBar::tab {{
    background-color: transparent;
    color: {c['text_dim']};
    padding: 8px 16px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {c['text']};
    border-bottom: 2px solid {c['accent']};
}}
QTabBar::tab:hover:!selected {{
    color: {c['text']};
}}

/* ---------- Check / Radio ---------- */
QCheckBox, QRadioButton {{
    spacing: 8px;
    color: {c['text']};
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
}}
QCheckBox::indicator:unchecked {{
    background-color: {c['bg_alt']};
    border: 1px solid {c['border_lt']};
    border-radius: 3px;
}}
QCheckBox::indicator:checked {{
    background-color: {c['accent']};
    border: 1px solid {c['accent']};
    border-radius: 3px;
}}
QRadioButton::indicator:unchecked {{
    background-color: {c['bg_alt']};
    border: 1px solid {c['border_lt']};
    border-radius: 8px;
}}
QRadioButton::indicator:checked {{
    background-color: {c['accent']};
    border: 4px solid {c['bg_alt']};
    border-radius: 8px;
}}

/* ---------- Progress ---------- */
QProgressBar {{
    background-color: {c['bg_alt']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    text-align: center;
    height: 18px;
}}
QProgressBar::chunk {{
    background-color: {c['accent']};
    border-radius: 5px;
}}

/* ---------- Tooltip ---------- */
QToolTip {{
    background-color: {c['bg_elev']};
    color: {c['text']};
    border: 1px solid {c['border_lt']};
    padding: 4px 8px;
    border-radius: 4px;
}}
"""
