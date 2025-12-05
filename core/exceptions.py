#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自定义异常类模块

定义项目中使用的自定义异常，用于解耦GUI与业务逻辑
"""


class THzAnalysisError(Exception):
    """THz分析基础异常类"""
    pass


class DataReadError(THzAnalysisError):
    """数据读取错误"""
    def __init__(self, file_path: str, message: str):
        self.file_path = file_path
        self.message = message
        super().__init__(f"读取文件 '{file_path}' 时出错: {message}")


class DataFormatError(THzAnalysisError):
    """数据格式错误"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class DataLengthMismatchError(THzAnalysisError):
    """数据长度不匹配警告/错误"""
    def __init__(self, sample_name: str, ref_length: int, sample_length: int, truncated_length: int):
        self.sample_name = sample_name
        self.ref_length = ref_length
        self.sample_length = sample_length
        self.truncated_length = truncated_length
        super().__init__(
            f"文件 '{sample_name}' 的数据点数({sample_length})与参考文件({ref_length})不匹配，"
            f"已自动截断至 {truncated_length} 个点"
        )


class CalculationError(THzAnalysisError):
    """计算过程错误"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"计算过程中出错: {message}")


class ParameterError(THzAnalysisError):
    """参数错误"""
    def __init__(self, param_name: str, message: str):
        self.param_name = param_name
        self.message = message
        super().__init__(f"参数 '{param_name}' 错误: {message}")


class SaveError(THzAnalysisError):
    """保存文件错误"""
    def __init__(self, file_path: str, message: str):
        self.file_path = file_path
        self.message = message
        super().__init__(f"保存文件 '{file_path}' 时出错: {message}")
