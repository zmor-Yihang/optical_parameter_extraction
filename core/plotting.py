"""THz 分析结果绘图。"""

from __future__ import annotations

from collections.abc import Sequence

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backend_bases import MouseEvent
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from .physics import OpticalPropertyData
from .preprocessing import PreparedSignals


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
    figure = plt.figure(figsize=(9, 7))
    figure.patch.set_facecolor("#F5F5F5")

    short_names = tuple(short_display_name(name) for name in signals.sample_names)

    time_axis = figure.add_subplot(2, 1, 1)
    time_axis.set_facecolor("#F8F8F8")
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
        "k",
        linewidth=2,
        label="参考信号",
        gid="参考信号",
    )
    time_axis.grid(True)
    time_axis.set_title("时域信号")
    time_axis.set_xlabel("延迟 (ps)")
    time_axis.set_ylabel("振幅")

    frequency_axis = figure.add_subplot(2, 1, 2)
    frequency_axis.set_facecolor("#F8F8F8")
    frequency_axis.plot(
        properties.frequency,
        _magnitude_to_db(properties.reference_fft_magnitude),
        "k",
        linewidth=2,
        label="参考光谱",
        gid="参考光谱",
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

    _apply_shared_legend(figure, sample_count=len(signals.samples))
    figure.tight_layout()
    return figure


def create_optical_parameters_figure(
    sample_names: tuple[str, ...],
    properties: OpticalPropertyData,
) -> Figure:
    """创建折射率、消光系数和吸收系数图。"""
    figure = plt.figure(figsize=(9, 10))
    figure.patch.set_facecolor("#F5F5F5")
    short_names = tuple(short_display_name(name) for name in sample_names)

    _plot_comparison_axis(
        figure.add_subplot(3, 1, 1),
        properties.frequency,
        properties.refractive_indices,
        short_names,
        full_names=sample_names,
        title="折射率对比",
        ylabel="折射率",
        with_labels=True,
    )
    _plot_comparison_axis(
        figure.add_subplot(3, 1, 2),
        properties.frequency,
        properties.extinction_coefficients,
        short_names,
        full_names=sample_names,
        title="消光系数对比",
        ylabel="消光系数",
        with_labels=False,
    )
    _plot_comparison_axis(
        figure.add_subplot(3, 1, 3),
        properties.frequency,
        properties.absorption_coefficients,
        short_names,
        full_names=sample_names,
        title="吸收系数对比",
        ylabel="吸收系数 (cm^-1)",
        with_labels=False,
    )

    _apply_shared_legend(figure, sample_count=len(sample_names))
    figure.tight_layout()
    return figure


def create_dielectric_figure(
    sample_names: tuple[str, ...],
    properties: OpticalPropertyData,
) -> Figure:
    """创建介电常数和介电损耗图。"""
    figure = plt.figure(figsize=(9, 10))
    figure.patch.set_facecolor("#F5F5F5")
    short_names = tuple(short_display_name(name) for name in sample_names)

    _plot_comparison_axis(
        figure.add_subplot(3, 1, 1),
        properties.frequency,
        properties.dielectric_real,
        short_names,
        full_names=sample_names,
        title="介电常数实部对比",
        ylabel="介电常数实部 ε'",
        with_labels=True,
    )
    _plot_comparison_axis(
        figure.add_subplot(3, 1, 2),
        properties.frequency,
        properties.dielectric_imag,
        short_names,
        full_names=sample_names,
        title='介电常数虚部对比',
        ylabel='介电常数虚部 ε"',
        with_labels=False,
    )
    _plot_comparison_axis(
        figure.add_subplot(3, 1, 3),
        properties.frequency,
        properties.loss_tangents,
        short_names,
        full_names=sample_names,
        title="介电损耗对比",
        ylabel="介电损耗 tan δ",
        with_labels=False,
    )

    _apply_shared_legend(figure, sample_count=len(sample_names))
    figure.tight_layout()
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
    figure = plt.figure(figsize=(10, 6))
    figure.patch.set_facecolor("#F5F5F5")
    axis = figure.add_subplot(1, 1, 1)
    axis.set_facecolor("#F8F8F8")

    reference_labels = {"参考信号", "参考光谱"}

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

    _apply_shared_legend(figure, sample_count=sample_count)
    figure.tight_layout()
    return figure


def enable_curve_hover(canvas) -> None:
    """为画布上的曲线启用悬停显示样品全名。"""
    figure = canvas.figure
    annotation = figure.text(
        0.02,
        0.98,
        "",
        transform=figure.transFigure,
        va="top",
        ha="left",
        fontsize=9,
        color="#222222",
        bbox={
            "boxstyle": "round,pad=0.3",
            "facecolor": "#FFFFEE",
            "edgecolor": "#CCCCCC",
            "alpha": 0.92,
        },
        visible=False,
        zorder=1000,
    )
    state = {"annotation": annotation, "last_label": None}

    def on_move(event: MouseEvent) -> None:
        if event.inaxes is None:
            if state["annotation"].get_visible():
                state["annotation"].set_visible(False)
                state["last_label"] = None
                canvas.draw_idle()
            return

        matched_label = None
        for line in event.inaxes.get_lines():
            if not line.get_visible():
                continue
            contains, _ = line.contains(event)
            if contains:
                matched_label = line.get_gid() or line.get_label()
                break

        if matched_label is None:
            if state["annotation"].get_visible():
                state["annotation"].set_visible(False)
                state["last_label"] = None
                canvas.draw_idle()
            return

        if matched_label == state["last_label"] and state["annotation"].get_visible():
            return

        state["last_label"] = matched_label
        state["annotation"].set_text(str(matched_label))
        state["annotation"].set_visible(True)
        canvas.draw_idle()

    canvas.mpl_connect("motion_notify_event", on_move)


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
    axis.set_facecolor("#F8F8F8")
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


def _apply_shared_legend(figure: Figure, sample_count: int) -> None:
    """一张 Figure 最多一个公共图例；样品过多时不绘制图例。"""
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

    figure.legend(
        handles,
        labels,
        loc="upper right",
        fontsize=8,
        framealpha=0.9,
        borderaxespad=0.4,
    )


def _magnitude_to_db(magnitude: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore"):
        return 20 * np.log10(magnitude)