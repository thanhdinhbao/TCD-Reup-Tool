"""
Ultra-Modern Cyber Dark Theme for TCD REUP TOOL.
Inspired by modern Discord, Linear, and VS Code dark aesthetics.
Features rich linear gradients, crisp borders, glowing accent highlights,
refined micro-typography, and polished interactive states.
"""

TCD_NAVY_QSS = """
/* Global Reset & Typography */
QWidget {
    background-color: #0D131F;
    color: #E2E8F0;
    font-family: 'Segoe UI', 'SF Pro Display', -apple-system, Roboto, sans-serif;
    font-size: 12px;
    outline: none;
}

QMainWindow, QDialog {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #090E17, stop:0.5 #0D1422, stop:1 #0A101C);
}

/* Group Containers & Cards */
QGroupBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #141D2D, stop:1 #111826);
    border: 1px solid #1F2D44;
    border-radius: 9px;
    margin-top: 14px;
    padding-top: 18px;
    padding-left: 12px;
    padding-right: 12px;
    padding-bottom: 12px;
    font-weight: 700;
    font-size: 13px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 3px 10px;
    color: #60A5FA;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1A263B, stop:1 #141D2D);
    border: 1px solid #283B55;
    border-radius: 5px;
    font-size: 12px;
    font-weight: bold;
}

QFrame#card_panel, QFrame#banner_card {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151F31, stop:1 #111A29);
    border: 1px solid #1E2D44;
    border-radius: 9px;
}

/* Inputs, SpinBoxes & Dropdowns */
QLineEdit, QSpinBox, QTimeEdit, QComboBox {
    background-color: #0A0F1A;
    border: 1px solid #23354E;
    border-radius: 7px;
    color: #F8FAFC;
    padding: 6px 12px;
    font-size: 12px;
    min-height: 22px;
    selection-background-color: #2563EB;
}

QLineEdit:hover, QSpinBox:hover, QTimeEdit:hover, QComboBox:hover {
    border: 1px solid #38BDF8;
    background-color: #0C1322;
}

QLineEdit:focus, QSpinBox:focus, QTimeEdit:focus, QComboBox:focus {
    border: 1px solid #60A5FA;
    background-color: #0E1626;
}

QComboBox {
    padding-right: 26px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #23354E;
    border-top-right-radius: 7px;
    border-bottom-right-radius: 7px;
    background-color: #121B2A;
}

QComboBox QAbstractItemView {
    background-color: #111A29;
    border: 1px solid #283E5E;
    selection-background-color: #1E3A8A;
    selection-color: #FFFFFF;
    color: #E2E8F0;
    padding: 4px;
    border-radius: 6px;
}

/* Buttons System */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1F2D42, stop:1 #172335);
    border: 1px solid #2E4362;
    border-radius: 7px;
    color: #F1F5F9;
    padding: 7px 16px;
    font-weight: 600;
    font-size: 12px;
    min-height: 22px;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #273954, stop:1 #1C2B40);
    border: 1px solid #38BDF8;
    color: #FFFFFF;
}

QPushButton:pressed {
    background-color: #131D2D;
    border: 1px solid #0284C7;
}

QPushButton:disabled {
    background-color: #101622;
    color: #475569;
    border: 1px solid #1A2433;
}

/* Special Button Variants */
QPushButton#btn_start {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #059669, stop:1 #047857);
    border: 1px solid #10B981;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 13px;
    padding: 7px 20px;
}

QPushButton#btn_start:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #10B981, stop:1 #059669);
    border: 1px solid #34D399;
}

QPushButton#btn_stop {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #DC2626, stop:1 #991B1B);
    border: 1px solid #EF4444;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 13px;
    padding: 7px 20px;
}

QPushButton#btn_stop:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #EF4444, stop:1 #B91C1C);
    border: 1px solid #F87171;
}

QPushButton#btn_license {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3D2D0C, stop:1 #291D06);
    border: 1px solid #F59E0B;
    color: #FDE68A;
    font-weight: bold;
}

QPushButton#btn_license:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #574011, stop:1 #382607);
    border: 1px solid #FBBF24;
    color: #FEF08A;
}

QPushButton#btn_primary {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2563EB, stop:1 #1D4ED8);
    border: 1px solid #3B82F6;
    color: #FFFFFF;
    font-weight: bold;
}

QPushButton#btn_primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3B82F6, stop:1 #2563EB);
    border: 1px solid #60A5FA;
}

/* Checkboxes & Radio Buttons */
QCheckBox, QRadioButton {
    color: #CBD5E1;
    font-weight: 500;
    spacing: 7px;
}

QCheckBox:hover, QRadioButton:hover {
    color: #F8FAFC;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    background-color: #0A0F1A;
    border: 1px solid #2A3E5C;
    border-radius: 4px;
}

QRadioButton::indicator {
    border-radius: 8px;
}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border: 1px solid #38BDF8;
}

QCheckBox::indicator:checked {
    background-color: #0284C7;
    border: 1px solid #38BDF8;
}

QRadioButton::indicator:checked {
    background-color: #0284C7;
    border: 1px solid #38BDF8;
}

/* Table & List Styling */
QTableWidget, QListWidget, QTreeWidget {
    background-color: #0A0F1A;
    alternate-background-color: #0E1524;
    border: 1px solid #1C2B40;
    border-radius: 8px;
    gridline-color: #162233;
    color: #F1F5F9;
    selection-background-color: #1E3A8A;
    selection-color: #FFFFFF;
}

QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #131E2E;
}

QTableWidget::item:selected, QListWidget::item:selected {
    background-color: #1E3A8A;
    color: #FFFFFF;
}

QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #182335, stop:1 #131B29);
    color: #94A3B8;
    padding: 7px 10px;
    border: none;
    border-right: 1px solid #1C2B40;
    border-bottom: 1px solid #1C2B40;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
}

/* Console Logs */
QTextEdit#console_log {
    background-color: #070B12;
    border: 1px solid #1A273B;
    border-radius: 8px;
    color: #E2E8F0;
    font-family: 'Consolas', 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 12px;
    line-height: 1.5;
    padding: 10px;
}

/* Progress Bars */
QProgressBar {
    background-color: #0A0F1A;
    border: 1px solid #1C2B40;
    border-radius: 6px;
    text-align: center;
    color: #E2E8F0;
    font-weight: bold;
    font-size: 11px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8);
    border-radius: 5px;
}

/* Sleek Slim Scrollbars */
QScrollBar:vertical {
    background: #080D16;
    width: 8px;
    margin: 0;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #23354E;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #3B5373;
}

QScrollBar:horizontal {
    background: #080D16;
    height: 8px;
    margin: 0;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #23354E;
    min-width: 24px;
    border-radius: 4px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    height: 0px;
}
"""

GALAXY_DARK_QSS = TCD_NAVY_QSS
