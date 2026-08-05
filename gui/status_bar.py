#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
状态栏模块
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QProgressBar, QApplication
)


class StatusBar(QWidget):
    """状态栏：状态文本 + 进度条"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            StatusBar {
                background-color: #FAFAFA;
                border-top: 1px solid #D0D0D0;
            }
        """)
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(8)

        self.status_indicator = QLabel("●")
        self.status_indicator.setFixedWidth(14)
        self.status_indicator.setStyleSheet("color: #6B8F71; font-size: 11px;")
        layout.addWidget(self.status_indicator)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #444444;
                font-size: 12px;
            }
        """)
        self.status_label.setMinimumWidth(100)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #D0D0D0;
                border-radius: 2px;
                background-color: #F0F0F0;
                text-align: center;
                height: 16px;
                color: #444444;
            }
            QProgressBar::chunk {
                background-color: #5B7C99;
                border-radius: 1px;
            }
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar, 1)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("""
            QLabel {
                color: #777777;
                font-size: 11px;
            }
        """)
        self.progress_label.setMinimumWidth(180)
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)

        layout.addStretch()

    def set_status(self, message: str, status_type: str = "ready"):
        color_map = {
            'ready': '#6B8F71',
            'working': '#B0A05A',
            'error': '#B85C5C',
            'success': '#6B8F71'
        }
        color = color_map.get(status_type, '#6B8F71')

        self.status_indicator.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.status_label.setText(message)
        QApplication.processEvents()

    def show_progress(self, visible: bool = True):
        self.progress_bar.setVisible(visible)
        self.progress_label.setVisible(visible)

        if not visible:
            self.progress_bar.setValue(0)
            self.progress_label.setText("")

        QApplication.processEvents()

    def update_progress(self, current: int, total: int, message: str = ""):
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)

        self.progress_label.setText(message)
        QApplication.processEvents()