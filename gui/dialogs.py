#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
对话框模块
"""

import os
import subprocess
import tempfile
from datetime import datetime
from html import escape

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser, QPushButton,
    QLabel, QGroupBox, QProgressBar, QMessageBox, QPlainTextEdit,
)

from core.version import APP_VERSION, INSTALLER_DOWNLOAD_URL
from core.updater import UpdateInfo, sha256_of
from utils import info

from .update_checker import UpdateDownloadWorker


class HelpDialog(QDialog):
    """帮助对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("使用说明")
        self.setMinimumSize(650, 550)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; }")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setStyleSheet(
            "QTextBrowser { border: none; background-color: #FFFFFF; font-size: 10pt; color: #333333; }"
        )

        help_html = """
<h2 style="color: #333333; text-align: center; margin-bottom: 16px;">THz 时域光谱分析系统 - 使用说明</h2>

<h3 style="color: #444444;">基本流程</h3>
<ol style="line-height: 1.7; margin-left: 16px;">
    <li><b>选择参考/样品文件</b>：在左侧「参考文件」「样品文件」区域点击「添加」，或把文件拖进对应列表框；支持 BT-FTS 时域 txt、两列 Excel / txt。若程序无法识别，请先自行整理为两列标准格式（时间 ps、幅值）后再导入</li>
    <li><b>设置参数</b>：样品厚度（mm，支持逐样品设置）；如需去除多次反射，可开启 Tukey 窗函数并设置范围</li>
    <li><b>运行分析</b>：点击「运行分析」开始计算，右侧三个标签页分别显示时域/频域、光学参数、介电特性图表</li>
    <li><b>保存结果</b>：「保存光学参数」导出光学参数表，「保存时域数据」「保存频域数据」分别导出时域/频域 Excel</li>
</ol>

<h3 style="color: #444444;">其他</h3>
<p style="line-height: 1.7; margin-left: 8px;">
• <b>检查更新</b>：菜单「帮助 → 检查更新」
</p>

<h3 style="color: #444444;">注意事项</h3>
<p style="line-height: 1.7; margin-left: 8px;">
• 标准数据为两列：第一列时间（ps），第二列电场振幅，可保存为 Excel（.xlsx）或 txt<br>
• 参考与样品文件的采样点数应一致，不一致时程序自动截断并给出警告<br>
• 样品厚度单位为毫米（mm）
</p>
"""

        text_browser.setHtml(help_html)
        layout.addWidget(text_browser)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_btn = QPushButton("确定")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F5;
                color: #333333;
                border: 1px solid #D0D0D0;
                border-radius: 3px;
                padding: 6px 24px;
            }
            QPushButton:hover {
                background-color: #EBEBEB;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)


STANDARD_FORMAT_GUIDE_HTML = """
<h3 style="color: #333333; margin-top: 0;">请先整理为两列数据</h3>
<p style="line-height: 1.7; color: #555555;">
只需两列：第 1 列时间，第 2 列幅值。保存为 Excel（.xlsx）或 txt / csv 后重新添加。
</p>
<table border="1" cellspacing="0" cellpadding="6" style="border-collapse: collapse; color: #333333;">
    <tr style="background-color: #EFEFEF;">
        <th>时间 Time[ps]</th>
        <th>幅值 Amplitude</th>
    </tr>
    <tr><td align="right">0.000</td><td align="right">-1.23e-04</td></tr>
    <tr><td align="right">0.033</td><td align="right">2.45e-03</td></tr>
    <tr><td align="right">0.066</td><td align="right">3.10e-03</td></tr>
    <tr><td align="right">0.099</td><td align="right">1.87e-03</td></tr>
</p>
"""


class FormatGuideDialog(QDialog):
    """文件格式无法识别时，引导用户自行转换为标准 Excel / txt。"""

    def __init__(self, failed_items: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("请转换为标准格式")
        self.setMinimumSize(560, 460)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; }")
        self._failed_items = [item for item in (failed_items or []) if item]
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setStyleSheet(
            "QTextBrowser { border: none; background-color: #FFFFFF; font-size: 10pt; color: #333333; }"
        )
        parts = [STANDARD_FORMAT_GUIDE_HTML]
        if self._failed_items:
            preview = "<br>".join(
                f"• {item}" for item in self._failed_items[:8]
            )
            extra = (
                f"<br>…另有 {len(self._failed_items) - 8} 个文件"
                if len(self._failed_items) > 8
                else ""
            )
            parts.insert(
                0,
                "<p style='color:#B85C5C; line-height:1.7;'>"
                f"<b>以下文件无法识别：</b><br>{preview}{extra}</p>",
            )
        browser.setHtml("".join(parts))
        layout.addWidget(browser, 1)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_btn = QPushButton("知道了")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F5;
                color: #333333;
                border: 1px solid #D0D0D0;
                border-radius: 3px;
                padding: 6px 24px;
            }
            QPushButton:hover {
                background-color: #EBEBEB;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)


class AboutDialog(QDialog):
    """关于对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于")
        self.setMinimumSize(500, 420)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; }")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setStyleSheet(
            "QTextBrowser { border: none; background-color: #FFFFFF; font-size: 10pt; color: #333333; }"
        )

        about_html = """
<div style="text-align: center;">
    <h2 style="color: #333333; margin-bottom: 8px;">THz 时域光谱分析系统</h2>
    <p style="color: #777777; font-size: 11pt;">太赫兹时域光谱（THz-TDS）光学参数提取工具</p>
</div>

<hr style="border: 1px solid #EEEEEE; margin: 12px 0;">

<table style="width: 100%; margin: 8px 0;">
    <tr><td style="width: 100px; color: #666666;"><b>版本</b></td><td>v@VERSION@</td></tr>
    <tr><td style="color: #666666;"><b>开发框架</b></td><td>Python 3 + PyQt6 + Matplotlib</td></tr>
</table>

<h3 style="color: #444444; margin-top: 12px;">简介</h3>
<p style="line-height: 1.6; margin-left: 8px; color: #555555;">
基于 THz-TDS 技术，通过比较参考与样品信号的传输函数，提取折射率、消光系数、吸收系数及介电特性，支持批量分析与结果导出。
</p>

<hr style="border: 1px solid #EEEEEE; margin: 12px 0;">

<div style="text-align: center; margin-top: 12px;">
    <p style="color: #444444; font-weight: bold; font-size: 11pt;">南京航空航天大学</p>
    <p style="color: #666666;">高电压与绝缘技术实验室</p>
    <p style="color: #888888; font-size: 9pt; margin-top: 4px;">Nanjing University of Aeronautics and Astronautics</p>
</div>

<p style="text-align: center; margin-top: 16px; color: #999999; font-size: 9pt;">
© @YEAR@ THz光学参数分析系统. All rights reserved.
</p>
"""

        text_browser.setHtml(
            about_html.replace("@VERSION@", APP_VERSION).replace(
                "@YEAR@", str(datetime.now().year)
            )
        )
        layout.addWidget(text_browser)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_btn = QPushButton("确定")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F5;
                color: #333333;
                border: 1px solid #D0D0D0;
                border-radius: 3px;
                padding: 6px 24px;
            }
            QPushButton:hover {
                background-color: #EBEBEB;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)


def manual_download_html(prefix: str = "", url: str = "") -> str:
    """生成含可点击下载地址的富文本（供更新对话框与下载失败提示复用）。

    url 缺省时回退到内置的安装包下载地址；传入 url 可适配自定义更新源。
    """
    url = url or INSTALLER_DOWNLOAD_URL
    return (
        f'<span style="font-size:9pt; color:#666666;">{prefix}'
        f'<a href="{url}" style="color:#1565C0;">{url}</a></span>'
    )


class UpdateDialog(QDialog):
    """新版本提示与在线更新对话框。

    提供「立即更新」（下载 → SHA256 校验 → 启动安装程序）与「稍后」两种操作；
    点击立即更新并确认后，通过 install_requested 信号请求主窗口退出。
    """

    install_requested = pyqtSignal()

    def __init__(self, update_info: UpdateInfo, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.download_worker = None
        self.setWindowTitle("发现新版本")
        self.setMinimumSize(540, 460)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; }")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QLabel(f"发现新版本 v{self.update_info.version}")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-size: 15pt; font-weight: bold; color: #2E7D32;")
        layout.addWidget(header)

        current_label = QLabel(f"当前版本 v{APP_VERSION}")
        current_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        current_label.setStyleSheet("color: #777777; font-size: 10pt;")
        layout.addWidget(current_label)

        if self.update_info.release_date:
            date_label = QLabel(f"发布日期：{self.update_info.release_date}")
            date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            date_label.setStyleSheet("color: #666666; font-size: 9pt;")
            layout.addWidget(date_label)

        changelog_group = QGroupBox("更新内容")
        changelog_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #FFFFFF;
                color: #333333;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: #555555;
            }
        """)
        cl_layout = QVBoxLayout(changelog_group)
        self.changelog_browser = QTextBrowser()
        self.changelog_browser.setOpenExternalLinks(True)
        # 更新内容 + 可点击的手动下载地址，同处一个提示框内
        changelog_text = escape(
            self.update_info.changelog or "暂无更新说明"
        ).replace("\n", "<br>")
        self.changelog_browser.setHtml(
            f"<div>{changelog_text}</div>"
            f"<div style=\"margin-top:8px;\">"
            + manual_download_html("自动更新失败？可手动下载：", self.update_info.download_url)
            + "</div>"
        )
        self.changelog_browser.setStyleSheet(
            "QTextBrowser { border: none; background-color: #FAFAFA; font-size: 10pt; color: #333333; }"
        )
        cl_layout.addWidget(self.changelog_browser)
        layout.addWidget(changelog_group, 1)

        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        self.status_label.setStyleSheet("color: #666666; font-size: 9pt;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(14)
        layout.addWidget(self.progress_bar)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.later_btn = QPushButton("稍后")
        self.later_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F5;
                color: #333333;
                border: 1px solid #D0D0D0;
                border-radius: 3px;
                padding: 6px 24px;
            }
            QPushButton:hover {
                background-color: #EBEBEB;
            }
            QPushButton:disabled {
                color: #A0A0A0;
            }
        """)
        self.later_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.later_btn)

        self.update_btn = QPushButton("立即更新")
        self.update_btn.setStyleSheet("""
            QPushButton {
                background-color: #2E7D32;
                color: #FFFFFF;
                border: none;
                border-radius: 3px;
                padding: 6px 24px;
            }
            QPushButton:hover {
                background-color: #256B29;
            }
            QPushButton:disabled {
                background-color: #A0A0A0;
            }
        """)
        self.update_btn.clicked.connect(self._start_download)
        button_layout.addWidget(self.update_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _start_download(self):
        """开始下载安装包到系统临时目录。"""
        dest_dir = os.path.join(tempfile.gettempdir(), "THzAnalyzer_update")
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, "install.exe")

        self.update_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("正在下载更新...")

        self.download_worker = UpdateDownloadWorker(
            self.update_info.download_url, dest_path, self
        )
        self.download_worker.progress_updated.connect(self._on_download_progress)
        self.download_worker.download_finished.connect(self._on_download_finished)
        self.download_worker.download_error.connect(self._on_download_error)
        self.download_worker.start()

    def _is_downloading(self) -> bool:
        worker = self.download_worker
        try:
            return worker is not None and worker.isRunning()
        except RuntimeError:
            return False

    def reject(self):
        if self._is_downloading():
            self.download_worker.requestInterruption()
            self.download_worker.wait(1500)
        super().reject()

    def closeEvent(self, event):
        if self._is_downloading():
            self.download_worker.requestInterruption()
            self.download_worker.wait(1500)
        super().closeEvent(event)

    def _on_download_progress(self, downloaded: int, total: int):
        """下载进度回调。"""
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(downloaded)
            percent = int(downloaded / total * 100)
            self.status_label.setText(f"正在下载更新... {percent}%")
        else:
            self.progress_bar.setRange(0, 0)

    def _on_download_error(self, message: str):
        """下载失败回调：提示错误并给出可点击的手动下载地址。"""
        self._reset_buttons()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("下载失败")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(f"更新包下载失败：<br>{escape(message)}")
        box.setInformativeText(
            manual_download_html("可手动下载安装包：", self.update_info.download_url)
        )
        # QMessageBox 中的链接默认不可点击，需对每个文本标签开启外部链接
        for label in box.findChildren(QLabel):
            label.setOpenExternalLinks(True)
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextBrowserInteraction
            )
        box.exec()

    def _on_download_finished(self, dest_path: str):
        """下载完成：校验完整性，确认后启动安装程序。"""
        # SHA256 完整性校验（更新源提供时）
        if self.update_info.sha256:
            try:
                actual = sha256_of(dest_path)
            except OSError as exc:
                QMessageBox.critical(self, "校验失败", f"无法读取已下载文件：{exc}")
                self._reset_buttons()
                return
            if actual.lower() != self.update_info.sha256.lower():
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
                QMessageBox.critical(
                    self, "校验失败",
                    "安装包校验失败（文件可能已损坏），请稍后重试或手动下载安装。",
                )
                self._reset_buttons()
                return

        ret = QMessageBox.question(
            self, "确认更新",
            "更新将关闭当前程序并启动安装向导。\n"
            "请按安装向导完成升级，升级后需重新打开本软件。\n\n是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ret != QMessageBox.StandardButton.Yes:
            self._reset_buttons()
            return

        try:
            subprocess.Popen([dest_path], cwd=tempfile.gettempdir())
        except OSError as exc:
            QMessageBox.critical(self, "启动失败", f"无法启动安装程序：\n{exc}")
            self._reset_buttons()
            return

        info("已启动更新安装程序，程序即将退出")
        self.install_requested.emit()
        self.accept()

    def _reset_buttons(self):
        """恢复按钮与进度显示到初始状态。"""
        self.update_btn.setEnabled(True)
        self.later_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)


class LogDialog(QDialog):
    """运行日志查看窗口（非模态，从菜单栏「日志」打开）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("运行日志")
        self.setMinimumSize(640, 400)
        self.resize(720, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        self.log_view.setStyleSheet("""
            QPlainTextEdit {
                background-color: #FFFFFF;
                color: #333333;
                font-family: Consolas, "Courier New", monospace;
                font-size: 11px;
                border: 1px solid #D0D0D0;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.log_view, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        clear_btn = QPushButton("清空显示")
        clear_btn.setToolTip("仅清空当前窗口显示，不影响日志文件")
        clear_btn.clicked.connect(self.log_view.clear)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

    def append_html(self, html: str):
        """追加一行带颜色的日志。"""
        self.log_view.appendHtml(html)