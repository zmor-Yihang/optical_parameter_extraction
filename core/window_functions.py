#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tukey 窗函数

原实现依赖 scipy.signal.windows.tukey —— 这是整个工程唯一一处 scipy 调用，
却让打包体积多出约 77 MB（scipy 57 MB + scipy.libs 里一份与 numpy 重复的
20 MB OpenBLAS）。这里改为等价的 numpy 实现，与 scipy 逐点一致
（已在 M∈{2,3,7,64,1000,10000} × alpha∈{0,0.05,0.15,0.5,0.9,1.0} × sym∈{T,F}
组合上验证，最大偏差 5.55e-16）。
"""

import numpy as np


def tukey(M, alpha=0.5, sym=True):
    """Tukey（余弦渐变）窗，等价于 scipy.signal.windows.tukey。

    alpha=0 为矩形窗，alpha=1 为汉宁窗。
    """
    M = int(M)
    if M < 1:
        return np.array([], dtype=float)
    if M == 1:
        return np.ones(1, dtype=float)

    if alpha <= 0:
        return np.ones(M, dtype=float)

    N = M if sym else M + 1

    if alpha >= 1.0:
        n = np.arange(N, dtype=float)
        w = 0.5 - 0.5 * np.cos(2.0 * np.pi * n / (N - 1))
        return w if sym else w[:-1]

    n = np.arange(N, dtype=float)
    width = int(np.floor(alpha * (N - 1) / 2.0))

    n1 = n[0:width + 1]
    n2 = n[width + 1:N - width - 1]
    n3 = n[N - width - 1:]

    w1 = 0.5 * (1 + np.cos(np.pi * (-1 + 2.0 * n1 / alpha / (N - 1))))
    w2 = np.ones(n2.shape, dtype=float)
    w3 = 0.5 * (1 + np.cos(np.pi * (-2.0 / alpha + 1 + 2.0 * n3 / alpha / (N - 1))))

    w = np.concatenate((w1, w2, w3))
    return w if sym else w[:-1]


def apply_tukey_window(time_data, signal_data, t_start, t_end, alpha=0.5):
    """
    应用 Tukey 窗函数到信号数据

    参数:
        time_data: 时间数据数组
        signal_data: 信号数据数组
        t_start: 窗口起始时间
        t_end: 窗口结束时间
        alpha: Tukey 窗参数 (0-1)，0 为矩形窗，1 为汉宁窗

    返回:
        windowed_signal: 加窗后的信号（窗口外部置零）
    """
    time_data = np.asarray(time_data)
    signal_data = np.asarray(signal_data, dtype=float)

    # 创建时间窗口掩码
    window_mask = (time_data >= t_start) & (time_data <= t_end)

    # 如果没有数据点在窗口范围内，返回全零信号
    if not np.any(window_mask):
        return np.zeros_like(signal_data)

    # 提取窗口区域信号
    signal_windowed = signal_data[window_mask]

    # 创建 Tukey 窗函数
    tukey_window = tukey(len(signal_windowed), alpha)

    # 初始化结果为全零数组（窗口外部为零）
    windowed_signal = np.zeros_like(signal_data)

    # 仅对窗口内部应用 Tukey 窗函数
    windowed_signal[window_mask] = signal_windowed * tukey_window

    return windowed_signal


def get_window_function_preview(window_size, alpha=0.5):
    """
    获取 Tukey 窗函数预览

    参数:
        window_size: 窗口大小
        alpha: Tukey 窗参数 (0-1)

    返回:
        window_function: 窗函数数组
    """
    return tukey(window_size, alpha)


def suggest_window_params(time_ps, amplitude, pre_ps=3.0, post_ps=25.0, alpha=0.15):
    """
    按主脉冲位置给出推荐的窗口参数。

    固定的 0–30 ps 窗口对厚样品是危险的：样品越厚主脉冲越靠后，
    例如 4 mm GFRP 的主脉冲落在 29.8 ps，正好被切在窗口边缘上。
    按峰位自动定位可以避免这个问题。

    参数:
        time_ps: 时间轴 (ps)
        amplitude: 幅值
        pre_ps / post_ps: 主峰前后各保留多长 (ps)
        alpha: 渐变比例，0.1–0.2 通常足以压制截断纹波

    返回:
        dict: {'t_start': ..., 't_end': ..., 'alpha': ...}
    """
    t = np.asarray(time_ps, dtype=float)
    y = np.asarray(amplitude, dtype=float)
    if t.size < 2:
        return {
            "t_start": float(t[0]) if t.size else 0.0,
            "t_end": float(t[-1]) if t.size else 0.0,
            "alpha": float(alpha),
        }
    peak_index = int(np.argmax(np.abs(y - np.median(y))))
    t_peak = float(t[peak_index])
    return {
        "t_start": max(float(t[0]), t_peak - float(pre_ps)),
        "t_end": min(float(t[-1]), t_peak + float(post_ps)),
        "alpha": float(alpha),
    }


__all__ = [
    "tukey",
    "apply_tukey_window",
    "get_window_function_preview",
    "suggest_window_params",
]
