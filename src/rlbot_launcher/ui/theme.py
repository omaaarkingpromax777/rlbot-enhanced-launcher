ACCENT = "#3b82f6"
BG = "#0f1115"
PANEL = "#171a21"
PANEL_2 = "#1f2430"
BORDER = "#2a3040"
TEXT = "#e6e8ee"
MUTED = "#8b93a7"
BLUE_TEAM = "#2f6fed"
ORANGE_TEAM = "#f08a24"

QSS = f"""
* {{ font-family: "Segoe UI", "Noto Sans Arabic", "Noto Sans", sans-serif; font-size: 13px; color: {TEXT}; }}
QMainWindow, QWidget#root {{ background: {BG}; }}
QWidget#sidebar {{ background: {PANEL}; border-left: 1px solid {BORDER}; }}
QLabel#brand {{ font-size: 17px; font-weight: 700; padding: 18px 16px 4px 16px; }}
QLabel#brandSub {{ color: {MUTED}; padding: 0 16px 16px 16px; font-size: 11px; }}
QPushButton#nav {{ text-align: right; padding: 11px 18px; border: none; border-radius: 8px; margin: 2px 10px; color: {MUTED}; font-size: 14px; }}
QPushButton#nav:hover {{ background: {PANEL_2}; color: {TEXT}; }}
QPushButton#nav:checked {{ background: {ACCENT}; color: white; font-weight: 600; }}
QLabel#h1 {{ font-size: 22px; font-weight: 700; }}
QLabel#muted {{ color: {MUTED}; }}
QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 12px; }}
QPushButton {{ background: {PANEL_2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px 14px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: {MUTED}; }}
QPushButton#primary {{ background: {ACCENT}; border: none; color: white; font-weight: 600; padding: 10px 22px; font-size: 14px; }}
QPushButton#primary:hover {{ background: #2563eb; }}
QPushButton#danger {{ background: #b42318; border: none; color: white; }}
QPushButton#chip {{ border-radius: 14px; padding: 5px 12px; font-size: 12px; }}
QPushButton#chip:checked {{ background: {ACCENT}; border-color: {ACCENT}; color: white; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {PANEL_2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 7px 10px; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{ background: {PANEL_2}; selection-background-color: {ACCENT}; }}
QTableView, QListWidget {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; gridline-color: {BORDER}; selection-background-color: #23324d; alternate-background-color: #1a1e27; }}
QTextBrowser {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; padding: 8px; }}
QHeaderView::section {{ background: {PANEL_2}; color: {MUTED}; border: none; padding: 8px; font-weight: 600; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 8px 16px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QProgressBar {{ background: {PANEL_2}; border: none; border-radius: 6px; height: 10px; text-align: center; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 6px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; }}
QScrollArea {{ border: none; background: transparent; }}
QWidget#bracketInner {{ background: {BG}; }}
QScrollBar:horizontal, QScrollBar:vertical {{ background: {PANEL}; border: none; height: 10px; width: 10px; }}
QScrollBar::handle {{ background: {BORDER}; border-radius: 5px; min-width: 30px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QStatusBar {{ background: {PANEL}; color: {MUTED}; border-top: 1px solid {BORDER}; }}
"""
