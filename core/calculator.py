#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""THz 光学参数分析流程编排。"""

from collections.abc import Callable, Sequence
from typing import Any

from matplotlib.figure import Figure

from utils import exception, info, warning

from .exceptions import CalculationError
from .physics import OpticalPropertyData, calculate_optical_properties
from .plotting import (
    create_dielectric_figure,
    create_optical_parameters_figure,
    create_time_frequency_figure,
)
from .preprocessing import PreparedSignals, preprocess_measurements
from .signal_loading import load_measurements


ProgressCallback = Callable[[int, int, str], None]


class CalculationProgress:
    """将分析阶段转换为统一进度回调。"""

    def __init__(self, callback: ProgressCallback | None = None):
        self.callback = callback
        self.total_steps = 0
        self.current_step = 0

    def set_total(self, total: int) -> None:
        self.total_steps = total
        self.current_step = 0

    def update(self, message: str) -> None:
        self.current_step += 1
        if self.callback:
            self.callback(self.current_step, self.total_steps, message)


class CalculationResult:
    """兼容 GUI 的分析结果容器。"""

    def __init__(self):
        self.fig1: Figure | None = None
        self.fig2: Figure | None = None
        self.fig3: Figure | None = None
        self.data: dict[str, Any] | None = None
        self.prepared_signals: PreparedSignals | None = None
        self.properties: OpticalPropertyData | None = None
        self.warnings: list[str] = []
        self.success = False


def calculate_optical_params(
    ref_file: str,
    sam_files: Sequence[str],
    sam_names: Sequence[str],
    d: float,
    start_row: int = 1,
    use_window: bool = False,
    ref_window_params: dict[str, float] | None = None,
    per_sample_window_params: Sequence[dict[str, float] | None] | None = None,
    per_sample_thickness: Sequence[float | None] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> CalculationResult:
    """
    执行加载、预处理和物理计算。

    不在此创建 Matplotlib Figure，避免后台线程触发 GUI 后端警告。
    图表请在主线程调用 build_result_figures。
    """
    result = CalculationResult()
    progress = CalculationProgress(progress_callback)
    # 参考 + 各样品 + 预处理 + FFT + 完成
    progress.set_total(len(sam_files) + 4)

    try:
        info(f"开始计算光学参数，样品数量: {len(sam_files)}")

        measurements = load_measurements(
            ref_file=ref_file,
            sam_files=sam_files,
            sam_names=sam_names,
            start_row=start_row,
            progress_reporter=progress.update,
        )

        progress.update("预处理信号...")
        prepared_signals = preprocess_measurements(
            measurements,
            use_window=use_window,
            ref_window_params=ref_window_params,
            per_sample_window_params=per_sample_window_params,
        )
        _record_warnings(result, prepared_signals.warnings)
        if use_window and ref_window_params:
            info("参考信号窗函数已应用")

        progress.update("执行FFT及光学参数计算...")
        properties = calculate_optical_properties(
            prepared_signals,
            d,
            per_sample_thickness_mm=per_sample_thickness,
        )

        result.prepared_signals = prepared_signals
        result.properties = properties
        result.data = _build_result_data(
            prepared_signals,
            properties,
            measurements=measurements,
            thickness=d,
            use_window=use_window,
            per_sample_thickness=per_sample_thickness,
        )
        result.success = True
        progress.update("计算完成")
        info("光学参数计算完成")
        return result
    except Exception as exc:
        exception(f"计算过程中出错: {exc}")
        raise CalculationError(str(exc)) from exc


def build_result_figures(result: CalculationResult) -> CalculationResult:
    """
    在 GUI 主线程根据计算结果生成图表。

    必须在主线程调用；后台线程只负责 calculate_optical_params。
    """
    if not result.success or result.prepared_signals is None or result.properties is None:
        return result

    prepared_signals = result.prepared_signals
    properties = result.properties

    result.fig1 = create_time_frequency_figure(prepared_signals, properties)
    result.fig2 = create_optical_parameters_figure(
        prepared_signals.sample_names,
        properties,
    )
    result.fig3 = create_dielectric_figure(
        prepared_signals.sample_names,
        properties,
    )
    return result


def _record_warnings(result: CalculationResult, warnings: Sequence[str]) -> None:
    for message in warnings:
        result.warnings.append(message)
        warning(message)


def _build_result_data(
    prepared_signals: PreparedSignals,
    properties: OpticalPropertyData,
    measurements=None,
    thickness: float | None = None,
    use_window: bool = False,
    per_sample_thickness: Sequence[float | None] | None = None,
) -> dict[str, Any]:
    """组装当前 GUI 和导出模块依赖的兼容数据结构。"""
    source_files: dict[str, str] = {}
    if measurements is not None:
        source_files["reference"] = measurements.reference.path
        for sample in measurements.samples:
            source_files[sample.name] = sample.path

    return {
        "thickness": thickness,
        "use_window": use_window,
        "per_sample_thickness": list(per_sample_thickness) if per_sample_thickness else None,
        "source_files": source_files,
        "F": properties.frequency,
        "Nsam": list(properties.refractive_indices),
        "Ksam": list(properties.extinction_coefficients),
        "Asam": list(properties.absorption_coefficients),
        "Epsilon_real": list(properties.dielectric_real),
        "Epsilon_imag": list(properties.dielectric_imag),
        "TanDelta": list(properties.loss_tangents),
        "sam_names": list(prepared_signals.sample_names),
        "time_data": prepared_signals.time,
        "ref_windowed": prepared_signals.reference,
        "samples_windowed": list(prepared_signals.samples),
        "ref_fft": properties.reference_fft_magnitude,
        "samples_fft": list(properties.sample_fft_magnitudes),
    }
