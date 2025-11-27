import numpy as np
import matplotlib.pyplot as plt
from PyQt6.QtWidgets import QMessageBox


def calculate_optical_params(ref_file, sam_files, sam_names, d, start_row=1, use_window=False, ref_window_params=None, per_sample_window_params=None):
    """
    计算THz光学参数
    
    参数:
        ref_file: 参考信号文件路径
        sam_files: 样品信号文件路径列表
        sam_names: 样品名称列表
        d: 样品厚度(mm)
        start_row: 数据内容起始行（从1开始）
        use_window: 是否使用Tukey窗函数
        ref_window_params: 参考信号的窗函数参数字典，包含 t_start, t_end, alpha
        per_sample_window_params: 每个样品的窗函数参数列表，每个元素是一个字典
        
    返回:
        fig1, fig2, fig3: 三个图表对象
        results_data: 计算结果数据字典
    """
    try:
        from .data_io import read_data_file
        
        # 读取参考信号数据
        refData = read_data_file(ref_file, start_row)
        reft = refData.iloc[:, 0].values.astype(float)
        refa = refData.iloc[:, 1].values.astype(float)
        
        # 保存原始参考信号副本用于后续处理
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
        
        # 定义颜色
        colors = ['red', 'blue', 'green', 'purple', 'orange', 'brown', 'pink', 'gray', 'olive', 'cyan']
        
        # 创建时域和频域图表
        fig1 = plt.figure(figsize=(9, 7))
        fig1.patch.set_facecolor('#F5F5F5')

        # 参考信号图像 - 先不绘制,等处理完所有样品后再绘制
        ax1 = fig1.add_subplot(2, 1, 1)
        ax1.set_facecolor('#F8F8F8')

        all_sama = []
        all_Nsam = []
        all_Ksam = []
        all_Asam = []
        all_Epsilon_real = []  # 介电常数实部
        all_Epsilon_imag = []  # 介电常数虚部
        all_TanDelta = []      # 介电损耗

        # 读取每个样品数据
        for i, samFilePath in enumerate(sam_files):
            # 读取样品数据
            samData = read_data_file(samFilePath, start_row)
            
            # 处理数据长度不匹配的情况
            if len(samData.index) != len(refData.index):
                min_length = min(len(samData.index), len(refData.index))
                if len(refData.index) > min_length:
                    reft = reft[:min_length]
                    refa = refa[:min_length]
                    refa_original = refa_original[:min_length]
                samData = samData.iloc[:min_length, :]
                QMessageBox.warning(None, "警告", f"文件 {sam_names[i]} 的数据点数与参考文件不匹配，已自动截断至 {min_length} 个点")
            
            sama = samData.iloc[:, 1].values.astype(float)
            
            # 如果启用窗函数，应用Tukey窗函数到样品信号
            if use_window:
                from .window_functions import apply_tukey_window
                # 使用样品对应的窗函数参数
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
        
        # 最后绘制参考信号,确保显示的是加窗后的数据
        ax1.plot(reft, refa, 'k', linewidth=2, label='参考信号')
        
        ax1.grid(True)
        ax1.set_title('时域信号')
        ax1.set_xlabel('延迟 (ps)')
        ax1.set_ylabel('振幅')
        ax1.legend()
        
        # FFT计算
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
        
        # 画出参考信号的FFT
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
            nsam = 1 - phiu0 * 3e8 / (2 * np.pi * F * 1e12 * d * 1e-3)
            nsam[0] = nsam[1] if len(nsam) > 1 else 1
            all_Nsam.append(nsam)
            
            # 计算消光系数
            ksam = np.log(4 * nsam / rho0 / ((nsam + 1) ** 2)) * 3e8 / (2 * np.pi * F * 1e12 * d * 10**(-3))
            ksam[0] = ksam[1] if len(ksam) > 1 else 0
            all_Ksam.append(ksam)
            
            # 计算吸收系数(单位: cm^-1)
            asam = 2 * 2 * np.pi * F * 1e12 * ksam / 3e8 / 100
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
        fig2 = _create_optical_params_figure(F, all_Nsam, all_Ksam, all_Asam, sam_names, colors)
        
        # 创建介电特性图表
        fig3 = _create_dielectric_figure(F, all_Epsilon_real, all_Epsilon_imag, all_TanDelta, sam_names, colors)
        
        # 返回计算结果数据
        results_data = {
            'F': F,
            'Nsam': all_Nsam,
            'Ksam': all_Ksam,
            'Asam': all_Asam,
            'Epsilon_real': all_Epsilon_real,
            'Epsilon_imag': all_Epsilon_imag,
            'TanDelta': all_TanDelta,
            'sam_names': sam_names
        }
        
        return fig1, fig2, fig3, results_data
        
    except Exception as e:
        QMessageBox.critical(None, "计算错误", f"计算过程中出错: {str(e)}")
        return None, None, None, None


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
