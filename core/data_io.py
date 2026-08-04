#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据输入输出模块

- 读取：统一走 core.standard_format，任何来源格式都会被转换为两列 [时间(ps), 幅值]
- 写出：所有结果一律保存为 txt（'#' 注释头 + 制表符分隔的数值表），
        与阶段一导出的标准数据格式保持一致，便于追溯与再处理。
"""

import os
from collections.abc import Mapping
from datetime import datetime

import numpy as np
import pandas as pd

from utils import info, exception
from .exceptions import DataReadError, SaveError
from .standard_format import (
    NUMBER_FORMAT,
    delay_um_to_ps,
    detect_source_format,
    read_standard_txt,
    standardize_file,
    write_standard_txt,
)


# 兼容旧代码：延迟台位移(um) 到时间(ps) 的换算系数
DELAY_UM_TO_PS = float(delay_um_to_ps(1.0))


def read_data_file(file_path, start_row=1):
    """
    通用数据读取函数，返回统一的两列数据。

    参数:
        file_path: 文件路径
        start_row: 数据内容起始行（从1开始，跳过前 start_row-1 行，无表头）
            注意：对标准 txt 与 BT-FTS 时域扫描格式无效（由文件结构自动判定）

    返回:
        pandas.DataFrame: 列为 ['time', 'intensity']

    支持:
        - 本程序阶段一导出的标准 txt（带 '# THz-STD' 头）
        - BT-FTS 系列仪器导出的时域扫描 txt（多扫描时自动取平均）
        - Excel (.xlsx/.xls)
        - 任意分隔符的两列文本 (.txt/.csv/.dat/.asc)
    """
    try:
        signals = standardize_file(file_path, start_row=start_row, scan_mode="average")
        info(f"成功读取文件: {file_path}")
        return signals[0].to_dataframe()
    except DataReadError:
        raise
    except Exception as e:
        exception(f"读取文件 {file_path} 时出错")
        raise DataReadError(file_path, str(e))


def load_standard_signal(file_path, start_row=1):
    """读取单个文件并返回 StandardSignal（多扫描取平均）。"""
    return standardize_file(file_path, start_row=start_row, scan_mode="average")[0]


# ---------------------------------------------------------------------------
# txt 表格写出
# ---------------------------------------------------------------------------

def write_table_txt(file_path, columns, metadata=None):
    """
    写出统一风格的 txt 数据表。

    参数:
        file_path: 目标路径
        columns: dict[列名, 一维数组]，按插入顺序写出
        metadata: dict[键, 值]，写为 '# 键: 值' 注释行

    返回:
        str: 实际写出的路径
    """
    if not columns:
        raise SaveError(file_path, "没有可写出的数据列")

    try:
        arrays = []
        names = []
        for name, values in columns.items():
            array = np.asarray(values, dtype=float).ravel()
            arrays.append(array)
            names.append(str(name))

        length = min(array.size for array in arrays)
        if length == 0:
            raise SaveError(file_path, "数据列为空")
        arrays = [array[:length] for array in arrays]

        directory = os.path.dirname(os.path.abspath(file_path))
        if directory:
            os.makedirs(directory, exist_ok=True)

        header = dict(metadata or {})
        header.setdefault("generated_at", datetime.now().isoformat(timespec="seconds"))
        header.setdefault("rows", str(length))

        with open(file_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# THz-RESULT-1.0\n")
            for key, value in header.items():
                text = str(value).replace("\n", " ").replace("\r", " ")
                fh.write(f"# {key}: {text}\n")
            fh.write("# " + "\t".join(names) + "\n")
            for row in range(length):
                fh.write(
                    "\t".join(NUMBER_FORMAT % array[row] for array in arrays) + "\n"
                )

        info(f"数据已保存到: {file_path} ({length} 行 x {len(names)} 列)")
        return file_path
    except SaveError:
        raise
    except Exception as e:
        exception(f"写出 txt 数据时出错: {e}")
        raise SaveError(file_path, str(e))


def read_table_txt(file_path):
    """读回 write_table_txt 写出的数据表，返回 (DataFrame, metadata)。"""
    metadata = {}
    names = None
    rows = []
    try:
        with open(file_path, "r", encoding="utf-8-sig", errors="replace") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    body = line.lstrip("#").strip()
                    if not body or body.startswith("THz-"):
                        continue
                    if "\t" in body:
                        names = [item.strip() for item in body.split("\t")]
                    elif ":" in body:
                        key, _sep, value = body.partition(":")
                        metadata[key.strip()] = value.strip()
                    continue
                rows.append([float(item) for item in line.split("\t")])

        frame = pd.DataFrame(rows, columns=names) if names else pd.DataFrame(rows)
        return frame, metadata
    except Exception as e:
        exception(f"读取 txt 数据表 {file_path} 时出错")
        raise DataReadError(file_path, str(e))


def _ensure_txt_path(filename):
    root, ext = os.path.splitext(filename)
    return filename if ext.lower() == ".txt" else f"{root}.txt"


def _result_metadata(results_data, extra=None):
    metadata = {
        "stage": "2-optical-parameters",
        "sample_count": str(len(results_data.get("sam_names", []) or [])),
    }
    thickness = results_data.get("thickness")
    if thickness is not None:
        metadata["thickness_mm"] = str(thickness)
    if results_data.get("use_window") is not None:
        metadata["use_window"] = str(results_data.get("use_window"))
    sources = results_data.get("source_files")
    if isinstance(sources, Mapping):
        for key, value in sources.items():
            metadata[f"source.{key}"] = value
    metadata.update(extra or {})
    return metadata


# ---------------------------------------------------------------------------
# 结果保存（统一 txt）
# ---------------------------------------------------------------------------

def save_results_to_txt(results_data, filename):
    """
    将光学参数计算结果保存为 txt。

    参数:
        results_data: 计算结果数据字典
        filename: 保存的文件路径（非 .txt 后缀会自动改为 .txt）

    返回:
        str: 实际保存的文件路径
    """
    target = _ensure_txt_path(filename)
    info(f"开始保存光学参数到: {target}")

    frequency = results_data.get("F")
    if frequency is None:
        raise SaveError(target, "结果中缺少频率数据")

    sam_names = results_data.get("sam_names", []) or []
    columns = {"Frequency[THz]": frequency}
    for i, name in enumerate(sam_names):
        columns[f"{name}|n"] = results_data["Nsam"][i]
        columns[f"{name}|k"] = results_data["Ksam"][i]
        columns[f"{name}|alpha[cm^-1]"] = results_data["Asam"][i]
        columns[f"{name}|eps_real"] = results_data["Epsilon_real"][i]
        columns[f"{name}|eps_imag"] = results_data["Epsilon_imag"][i]
        columns[f"{name}|tan_delta"] = results_data["TanDelta"][i]

    metadata = _result_metadata(results_data, {"content": "optical-parameters"})
    return write_table_txt(target, columns, metadata)


def save_time_freq_domain_data_to_txt(results_data, filename):
    """
    将加窗后的时域、频域数据分别保存为 txt。

    参数:
        results_data: 计算结果数据字典
        filename: 基准路径，实际生成 *_时域.txt 与 *_频域.txt

    返回:
        list[str]: 实际保存的文件路径列表
    """
    target = _ensure_txt_path(filename)
    root, _ext = os.path.splitext(target)
    info(f"开始保存时频域数据到: {root}_时域.txt / {root}_频域.txt")

    sam_names = results_data.get("sam_names", []) or []
    time_data = results_data.get("time_data")
    ref_windowed = results_data.get("ref_windowed")
    samples_windowed = results_data.get("samples_windowed") or []
    frequency = results_data.get("F")
    ref_fft = results_data.get("ref_fft")
    samples_fft = results_data.get("samples_fft") or []

    saved = []

    if time_data is not None and ref_windowed is not None:
        columns = {"Time[ps]": time_data, "Reference|windowed": ref_windowed}
        for i, name in enumerate(sam_names):
            if i < len(samples_windowed):
                columns[f"{name}|windowed"] = samples_windowed[i]
        metadata = _result_metadata(results_data, {"content": "time-domain"})
        saved.append(write_table_txt(f"{root}_时域.txt", columns, metadata))

    if frequency is not None and ref_fft is not None:
        columns = {"Frequency[THz]": frequency, "Reference|magnitude": ref_fft}
        for i, name in enumerate(sam_names):
            if i < len(samples_fft):
                columns[f"{name}|magnitude"] = samples_fft[i]
        metadata = _result_metadata(results_data, {"content": "frequency-domain"})
        saved.append(write_table_txt(f"{root}_频域.txt", columns, metadata))

    if not saved:
        raise SaveError(target, "结果中缺少时域/频域数据")

    return saved


__all__ = [
    "DELAY_UM_TO_PS",
    "read_data_file",
    "load_standard_signal",
    "read_standard_txt",
    "write_standard_txt",
    "detect_source_format",
    "write_table_txt",
    "read_table_txt",
    "save_results_to_txt",
    "save_time_freq_domain_data_to_txt",
]
