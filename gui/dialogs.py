#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
对话框模块
"""

import os
import subprocess
import tempfile

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser, QPushButton,
    QLabel, QGroupBox, QProgressBar, QMessageBox, QPlainTextEdit,
)

from core.version import APP_VERSION
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
<h2 style="color: #333333; text-align: center; margin-bottom: 16px;">THz 时域光谱分析系统 - 使用指南</h2>

<h3 style="color: #444444;">两阶段处理流程</h3>
<p style="line-height: 1.7; margin-left: 8px;">
<b>选择数据</b> —— 直接在左侧选择参考/样品文件（支持原始格式）；<br>
<b>自动标准化</b> —— 选中的原始文件会在后台自动转换为两列标准 txt 并用于计算；<br>
<b>参数计算</b> —— 基于统一格式计算光学参数，结果以 txt 保存。
</p>

<h3 style="color: #444444;">基本流程</h3>
<ol style="line-height: 1.7; margin-left: 16px;">
    <li><b>选择参考/样品文件</b>：在左侧"参考文件""样品文件"区域点击"添加"
        <ul style="margin-left: 12px; margin-top: 4px;">
            <li>支持格式：BT-FTS 时域扫描 txt、Excel (.xlsx/.xls)、CSV、任意分隔符两列文本、以及已导出的标准 txt</li>
            <li>选择后会<b>自动标准化</b>：原始格式被转换为第一列时间(ps)、第二列幅值的标准 txt（暂存于系统临时目录，不在项目目录生成文件夹），分析直接使用这些标准文件；如需保留，用"工具 → 导出标准格式"导出到指定目录</li>
            <li>多扫描文件会自动拆分为多条；样品支持批量添加、删除、清空</li>
        </ul>
    </li>
    <li><b>导出标准格式（工具）</b>：菜单"工具 → 导出标准格式"（快捷键 Ctrl+D）
        <ul style="margin-left: 12px; margin-top: 4px;">
            <li>把当前"参考文件"与"样品文件"中的标准 txt 一次性复制导出</li>
            <li>点击后弹出目录选择框，直接导出到所选目录（无需其他界面配置）</li>
            <li>标准 txt 的注释头记录来源文件、扫描序号、采样参数，保证结果可追溯</li>
        </ul>
    </li>
    <li><b>设置参数</b>：
        <ul style="margin-left: 12px; margin-top: 4px;">
            <li><b>数据起始行</b>：默认"自动检测"（推荐），自动跳过表头定位数值数据；标准 txt 与 BT-FTS 扫描格式自动识别无需设置</li>
            <li><b>样品厚度</b>：输入样品的厚度值（单位：mm），支持历史记录</li>
        </ul>
    </li>
    <li><b>Tukey窗函数</b>（可选）：开启开关后可设置窗函数参数，用于去除多次反射</li>
    <li><b>运行分析</b>：点击"运行分析"按钮开始计算光学参数</li>
    <li><b>保存结果</b>：分析完成后导出 txt —— "保存结果"生成光学参数表，"保存时频域数据"生成 *_时域.txt 与 *_频域.txt</li>
</ol>

<h3 style="color: #444444;">Tukey窗函数设置</h3>
<p style="line-height: 1.7; margin-left: 8px;">
Tukey窗函数用于截取时域信号的特定区域，去除多次反射干扰：<br><br>
• <b>起始时间 (ps)</b>：窗函数作用的起始时间点，应在主脉冲之前<br>
• <b>结束时间 (ps)</b>：窗函数作用的结束时间点，应在第一次反射脉冲之前<br>
• <b>α参数 (0-1)</b>：控制窗函数边缘的平滑程度
</p>
<ul style="line-height: 1.6; margin-left: 24px;">
    <li>α=0：矩形窗，边缘陡峭，频域旁瓣大</li>
    <li>α=1：汉宁窗，边缘平滑，频域旁瓣小</li>
    <li>推荐值：0.3-0.7，兼顾时域截断和频域特性</li>
</ul>
<p style="line-height: 1.7; margin-left: 8px;">
<b>快速设置</b>：可分别为参考信号和样品信号设置不同的窗函数参数
</p>

<h3 style="color: #444444;">结果查看</h3>
<p style="line-height: 1.7; margin-left: 8px;">
分析完成后，右侧面板显示三个标签页：
</p>
<p style="line-height: 1.6; margin-left: 8px;">
• <b>时域和频域信号</b>：上图为时域信号波形，下图为频域幅度谱(dB)<br>
• <b>光学参数</b>：折射率n(ω)、消光系数k(ω)、吸收系数α(ω)<br>
• <b>介电特性</b>：介电常数实部ε'、虚部ε''、介电损耗tanδ<br>
• <b>弹出图表</b>：点击按钮可在独立窗口中查看对应曲线
</p>

<h3 style="color: #444444;">快捷操作</h3>
<p style="line-height: 1.7; margin-left: 8px;">
• <b>拖放文件</b>：直接拖放文件到样品文件列表区域<br>
• <b>F1</b>：打开本帮助对话框<br>
• <b>Ctrl+Q</b>：退出程序<br>
• <b>图表工具栏</b>：每个图表下方有导航工具栏，支持缩放、平移、保存图片<br>
• <b>自动保存</b>：程序会自动保存参数设置到配置文件
</p>

<h3 style="color: #444444;">注意事项</h3>
<p style="line-height: 1.7; margin-left: 8px;">
• <b>数据格式</b>：第一列为时间数据(ps)，第二列为电场振幅数据<br>
• <b>数据一致性</b>：参考文件和样品文件的时间采样点数应一致<br>
• <b>厚度单位</b>：样品厚度必须使用毫米(mm)为单位<br>
• <b>频率范围</b>：默认显示0-5 THz范围，可通过工具栏调整
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
    <p style="color: #777777; font-size: 11pt;">太赫兹光学参数提取工具</p>
</div>

<hr style="border: 1px solid #EEEEEE; margin: 12px 0;">

<table style="width: 100%; margin: 8px 0;">
    <tr><td style="width: 100px; color: #666666;"><b>版本</b></td><td>v@VERSION@</td></tr>
    <tr><td style="color: #666666;"><b>更新日期</b></td><td>2026年8月5日</td></tr>
    <tr><td style="color: #666666;"><b>开发框架</b></td><td>Python 3 + PyQt6 + Matplotlib</td></tr>
</table>

<h3 style="color: #444444; margin-top: 16px;">主要功能</h3>
<ul style="line-height: 1.7; margin-left: 8px;">
    <li><b>时域/频域分析</b>：THz时域信号的FFT变换与频谱分析</li>
    <li><b>光学参数提取</b>：基于传输函数法计算折射率n、消光系数k、吸收系数α</li>
    <li><b>介电特性计算</b>：计算复介电常数ε'、ε''及介电损耗tanδ</li>
    <li><b>Tukey窗函数</b>：可调参数的窗函数，去除多次反射干扰</li>
    <li><b>批量处理</b>：支持同时分析多个样品，自动对比显示</li>
    <li><b>统一数据格式</b>：多来源格式一键转换为两列标准 txt，全流程可追溯</li>
    <li><b>结果导出</b>：所有结果统一保存为 CSV 格式（逗号分隔、带表头）</li>
    <li><b>异步计算</b>：后台线程计算，不阻塞界面</li>
</ul>

<h3 style="color: #444444; margin-top: 12px;">技术原理</h3>
<p style="line-height: 1.6; margin-left: 8px; color: #555555;">
本软件基于THz-TDS（太赫兹时域光谱）技术，通过比较参考信号和样品信号的传输函数，利用相位信息提取折射率，利用幅度信息提取消光系数和吸收系数。
</p>

<hr style="border: 1px solid #EEEEEE; margin: 12px 0;">

<div style="text-align: center; margin-top: 12px;">
    <p style="color: #444444; font-weight: bold; font-size: 11pt;">南京航空航天大学</p>
    <p style="color: #666666;">高电压与绝缘技术实验室</p>
    <p style="color: #888888; font-size: 9pt; margin-top: 4px;">Nanjing University of Aeronautics and Astronautics</p>
</div>

<p style="text-align: center; margin-top: 16px; color: #999999; font-size: 9pt;">
© 2025 THz光学参数分析系统. All rights reserved.
</p>
"""

        text_browser.setHtml(about_html.replace("@VERSION@", APP_VERSION))
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
        self.changelog_browser.setOpenExternalLinks(False)
        self.changelog_browser.setPlainText(self.update_info.changelog or "暂无更新说明")
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
        """下载失败回调。"""
        self._reset_buttons()
        QMessageBox.critical(
            self, "下载失败",
            f"更新包下载失败：\n{message}\n\n"
            f"可手动访问以下地址下载安装：\n{self.update_info.download_url}",
        )

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