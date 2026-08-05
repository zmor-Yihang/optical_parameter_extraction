#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
对话框模块
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser, QPushButton
)


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
    <tr><td style="width: 100px; color: #666666;"><b>版本</b></td><td>v4.6.0</td></tr>
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

        text_browser.setHtml(about_html)
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