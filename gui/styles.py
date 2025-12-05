#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
样式表模块

包含应用程序使用的所有样式表定义
"""


def get_main_window_style() -> str:
    """获取主窗口样式表"""
    return """
        /* 主窗口样式 */
        QMainWindow {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #FFFFFF, stop:0.5 #F8F8F8, stop:1 #FFFFFF);
        }
        
        /* 组合框样式 */
        QComboBox {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #FFFFFF, stop:1 #F0F0F0);
            border: 2px solid #CCCCCC;
            border-radius: 6px;
            padding: 6px;
            color: #333333;
            min-width: 6em;
            font-weight: 500;
        }
        QComboBox:focus {
            border: 2px solid #4A90E2;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #FFFFFF, stop:1 #F8F8F8);
        }
        QComboBox:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #FFFFFF, stop:1 #F8F8F8);
            border: 2px solid #999999;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left-width: 2px;
            border-left-color: #CCCCCC;
            border-left-style: solid;
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #F0F0F0, stop:1 #E0E0E0);
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid #333333;
            width: 0px;
            height: 0px;
        }
        QComboBox QAbstractItemView {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #FFFFFF, stop:1 #F0F0F0);
            border: 2px solid #CCCCCC;
            color: #333333;
            selection-background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #4A90E2, stop:1 #3A80D2);
            selection-color: #FFFFFF;
            border-radius: 4px;
        }
        
        /* 分组框样式 */
        QGroupBox {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(255, 255, 255, 0.9), stop:1 rgba(240, 240, 240, 0.9));
            border: 2px solid #CCCCCC;
            border-radius: 8px;
            margin-top: 1ex;
            font-weight: bold;
            color: #333333;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 8px 0 8px;
            color: #4A90E2;
            font-size: 11px;
        }
        
        /* 列表控件样式 */
        QListWidget {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #FFFFFF, stop:1 #F8F8F8);
            border: 2px solid #CCCCCC;
            border-radius: 6px;
            color: #333333;
            selection-background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #4A90E2, stop:1 #3A80D2);
            alternate-background-color: #F0F0F0;
        }
        QListWidget::item {
            padding: 8px;
            border-bottom: 1px solid #EEEEEE;
        }
        QListWidget::item:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #F8F8F8, stop:1 #EEEEEE);
        }
        
        /* 输入框样式 */
        QLineEdit {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #FFFFFF, stop:1 #F8F8F8);
            border: 2px solid #CCCCCC;
            border-radius: 6px;
            padding: 6px;
            color: #333333;
            font-size: 10px;
        }
        QLineEdit:focus {
            border: 2px solid #4A90E2;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #FFFFFF, stop:1 #F0F0F0);
        }
        
        /* 标签页样式 */
        QTabWidget {
            background: transparent;
        }
        QTabWidget::pane {
            border: 2px solid #CCCCCC;
            border-radius: 6px;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(255, 255, 255, 0.9), stop:1 rgba(248, 248, 248, 0.9));
        }
        QTabBar::tab {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #F0F0F0, stop:1 #E0E0E0);
            border: 2px solid #CCCCCC;
            border-bottom: none;
            border-radius: 6px 6px 0 0;
            padding: 8px 16px;
            margin-right: 2px;
            color: #666666;
        }
        QTabBar::tab:selected {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #4A90E2, stop:1 #3A80D2);
            color: #FFFFFF;
            border-color: #4A90E2;
        }
        QTabBar::tab:hover:!selected {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #F8F8F8, stop:1 #F0F0F0);
            color: #333333;
        }
        
        /* 分割器样式 */
        QSplitter::handle {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #CCCCCC, stop:0.5 #DDDDDD, stop:1 #CCCCCC);
            border-radius: 2px;
        }
        QSplitter::handle:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #4A90E2, stop:0.5 #5A9AE2, stop:1 #4A90E2);
        }
        
        /* 状态标签样式 */
        QLabel[accessibleName="status"] {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(255, 255, 255, 0.9), stop:1 rgba(240, 240, 240, 0.9));
            border: 2px solid #CCCCCC;
            border-radius: 6px;
            padding: 8px;
            color: #333333;
        }
        
        /* 进度条样式 */
        QProgressBar {
            border: 2px solid #CCCCCC;
            border-radius: 5px;
            background-color: #F0F0F0;
            text-align: center;
            color: #333333;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #4A90E2, stop:1 #3A80D2);
            border-radius: 3px;
        }
    """


def get_menubar_style() -> str:
    """获取菜单栏样式"""
    return """
        QMenuBar {
            background-color: #F8F8F8;
            color: #333333;
            border-bottom: 1px solid #CCCCCC;
        }
        QMenuBar::item {
            padding: 5px 10px;
            background-color: transparent;
        }
        QMenuBar::item:selected {
            background-color: #E0E0E0;
        }
        QMenu {
            background-color: #FFFFFF;
            color: #333333;
            border: 1px solid #CCCCCC;
        }
        QMenu::item {
            padding: 5px 30px 5px 20px;
        }
        QMenu::item:selected {
            background-color: #E0E0E0;
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
            border: 2px solid #CCCCCC;
            border-radius: 8px;
            background-color: #F0F0F0;
            text-align: center;
            color: #333333;
            min-height: 25px;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #4CAF50, stop:1 #45a049);
            border-radius: 6px;
        }
    """
