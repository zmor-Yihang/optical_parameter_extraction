#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
样式表模块

简约扁平风格：无渐变、细边框、中性色
"""


def get_main_window_style() -> str:
    """获取主窗口样式表"""
    return """
        QMainWindow {
            background-color: #FFFFFF;
        }

        QComboBox {
            background-color: #FFFFFF;
            border: 1px solid #D0D0D0;
            border-radius: 3px;
            padding: 4px 6px;
            color: #333333;
            min-width: 6em;
        }
        QComboBox:focus {
            border: 1px solid #5B7C99;
        }
        QComboBox:hover {
            border: 1px solid #A0A0A0;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 18px;
            border-left: 1px solid #D0D0D0;
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #666666;
            width: 0px;
            height: 0px;
        }
        QComboBox QAbstractItemView {
            background-color: #FFFFFF;
            border: 1px solid #D0D0D0;
            color: #333333;
            selection-background-color: #E8EEF4;
            selection-color: #222222;
        }

        QGroupBox {
            background-color: #FAFAFA;
            border: 1px solid #D0D0D0;
            border-radius: 4px;
            margin-top: 1ex;
            font-weight: bold;
            color: #333333;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: #555555;
            font-size: 11px;
        }

        QListWidget {
            background-color: #FFFFFF;
            border: 1px solid #D0D0D0;
            border-radius: 3px;
            color: #333333;
            selection-background-color: #E8EEF4;
            selection-color: #222222;
            alternate-background-color: #F7F7F7;
        }
        QListWidget::item {
            padding: 5px;
            border-bottom: 1px solid #EEEEEE;
        }
        QListWidget::item:hover {
            background-color: #F0F0F0;
        }

        /* 细滚动条 */
        QListWidget QScrollBar:vertical {
            background: #F5F5F5;
            width: 8px;
            margin: 0;
            border: none;
        }
        QListWidget QScrollBar::handle:vertical {
            background: #C0C0C0;
            min-height: 20px;
            border-radius: 4px;
        }
        QListWidget QScrollBar::handle:vertical:hover {
            background: #A8A8A8;
        }
        QListWidget QScrollBar:horizontal {
            background: #F5F5F5;
            height: 8px;
            margin: 0;
            border: none;
        }
        QListWidget QScrollBar::handle:horizontal {
            background: #C0C0C0;
            min-width: 20px;
            border-radius: 4px;
        }
        QListWidget QScrollBar::handle:horizontal:hover {
            background: #A8A8A8;
        }
        QListWidget QScrollBar::add-line, QListWidget QScrollBar::sub-line {
            width: 0px;
            height: 0px;
        }
        QListWidget QScrollBar::add-page, QListWidget QScrollBar::sub-page {
            background: transparent;
        }

        QLineEdit {
            background-color: #FFFFFF;
            border: 1px solid #D0D0D0;
            border-radius: 3px;
            padding: 4px 6px;
            color: #333333;
            font-size: 10px;
        }
        QLineEdit:focus {
            border: 1px solid #5B7C99;
        }

        QTabWidget {
            background: transparent;
        }
        QTabWidget::pane {
            border: 1px solid #D0D0D0;
            border-radius: 3px;
            background-color: #FFFFFF;
        }
        QTabBar::tab {
            background-color: #F0F0F0;
            border: 1px solid #D0D0D0;
            border-bottom: none;
            border-radius: 3px 3px 0 0;
            padding: 6px 12px;
            margin-right: 1px;
            color: #555555;
        }
        QTabBar::tab:selected {
            background-color: #FFFFFF;
            color: #222222;
            border-bottom: 1px solid #FFFFFF;
        }
        QTabBar::tab:hover:!selected {
            background-color: #E8E8E8;
            color: #333333;
        }

        QSplitter::handle {
            background-color: #D8D8D8;
        }
        QSplitter::handle:hover {
            background-color: #B0B0B0;
        }

        QLabel[accessibleName="status"] {
            background-color: #F7F7F7;
            border: 1px solid #D0D0D0;
            border-radius: 3px;
            padding: 6px;
            color: #333333;
        }

        QProgressBar {
            border: 1px solid #D0D0D0;
            border-radius: 3px;
            background-color: #F0F0F0;
            text-align: center;
            color: #333333;
        }
        QProgressBar::chunk {
            background-color: #5B7C99;
            border-radius: 2px;
        }

        QPushButton {
            background-color: #F5F5F5;
            border: 1px solid #D0D0D0;
            border-radius: 3px;
            padding: 5px 10px;
            color: #333333;
        }
        QPushButton:hover {
            background-color: #EBEBEB;
            border-color: #B8B8B8;
        }
        QPushButton:pressed {
            background-color: #E0E0E0;
        }
        QPushButton:disabled {
            background-color: #F5F5F5;
            color: #A0A0A0;
            border-color: #E0E0E0;
        }
    """


def get_menubar_style() -> str:
    """获取菜单栏样式"""
    return """
        QMenuBar {
            background-color: #FAFAFA;
            color: #333333;
            border-bottom: 1px solid #D0D0D0;
        }
        QMenuBar::item {
            padding: 4px 10px;
            background-color: transparent;
        }
        QMenuBar::item:selected {
            background-color: #E8E8E8;
        }
        QMenu {
            background-color: #FFFFFF;
            color: #333333;
            border: 1px solid #D0D0D0;
        }
        QMenu::item {
            padding: 5px 28px 5px 16px;
        }
        QMenu::item:selected {
            background-color: #E8EEF4;
        }
    """


def get_progress_dialog_style() -> str:
    """获取进度对话框样式"""
    return """
        QDialog {
            background-color: #FFFFFF;
        }
        QLabel {
            color: #333333;
            font-size: 11pt;
        }
        QProgressBar {
            border: 1px solid #D0D0D0;
            border-radius: 3px;
            background-color: #F0F0F0;
            text-align: center;
            color: #333333;
            min-height: 22px;
        }
        QProgressBar::chunk {
            background-color: #5B7C99;
            border-radius: 2px;
        }
    """