import numpy as np
from scipy import signal

def apply_tukey_window(time_data, signal_data, t_start, t_end, alpha=0.5):
    """
    应用Tukey窗函数到信号数据
    
    参数:
        time_data: 时间数据数组
        signal_data: 信号数据数组
        t_start: 窗口起始时间
        t_end: 窗口结束时间
        alpha: Tukey窗参数 (0-1)，0为矩形窗，1为汉宁窗
        
    返回:
        windowed_signal: 加窗后的信号 (窗口外部置零)
    """
    # 创建时间窗口掩码
    window_mask = (time_data >= t_start) & (time_data <= t_end)
    
    # 如果没有数据点在窗口范围内，返回全零信号
    if not np.any(window_mask):
        return np.zeros_like(signal_data)
    
    # 提取窗口区域信号
    signal_windowed = signal_data[window_mask]
    
    # 创建Tukey窗函数
    window_size = len(signal_windowed)
    tukey_window = signal.windows.tukey(window_size, alpha)
    
    # 初始化结果为全零数组 (窗口外部为零)
    windowed_signal = np.zeros_like(signal_data)
    
    # 仅对窗口内部应用Tukey窗函数
    windowed_signal[window_mask] = signal_windowed * tukey_window
    
    return windowed_signal

def get_window_function_preview(window_size, alpha=0.5):
    """
    获取Tukey窗函数预览
    
    参数:
        window_size: 窗口大小
        alpha: Tukey窗参数 (0-1)
        
    返回:
        window_function: 窗函数数组
    """
    return signal.windows.tukey(window_size, alpha)