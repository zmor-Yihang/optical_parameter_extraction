#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
坐标范围手动设置条

为单个 matplotlib FigureCanvas 提供交互式 X/Y 轴显示范围控制：
- 支持按子图（axes）独立设置坐标范围
- X / Y 的最小值、最大值输入框，留空表示保持当前范围
- 填写后点「应用」才生效，输入过程不改变图表
- 「自动」按钮恢复绘图时的初始默认显示范围，并回填真实范围

实现只调用 matplotlib 公开接口（Axes.get_xlim / get_ylim / set_xlim /
set_ylim / Figure.draw_idle），与 NavigationToolbar、
多子图、共享轴等现有绘图能力完全兼容，不依赖任何绘图内部实现。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


def _parse_float(text: str) -> float | None:
    """把输入框文本解析为浮点数；空串或非法值返回 None（表示保持当前）。"""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class AxisRangeBar(QWidget):
    """手动设置 matplotlib 坐标轴显示范围的交互控件条。"""

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.figure = canvas.figure
        self._updating = False
        # 记录绘图完成时的初始显示范围，「自动」按钮据此复原
        self._default_limits = {
            ax: (ax.get_xlim(), ax.get_ylim()) for ax in self.figure.axes
        }
        self.setStyleSheet(
            "AxisRangeBar { background-color: #F7F7F7; border: 1px solid #E0E0E0;"
            " border-radius: 3px; }"
            "AxisRangeBar QLineEdit { background-color: #FFFFFF; }"
        )
        self._setup_ui()
        self._refresh_axes_combo()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(5)

        title = QLabel("坐标范围")
        title.setToolTip(
            "手动设置图表显示范围：\n"
            "· X 轴范围 / Y 轴范围 分组，每组最小/最大值可独立填写，留空表示保持当前\n"
            "· 填写后点「应用」生效，输入过程不改变图表\n"
            "· 「子图」可选择要设置范围的单个子图\n"
            "· 「自动」恢复绘图时的初始默认显示范围"
        )
        title.setStyleSheet("color: #555555; font-weight: bold;")
        layout.addWidget(title)

        layout.addWidget(QLabel("子图:"))
        self.axes_combo = QComboBox()
        self.axes_combo.setMinimumWidth(110)
        self.axes_combo.currentIndexChanged.connect(
            lambda _index: self._sync_from_axes()
        )
        layout.addWidget(self.axes_combo)

        layout.addSpacing(8)
        x_label = QLabel("X 轴范围:")
        x_label.setStyleSheet("color: #555555;")
        layout.addWidget(x_label)
        self.xmin_edit = self._make_edit(layout, "Xmin", "X 轴最小值（留空 = 保持当前）")
        self.xmax_edit = self._make_edit(layout, "Xmax", "X 轴最大值（留空 = 保持当前）")

        layout.addSpacing(4)
        y_label = QLabel("Y 轴范围:")
        y_label.setStyleSheet("color: #555555;")
        layout.addWidget(y_label)
        self.ymin_edit = self._make_edit(layout, "Ymin", "Y 轴最小值（留空 = 保持当前）")
        self.ymax_edit = self._make_edit(layout, "Ymax", "Y 轴最大值（留空 = 保持当前）")

        layout.addSpacing(8)
        apply_btn = QPushButton("应用")
        apply_btn.clicked.connect(self._apply)
        layout.addWidget(apply_btn)

        auto_btn = QPushButton("自动")
        auto_btn.setToolTip("恢复初始默认显示范围")
        auto_btn.clicked.connect(self._auto)
        layout.addWidget(auto_btn)

        layout.addStretch()

    def _make_edit(self, layout: QHBoxLayout, short: str, long_tip: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setFixedWidth(58)
        edit.setPlaceholderText(short)
        edit.setToolTip(long_tip)
        edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(edit)
        return edit

    # ------------------------------------------------------------------
    # 子图选择
    # ------------------------------------------------------------------
    def _refresh_axes_combo(self):
        """枚举当前 Figure 的全部子图，供单个子图独立设置范围。"""
        self._updating = True
        try:
            self.axes_combo.clear()
            for index, ax in enumerate(self.figure.axes):
                title = (ax.get_title() or "").strip()
                label = title if len(title) <= 10 else title[:9] + "…"
                text = f"子图{index + 1}: {label}" if label else f"子图{index + 1}"
                self.axes_combo.addItem(text, ax)
        finally:
            self._updating = False
        self._sync_from_axes()

    def _selected_axes(self) -> list:
        """返回当前选择要应用的 Axes 列表（仅单个子图）。"""
        target = self.axes_combo.currentData()
        return [target] if target is not None else []

    # ------------------------------------------------------------------
    # 范围应用
    # ------------------------------------------------------------------
    def _apply(self):
        """把输入框中的范围应用到选中的子图。"""
        if self._updating:
            return
        xmin = _parse_float(self.xmin_edit.text())
        xmax = _parse_float(self.xmax_edit.text())
        ymin = _parse_float(self.ymin_edit.text())
        ymax = _parse_float(self.ymax_edit.text())
        if xmin is None and xmax is None and ymin is None and ymax is None:
            return

        for ax in self._selected_axes():
            if xmin is not None or xmax is not None:
                lo, hi = ax.get_xlim()
                if xmin is not None:
                    lo = xmin
                if xmax is not None:
                    hi = xmax
                if lo < hi:
                    ax.set_xlim(lo, hi)
            if ymin is not None or ymax is not None:
                lo, hi = ax.get_ylim()
                if ymin is not None:
                    lo = ymin
                if ymax is not None:
                    hi = ymax
                if lo < hi:
                    ax.set_ylim(lo, hi)
        self.canvas.draw_idle()

    def _auto(self):
        """恢复绘图时的初始默认显示范围，并把真实范围回填到输入框。"""
        for ax in self._selected_axes():
            limits = self._default_limits.get(ax)
            if limits is not None:
                ax.set_xlim(*limits[0])
                ax.set_ylim(*limits[1])
            else:
                # 控件创建后新增的子图没有快照，退回数据自适应
                ax.relim()
                ax.autoscale(enable=True, axis="both")
                ax.autoscale_view()
        self.canvas.draw_idle()
        self._sync_from_axes()

    def _sync_from_axes(self):
        """把当前选中子图的真实显示范围回填到输入框。"""
        self._updating = True
        try:
            axes = self._selected_axes()
            if not axes:
                for edit in (self.xmin_edit, self.xmax_edit, self.ymin_edit, self.ymax_edit):
                    edit.clear()
                return
            ax = axes[-1]
            xlo, xhi = ax.get_xlim()
            ylo, yhi = ax.get_ylim()
            self.xmin_edit.setText(f"{xlo:g}")
            self.xmax_edit.setText(f"{xhi:g}")
            self.ymin_edit.setText(f"{ylo:g}")
            self.ymax_edit.setText(f"{yhi:g}")
        finally:
            self._updating = False
