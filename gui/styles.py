"""应用的亮色 / 暗色主题（Qt 调色板和共享控件样式）。"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication


WHITE = "#FFFFFF"
WORKSPACE = "#F1F5FA"
SUBTLE = "#F7F9FD"
TEXT = "#17263B"
MUTED = "#53647B"
DISABLED = "#738298"
RULE = "#E1E8F1"
BORDER = "#CFDAE8"
HOVER = "#F1F6FD"
SELECTED = "#E5EFFF"
ACCENT = "#2358B8"
ACCENT_HOVER = "#1C4BA0"
ACCENT_PRESSED = "#163C82"
FOCUS = "#4072CE"

# 暗色主题使用独立的高亮蓝，避免亮色主题的深蓝在深色底上对比不足。
DARK_SURFACE = "#18212C"
DARK_WORKSPACE = "#101720"
DARK_SUBTLE = "#202B38"
DARK_TEXT = "#E7EEF7"
DARK_MUTED = "#AAB8C9"
DARK_DISABLED = "#77869A"
DARK_RULE = "#303D4D"
DARK_BORDER = "#46576C"
DARK_HOVER = "#29384A"
DARK_SELECTED = "#2D4F79"
DARK_ACCENT = "#7DB8FF"
DARK_ACCENT_HOVER = "#A0CEFF"
DARK_ACCENT_PRESSED = "#5C9CEB"
DARK_FOCUS = "#9BCBFF"


def _apply_theme(app: QApplication, *, dark: bool) -> None:
    app.styleHints().setColorScheme(
        Qt.ColorScheme.Dark if dark else Qt.ColorScheme.Light
    )
    app.setStyle("Fusion")
    roles = QPalette.ColorRole
    palette = app.palette()
    if dark:
        colors = {
            roles.Window: DARK_WORKSPACE,
            roles.WindowText: DARK_TEXT,
            roles.Base: DARK_SURFACE,
            roles.AlternateBase: DARK_SUBTLE,
            roles.Text: DARK_TEXT,
            roles.PlaceholderText: DARK_MUTED,
            roles.Button: DARK_SURFACE,
            roles.ButtonText: DARK_TEXT,
            roles.ToolTipBase: DARK_SURFACE,
            roles.ToolTipText: DARK_TEXT,
            roles.Highlight: DARK_SELECTED,
            roles.HighlightedText: DARK_TEXT,
            roles.Accent: DARK_ACCENT,
            roles.Link: DARK_ACCENT,
            roles.Mid: DARK_BORDER,
        }
        disabled = DARK_DISABLED
        stylesheet = DARK_STYLE
    else:
        colors = {
            roles.Window: WHITE,
            roles.WindowText: TEXT,
            roles.Base: WHITE,
            roles.AlternateBase: SUBTLE,
            roles.Text: TEXT,
            roles.PlaceholderText: MUTED,
            roles.Button: WHITE,
            roles.ButtonText: TEXT,
            roles.ToolTipBase: WHITE,
            roles.ToolTipText: TEXT,
            roles.Highlight: SELECTED,
            roles.HighlightedText: TEXT,
            roles.Accent: ACCENT,
            roles.Link: ACCENT,
            roles.Mid: BORDER,
        }
        disabled = DISABLED
        stylesheet = LIGHT_STYLE
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (roles.WindowText, roles.Text, roles.ButtonText, roles.PlaceholderText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(disabled))
    app.setPalette(palette)

    font = QFont()
    font.setFamilies(["Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", "Arial"])
    font.setPointSizeF(9.5)
    app.setFont(font)
    app.setStyleSheet(stylesheet)


def apply_light_theme(app: QApplication) -> None:
    """应用亮色主题。"""
    _apply_theme(app, dark=False)


def apply_dark_theme(app: QApplication) -> None:
    """应用暗色主题。"""
    _apply_theme(app, dark=True)


LIGHT_STYLE = f"""
    QMainWindow, QWidget#workspace, QWidget#subplotDetail {{
        background-color: {WORKSPACE};
    }}
    QDialog, QWidget#sidebarContent {{ background-color: {WHITE}; }}
    QFrame#appHeader {{
        background-color: {WHITE};
        border-bottom: 1px solid {RULE};
    }}
    QFrame[uiRole="card"] {{
        background-color: {WHITE};
        border: 1px solid {RULE};
        border-radius: 8px;
    }}
    QFrame#sectionRule {{ background-color: {RULE}; }}
    QFrame#sidebarFooter {{ border-top: 1px solid {RULE}; }}
    QWidget#resultPage {{ background-color: {WHITE}; }}
    QLabel#brandMark, QLabel#emptyMark {{
        background-color: {SELECTED};
        border-radius: 10px;
    }}
    QLabel#brandMark {{
        background-color: {ACCENT};
        border-radius: 8px;
    }}
    QLabel#appTitle {{ font-size: 14pt; font-weight: bold; }}
    QLabel[uiRole="panelTitle"], QLabel#emptyTitle {{
        font-size: 13pt;
        font-weight: bold;
    }}
    QLabel[uiRole="hint"] {{ color: {MUTED}; }}
    QLabel[uiRole="sectionTitle"] {{ font-weight: bold; }}
    QLabel[uiRole="count"] {{
        background-color: {SELECTED};
        border-radius: 8px;
        color: {ACCENT};
        padding: 1px 7px;
        font-size: 9pt;
    }}

    QGroupBox {{
        background-color: {WHITE};
        border: 1px solid {RULE};
        border-radius: 8px;
        margin-top: 11px;
        padding-top: 6px;
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 4px;
        background-color: {WHITE};
        color: {TEXT};
    }}

    QPushButton, QToolButton#exportButton {{
        background-color: {WHITE};
        border: 1px solid {BORDER};
        border-radius: 7px;
        padding: 5px 11px;
        color: {TEXT};
    }}
    QPushButton:hover, QToolButton#exportButton:hover {{
        background-color: {HOVER};
        border-color: {FOCUS};
    }}
    QPushButton:pressed, QToolButton#exportButton:pressed {{ background-color: {SELECTED}; }}
    QPushButton:focus, QToolButton#exportButton:focus {{ border-color: {FOCUS}; }}
    QPushButton:disabled, QToolButton#exportButton:disabled {{
        background-color: {SUBTLE};
        border-color: {RULE};
        color: {DISABLED};
    }}
    QPushButton[uiRole="primary"]:enabled {{
        background-color: {ACCENT};
        border-color: {ACCENT};
        color: {WHITE};
        font-weight: bold;
    }}
    QPushButton[uiRole="primary"]:hover, QPushButton[uiRole="primary"]:focus {{
        background-color: {ACCENT_HOVER};
        border-color: {ACCENT_PRESSED};
    }}
    QPushButton[uiRole="primary"]:pressed {{ background-color: {ACCENT_PRESSED}; }}
    QPushButton#runAnalysis {{ min-height: 24px; }}
    QPushButton[uiRole="soft"]:enabled, QToolButton#exportButton:enabled {{
        background-color: {HOVER};
        border-color: {BORDER};
        color: {ACCENT};
    }}
    QPushButton[uiRole="soft"]:hover, QPushButton[uiRole="soft"]:focus,
    QPushButton[uiRole="soft"]:checked,
    QToolButton#exportButton:hover, QToolButton#exportButton:focus {{
        background-color: {SELECTED};
        border-color: {FOCUS};
    }}
    QToolButton#exportButton {{ padding-right: 21px; }}
    QToolButton#exportButton::menu-indicator {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        right: 7px;
    }}
    QPushButton[uiRole="plain"] {{ border-color: transparent; padding: 3px 6px; }}
    QPushButton[uiRole="plain"]:disabled {{ background-color: {WHITE}; }}
    QPushButton[uiRole="plain"]:focus {{ border-color: {FOCUS}; }}
    QPushButton#windowToggle {{
        background-color: {RULE};
        border-color: transparent;
        border-radius: 10px;
        padding: 0 4px;
        font-size: 12px;
        color: {MUTED};
        text-align: left;
    }}
    QPushButton#windowToggle:checked {{
        background-color: {ACCENT};
        color: {WHITE};
        text-align: right;
    }}
    QPushButton#windowToggle:focus {{ border-color: {FOCUS}; }}
    QPushButton#windowToggle:checked:focus {{ border-color: {ACCENT_PRESSED}; }}

    QLineEdit {{
        background-color: {WHITE};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 4px 7px;
    }}
    QLineEdit:hover, QLineEdit:focus {{ border-color: {FOCUS}; }}
    QLineEdit:disabled {{ border-color: {RULE}; color: {DISABLED}; }}
    QComboBox {{ min-height: 27px; }}
    QComboBox QLineEdit {{ background: transparent; border: none; padding: 0 4px; }}
    QComboBox QAbstractItemView {{
        background-color: {WHITE};
        border: 1px solid {BORDER};
        selection-background-color: {SELECTED};
        selection-color: {TEXT};
    }}

    QListWidget, QTextBrowser, QPlainTextEdit {{
        background-color: {WHITE};
        border: 1px solid {BORDER};
        border-radius: 7px;
        selection-background-color: {SELECTED};
        selection-color: {TEXT};
    }}
    QListWidget[dropZone="true"] {{ background-color: {SUBTLE}; border-style: dashed; }}
    QListWidget[dropZone="true"]:focus {{ border-color: {FOCUS}; }}
    QListWidget[dragActive="true"] {{
        background-color: {SELECTED};
        border-color: {FOCUS};
    }}
    QListWidget:focus, QTextBrowser:focus, QPlainTextEdit:focus {{ border-color: {FOCUS}; }}
    QListWidget::item {{ padding: 5px 7px; border-radius: 4px; }}
    QListWidget::item:hover:!selected {{ background-color: {HOVER}; }}
    QTextBrowser[uiRole="dialogBody"] {{ border: none; font-size: 10pt; }}
    QPlainTextEdit#runLog {{ font-family: Consolas, "Courier New"; font-size: 9pt; }}
    QScrollArea {{ background-color: {WHITE}; border: none; }}

    QScrollBar:vertical, QScrollBar:horizontal {{
        background-color: {WHITE};
        border: none;
        margin: 0;
    }}
    QScrollBar:vertical {{ width: 8px; }}
    QScrollBar:horizontal {{ height: 8px; }}
    QScrollBar::handle {{ background-color: {BORDER}; border-radius: 4px; }}
    QScrollBar::handle:vertical {{ min-height: 20px; }}
    QScrollBar::handle:horizontal {{ min-width: 20px; }}
    QScrollBar::handle:hover {{ background-color: #A0A0A0; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QTabWidget::pane {{ background-color: {WHITE}; border-top: 1px solid {RULE}; }}
    QTabBar::tab {{
        background-color: {SUBTLE};
        border: 1px solid transparent;
        border-radius: 7px;
        padding: 6px 14px;
        margin: 0 5px 8px 0;
        color: {MUTED};
    }}
    QTabBar::tab:selected {{
        background-color: {SELECTED};
        color: {ACCENT};
        font-weight: bold;
    }}
    QTabBar::tab:hover:!selected {{ background-color: {HOVER}; color: {TEXT}; }}
    QTabBar::tab:focus:selected {{ border-color: {FOCUS}; }}
    QTabBar#curveViews::tab {{
        padding: 5px 9px;
        margin: 0 3px 0 0;
    }}
    QTabBar#curveViews::tab:selected {{ border-color: {BORDER}; }}
    QTabBar#curveViews::tab:focus:selected {{ border-color: {FOCUS}; }}
    QToolBar#curveToolbar {{ background-color: {WHITE}; border-color: transparent; }}
    QSplitter::handle:horizontal {{ background: transparent; margin: 8px 5px; border-radius: 2px; }}
    QSplitter::handle:horizontal:hover {{ background-color: {BORDER}; }}

    QMenuBar {{ background-color: {SUBTLE}; border-bottom: 1px solid {RULE}; padding-left: 6px; }}
    QMenuBar::item {{ padding: 4px 11px; background: transparent; }}
    QMenuBar::item:selected {{ background-color: {HOVER}; }}
    QMenuBar::item:pressed {{ background-color: {SELECTED}; }}
    QMenu {{ background-color: {WHITE}; border: 1px solid {BORDER}; padding: 4px; }}
    QMenu::item {{ padding: 6px 22px 6px 12px; border-radius: 4px; }}
    QMenu::item:selected {{ background-color: {SELECTED}; }}
    QMenu::item:disabled {{ color: {DISABLED}; }}
    QToolTip {{ background-color: {WHITE}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px; }}

    QToolBar {{
        background-color: {SUBTLE};
        border: 1px solid {RULE};
        border-radius: 7px;
        padding: 2px 4px;
        spacing: 3px;
    }}
    QToolBar QToolButton {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 5px;
        padding: 4px;
    }}
    QToolBar QToolButton:hover {{ background-color: {HOVER}; border-color: {BORDER}; }}
    QToolBar QToolButton:pressed, QToolBar QToolButton:checked {{ background-color: {SELECTED}; }}
    QToolBar QToolButton:focus {{ border-color: {FOCUS}; }}
    QWidget#axisRange {{ background-color: {SUBTLE}; border: 1px solid {RULE}; border-radius: 7px; }}
    QWidget#axisRange QLineEdit {{ padding-left: 4px; padding-right: 4px; }}
    QWidget#axisRange QPushButton {{ padding-left: 8px; padding-right: 8px; }}
    QWidget#analysisStatus {{ background-color: {WORKSPACE}; }}
    QProgressBar {{
        background-color: {SELECTED};
        border: none;
        border-radius: 3px;
    }}
    QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 3px; }}
"""


def _make_dark_style(light_style: str) -> str:
    """把共享 QSS 的语义色替换为暗色主题色。"""
    style = light_style
    # WHITE 同时用于表面和主按钮文字，先按 QSS 属性分别处理。
    style = style.replace(
        f"background-color: {WHITE}", f"background-color: {DARK_SURFACE}"
    )
    style = style.replace(f"background: {WHITE}", f"background: {DARK_SURFACE}")
    style = style.replace(f"color: {WHITE}", f"color: {DARK_TEXT}")
    style = style.replace(f"border-color: {WHITE}", f"border-color: {DARK_SURFACE}")

    replacements = (
        (WORKSPACE, DARK_WORKSPACE),
        (SUBTLE, DARK_SUBTLE),
        (TEXT, DARK_TEXT),
        (MUTED, DARK_MUTED),
        (DISABLED, DARK_DISABLED),
        (RULE, DARK_RULE),
        (BORDER, DARK_BORDER),
        (HOVER, DARK_HOVER),
        (SELECTED, DARK_SELECTED),
        (ACCENT_HOVER, DARK_ACCENT_HOVER),
        (ACCENT_PRESSED, DARK_ACCENT_PRESSED),
        (ACCENT, DARK_ACCENT),
        (FOCUS, DARK_FOCUS),
        ("#A0A0A0", "#8998AA"),
    )
    for source, target in replacements:
        style = style.replace(source, target)
    return style


DARK_STYLE = _make_dark_style(LIGHT_STYLE)
