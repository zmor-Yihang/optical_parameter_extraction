"""时域信号对齐与窗函数预处理。"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from .signal_loading import LoadedMeasurementSet
from .window_functions import apply_tukey_window, tukey


WindowParameters = Mapping[str, float]

#: 估计基线时最多取主脉冲之前多少比例的采样点
BASELINE_MAX_FRACTION = 0.05


@dataclass(frozen=True)
class PreparedSignals:
    """具有统一时间轴、可直接进入物理计算的信号。"""

    time: np.ndarray
    reference_original: np.ndarray
    reference: np.ndarray
    samples: tuple[np.ndarray, ...]
    sample_names: tuple[str, ...]
    warnings: tuple[str, ...]


def remove_baseline(amplitude: np.ndarray) -> np.ndarray:
    """扣除时域直流偏置。

    用主脉冲到达之前的一段求均值再扣除。BT-FTS5500 导出的波形普遍带有
    十几个计数的直流偏置，不扣掉会在频谱最低几个频点引入虚假的直流分量，
    污染低频端的幅度与相位。
    """
    values = np.asarray(amplitude, dtype=float)
    if values.size < 16:
        return values - float(np.mean(values))
    peak_index = int(np.argmax(np.abs(values - np.median(values))))
    count = max(8, min(peak_index // 2, int(values.size * BASELINE_MAX_FRACTION)))
    return values - float(np.mean(values[:count]))


def preprocess_measurements(
    measurements: LoadedMeasurementSet,
    use_window: bool = False,
    ref_window_params: WindowParameters | None = None,
    per_sample_window_params: Sequence[WindowParameters | None] | None = None,
    remove_dc: bool = True,
) -> PreparedSignals:
    """统一信号长度，扣除直流偏置，并按配置应用 Tukey 窗。

    参数:
        remove_dc: 是否扣除时域直流偏置（默认开启）。设为 False 退回旧行为。
    """
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

    window_warnings: list[str] = []

    time = _copy_prefix(measurements.reference.time, target_length)
    reference_original = _copy_prefix(
        measurements.reference.amplitude,
        target_length,
    )
    if remove_dc:
        reference_original = remove_baseline(reference_original)
    ref_params = ref_window_params if use_window else None
    window_warnings.extend(_check_window_covers_pulse(time, reference_original, ref_params, "参考信号"))
    reference = _apply_configured_window(time, reference_original, ref_params)

    prepared_samples_list = []
    for index, sample in enumerate(measurements.samples):
        amplitude = _prepare_amplitude(sample.amplitude, target_length, remove_dc)
        params = (
            _sample_window_params(per_sample_window_params, index)
            if use_window
            else None
        )
        window_warnings.extend(
            _check_window_covers_pulse(time, amplitude, params, sample.name)
        )
        prepared_samples_list.append(
            _apply_configured_window(time, amplitude, params)
        )
    prepared_samples = tuple(prepared_samples_list)

    return PreparedSignals(
        time=time,
        reference_original=reference_original,
        reference=reference,
        samples=prepared_samples,
        sample_names=tuple(sample.name for sample in measurements.samples),
        warnings=warnings + tuple(window_warnings),
    )


def _check_window_covers_pulse(
    time: np.ndarray,
    amplitude: np.ndarray,
    parameters: WindowParameters | None,
    name: str,
) -> list[str]:
    """检查主脉冲是否被 Tukey 窗削弱，是则给出警告。

    只判断"峰是否在窗口内"是不够的：Tukey 窗两端各有 alpha/2 的余弦渐变区，
    alpha=0.5 时首尾各 25% 的长度都在衰减。主脉冲哪怕落在窗口里，只要落进
    渐变区就会被明显压低，得到的光学参数不可信，而界面上看不出任何异常。

    这里直接算出主脉冲位置上的实际窗函数权重，低于 0.9 就提示。
    """
    if parameters is None or time.size < 2:
        return []

    t_start = float(parameters.get("t_start", float(time[0])))
    t_end = float(parameters.get("t_end", float(time[-1])))
    alpha = float(parameters.get("alpha", 0.5))
    if t_end <= t_start:
        return [f"{name}: 窗口起止时间无效（{t_start:.2f} ~ {t_end:.2f} ps）"]

    peak_index = int(np.argmax(np.abs(amplitude - np.median(amplitude))))
    peak_time = float(time[peak_index])

    mask = (time >= t_start) & (time <= t_end)
    if not mask[peak_index]:
        return [
            f"{name}: 主脉冲位于 {peak_time:.2f} ps，落在窗口 "
            f"{t_start:.2f} ~ {t_end:.2f} ps 之外，结果不可信，请调整窗口范围"
        ]

    weights = tukey(int(mask.sum()), alpha)
    position = int(np.count_nonzero(mask[:peak_index]))
    if position >= weights.size:
        return []
    weight = float(weights[position])
    if weight < 0.9:
        return [
            f"{name}: 主脉冲位于 {peak_time:.2f} ps，落在窗口 "
            f"{t_start:.2f} ~ {t_end:.2f} ps 的渐变区内（幅度被压到 "
            f"{weight * 100:.0f}%），结果不可信，请放宽窗口或减小 alpha"
        ]
    return []


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


def _prepare_amplitude(
    values: np.ndarray,
    length: int,
    remove_dc: bool,
) -> np.ndarray:
    prepared = _copy_prefix(values, length)
    return remove_baseline(prepared) if remove_dc else prepared


def _copy_prefix(values: np.ndarray, length: int) -> np.ndarray:
    return np.array(values[:length], dtype=float, copy=True)
