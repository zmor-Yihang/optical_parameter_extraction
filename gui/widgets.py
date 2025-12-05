#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自定义控件模块

包含项目中使用的自定义Qt控件
"""

import math
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QLinearGradient, QColor, QBrush


class AnimatedBackgroundWidget(QWidget):
    """动态背景组件，显示浅蓝色到浅紫色的渐变动画效果"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_angle)
        self.timer.start(50)  # 50ms更新一次
        
    def update_angle(self):
        """更新角度并重绘"""
        self.angle = (self.angle + 2) % 360
        self.update()
        
    def paintEvent(self, event):
        """绘制渐变背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 创建线性渐变
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        
        # 根据角度调整颜色
        angle_rad = self.angle * 3.14159 / 180
        r1 = int(173 + 50 * (1 + math.sin(angle_rad)) / 2)
        g1 = int(216 + 30 * (1 + math.sin(angle_rad + 2.094)) / 2)
        b1 = int(230 + 20 * (1 + math.sin(angle_rad + 4.188)) / 2)
        
        r2 = int(216 + 30 * (1 + math.sin(angle_rad + 1.047)) / 2)
        g2 = int(191 + 40 * (1 + math.sin(angle_rad + 3.141)) / 2)
        b2 = int(216 + 30 * (1 + math.sin(angle_rad + 5.235)) / 2)
        
        r3 = int(230 + 20 * (1 + math.sin(angle_rad + 2.094)) / 2)
        g3 = int(230 + 20 * (1 + math.sin(angle_rad + 4.188)) / 2)
        b3 = int(250 + 5 * (1 + math.sin(angle_rad + 0)) / 2)
        
        color1 = QColor(r1, g1, b1)
        color2 = QColor(r2, g2, b2)
        color3 = QColor(r3, g3, b3)
        
        # 设置渐变色
        gradient.setColorAt(0, color1)
        gradient.setColorAt(0.5, color2)
        gradient.setColorAt(1, color3)
        
        # 绘制
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())


class AnimatedButton(QPushButton):
    """带动画效果的按钮"""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._opacity = 1.0
        self.setup_animations()
    
    def setup_animations(self):
        """设置动画效果"""
        # 透明度动画
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
    
    def enterEvent(self, event):
        """鼠标进入事件"""
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.8)
        self.fade_animation.start()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开事件"""
        self.fade_animation.setStartValue(0.8)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()
        super().leaveEvent(event)
