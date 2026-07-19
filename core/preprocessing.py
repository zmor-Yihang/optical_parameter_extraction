"""时域信号对齐与窗函数预处理。"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from .signal_loading import LoadedMeasurementSet
from .window_functions import apply_tukey_window


WindowParameters = Mapping[str, float]


@dataclass(frozen=True)
class PreparedSignals:
    """具有统一时间轴、可直接进入物理计算的信号。"""

    time: np.ndarray
    reference_original: np.ndarray
    reference: np.ndarray
    samples: tuple[np.ndarray, ...]
    sample_names: tuple[str, ...]
    warnings: tuple[str, ...]


def preprocess_measurements(
    measurements: LoadedMeasurementSet,
    use_window: bool = False,
    ref_window_params: WindowParameters | None = None,
    per_sample_window_params: Sequence[WindowParameters | None] | None = None,
) -> PreparedSignals:
    """统一信号长度，并按配置应用 Tukey 窗。"""
    signals = (measurements.reference, *measurements.samples)
    target_length = min(len(signal.amplitude) for signal in signals)
    if target_length < 2:
        raise ValueError("信号至少需要两个数据点")

    reference_length = len(measurements.reference.amplitude)
    warnings = tuple(
        f"文件 {sample.name} 的数据点数与参考文件不匹配，已自动截断至 {target_length} 个点"
        for sample in measurements.samples
        if len(sample.amplitude) != reference_length
    )

    time = _copy_prefix(measurements.reference.time, target_length)
    reference_original = _copy_prefix(
        measurements.reference.amplitude,
        target_length,
    )
    reference = _apply_configured_window(
        time,
        reference_original,
        ref_window_params if use_window else None,
    )

    prepared_samples = tuple(
        _apply_configured_window(
            time,
            _copy_prefix(sample.amplitude, target_length),
            _sample_window_params(per_sample_window_params, index)
            if use_window
            else None,
        )
        for index, sample in enumerate(measurements.samples)
    )

    return PreparedSignals(
        time=time,
        reference_original=reference_original,
        reference=reference,
        samples=prepared_samples,
        sample_names=tuple(sample.name for sample in measurements.samples),
        warnings=warnings,
    )


def _sample_window_params(
    parameters: Sequence[WindowParameters | None] | None,
    index: int,
) -> WindowParameters | None:
    if parameters is None or index >= len(parameters):
        return None
    return parameters[index]


def _apply_configured_window(
    time: np.ndarray,
    amplitude: np.ndarray,
    parameters: WindowParameters | None,
) -> np.ndarray:
    if parameters is None:
        return amplitude.copy()

    return apply_tukey_window(
        time,
        amplitude,
        parameters.get("t_start", float(time[0])),
        parameters.get("t_end", float(time[-1])),
        parameters.get("alpha", 0.5),
    )


def _copy_prefix(values: np.ndarray, length: int) -> np.ndarray:
    return np.array(values[:length], dtype=float, copy=True)