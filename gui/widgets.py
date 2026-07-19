#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自定义控件模块
"""

from PyQt6.QtWidgets import QPushButton


class FlatButton(QPushButton):
    """扁平按钮（无动画）"""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)


# 兼容旧名称
AnimatedButton = FlatButton