#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
工作线程模块

提供异步计算和保存功能，避免GUI阻塞
"""

from typing import List, Dict, Optional
from PyQt6.QtCore import QThread, pyqtSignal

from core import calculate_optical_params, CalculationResult
from core.data_io import (
    save_frequency_domain_data_to_excel,
    save_results_to_excel,
    save_time_domain_data_to_excel,
    save_time_freq_domain_data_to_excel,
)
from core.results import AnalysisResult
from core.standard_format import StandardSignal


class CalculationWorker(QThread):
    """计算工作线程"""
    
    # 信号定义
    progress_updated = pyqtSignal(int, int, str)  # 当前步骤, 总步骤, 描述
    calculation_finished = pyqtSignal(object)  # CalculationResult
    calculation_error = pyqtSignal(str)  # 错误信息
    warning_occurred = pyqtSignal(str)  # 警告信息
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 计算参数
        self.ref_file: str = ""
        self.sam_files: List[str] = []
        self.sam_names: List[str] = []
        self.thickness: float = 0.5
        self.use_window: bool = False
        self.ref_window_params: Optional[Dict] = None
        self.per_sample_window_params: Optional[List[Optional[Dict]]] = None
        self.per_sample_thickness: Optional[List[Optional[float]]] = None
        self.ref_signal: Optional[StandardSignal] = None
        self.sam_signals: Optional[List[Optional[StandardSignal]]] = None
    
    def set_parameters(
        self,
        ref_file: str,
        sam_files: List[str],
        sam_names: List[str],
        thickness: float,
        use_window: bool = False,
        ref_window_params: Optional[Dict] = None,
        per_sample_window_params: Optional[List[Optional[Dict]]] = None,
        per_sample_thickness: Optional[List[Optional[float]]] = None,
        ref_signal: Optional[StandardSignal] = None,
        sam_signals: Optional[List[Optional[StandardSignal]]] = None,
    ):
        """设置计算参数"""
        self.ref_file = ref_file
        self.sam_files = sam_files
        self.sam_names = sam_names
        self.thickness = thickness
        self.use_window = use_window
        self.ref_window_params = ref_window_params
        self.per_sample_window_params = per_sample_window_params
        self.per_sample_thickness = per_sample_thickness
        self.ref_signal = ref_signal
        self.sam_signals = sam_signals
    
    def _progress_callback(self, current: int, total: int, message: str):
        """进度回调"""
        self.progress_updated.emit(current, total, message)
    
    def run(self):
        """执行计算"""
        try:
            result = calculate_optical_params(
                ref_file=self.ref_file,
                sam_files=self.sam_files,
                sam_names=self.sam_names,
                d=self.thickness,
                use_window=self.use_window,
                ref_window_params=self.ref_window_params,
                per_sample_window_params=self.per_sample_window_params,
                per_sample_thickness=self.per_sample_thickness,
                progress_callback=self._progress_callback,
                ref_signal=self.ref_signal,
                sam_signals=self.sam_signals,
            )
            
            if self.isInterruptionRequested():
                return
            if result.warnings:
                self.warning_occurred.emit("\n".join(result.warnings))
            
            self.calculation_finished.emit(result)
            
        except Exception as e:
            self.calculation_error.emit(str(e))


class SaveWorker(QThread):
    """保存 Excel 结果工作线程"""
    
    # 信号定义
    progress_updated = pyqtSignal(int, int, str)  # 当前进度, 总进度, 描述
    save_finished = pyqtSignal(str)  # 保存的文件路径
    save_error = pyqtSignal(str)  # 错误信息
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.results_data: Optional[AnalysisResult] = None
        self.file_path: str = ""
        self.save_type: str = "optical"  # 'optical' / 'time' / 'freq' / 'time_freq'
    
    def set_parameters(self, results_data: AnalysisResult, file_path: str, save_type: str = "optical"):
        """设置保存参数
        
        参数:
            results_data: 分析结果数据（AnalysisResult）
            file_path: 保存文件路径
            save_type: 保存类型，'optical'=光学参数,
                       'time'=时域数据, 'freq'=频域数据,
                       'time_freq'=时域+频域（兼容旧入口）
        """
        self.results_data = results_data
        self.file_path = file_path
        self.save_type = save_type
    
    def run(self):
        """执行保存"""
        try:
            self.progress_updated.emit(10, 100, "正在准备数据...")
            
            if self.results_data is None:
                self.save_error.emit("没有可保存的数据")
                return
            
            self.progress_updated.emit(30, 100, "正在写入 Excel 文件...")
            
            # 根据保存类型调用不同的保存函数（每个文件一个工作表，工作表名用文件名）
            if self.save_type == "time":
                saved_path = save_time_domain_data_to_excel(
                    self.results_data, self.file_path
                )
            elif self.save_type == "freq":
                saved_path = save_frequency_domain_data_to_excel(
                    self.results_data, self.file_path
                )
            elif self.save_type == "time_freq":
                saved_path = save_time_freq_domain_data_to_excel(
                    self.results_data, self.file_path
                )
            else:
                saved_path = save_results_to_excel(self.results_data, self.file_path)
            
            if self.isInterruptionRequested():
                return
            self.progress_updated.emit(100, 100, "保存完成")
            self.save_finished.emit(saved_path)
            
        except Exception as e:
            self.save_error.emit(str(e))
