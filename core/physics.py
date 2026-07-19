"""THz 光谱与光学参数计算。"""

from dataclasses import dataclass

import numpy as np

from .preprocessing import PreparedSignals


C_LIGHT = 3e8


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


def calculate_optical_properties(
    signals: PreparedSignals,
    thickness_mm: float,
) -> OpticalPropertyData:
    """由预处理后的时域信号计算频谱和光学参数。"""
    thickness_mm = float(thickness_mm)
    if not np.isfinite(thickness_mm) or thickness_mm <= 0:
        raise ValueError("样品厚度必须为正数")

    point_count = len(signals.time)
    if point_count < 2:
        raise ValueError("信号至少需要两个数据点")
    if any(len(sample) != point_count for sample in signals.samples):
        raise ValueError("预处理后的信号长度不一致")

    sample_interval_ps = float(signals.time[1] - signals.time[0])
    if not np.isfinite(sample_interval_ps) or sample_interval_ps == 0:
        raise ValueError("时间采样间隔必须为非零有限值")

    frequency = _frequency_axis(point_count, sample_interval_ps)
    reference_fft = _one_sided_fft(signals.reference, len(frequency))
    reference_fft_magnitude = np.abs(reference_fft / point_count)

    sample_fft_magnitudes = []
    refractive_indices = []
    extinction_coefficients = []
    absorption_coefficients = []
    dielectric_real = []
    dielectric_imag = []
    loss_tangents = []

    for sample in signals.samples:
        sample_fft = _one_sided_fft(sample, len(frequency))
        sample_fft_magnitudes.append(np.abs(sample_fft / point_count))

        optical_values = _calculate_sample_properties(
            frequency,
            reference_fft,
            sample_fft,
            thickness_mm,
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
    )


def _frequency_axis(point_count: int, sample_interval_ps: float) -> np.ndarray:
    sample_rate_thz = 1.0 / sample_interval_ps
    frequency_step_thz = sample_rate_thz / point_count
    return frequency_step_thz * np.arange(point_count // 2 + 1)


def _one_sided_fft(signal: np.ndarray, frequency_count: int) -> np.ndarray:
    return np.fft.fft(signal)[:frequency_count]


def _calculate_sample_properties(
    frequency: np.ndarray,
    reference_fft: np.ndarray,
    sample_fft: np.ndarray,
    thickness_mm: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    thickness_m = thickness_mm * 1e-3
    angular_frequency = 2 * np.pi * frequency * 1e12

    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        transfer_function = sample_fft / reference_fft
        magnitude = np.abs(transfer_function)
        phase = np.unwrap(np.angle(transfer_function))

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