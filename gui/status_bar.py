#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
状态栏模块

包含状态显示和进度条的状态栏组件
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QProgressBar, QApplication
)
from PyQt6.QtCore import Qt


class StatusBar(QWidget):
    """
    状态栏组件
    
    显示当前状态信息和进度条
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置界面"""
        self.setStyleSheet("""
            StatusBar {
                background-color: #F5F5F5;
                border-top: 1px solid #CCCCCC;
            }
        """)
        self.setFixedHeight(32)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # 状态指示器
        self.status_indicator = QLabel("●")
        self.status_indicator.setFixedWidth(20)
        self.status_indicator.setStyleSheet("color: #28A745; font-size: 14px;")
        layout.addWidget(self.status_indicator)
        
        # 状态文本
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #333333;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        self.status_label.setMinimumWidth(120)
        layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: #E0E0E0;
                text-align: center;
                height: 18px;
                color: #333333;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #81C784);
                border-radius: 3px;
            }
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar, 1)
        
        # 进度文本
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 11px;
            }
        """)
        self.progress_label.setMinimumWidth(200)
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)
        
        # 弹性空间
        layout.addStretch()
    
    def set_status(self, message: str, status_type: str = "ready"):
        """
        设置状态
        
        Args:
            message: 状态消息
            status_type: 状态类型 ('ready', 'working', 'error', 'success')
        """
        color_map = {
            'ready': '#28A745',
            'working': '#FFC107',
            'error': '#DC3545',
            'success': '#28A745'
        }
        color = color_map.get(status_type, '#28A745')
        
        self.status_indicator.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.status_label.setText(message)
        QApplication.processEvents()
    
    def show_progress(self, visible: bool = True):
        """显示/隐藏进度条"""
        self.progress_bar.setVisible(visible)
        self.progress_label.setVisible(visible)
        
        if not visible:
            self.progress_bar.setValue(0)
            self.progress_label.setText("")
        
        QApplication.processEvents()
    
    def update_progress(self, current: int, total: int, message: str = ""):
        """
        更新进度
        
        Args:
            current: 当前进度
            total: 总进度
            message: 进度消息
        """
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)
        
        self.progress_label.setText(message)
        QApplication.processEvents()
    
    def cleanup(self):
        """清理资源"""
        pass
