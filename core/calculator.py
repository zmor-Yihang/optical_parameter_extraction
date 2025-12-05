#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
光学参数计算模块

提供THz时域光谱分析的核心计算功能
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict, Tuple, Optional, Callable, Any

from utils import info, warning, error, exception
from .exceptions import CalculationError


# 物理常量
C_LIGHT = 3e8  # 光速 m/s


class CalculationProgress:
    """计算进度回调类"""
    
    def __init__(self, callback: Optional[Callable[[int, int, str], None]] = None):
        """
        初始化进度回调
        
        Args:
            callback: 进度回调函数，参数为 (当前步骤, 总步骤, 描述)
        """
        self.callback = callback
        self.total_steps = 0
        self.current_step = 0
    
    def set_total(self, total: int):
        """设置总步骤数"""
        self.total_steps = total
        self.current_step = 0
    
    def update(self, message: str):
        """更新进度"""
        self.current_step += 1
        if self.callback:
            self.callback(self.current_step, self.total_steps, message)


class CalculationResult:
    """计算结果类"""
    
    def __init__(self):
        self.fig1: Optional[plt.Figure] = None  # 时域频域图
        self.fig2: Optional[plt.Figure] = None  # 光学参数图
        self.fig3: Optional[plt.Figure] = None  # 介电特性图
        self.data: Optional[Dict[str, Any]] = None  # 计算数据
        self.warnings: List[str] = []  # 警告信息列表
        self.success: bool = False


def calculate_optical_params(
    ref_file: str,
    sam_files: List[str],
    sam_names: List[str],
    d: float,
    start_row: int = 1,
    use_window: bool = False,
    ref_window_params: Optional[Dict] = None,
    per_sample_window_params: Optional[List[Optional[Dict]]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> CalculationResult:
    """
    计算THz光学参数
    
    Args:
        ref_file: 参考信号文件路径
        sam_files: 样品信号文件路径列表
        sam_names: 样品名称列表
        d: 样品厚度(mm)
        start_row: 数据内容起始行（从1开始）
        use_window: 是否使用Tukey窗函数
        ref_window_params: 参考信号的窗函数参数字典
        per_sample_window_params: 每个样品的窗函数参数列表
        progress_callback: 进度回调函数
        
    Returns:
        CalculationResult: 计算结果对象
    """
    result = CalculationResult()
    progress = CalculationProgress(progress_callback)
    
    # 计算总步骤数: 读取参考 + 读取每个样品 + FFT计算 + 创建图表
    total_steps = 1 + len(sam_files) + 1 + 3
    progress.set_total(total_steps)
    
    try:
        from .data_io import read_data_file
        
        info(f"开始计算光学参数，样品数量: {len(sam_files)}")
        
        # 读取参考信号数据
        progress.update("读取参考信号...")
        refData = read_data_file(ref_file, start_row)
        reft = refData.iloc[:, 0].values.astype(float)
        refa = refData.iloc[:, 1].values.astype(float)
        
        info(f"参考信号读取完成，数据点数: {len(reft)}")
        
        # 保存原始参考信号副本
        refa_original = refa.copy()
        
        # 如果启用窗函数，应用Tukey窗函数到参考信号
        if use_window and ref_window_params:
            from .window_functions import apply_tukey_window
            refa = apply_tukey_window(
                reft, 
                refa, 
                ref_window_params.get('t_start', reft[0]), 
                ref_window_params.get('t_end', reft[-1]), 
                ref_window_params.get('alpha', 0.5)
            )
            info("参考信号窗函数已应用")
        
        # 定义颜色
        colors = ['red', 'blue', 'green', 'purple', 'orange', 'brown', 'pink', 'gray', 'olive', 'cyan']
        
        # 创建时域和频域图表
        fig1 = plt.figure(figsize=(9, 7))
        fig1.patch.set_facecolor('#F5F5F5')

        ax1 = fig1.add_subplot(2, 1, 1)
        ax1.set_facecolor('#F8F8F8')

        all_sama = []
        all_Nsam = []
        all_Ksam = []
        all_Asam = []
        all_Epsilon_real = []
        all_Epsilon_imag = []
        all_TanDelta = []

        # 读取每个样品数据
        for i, samFilePath in enumerate(sam_files):
            progress.update(f"读取样品 {sam_names[i]}...")
            
            samData = read_data_file(samFilePath, start_row)
            
            # 处理数据长度不匹配的情况
            if len(samData.index) != len(refData.index):
                min_length = min(len(samData.index), len(refData.index))
                if len(refData.index) > min_length:
                    reft = reft[:min_length]
                    refa = refa[:min_length]
                    refa_original = refa_original[:min_length]
                samData = samData.iloc[:min_length, :]
                
                # 记录警告信息
                warn_msg = f"文件 {sam_names[i]} 的数据点数与参考文件不匹配，已自动截断至 {min_length} 个点"
                result.warnings.append(warn_msg)
                warning(warn_msg)
            
            sama = samData.iloc[:, 1].values.astype(float)
            
            # 如果启用窗函数，应用Tukey窗函数到样品信号
            if use_window:
                from .window_functions import apply_tukey_window
                sample_idx = i
                if per_sample_window_params and sample_idx < len(per_sample_window_params) and per_sample_window_params[sample_idx] is not None:
                    sample_params = per_sample_window_params[sample_idx]
                    sama = apply_tukey_window(
                        reft, 
                        sama, 
                        sample_params.get('t_start', reft[0]), 
                        sample_params.get('t_end', reft[-1]), 
                        sample_params.get('alpha', 0.5)
                    )
                
            all_sama.append(sama)
            
            # 绘制样品信号
            ax1.plot(reft, sama, color=colors[i % len(colors)], label=f'{sam_names[i]} 信号')
            info(f"样品 {sam_names[i]} 读取完成")
        
        # 绘制参考信号
        ax1.plot(reft, refa, 'k', linewidth=2, label='参考信号')
        
        ax1.grid(True)
        ax1.set_title('时域信号')
        ax1.set_xlabel('延迟 (ps)')
        ax1.set_ylabel('振幅')
        ax1.legend()
        
        # FFT计算
        progress.update("执行FFT计算...")
        N = len(reft)
        fs = 1/(reft[1]-reft[0])
        df = fs/N
        Na = round(len(reft)/2)+1
        F = df * np.arange(0, N//2 + 1)
        
        # 计算参考信号的FFT
        refFFT = np.fft.fft(refa)
        refFAAll = np.abs(refFFT/N)
        refFA = refFAAll[:Na]
        refFAdB = 20 * np.log10(refFA)
        
        ax2 = fig1.add_subplot(2, 1, 2)
        ax2.set_facecolor('#F8F8F8')
        ax2.plot(F, refFAdB, 'k', linewidth=2, label='参考光谱')
        
        # 计算每个样品的光谱和光学参数
        for i, sama in enumerate(all_sama):
            samFFT = np.fft.fft(sama)
            samFAAll = np.abs(samFFT/N)
            samFA = samFAAll[:Na]
            samFAdB = 20 * np.log10(samFA)

            ax2.plot(F, samFAdB, color=colors[i % len(colors)], linewidth=2, label=f'{sam_names[i]} 光谱')

            H0 = samFFT / refFFT
            H0 = H0[:Na]
            rho0 = np.abs(H0)
            phi = np.angle(H0)
            phiu0 = np.unwrap(phi)
            
            # 计算折射率
            nsam = 1 - phiu0 * C_LIGHT / (2 * np.pi * F * 1e12 * d * 1e-3)
            nsam[0] = nsam[1] if len(nsam) > 1 else 1
            all_Nsam.append(nsam)
            
            # 计算消光系数
            ksam = np.log(4 * nsam / rho0 / ((nsam + 1) ** 2)) * C_LIGHT / (2 * np.pi * F * 1e12 * d * 10**(-3))
            ksam[0] = ksam[1] if len(ksam) > 1 else 0
            all_Ksam.append(ksam)
            
            # 计算吸收系数(单位: cm^-1)
            asam = 2 * 2 * np.pi * F * 1e12 * ksam / C_LIGHT / 100
            asam[0] = asam[1] if len(asam) > 1 else 0
            all_Asam.append(asam)
            
            # 计算介电常数实部 ε'(ω) = n²(ω) - k²(ω)
            epsilon_real = nsam**2 - ksam**2
            all_Epsilon_real.append(epsilon_real)
            
            # 计算介电常数虚部 ε"(ω) = 2n(ω)k(ω)
            epsilon_imag = 2 * nsam * ksam
            all_Epsilon_imag.append(epsilon_imag)
            
            # 计算介电损耗 tan δ = ε"(ω)/ε'(ω)
            tan_delta = np.zeros_like(epsilon_real)
            mask = (epsilon_real != 0)
            tan_delta[mask] = epsilon_imag[mask] / epsilon_real[mask]
            all_TanDelta.append(tan_delta)
        
        ax2.grid(True)
        ax2.set_title('频域信号')
        ax2.set_xlabel('频率 (THz)')
        ax2.set_ylabel('振幅 (dB)')
        ax2.legend()
        ax2.set_xlim(0, 5)
        ax2.autoscale(axis='y')
        
        fig1.tight_layout()
        
        # 创建光学参数图表
        progress.update("生成光学参数图表...")
        fig2 = _create_optical_params_figure(F, all_Nsam, all_Ksam, all_Asam, sam_names, colors)
        
        # 创建介电特性图表
        progress.update("生成介电特性图表...")
        fig3 = _create_dielectric_figure(F, all_Epsilon_real, all_Epsilon_imag, all_TanDelta, sam_names, colors)
        
        # 完成
        progress.update("计算完成")
        
        # 组装结果
        result.fig1 = fig1
        result.fig2 = fig2
        result.fig3 = fig3
        result.data = {
            'F': F,
            'Nsam': all_Nsam,
            'Ksam': all_Ksam,
            'Asam': all_Asam,
            'Epsilon_real': all_Epsilon_real,
            'Epsilon_imag': all_Epsilon_imag,
            'TanDelta': all_TanDelta,
            'sam_names': sam_names
        }
        result.success = True
        
        info("光学参数计算完成")
        return result
        
    except Exception as e:
        exception(f"计算过程中出错: {str(e)}")
        raise CalculationError(str(e))


def _create_optical_params_figure(F, all_Nsam, all_Ksam, all_Asam, sam_names, colors):
    """创建光学参数对比图表"""
    fig2 = plt.figure(figsize=(9, 10))
    fig2.patch.set_facecolor('#F5F5F5')
    
    # 折射率对比
    ax3 = fig2.add_subplot(3, 1, 1)
    ax3.set_facecolor('#F8F8F8')
    for i in range(len(all_Nsam)):
        ax3.plot(F, all_Nsam[i], color=colors[i % len(colors)], linewidth=2.5, label=sam_names[i])
    ax3.set_xlabel('频率 (THz)')
    ax3.set_ylabel('折射率')
    ax3.set_title('折射率对比')
    ax3.legend()
    ax3.grid(True)
    ax3.set_xlim(0, 5)
    ax3.autoscale(axis='y')
    
    # 消光系数对比
    ax4 = fig2.add_subplot(3, 1, 2)
    ax4.set_facecolor('#F8F8F8')
    for i in range(len(all_Ksam)):
        ax4.plot(F, all_Ksam[i], color=colors[i % len(colors)], linewidth=2.5, label=sam_names[i])
    ax4.set_xlabel('频率 (THz)')
    ax4.set_ylabel('消光系数')
    ax4.set_title('消光系数对比')
    ax4.legend()
    ax4.grid(True)
    ax4.set_xlim(0, 5)
    ax4.autoscale(axis='y')
    
    # 吸收系数对比
    ax5 = fig2.add_subplot(3, 1, 3)
    ax5.set_facecolor('#F8F8F8')
    for i in range(len(all_Asam)):
        ax5.plot(F, all_Asam[i], color=colors[i % len(colors)], linewidth=2.5, label=sam_names[i])
    ax5.set_xlabel('频率 (THz)')
    ax5.set_ylabel('吸收系数 (cm^-1)')
    ax5.set_title('吸收系数对比')
    ax5.legend()
    ax5.grid(True)
    ax5.set_xlim(0, 5)
    ax5.autoscale(axis='y')
    
    fig2.tight_layout()
    return fig2


def _create_dielectric_figure(F, all_Epsilon_real, all_Epsilon_imag, all_TanDelta, sam_names, colors):
    """创建介电特性图表"""
    fig3 = plt.figure(figsize=(9, 10))
    fig3.patch.set_facecolor('#F5F5F5')
    
    # 介电常数实部对比
    ax6 = fig3.add_subplot(3, 1, 1)
    ax6.set_facecolor('#F8F8F8')
    for i in range(len(all_Epsilon_real)):
        ax6.plot(F, all_Epsilon_real[i], color=colors[i % len(colors)], linewidth=2.5, label=sam_names[i])
    ax6.set_xlabel('频率 (THz)')
    ax6.set_ylabel('介电常数实部 ε\'')
    ax6.set_title('介电常数实部对比')
    ax6.legend()
    ax6.grid(True)
    ax6.set_xlim(0, 5)
    ax6.autoscale(axis='y')
    
    # 介电常数虚部对比
    ax7 = fig3.add_subplot(3, 1, 2)
    ax7.set_facecolor('#F8F8F8')
    for i in range(len(all_Epsilon_imag)):
        ax7.plot(F, all_Epsilon_imag[i], color=colors[i % len(colors)], linewidth=2.5, label=sam_names[i])
    ax7.set_xlabel('频率 (THz)')
    ax7.set_ylabel('介电常数虚部 ε\"')
    ax7.set_title('介电常数虚部对比')
    ax7.legend()
    ax7.grid(True)
    ax7.set_xlim(0, 5)
    ax7.autoscale(axis='y')
    
    # 介电损耗对比
    ax8 = fig3.add_subplot(3, 1, 3)
    ax8.set_facecolor('#F8F8F8')
    for i in range(len(all_TanDelta)):
        ax8.plot(F, all_TanDelta[i], color=colors[i % len(colors)], linewidth=2.5, label=sam_names[i])
    ax8.set_xlabel('频率 (THz)')
    ax8.set_ylabel('介电损耗 tan δ')
    ax8.set_title('介电损耗对比')
    ax8.legend()
    ax8.grid(True)
    ax8.set_xlim(0, 5)
    ax8.autoscale(axis='y')
    
    fig3.tight_layout()
    return fig3
