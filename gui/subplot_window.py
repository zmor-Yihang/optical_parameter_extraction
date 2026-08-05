#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
子图详情查看窗口

以非模态窗口展示每个结果子图的标题、放大图表与关键指标摘要：
- 顶部导航：下拉框 + 「上一个 / 下一个」按钮切换不同子图
- 中部：当前子图的放大可视化图表
- 底部：子图标题、轴范围、曲线数量与每条曲线的 min / max / mean 摘要

窗口为独立顶级窗口，可拖动标题栏、可拖边缘调整大小；以 show() 非模态
方式弹出，主界面背景保持可见、可继续操作。

图表与摘要基于进入窗口时的数据快照渲染，不依赖主窗口 Figure 存活，
与 matplotlib 现有绘图接口及多子图 / 多 Figure 结构完全兼容。
"""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .axis_range import AxisRangeBar

#: 曲线数量超过该值时不再绘制图例，避免遮挡
LEGEND_LIMIT = 12


def _snapshot_figures(figures: dict[str, Figure]) -> list[dict]:
    """把各 Figure 的子图数据与元信息打成快照列表。"""
    entries = []
    for fig_name, figure in figures.items():
        if figure is None:
            continue
        for index, ax in enumerate(figure.axes):
            title = (ax.get_title() or "").strip()
            entries.append(
                {
                    "figure": fig_name,
                    "title": title or f"子图 {index + 1}",
                    "xlabel": ax.get_xlabel(),
                    "ylabel": ax.get_ylabel(),
                    "xlim": tuple(float(v) for v in ax.get_xlim()),
                    "ylim": tuple(float(v) for v in ax.get_ylim()),
                    "lines": [
                        {
                            "x": line.get_xdata(),
                            "y": line.get_ydata(),
                            "color": line.get_color(),
                            "linestyle": line.get_linestyle(),
                            "linewidth": float(line.get_linewidth() or 1.0),
                            "label": line.get_label(),
                        }
                        for line in ax.get_lines()
                    ],
                }
            )
    return entries


class SubplotDetailWindow(QWidget):
    """子图详情查看窗口（非模态，支持拖拽与调整大小）。"""

    def __init__(self, figures: dict[str, Figure], parent=None):
        super().__init__(parent)
        self._entries = _snapshot_figures(figures)
        self._canvas = None
        self._toolbar = None
        self._axis_bar = None

        self.setWindowTitle("子图详情")
        self.setMinimumSize(820, 520)
        self.resize(1040, 640)
        # 独立顶级窗口：可拖动标题栏、可调整大小；非模态，主界面保持可见
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowModality(Qt.WindowModality.NonModal)

        self._setup_ui()
        self._populate_nav()
        if self._entries:
            self._show_index(0)
        else:
            self.nav_combo.setEnabled(False)
            self.summary_text.setPlainText("没有可展示的子图数据，请先运行分析。")

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # 导航栏
        nav = QHBoxLayout()
        nav.setSpacing(6)
        nav.addWidget(QLabel("子图:"))
        self.nav_combo = QComboBox()
        self.nav_combo.currentIndexChanged.connect(self._show_index)
        nav.addWidget(self.nav_combo, 1)

        prev_btn = QPushButton("上一个")
        prev_btn.clicked.connect(lambda: self._step(-1))
        nav.addWidget(prev_btn)
        next_btn = QPushButton("下一个")
        next_btn.clicked.connect(lambda: self._step(1))
        nav.addWidget(next_btn)
        root.addLayout(nav)

        # 左右分割：左边信息，右边图
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # 左：信息面板（标题 + 关键指标摘要）
        info_panel = QWidget()
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(4, 4, 8, 4)
        info_layout.setSpacing(8)

        self.title_label = QLabel("")
        title_font = self.title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(11)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #333333;")
        self.title_label.setWordWrap(True)
        info_layout.addWidget(self.title_label)

        self.summary_text = QTextBrowser()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMinimumWidth(260)
        self.summary_text.setStyleSheet(
            "QTextBrowser { background-color: #FAFAFA; border: 1px solid #E0E0E0;"
            " border-radius: 3px; font-size: 10pt; }"
        )
        info_layout.addWidget(self.summary_text, 1)
        splitter.addWidget(info_panel)

        # 右：图面板（matplotlib 工具栏 + 图表）
        self.plot_container = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_container)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(self.plot_container)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 720])
        root.addWidget(splitter, 1)

    def _populate_nav(self):
        self.nav_combo.blockSignals(True)
        try:
            self.nav_combo.clear()
            for entry in self._entries:
                self.nav_combo.addItem(entry["title"])
        finally:
            self.nav_combo.blockSignals(False)

    def _step(self, delta: int):
        count = self.nav_combo.count()
        if count == 0:
            return
        self.nav_combo.setCurrentIndex(
            (self.nav_combo.currentIndex() + delta) % count
        )

    # ------------------------------------------------------------------
    # 内容渲染
    # ------------------------------------------------------------------
    def _show_index(self, index: int):
        if not self._entries or not (0 <= index < len(self._entries)):
            return
        entry = self._entries[index]
        self._rebuild_plot(entry)
        self.title_label.setText(entry["title"])
        self.summary_text.setHtml(self._summary_html(entry))

    def _rebuild_plot(self, entry: dict):
        if self._canvas is not None:
            self._canvas.setParent(None)
            self._canvas.deleteLater()
            self._canvas = None
        if self._toolbar is not None:
            self._toolbar.setParent(None)
            self._toolbar.deleteLater()
            self._toolbar = None
        if self._axis_bar is not None:
            self._axis_bar.setParent(None)
            self._axis_bar.deleteLater()
            self._axis_bar = None

        figure = Figure(figsize=(7.2, 4.6))
        figure.patch.set_facecolor("#FFFFFF")
        axis = figure.add_subplot(1, 1, 1)
        axis.set_facecolor("#F8F8F8")
        for line in entry["lines"]:
            axis.plot(
                line["x"],
                line["y"],
                color=line["color"],
                linestyle=line["linestyle"],
                linewidth=line["linewidth"],
                label=line["label"],
            )
        axis.set_title(entry["title"])
        axis.set_xlabel(entry["xlabel"])
        axis.set_ylabel(entry["ylabel"])
        axis.set_xlim(*entry["xlim"])
        axis.set_ylim(*entry["ylim"])
        axis.grid(True)

        labels = [
            line["label"]
            for line in entry["lines"]
            if line["label"] and not str(line["label"]).startswith("_")
        ]
        if labels and len(labels) <= LEGEND_LIMIT:
            axis.legend(loc="best", fontsize=8)
        figure.tight_layout()

        canvas = FigureCanvas(figure)
        # matplotlib 自带导航工具栏：放大 / 缩小 / 拖拽平移 / 复位 / 保存图片
        toolbar = NavigationToolbar(canvas, self.plot_container)
        # 自定义坐标范围条：X/Y 量程手动设置（填写后点「应用」生效，「自动」复原）
        axis_bar = AxisRangeBar(canvas)
        self.plot_layout.addWidget(toolbar)
        self.plot_layout.addWidget(axis_bar)
        self.plot_layout.addWidget(canvas)
        self._toolbar = toolbar
        self._axis_bar = axis_bar
        self._canvas = canvas

    def _summary_html(self, entry: dict) -> str:
        parts = [
            f"<b>子图标题：</b>{entry['title']}",
            f"<b>X 范围：</b>[{entry['xlim'][0]:.4g}, {entry['xlim'][1]:.4g}]",
            f"<b>Y 范围：</b>[{entry['ylim'][0]:.4g}, {entry['ylim'][1]:.4g}]",
            f"<b>曲线数量：</b>{len(entry['lines'])}",
        ]
        lines_html = []
        for index, line in enumerate(entry["lines"], start=1):
            values = np.asarray(line["y"], dtype=float)
            label = str(line["label"])
            if not label or label.startswith("_"):
                label = f"曲线 {index}"
            block = [f"• <b>{label}</b>"]
            finite = np.isfinite(values)
            if finite.any():
                valid = values[finite]
                block.append(f"&nbsp;&nbsp;点数：{len(values)}")
                block.append(f"&nbsp;&nbsp;min：{valid.min():.4g}")
                block.append(f"&nbsp;&nbsp;max：{valid.max():.4g}")
                block.append(f"&nbsp;&nbsp;mean：{valid.mean():.4g}")
            else:
                block.append("&nbsp;&nbsp;无有效数值")
            lines_html.append("<br>".join(block))
        if lines_html:
            parts.append("<b>曲线摘要：</b><br>" + "<br>".join(lines_html))
        return "<br>".join(parts)
