#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
工作线程模块

提供异步计算和保存功能，避免GUI阻塞
"""

from typing import List, Dict, Optional, Any
from PyQt6.QtCore import QThread, pyqtSignal

from core import calculate_optical_params, CalculationResult, save_results_to_excel


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
        self.start_row: int = 1
        self.use_window: bool = False
        self.ref_window_params: Optional[Dict] = None
        self.per_sample_window_params: Optional[List[Optional[Dict]]] = None
    
    def set_parameters(
        self,
        ref_file: str,
        sam_files: List[str],
        sam_names: List[str],
        thickness: float,
        start_row: int = 1,
        use_window: bool = False,
        ref_window_params: Optional[Dict] = None,
        per_sample_window_params: Optional[List[Optional[Dict]]] = None
    ):
        """设置计算参数"""
        self.ref_file = ref_file
        self.sam_files = sam_files
        self.sam_names = sam_names
        self.thickness = thickness
        self.start_row = start_row
        self.use_window = use_window
        self.ref_window_params = ref_window_params
        self.per_sample_window_params = per_sample_window_params
    
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
                start_row=self.start_row,
                use_window=self.use_window,
                ref_window_params=self.ref_window_params,
                per_sample_window_params=self.per_sample_window_params,
                progress_callback=self._progress_callback
            )
            
            # 发送警告信息
            for warning_msg in result.warnings:
                self.warning_occurred.emit(warning_msg)
            
            self.calculation_finished.emit(result)
            
        except Exception as e:
            self.calculation_error.emit(str(e))


class SaveWorker(QThread):
    """保存Excel工作线程"""
    
    # 信号定义
    progress_updated = pyqtSignal(int, int, str)  # 当前进度, 总进度, 描述
    save_finished = pyqtSignal(str)  # 保存的文件路径
    save_error = pyqtSignal(str)  # 错误信息
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.results_data: Optional[Dict] = None
        self.file_path: str = ""
    
    def set_parameters(self, results_data: Dict, file_path: str):
        """设置保存参数"""
        self.results_data = results_data
        self.file_path = file_path
    
    def run(self):
        """执行保存"""
        try:
            self.progress_updated.emit(10, 100, "正在准备数据...")
            
            if self.results_data is None:
                self.save_error.emit("没有可保存的数据")
                return
            
            self.progress_updated.emit(30, 100, "正在写入Excel文件...")
            
            save_results_to_excel(self.results_data, self.file_path)
            
            self.progress_updated.emit(100, 100, "保存完成")
            self.save_finished.emit(self.file_path)
            
        except Exception as e:
            self.save_error.emit(str(e))
