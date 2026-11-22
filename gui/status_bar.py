#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
状态栏模块
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QProgressBar, QApplication
)


class StatusBar(QWidget):
    """状态栏：状态文本 + 进度条"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("analysisStatus")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 3)
        layout.setSpacing(8)

        self.status_indicator = QLabel("●")
        layout.addWidget(self.status_indicator)

        self.status_label = QLabel("就绪")
        self.status_label.setMinimumWidth(100)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedSize(144, 6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setProperty("uiRole", "hint")
        self.progress_label.setMinimumWidth(180)
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)

        layout.addStretch()
        self._set_indicator_color("ready")

    def _set_indicator_color(self, status_type: str):
        colors = {"ready": "#316C46", "working": "#876200", "error": "#A23535"}
        color = colors.get(status_type, colors["ready"])
        self.status_indicator.setStyleSheet(f"color: {color}; font-size: 11px;")

    def set_status(self, message: str, status_type: str = "ready"):
        self._set_indicator_color(status_type)
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
            message = f"{percentage}%  {message}".rstrip()
        self.progress_label.setText(message)
        QApplication.processEvents()