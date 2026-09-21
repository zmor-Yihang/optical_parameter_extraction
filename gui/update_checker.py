#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新检查/下载工作线程：在后台执行网络请求，避免阻塞 GUI。
"""

from PyQt6.QtCore import QThread, pyqtSignal

from core.updater import (
    UpdateInfo,
    UpdateNotFoundError,
    fetch_update_info,
    download_file,
)


class UpdateCheckWorker(QThread):
    """后台检查是否有新版本。"""

    check_finished = pyqtSignal(object)   # UpdateInfo
    check_not_found = pyqtSignal(str)     # 更新源不可用（无版本发布）
    check_error = pyqtSignal(str)         # 其他错误

    def __init__(self, source_url: str, current_version: str, parent=None):
        super().__init__(parent)
        self.source_url = source_url
        self.current_version = current_version

    def run(self):
        try:
            update_info = fetch_update_info(self.source_url)
            self.check_finished.emit(update_info)
        except UpdateNotFoundError as exc:
            self.check_not_found.emit(str(exc))
        except Exception as exc:
            self.check_error.emit(str(exc))


class UpdateDownloadWorker(QThread):
    """后台下载更新安装包。"""

    progress_updated = pyqtSignal(int, int)  # 已下载字节, 总字节
    download_finished = pyqtSignal(str)      # 保存路径
    download_error = pyqtSignal(str)         # 错误信息

    def __init__(self, url: str, dest_path: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.dest_path = dest_path

    def run(self):
        try:
            download_file(
                self.url,
                self.dest_path,
                self.progress_updated.emit,
                cancel_callback=self.isInterruptionRequested,
            )
            if self.isInterruptionRequested():
                return
            self.download_finished.emit(self.dest_path)
        except Exception as exc:
            if self.isInterruptionRequested():
                return
            self.download_error.emit(str(exc))
