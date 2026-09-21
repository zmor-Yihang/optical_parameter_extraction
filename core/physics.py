"""THz 光谱与光学参数计算。"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .preprocessing import PreparedSignals
from .standard_format import LIGHT_SPEED_UM_PER_PS


#: 真空光速 (m/s)。与 standard_format 的时间轴换算共用同一个常量，
#: 避免两处取值不一致导致折射率出现约 0.07% 的系统偏差。
C_LIGHT = LIGHT_SPEED_UM_PER_PS * 1e6

#: 相位分支拟合默认使用的频段占比：取参考谱高于峰值 -25 dB 的连续区间
PHASE_FIT_REF_DB = -25.0
#: 样品谱需高出噪声本底的余量 (dB)
PHASE_FIT_SNR_DB = 10.0
#: 分支拟合的频率下限 (THz)，低于此频率相位精度不足
PHASE_FIT_MIN_THZ = 0.1
#: 估计噪声本底用的高频段 (THz)。BT-FTS5500 的数据在 ~7 THz 以上被数字滤波，
#: 该段是干净的噪声平台；若频率轴到不了这里则退化为最高频 10%。
NOISE_BAND_THZ = (5.0, 6.8)
#: 相位分支拟合和噪声估计所需的最小数据点数
PHASE_FIT_MIN_POINTS = 8
NOISE_ESTIMATION_MIN_POINTS = 16


@dataclass(frozen=True)
class OpticalPropertyData:
    """不包含展示逻辑的光学参数计算结果。"""

    frequency: np.ndarray
    reference_fft_magnitude: np.ndarray
    sample_fft_magnitudes: tuple[np.ndarray, ...]
    refractive_indices: tuple[np.ndarray, ...]
    extinction_coefficients: tuple[np.ndarray, ...]
    absorption_coefficients: tuple[np.ndarray, ...]
    dielectric_real: tuple[np.ndarray, ...]
    dielectric_imag: tuple[np.ndarray, ...]
    loss_tangents: tuple[np.ndarray, ...]
    #: 每个样品实际用于 2π 分支判定的频段 (THz)，便于在日志/界面中追溯
    phase_fit_bands: tuple[tuple[float, float], ...] = ()


def calculate_optical_properties(
    signals: PreparedSignals,
    thickness_mm: float,
    correct_phase_branch: bool = True,
    per_sample_thickness_mm: Sequence[float | None] | None = None,
) -> OpticalPropertyData:
    """由预处理后的时域信号计算频谱和光学参数。

    参数:
        correct_phase_branch: 是否消除相位解缠的 2π 整数倍歧义（默认开启）。
            关掉即退回旧行为，仅用于结果对比。
        per_sample_thickness_mm: 与 signals.samples 一一对应的每个样品厚度(mm)。
            为 None 或某项为 None/非正数时，该项回退到 thickness_mm。
    """
    thickness_mm = float(thickness_mm)
    if not np.isfinite(thickness_mm) or thickness_mm <= 0:
        raise ValueError("样品厚度必须为正数")
    if per_sample_thickness_mm is not None:
        _validate_per_sample_thickness(thickness_mm, per_sample_thickness_mm)

    point_count = len(signals.time)
    if point_count < 2:
        raise ValueError("信号至少需要两个数据点")
    if any(len(sample) != point_count for sample in signals.samples):
        raise ValueError("预处理后的信号长度不一致")

    sample_interval_ps = float(signals.time[1] - signals.time[0])
    if not np.isfinite(sample_interval_ps) or sample_interval_ps == 0:
        raise ValueError("时间采样间隔必须为非零有限值")

    frequency = _frequency_axis(point_count, sample_interval_ps)
    reference_fft = _one_sided_fft(signals.reference)
    reference_fft_magnitude = np.abs(reference_fft / point_count)

    noise_floor = _estimate_noise_floor(reference_fft_magnitude, frequency)

    sample_fft_magnitudes = []
    refractive_indices = []
    extinction_coefficients = []
    absorption_coefficients = []
    dielectric_real = []
    dielectric_imag = []
    loss_tangents = []
    phase_fit_bands = []

    for index, sample in enumerate(signals.samples):
        sample_fft = _one_sided_fft(sample)
        sample_magnitude = np.abs(sample_fft / point_count)
        sample_fft_magnitudes.append(sample_magnitude)

        band = _suggest_phase_band(
            frequency,
            reference_fft_magnitude,
            sample_magnitude,
            noise_floor,
        )
        phase_fit_bands.append(band)

        sample_thickness_mm = _sample_thickness(
            thickness_mm,
            per_sample_thickness_mm,
            index,
        )
        optical_values = _calculate_sample_properties(
            frequency,
            reference_fft,
            sample_fft,
            sample_thickness_mm,
            phase_band=band if correct_phase_branch else None,
        )
        refractive_indices.append(optical_values[0])
        extinction_coefficients.append(optical_values[1])
        absorption_coefficients.append(optical_values[2])
        dielectric_real.append(optical_values[3])
        dielectric_imag.append(optical_values[4])
        loss_tangents.append(optical_values[5])

    return OpticalPropertyData(
        frequency=frequency,
        reference_fft_magnitude=reference_fft_magnitude,
        sample_fft_magnitudes=tuple(sample_fft_magnitudes),
        refractive_indices=tuple(refractive_indices),
        extinction_coefficients=tuple(extinction_coefficients),
        absorption_coefficients=tuple(absorption_coefficients),
        dielectric_real=tuple(dielectric_real),
        dielectric_imag=tuple(dielectric_imag),
        loss_tangents=tuple(loss_tangents),
        phase_fit_bands=tuple(phase_fit_bands),
    )


def _validate_per_sample_thickness(
    default_mm: float,
    per_sample_mm: Sequence[float | None],
) -> None:
    """校验每样品厚度列表中的显式值（None 表示回退默认值）。"""
    for index, value in enumerate(per_sample_mm):
        if value is None:
            continue
        value = float(value)
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"第 {index + 1} 个样品的厚度必须为正数，当前为 {value}")


def _sample_thickness(
    default_mm: float,
    per_sample_mm: Sequence[float | None] | None,
    index: int,
) -> float:
    """取第 index 个样品的实际厚度：优先使用单独设置，否则回退全局默认。"""
    if per_sample_mm is None:
        return default_mm
    if index >= len(per_sample_mm):
        return default_mm
    value = per_sample_mm[index]
    if value is None:
        return default_mm
    value = float(value)
    if not np.isfinite(value) or value <= 0:
        return default_mm
    return value


def _frequency_axis(point_count: int, sample_interval_ps: float) -> np.ndarray:
    sample_rate_thz = 1.0 / sample_interval_ps
    frequency_step_thz = sample_rate_thz / point_count
    return frequency_step_thz * np.arange(point_count // 2 + 1)


def _one_sided_fft(signal: np.ndarray) -> np.ndarray:
    """实数信号的单边频谱。

    原实现是 np.fft.fft(signal)[:n]，即算完整复数谱再丢一半；
    改用 rfft 后运算量和内存都减半，数值完全等价。
    rfft 已经只返回单边频谱，无需切片。
    """
    return np.fft.rfft(signal)


# ---------------------------------------------------------------------------
# 相位分支（2π）修正
# ---------------------------------------------------------------------------

def _estimate_noise_floor(magnitude: np.ndarray, frequency: np.ndarray) -> float:
    """用高频"无信号"平台估计噪声本底幅度。"""
    mask = (frequency >= NOISE_BAND_THZ[0]) & (frequency <= NOISE_BAND_THZ[1])
    if mask.sum() < NOISE_ESTIMATION_MIN_POINTS:
        mask = frequency >= frequency[-1] * 0.9
    if not mask.any():
        return 0.0
    return float(np.median(magnitude[mask]))


def _suggest_phase_band(
    frequency: np.ndarray,
    reference_magnitude: np.ndarray,
    sample_magnitude: np.ndarray,
    noise_floor: float,
) -> tuple[float, float]:
    """自动选出适合做分支拟合的频段：样品谱明显高于噪声本底的连续区间。

    厚样品/强吸收样品会自动得到更窄的区间，避免用噪声段去拟合分支。
    """
    if frequency.size < PHASE_FIT_MIN_POINTS:
        return (0.0, 0.0)

    good = frequency >= PHASE_FIT_MIN_THZ
    good &= reference_magnitude > reference_magnitude.max() * 10 ** (PHASE_FIT_REF_DB / 20.0)
    if noise_floor > 0:
        good &= sample_magnitude > noise_floor * 10 ** (PHASE_FIT_SNR_DB / 20.0)

    index = np.flatnonzero(good)
    if index.size < PHASE_FIT_MIN_POINTS:
        # 退化：取谱峰附近 1/4 频段
        peak = int(np.argmax(reference_magnitude))
        lo = max(1, peak // 2)
        hi = min(frequency.size - 1, peak * 2)
        return (float(frequency[lo]), float(frequency[hi]))

    # 取包含样品谱峰的那一段连续区间
    peak = int(np.argmax(sample_magnitude))
    pos = int(np.clip(np.searchsorted(index, peak), 0, index.size - 1))
    lo = hi = pos
    while lo > 0 and index[lo] - index[lo - 1] == 1:
        lo -= 1
    while hi < index.size - 1 and index[hi + 1] - index[hi] == 1:
        hi += 1
    return (float(frequency[index[lo]]), float(frequency[index[hi]]))


def _unwrap_phase(
    frequency: np.ndarray,
    transfer_function: np.ndarray,
    phase_band: tuple[float, float] | None,
    max_iterations: int = 5,
) -> np.ndarray:
    """解缠相位，并消除 2π 整数倍的分支歧义。

    np.unwrap 只保证相邻点连续，不保证整体落在正确的分支上。厚样品尤其危险：
    4 mm 量级的复合材料时延可达十几 ps，相位在分析频段内要跨十几个 2π，
    低频端信噪比稍差就可能整体偏一个周期，而曲线看上去依然平滑正常。

    物理约束：ν→0 时样品与参考的相位差必须趋于 0。因此在高信噪比频段内
    做线性拟合，把外推到 ν=0 的截距归零即可确定正确分支。
    """
    phase = np.unwrap(np.angle(transfer_function))
    if phase_band is None:
        return phase

    low, high = phase_band
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        return phase

    mask = (frequency >= low) & (frequency <= high)
    if mask.sum() < PHASE_FIT_MIN_POINTS:
        return phase

    x = frequency[mask]
    for _ in range(max_iterations):
        y = phase[mask]
        if not np.all(np.isfinite(y)):
            break
        slope, intercept = np.polyfit(x, y, 1)
        offset = np.round(intercept / (2.0 * np.pi))
        if offset == 0:
            break
        phase = phase - 2.0 * np.pi * offset
    return phase


def _calculate_sample_properties(
    frequency: np.ndarray,
    reference_fft: np.ndarray,
    sample_fft: np.ndarray,
    thickness_mm: float,
    phase_band: tuple[float, float] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    thickness_m = thickness_mm * 1e-3
    angular_frequency = 2 * np.pi * frequency * 1e12

    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        transfer_function = sample_fft / reference_fft
        magnitude = np.abs(transfer_function)
        phase = _unwrap_phase(frequency, transfer_function, phase_band)

        refractive_index = 1 - phase * C_LIGHT / (
            angular_frequency * thickness_m
        )
        extinction_coefficient = (
            np.log(
                4
                * refractive_index
                / magnitude
                / ((refractive_index + 1) ** 2)
            )
            * C_LIGHT
            / (angular_frequency * thickness_m)
        )
        absorption_coefficient = (
            2 * angular_frequency * extinction_coefficient / C_LIGHT / 100
        )

    refractive_index = _replace_dc_value(refractive_index, 1.0)
    extinction_coefficient = _replace_dc_value(extinction_coefficient, 0.0)
    absorption_coefficient = _replace_dc_value(absorption_coefficient, 0.0)

    epsilon_real = refractive_index**2 - extinction_coefficient**2
    epsilon_imag = 2 * refractive_index * extinction_coefficient
    with np.errstate(divide="ignore", invalid="ignore"):
        loss_tangent = np.divide(
            epsilon_imag,
            epsilon_real,
            out=np.zeros_like(epsilon_real),
            where=epsilon_real != 0,
        )

    return (
        refractive_index,
        extinction_coefficient,
        absorption_coefficient,
        epsilon_real,
        epsilon_imag,
        loss_tangent,
    )


def _replace_dc_value(values: np.ndarray, single_value: float) -> np.ndarray:
    result = values.copy()
    result[0] = result[1] if len(result) > 1 else single_value
    return result
