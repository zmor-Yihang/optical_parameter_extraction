#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日志界面桥接模块

把 'THzAnalyzer' logger 的日志流转发到主窗口左下角的日志面板。
日志可能来自工作线程（如计算/保存线程），通过 Qt 信号投递到主线程，
保证 QPlainTextEdit 只在主线程被写入。
"""

import logging
from html import escape

from PyQt6.QtCore import QObject, pyqtSignal


class LogViewHandler(logging.Handler, QObject):
    """把 'THzAnalyzer' logger 的记录转发为日志面板的显示信号。"""

    # (格式化后的消息, 小写级别名)
    message_appended = pyqtSignal(str, str)

    def __init__(self, parent=None):
        logging.Handler.__init__(self)
        QObject.__init__(self, parent)
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        self.setLevel(logging.DEBUG)

    def emit(self, record):
        try:
            message = self.format(record)
            self.message_appended.emit(message, record.levelname.lower())
        except Exception:
            self.handleError(record)


# 日志级别对应的显示颜色（配合白色面板）
LEVEL_COLORS = {
    "debug": "#999999",
    "info": "#333333",
    "warning": "#B8860B",
    "error": "#C62828",
    "critical": "#B71C1C",
}


def log_line_html(message: str, level: str) -> str:
    """把一条日志格式化为带颜色的 HTML 行。"""
    color = LEVEL_COLORS.get(level, "#DCDCDC")
    return f'<span style="color:{color};">{escape(message)}</span>'
