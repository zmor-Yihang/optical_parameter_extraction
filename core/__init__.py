"""
THz光学参数分析系统 - 核心计算模块
"""

from .calculator import (
    calculate_optical_params,
    build_result_figures,
    CalculationResult,
    CalculationProgress,
)
from .data_io import (
    read_data_file,
    load_standard_signal,
    read_table_txt,
    write_table_txt,
    save_results_to_txt,
    save_time_freq_domain_data_to_txt,
)
from .standard_format import (
    StandardSignal,
    INPUT_FILE_FILTER,
    SUPPORTED_INPUT_EXTENSIONS,
    detect_source_format,
    export_standard_signals,
    make_unique_names,
    read_standard_txt,
    standardize_file,
    standardize_files,
    write_standard_txt,
)
from .exceptions import (
    THzAnalysisError,
    DataReadError,
    DataFormatError,
    DataLengthMismatchError,
    CalculationError,
    ParameterError,
    SaveError
)

__all__ = [
    'calculate_optical_params',
    'build_result_figures',
    'CalculationResult',
    'CalculationProgress',
    'read_data_file',
    'load_standard_signal',
    'read_table_txt',
    'write_table_txt',
    'save_results_to_txt',
    'save_time_freq_domain_data_to_txt',
    'StandardSignal',
    'INPUT_FILE_FILTER',
    'SUPPORTED_INPUT_EXTENSIONS',
    'detect_source_format',
    'export_standard_signals',
    'make_unique_names',
    'read_standard_txt',
    'standardize_file',
    'standardize_files',
    'write_standard_txt',
    'THzAnalysisError',
    'DataReadError',
    'DataFormatError',
    'DataLengthMismatchError',
    'CalculationError',
    'ParameterError',
    'SaveError'
]
