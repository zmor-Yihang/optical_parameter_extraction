#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据输入输出模块

- 读取：统一走 core.standard_format，任何来源格式都会被转换为两列 [时间(ps), 幅值]
- 写出：
    - 分析结果保存为 Excel (.xlsx)：每个源文件一个工作表，工作表名使用文件名；
    - 同时保留 CSV 写出接口（write_table_csv / save_results_to_csv）供脚本与旧版调用。
"""

from __future__ import annotations

import csv
import os
import re
from collections.abc import Mapping
from datetime import datetime

import numpy as np

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
        StandardSignal: 含 .time / .amplitude 两个一维数组

    支持:
        - 本程序阶段一导出的标准 txt（带 '# THz-STD' 头）
        - BT-FTS 系列仪器导出的时域扫描 txt（多扫描时自动取平均）
        - Excel (.xlsx/.xls)
        - 任意分隔符的两列文本 (.txt/.csv/.dat/.asc)
    """
    try:
        signals = standardize_file(file_path, start_row=start_row, scan_mode="average")
        info(f"成功读取文件: {file_path}")
        return signals[0]
    except DataReadError:
        raise
    except Exception as e:
        exception(f"读取文件 {file_path} 时出错")
        raise DataReadError(file_path, str(e))


def load_standard_signal(file_path, start_row=1):
    """读取单个文件并返回 StandardSignal（多扫描取平均）。"""
    return standardize_file(file_path, start_row=start_row, scan_mode="average")[0]


# ---------------------------------------------------------------------------
# CSV 表格写出 / 读回
# ---------------------------------------------------------------------------

def write_table_csv(file_path, columns, metadata=None):
    """
    写出列式 CSV 数据表（逗号分隔、首行为表头）。

    参数:
        file_path: 目标路径
        columns: dict[列名, 一维数组]，按插入顺序写出
        metadata: 保留参数以兼容旧调用；不写入文件正文，
                  避免破坏电子表格对标准 CSV 的解析

    返回:
        str: 实际写出的路径
    """
    del metadata  # 兼容旧签名，CSV 正文仅含表头 + 数据行
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

        # utf-8-sig：带 BOM，Excel 等电子表格可正确识别 UTF-8 与中文列名
        # newline=""：交由 csv 模块处理换行，避免 Windows 多余空行
        with open(file_path, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(
                fh,
                delimiter=",",
                quotechar='"',
                quoting=csv.QUOTE_MINIMAL,
                lineterminator="\n",
            )
            writer.writerow(names)
            for row in range(length):
                writer.writerow(NUMBER_FORMAT % array[row] for array in arrays)

        info(f"数据已保存到: {file_path} ({length} 行 x {len(names)} 列)")
        return file_path
    except SaveError:
        raise
    except Exception as e:
        exception(f"写出 CSV 数据时出错: {e}")
        raise SaveError(file_path, str(e))


def write_table_txt(file_path, columns, metadata=None):
    """兼容旧接口：实际写出 CSV（路径后缀仍按调用方给定）。"""
    return write_table_csv(file_path, columns, metadata)


def read_table_csv(file_path):
    """读回 write_table_csv 写出的数据表。

    兼容：
      - 新格式 CSV（逗号分隔，可带 '# key: value' 注释头）
      - 旧格式结果 txt（制表符分隔，'# THz-RESULT' 头）

    返回 (columns, metadata)，其中 columns 为 dict[列名, np.ndarray]。
    """
    metadata = {}
    names = None
    try:
        with open(file_path, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
            # 先剥掉注释行，再交给 csv 解析，保证特殊字符与引号处理正确
            data_lines = []
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    body = line.lstrip("#").strip()
                    if not body or body.startswith("THz-"):
                        continue
                    # 旧 txt 表头：整行以 tab 分隔的列名
                    if "\t" in body and ":" not in body.split("\t", 1)[0]:
                        names = [item.strip() for item in body.split("\t")]
                        continue
                    if ":" in body:
                        key, _sep, value = body.partition(":")
                        metadata[key.strip()] = value.strip()
                    continue
                data_lines.append(raw)

        if not data_lines:
            return {}, metadata

        sample = "".join(data_lines[:8])
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        except csv.Error:
            dialect = csv.excel

        reader = csv.reader(data_lines, dialect)
        table = [row for row in reader if any(cell.strip() for cell in row)]
        if not table:
            return {}, metadata

        # 首行若无法全部解析为浮点，则视为表头
        first = table[0]
        def _all_float(cells):
            try:
                for cell in cells:
                    float(cell)
                return True
            except (TypeError, ValueError):
                return False

        if names is None and first and not _all_float(first):
            names = [str(cell).strip() for cell in first]
            table = table[1:]

        if not table:
            return {}, metadata

        width = max(len(row) for row in table)
        values = np.full((len(table), width), np.nan, dtype=float)
        for i, row in enumerate(table):
            for j, cell in enumerate(row):
                cell = (cell or "").strip()
                if not cell:
                    continue
                try:
                    values[i, j] = float(cell)
                except ValueError:
                    values[i, j] = np.nan

        if names and len(names) == width:
            columns = {name: values[:, i] for i, name in enumerate(names)}
        else:
            columns = {f"col{i}": values[:, i] for i in range(width)}
        return columns, metadata
    except Exception as e:
        exception(f"读取数据表 {file_path} 时出错")
        raise DataReadError(file_path, str(e))


def read_table_txt(file_path):
    """兼容旧接口：读回 CSV / 旧 txt 结果表。"""
    return read_table_csv(file_path)


def _ensure_csv_path(filename):
    root, ext = os.path.splitext(filename)
    return filename if ext.lower() == ".csv" else f"{root}.csv"


def _ensure_xlsx_path(filename):
    root, ext = os.path.splitext(filename)
    return filename if ext.lower() in (".xlsx", ".xlsm") else f"{root}.xlsx"


#: Excel 工作表名不允许的字符（: \ / ? * [ ]）
_INVALID_SHEET_CHARS = re.compile(r'[\\/:*?\[\]]')
#: Excel 工作表名最大长度
_MAX_SHEET_NAME_LEN = 31


def _safe_sheet_name(name: str, used: set[str] | None = None) -> str:
    """将文件名转换为合法的 Excel 工作表名（<=31 字符，去非法字符，避免重名）。"""
    cleaned = _INVALID_SHEET_CHARS.sub("_", str(name).strip())
    cleaned = cleaned or "Sheet"
    cleaned = cleaned[:_MAX_SHEET_NAME_LEN]
    if used is None:
        return cleaned
    base = cleaned
    counter = 2
    while cleaned in used:
        suffix = f"_{counter}"
        cleaned = f"{base[: _MAX_SHEET_NAME_LEN - len(suffix)]}{suffix}"
        counter += 1
    return cleaned


def _source_stem(source_files: Mapping, key: str, fallback: str) -> str:
    """从 source_files 中取源文件名的主干（不含扩展名），取不到时用 fallback。"""
    raw = source_files.get(key) if isinstance(source_files, Mapping) else None
    if raw:
        stem = os.path.splitext(os.path.basename(str(raw)))[0]
        if stem:
            return stem
    return fallback


def _write_excel_workbook(file_path, sheets: dict[str, dict]) -> str:
    """用 openpyxl 写出多工作表 Excel。

    参数:
        file_path: 目标路径
        sheets: 有序 dict{工作表名: {"headers": [列名...], "rows": [[值...], ...]}}

    返回:
        str: 实际写出的路径
    """
    from openpyxl import Workbook

    directory = os.path.dirname(os.path.abspath(file_path))
    if directory:
        os.makedirs(directory, exist_ok=True)

    workbook = Workbook()
    workbook.remove(workbook.active)  # 删除默认空工作表
    used_names: set[str] = set()
    for sheet_name, table in sheets.items():
        safe_name = _safe_sheet_name(sheet_name, used_names)
        used_names.add(safe_name)
        worksheet = workbook.create_sheet(title=safe_name)
        headers = table.get("headers") or []
        if headers:
            worksheet.append(list(headers))
        for row in table.get("rows") or []:
            worksheet.append(list(row))

    workbook.save(file_path)
    info(f"数据已保存到: {file_path} ({len(sheets)} 个工作表)")
    return file_path


def _stack_time_freq_tables(time_rows, time_headers, freq_rows, freq_headers) -> dict:
    """把时域表与频域表上下堆叠（中间空一行），构造成一个工作表的结构。"""
    headers: list = []
    rows: list = []
    if time_rows is not None:
        headers = list(time_headers)
        rows = [list(row) for row in time_rows]
    if freq_rows is not None:
        if time_rows is not None:
            rows.append([])  # 空行分隔两个表
        rows.append(list(freq_headers))
        rows.extend(list(row) for row in freq_rows)
    return {"headers": headers, "rows": rows}


def _result_metadata(results_data, extra=None):
    metadata = {
        "stage": "2-optical-parameters",
        "sample_count": str(len(results_data.get("sam_names", []) or [])),
    }
    thickness = results_data.get("thickness")
    if thickness is not None:
        metadata["thickness_mm"] = str(thickness)
    per_sample = results_data.get("per_sample_thickness")
    if per_sample:
        metadata["per_sample_thickness_mm"] = ";".join(
            str(value) if value is not None else "" for value in per_sample
        )
    if results_data.get("use_window") is not None:
        metadata["use_window"] = str(results_data.get("use_window"))
    sources = results_data.get("source_files")
    if isinstance(sources, Mapping):
        for key, value in sources.items():
            metadata[f"source.{key}"] = value
    metadata.update(extra or {})
    return metadata


# ---------------------------------------------------------------------------
# 结果保存（统一 CSV）
# ---------------------------------------------------------------------------

def save_results_to_csv(results_data, filename):
    """
    将光学参数计算结果保存为 CSV。

    参数:
        results_data: 计算结果数据字典
        filename: 保存的文件路径（非 .csv 后缀会自动改为 .csv）

    返回:
        str: 实际保存的文件路径
    """
    target = _ensure_csv_path(filename)
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
    return write_table_csv(target, columns, metadata)


def save_time_freq_domain_data_to_csv(results_data, filename):
    """
    将加窗后的时域、频域数据分别保存为 CSV。

    参数:
        results_data: 计算结果数据字典
        filename: 基准路径，实际生成 *_时域.csv 与 *_频域.csv

    返回:
        list[str]: 实际保存的文件路径列表
    """
    target = _ensure_csv_path(filename)
    root, _ext = os.path.splitext(target)
    info(f"开始保存时频域数据到: {root}_时域.csv / {root}_频域.csv")

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
        saved.append(write_table_csv(f"{root}_时域.csv", columns, metadata))

    if frequency is not None and ref_fft is not None:
        columns = {"Frequency[THz]": frequency, "Reference|magnitude": ref_fft}
        for i, name in enumerate(sam_names):
            if i < len(samples_fft):
                columns[f"{name}|magnitude"] = samples_fft[i]
        metadata = _result_metadata(results_data, {"content": "frequency-domain"})
        saved.append(write_table_csv(f"{root}_频域.csv", columns, metadata))

    if not saved:
        raise SaveError(target, "结果中缺少时域/频域数据")

    return saved


# ---------------------------------------------------------------------------
# 结果保存（Excel，每个文件一个工作表，工作表名用文件名）
# ---------------------------------------------------------------------------

def save_results_to_excel(results_data, filename):
    """将光学参数计算结果保存为 Excel，每个样品文件一个工作表，工作表名使用文件名。

    参数:
        results_data: 计算结果数据字典
        filename: 保存的文件路径（非 .xlsx 后缀会自动改为 .xlsx）

    返回:
        str: 实际保存的文件路径
    """
    target = _ensure_xlsx_path(filename)
    info(f"开始保存光学参数到: {target}")

    frequency = results_data.get("F")
    if frequency is None:
        raise SaveError(target, "结果中缺少频率数据")

    sam_names = results_data.get("sam_names", []) or []
    if not sam_names:
        raise SaveError(target, "没有可写出的样品数据")

    source_files = results_data.get("source_files")
    sheets = {}
    for i, name in enumerate(sam_names):
        sheet_title = _source_stem(source_files, name, str(name))
        sheets[sheet_title] = {
            "headers": [
                "Frequency[THz]",
                "n",
                "k",
                "alpha[cm^-1]",
                "eps_real",
                "eps_imag",
                "tan_delta",
            ],
            "rows": list(
                zip(
                    frequency,
                    results_data["Nsam"][i],
                    results_data["Ksam"][i],
                    results_data["Asam"][i],
                    results_data["Epsilon_real"][i],
                    results_data["Epsilon_imag"][i],
                    results_data["TanDelta"][i],
                )
            ),
        }

    return _write_excel_workbook(target, sheets)


def save_time_freq_domain_data_to_excel(results_data, filename):
    """将加窗后的时域、频域数据保存为 Excel，每个文件一个工作表，工作表名使用文件名。

    每个工作表内先写时域表（Time[ps]、参考加窗、该样品加窗），
    空一行后写频域表（Frequency[THz]、参考幅度、该样品幅度）。
    参考文件单独占一个工作表。

    参数:
        results_data: 计算结果数据字典
        filename: 保存的文件路径（非 .xlsx 后缀会自动改为 .xlsx）

    返回:
        str: 实际保存的文件路径
    """
    target = _ensure_xlsx_path(filename)
    info(f"开始保存时频域数据到: {target}")

    sam_names = results_data.get("sam_names", []) or []
    time_data = results_data.get("time_data")
    ref_windowed = results_data.get("ref_windowed")
    samples_windowed = results_data.get("samples_windowed") or []
    frequency = results_data.get("F")
    ref_fft = results_data.get("ref_fft")
    samples_fft = results_data.get("samples_fft") or []

    source_files = results_data.get("source_files")
    ref_title = _source_stem(source_files, "reference", "Reference")

    sheets = {}

    # 参考文件工作表：时域 + 频域（仅参考自身数据）
    ref_time_rows = (
        list(zip(time_data, ref_windowed))
        if time_data is not None and ref_windowed is not None
        else None
    )
    ref_freq_rows = (
        list(zip(frequency, ref_fft))
        if frequency is not None and ref_fft is not None
        else None
    )
    if ref_time_rows is not None or ref_freq_rows is not None:
        sheets[ref_title] = _stack_time_freq_tables(
            ref_time_rows,
            ["Time[ps]", "Reference|windowed"],
            ref_freq_rows,
            ["Frequency[THz]", "Reference|magnitude"],
        )

    # 每个样品一个工作表：时域 + 频域（参考 + 该样品）
    for i, name in enumerate(sam_names):
        time_rows = (
            list(zip(time_data, ref_windowed, samples_windowed[i]))
            if time_data is not None and ref_windowed is not None and i < len(samples_windowed)
            else None
        )
        freq_rows = (
            list(zip(frequency, ref_fft, samples_fft[i]))
            if frequency is not None and ref_fft is not None and i < len(samples_fft)
            else None
        )
        if time_rows is None and freq_rows is None:
            continue
        sheet_title = _source_stem(source_files, name, str(name))
        sheets[sheet_title] = _stack_time_freq_tables(
            time_rows,
            ["Time[ps]", "Reference|windowed", f"{name}|windowed"],
            freq_rows,
            ["Frequency[THz]", "Reference|magnitude", f"{name}|magnitude"],
        )

    if not sheets:
        raise SaveError(target, "结果中缺少时域/频域数据")

    return _write_excel_workbook(target, sheets)


# 兼容旧函数名
save_results_to_txt = save_results_to_csv
save_time_freq_domain_data_to_txt = save_time_freq_domain_data_to_csv


__all__ = [
    "DELAY_UM_TO_PS",
    "read_data_file",
    "load_standard_signal",
    "read_standard_txt",
    "write_standard_txt",
    "detect_source_format",
    "write_table_csv",
    "read_table_csv",
    "write_table_txt",
    "read_table_txt",
    "save_results_to_csv",
    "save_time_freq_domain_data_to_csv",
    "save_results_to_excel",
    "save_time_freq_domain_data_to_excel",
    "save_results_to_txt",
    "save_time_freq_domain_data_to_txt",
]
