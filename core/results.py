"""THz 分析结果数据模型。

历史实现里，计算结果被 `_build_result_data` 拼成一个巨型 dict
（`Nsam`/`Ksam`/`Asam`... 全部转为 Python list），由 core.data_io 以
`results_data["Nsam"]` 形式消费。该 dict 与保存层强耦合，且反复 list 转换
带来额外内存与拷贝开销。

本模块提供统一的 `AnalysisResult` 容器，直接保存 numpy 数组与元信息，
供 calculator 组装、data_io 保存/导出共同消费，替代原先的 dict 中间体。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class AnalysisResult:
    """一次分析的全部结果数据（保存/导出层直接消费）。

    字段与 `OpticalPropertyData` / `PreparedSignals` / 源文件信息一一对应，
    不再需要把 numpy 数组转成 Python list。
    """

    #: 频率轴 (THz)
    frequency: np.ndarray
    #: 样品名称（与各元组字段一一对应）
    sample_names: tuple[str, ...]
    #: 各光学参数（每项为一个样品、与 frequency 等长的数组）
    refractive_indices: tuple[np.ndarray, ...]
    extinction_coefficients: tuple[np.ndarray, ...]
    absorption_coefficients: tuple[np.ndarray, ...]
    dielectric_real: tuple[np.ndarray, ...]
    dielectric_imag: tuple[np.ndarray, ...]
    loss_tangents: tuple[np.ndarray, ...]
    #: 参考与各样品的频域幅值
    reference_fft_magnitude: np.ndarray
    sample_fft_magnitudes: tuple[np.ndarray, ...]
    #: 预处理后的时域数据（开启 Tukey 时为加窗结果，否则为原始信号）
    time: np.ndarray
    ref_windowed: np.ndarray
    samples_windowed: tuple[np.ndarray, ...]
    #: 源文件路径，键为 "reference" 或样品名
    source_files: dict[str, str] = field(default_factory=dict)

    #: 全局默认厚度 (mm)
    thickness: float | None = None
    #: 逐样品厚度 (mm)，None 表示该项回退全局默认
    per_sample_thickness: tuple[float | None, ...] | None = None
    #: 是否应用了窗函数
    use_window: bool = False
