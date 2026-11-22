"""THz 分析结果绘图。"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import matplotlib
import numpy as np
from matplotlib.backend_bases import MouseEvent
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from .physics import OpticalPropertyData
from .preprocessing import PreparedSignals

# 与 utils.matplotlib_setup 保持一致，避免本模块导入时把标题字号改回去
matplotlib.rcParams["axes.titlesize"] = 12

COLORS = (
    "red",
    "blue",
    "green",
    "purple",
    "orange",
    "brown",
    "pink",
    "gray",
    "olive",
    "cyan",
)

# 超过该数量时不在 Figure 内绘制图例，改由侧边颜色与悬停提示标识
LEGEND_INLINE_LIMIT = 12
SHORT_NAME_MAX_LEN = 28


def sample_color(index: int) -> str:
    """返回第 index 个样品的稳定颜色。"""
    return COLORS[index % len(COLORS)]


def short_display_name(name: str, max_len: int = SHORT_NAME_MAX_LEN) -> str:
    """列表与图例用的短名称。"""
    text = str(name).strip()
    if len(text) <= max_len:
        return text
    if max_len <= 1:
        return text[:max_len]
    return text[: max_len - 1] + "…"


def create_time_frequency_figure(
    signals: PreparedSignals,
    properties: OpticalPropertyData,
) -> Figure:
    """创建时域与频域信号图。"""
    figure = Figure(figsize=(9, 7))

    short_names = tuple(short_display_name(name) for name in signals.sample_names)
    reference_color = matplotlib.rcParams.get("text.color", "#17263B")

    time_axis = figure.add_subplot(2, 1, 1)
    for index, sample in enumerate(signals.samples):
        time_axis.plot(
            signals.time,
            sample,
            color=sample_color(index),
            linewidth=1.2,
            label=short_names[index],
            gid=signals.sample_names[index],
        )
    time_axis.plot(
        signals.time,
        signals.reference,
        color=reference_color,
        linewidth=2,
        label="参考信号",
        gid="参考信号",
    )
    time_axis.grid(True)
    time_axis.set_title("时域信号")
    time_axis.set_xlabel("延迟 (ps)")
    time_axis.set_ylabel("振幅")

    frequency_axis = figure.add_subplot(2, 1, 2)
    frequency_axis.plot(
        properties.frequency,
        _magnitude_to_db(properties.reference_fft_magnitude),
        color=reference_color,
        linewidth=2,
        label="参考信号",
        gid="参考信号",
    )
    for index, magnitude in enumerate(properties.sample_fft_magnitudes):
        frequency_axis.plot(
            properties.frequency,
            _magnitude_to_db(magnitude),
            color=sample_color(index),
            linewidth=1.2,
            label=short_names[index],
            gid=signals.sample_names[index],
        )
    frequency_axis.grid(True)
    frequency_axis.set_title("频域信号")
    frequency_axis.set_xlabel("频率 (THz)")
    frequency_axis.set_ylabel("振幅 (dB)")
    frequency_axis.set_xlim(0, 5)
    frequency_axis.autoscale(axis="y")

    _layout_figure(figure, sample_count=len(signals.samples))
    return figure


def create_optical_parameters_figure(
    sample_names: tuple[str, ...],
    properties: OpticalPropertyData,
) -> Figure:
    """创建折射率、消光系数和吸收系数图。"""
    figure = Figure(figsize=(9, 10))
    short_names = tuple(short_display_name(name) for name in sample_names)

    _plot_comparison_axis(
        figure.add_subplot(3, 1, 1),
        properties.frequency,
        properties.refractive_indices,
        short_names,
        full_names=sample_names,
        title="折射率",
        ylabel="折射率",
        with_labels=True,
    )
    _plot_comparison_axis(
        figure.add_subplot(3, 1, 2),
        properties.frequency,
        properties.extinction_coefficients,
        short_names,
        full_names=sample_names,
        title="消光系数",
        ylabel="消光系数",
        with_labels=False,
    )
    _plot_comparison_axis(
        figure.add_subplot(3, 1, 3),
        properties.frequency,
        properties.absorption_coefficients,
        short_names,
        full_names=sample_names,
        title="吸收系数",
        ylabel="吸收系数 (cm^-1)",
        with_labels=False,
    )

    _layout_figure(figure, sample_count=len(sample_names))
    return figure


def create_dielectric_figure(
    sample_names: tuple[str, ...],
    properties: OpticalPropertyData,
) -> Figure:
    """创建介电常数和介电损耗图。"""
    figure = Figure(figsize=(9, 10))
    short_names = tuple(short_display_name(name) for name in sample_names)

    _plot_comparison_axis(
        figure.add_subplot(3, 1, 1),
        properties.frequency,
        properties.dielectric_real,
        short_names,
        full_names=sample_names,
        title="介电常数实部",
        ylabel="介电常数实部 ε'",
        with_labels=True,
    )
    _plot_comparison_axis(
        figure.add_subplot(3, 1, 2),
        properties.frequency,
        properties.dielectric_imag,
        short_names,
        full_names=sample_names,
        title='介电常数虚部',
        ylabel='介电常数虚部 ε"',
        with_labels=False,
    )
    _plot_comparison_axis(
        figure.add_subplot(3, 1, 3),
        properties.frequency,
        properties.loss_tangents,
        short_names,
        full_names=sample_names,
        title="介电损耗",
        ylabel="介电损耗 tan δ",
        with_labels=False,
    )

    _layout_figure(figure, sample_count=len(sample_names))
    return figure


def create_single_series_figure(
    title: str,
    xlabel: str,
    ylabel: str,
    frequency: np.ndarray | None,
    series: Sequence[np.ndarray],
    sample_names: Sequence[str],
    *,
    xlim: tuple[float, float] | None = (0, 5),
    source_lines: Sequence[Line2D] | None = None,
) -> Figure:
    """创建弹出窗口用的单图（复用图例策略）。"""
    figure = Figure(figsize=(10, 6))
    axis = figure.add_subplot(1, 1, 1)

    reference_labels = {"参考信号"}

    if source_lines is not None:
        sample_count = 0
        for line in source_lines:
            full_name = str(line.get_gid() or line.get_label())
            if full_name in reference_labels:
                axis.plot(
                    line.get_xdata(),
                    line.get_ydata(),
                    color=line.get_color(),
                    linewidth=line.get_linewidth() or 2.0,
                    label=full_name,
                    gid=full_name,
                )
            else:
                axis.plot(
                    line.get_xdata(),
                    line.get_ydata(),
                    color=line.get_color(),
                    linewidth=line.get_linewidth() or 1.2,
                    label=short_display_name(full_name),
                    gid=full_name,
                )
                sample_count += 1
    else:
        sample_count = len(sample_names)
        short_names = [short_display_name(name) for name in sample_names]
        for index, values in enumerate(series):
            axis.plot(
                frequency,
                values,
                color=sample_color(index),
                linewidth=1.2,
                label=short_names[index],
                gid=sample_names[index],
            )

    axis.set_title(title)
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    axis.grid(True)
    if xlim is not None:
        axis.set_xlim(*xlim)
        axis.autoscale(axis="y")

    _layout_figure(figure, sample_count=sample_count)
    return figure


def enable_curve_hover(canvas) -> Callable[[], None]:
    """悬停显示样品全名，并返回切换视图时可用的清除函数。"""
    annotation = canvas.figure.text(
        0.02,
        0.96,
        "",
        va="top",
        ha="left",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#D5DFEB"},
        visible=False,
        zorder=1000,
    )
    annotation.set_in_layout(False)

    def clear(_event=None) -> None:
        if annotation.get_visible():
            annotation.set_visible(False)
            canvas.draw_idle()

    def on_move(event: MouseEvent) -> None:
        axis = event.inaxes
        if axis is not None and axis.get_visible():
            for line in axis.get_lines():
                if not line.get_visible() or not line.contains(event)[0]:
                    continue
                label = str(line.get_gid() or line.get_label())
                if (not annotation.get_visible() or annotation.get_text() != label
                        or annotation.get_transform() is not axis.transAxes):
                    annotation.set_text(label)
                    annotation.set_transform(axis.transAxes)
                    annotation.set_visible(True)
                    canvas.draw_idle()
                return
        clear()

    canvas.mpl_connect("motion_notify_event", on_move)
    canvas.mpl_connect("figure_leave_event", clear)
    return clear


def _plot_comparison_axis(
    axis,
    frequency: np.ndarray,
    values: tuple[np.ndarray, ...],
    short_names: Sequence[str],
    full_names: Sequence[str],
    title: str,
    ylabel: str,
    with_labels: bool,
) -> None:
    for index, sample_values in enumerate(values):
        axis.plot(
            frequency,
            sample_values,
            color=sample_color(index),
            linewidth=1.2,
            label=short_names[index] if with_labels else "_nolegend_",
            gid=full_names[index],
        )
    axis.set_xlabel("频率 (THz)")
    axis.set_ylabel(ylabel)
    axis.set_title(title)
    axis.grid(True)
    axis.set_xlim(0, 5)
    axis.autoscale(axis="y")


def _layout_figure(figure: Figure, sample_count: int) -> None:
    """自适应留出标题、刻度和图例空间，不随窗口缩小字号。"""
    figure.set_layout_engine("constrained", w_pad=0.12, h_pad=0.07, hspace=0.02)
    if sample_count > LEGEND_INLINE_LIMIT:
        return

    handles: list[Line2D] = []
    labels: list[str] = []
    seen: set[str] = set()

    for axis in figure.axes:
        axis_handles, axis_labels = axis.get_legend_handles_labels()
        for handle, label in zip(axis_handles, axis_labels):
            if not label or label.startswith("_") or label in seen:
                continue
            seen.add(label)
            handles.append(handle)
            labels.append(label)

    if not handles:
        return

    # 多样品时把图例放到右侧，避免在总览中占用多行子图的高度。
    use_side_legend = len(labels) > 4
    figure.legend(
        handles,
        labels,
        loc="outside right upper" if use_side_legend else "outside upper right",
        ncols=1 if use_side_legend else min(2, len(labels)),
        fontsize=9,
        columnspacing=1.2,
        borderaxespad=0.5,
    )


def _magnitude_to_db(magnitude: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore"):
        return 20 * np.log10(magnitude)
