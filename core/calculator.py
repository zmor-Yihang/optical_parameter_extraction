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
from .results import AnalysisResult
from .signal_loading import load_measurements
from .standard_format import StandardSignal


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
        #: 供保存/导出层消费的统一结果数据（AnalysisResult，替代旧 dict）
        self.data: AnalysisResult | None = None
        self.prepared_signals: PreparedSignals | None = None
        self.properties: OpticalPropertyData | None = None
        self.warnings: list[str] = []
        self.success = False


def calculate_optical_params(
    ref_file: str,
    sam_files: Sequence[str],
    sam_names: Sequence[str],
    d: float,
    use_window: bool = False,
    ref_window_params: dict[str, float] | None = None,
    per_sample_window_params: Sequence[dict[str, float] | None] | None = None,
    per_sample_thickness: Sequence[float | None] | None = None,
    progress_callback: ProgressCallback | None = None,
    ref_signal: StandardSignal | None = None,
    sam_signals: Sequence[StandardSignal | None] | None = None,
) -> CalculationResult:
    """
    执行加载、预处理和物理计算。

    不在此创建 Matplotlib Figure，避免后台线程触发 GUI 后端警告。
    图表请在主线程调用 build_result_figures。

    参数:
        ref_signal / sam_signals: 可选的、已在 GUI 中标准化过的内存信号。
            传入后跳过重复的文件读取与格式解析（避免二次标准化开销）。
            为 None 的项回退到按对应文件路径从磁盘读取。
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
            progress_reporter=progress.update,
            ref_signal=ref_signal,
            sam_signals=sam_signals,
        )

        progress.update("预处理信号...")
        prepared_signals = preprocess_measurements(
            measurements,
            use_window=use_window,
            ref_window_params=ref_window_params,
            per_sample_window_params=per_sample_window_params,
        )
        _record_warnings(result, prepared_signals.warnings)
        if use_window:
            info("Tukey 窗已启用，时域信号按窗口加窗")
        else:
            info("未启用 Tukey 窗，使用原始时域信号")

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
) -> AnalysisResult:
    """组装供保存/导出层消费的统一结果数据（AnalysisResult）。

    直接持有 numpy 数组，不再转成 Python list；源文件信息来自加载结果。
    """
    source_files: dict[str, str] = {}
    if measurements is not None:
        source_files["reference"] = measurements.reference.path
        for sample in measurements.samples:
            source_files[sample.name] = sample.path

    return AnalysisResult(
        frequency=properties.frequency,
        sample_names=prepared_signals.sample_names,
        refractive_indices=properties.refractive_indices,
        extinction_coefficients=properties.extinction_coefficients,
        absorption_coefficients=properties.absorption_coefficients,
        dielectric_real=properties.dielectric_real,
        dielectric_imag=properties.dielectric_imag,
        loss_tangents=properties.loss_tangents,
        reference_fft_magnitude=properties.reference_fft_magnitude,
        sample_fft_magnitudes=properties.sample_fft_magnitudes,
        time=prepared_signals.time,
        ref_windowed=prepared_signals.reference,
        samples_windowed=prepared_signals.samples,
        source_files=source_files,
        thickness=thickness,
        per_sample_thickness=(
            tuple(per_sample_thickness) if per_sample_thickness else None
        ),
        use_window=use_window,
    )
