#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一数据格式模块（阶段一）

职责：
    把各种来源的原始测量文件（BT-FTS 时域扫描 txt、Excel、任意分隔符文本、CSV）
    统一转换为两列标准数据：第一列时间(ps)、第二列幅值，并可导出为标准 txt。

标准 txt 结构（所有元数据以 '#' 注释行给出，保证可追溯）::

    # THz-STD-1.0
    # name: PTFE_scan1
    # source_file: D:/data/PTFE_20260804202059_Time.txt
    # source_format: thz-scan
    # ...
    # Time[ps]\tAmplitude
    0.0000000\t-1.23e-04
    ...

阶段二的所有计算都以该格式为输入，保证两个阶段的数据格式完全一致。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from utils import info, warning
from .exceptions import DataReadError, SaveError


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: 标准格式版本标识，写在标准 txt 的第一行
STANDARD_MAGIC = "THz-STD-1.0"

#: 标准两列列名
TIME_COLUMN = "Time[ps]"
AMPLITUDE_COLUMN = "Amplitude"

#: 数值写出格式（有效数字 9 位，兼顾精度与可读性）
NUMBER_FORMAT = "%.9g"

#: 光速，单位 um/ps
LIGHT_SPEED_UM_PER_PS = 299.792458

#: 延迟台位移与光程差的关系系数。
#: 1.0 表示单程光程差（光程差 = 位移）；若仪器为往返光程请改为 2.0。
DELAY_PATH_FACTOR = 1.0

#: 可识别的源格式标识
FORMAT_STANDARD = "standard-txt"
FORMAT_THZ_SCAN = "thz-scan"
FORMAT_EXCEL = "excel"
FORMAT_DELIMITED = "delimited-text"

#: 阶段一支持导入的文件后缀
SUPPORTED_INPUT_EXTENSIONS = (".txt", ".csv", ".dat", ".asc", ".xlsx", ".xls")

#: 文件选择对话框使用的过滤器
INPUT_FILE_FILTER = (
    "所有支持的格式 (*.txt *.csv *.dat *.asc *.xlsx *.xls);;"
    "文本文件 (*.txt *.csv *.dat *.asc);;"
    "Excel 文件 (*.xlsx *.xls);;"
    "所有文件 (*)"
)

#: 分析阶段（第二步）只接受经过预处理导出的标准两列 txt
STANDARD_TXT_FILTER = (
    "标准两列 txt (*.txt);;所有文件 (*)"
)


def delay_um_to_ps(x_um: np.ndarray | float) -> np.ndarray | float:
    """延迟台位移(um) 转换为时间延迟(ps)。"""
    return np.asarray(x_um) * DELAY_PATH_FACTOR / LIGHT_SPEED_UM_PER_PS


# ---------------------------------------------------------------------------
# 标准信号数据结构
# ---------------------------------------------------------------------------

@dataclass
class StandardSignal:
    """统一后的两列时域信号。"""

    name: str
    time: np.ndarray
    amplitude: np.ndarray
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.time = np.asarray(self.time, dtype=float).ravel()
        self.amplitude = np.asarray(self.amplitude, dtype=float).ravel()
        if self.time.size != self.amplitude.size:
            n = min(self.time.size, self.amplitude.size)
            self.time = self.time[:n]
            self.amplitude = self.amplitude[:n]
        if self.time.size < 2:
            raise ValueError(f"信号 {self.name} 至少需要两个数据点")

    # -- 基本属性 ---------------------------------------------------------
    @property
    def points(self) -> int:
        return int(self.time.size)

    @property
    def t_start(self) -> float:
        return float(self.time[0])

    @property
    def t_end(self) -> float:
        return float(self.time[-1])

    @property
    def dt(self) -> float:
        return float(np.mean(np.diff(self.time))) if self.points > 1 else 0.0

    @property
    def source_path(self) -> str:
        return self.metadata.get("source_file", "")

    @property
    def source_format(self) -> str:
        return self.metadata.get("source_format", "")

    def to_dataframe(self) -> pd.DataFrame:
        """转换为两列 DataFrame（列名 time / intensity，供计算层使用）。"""
        return pd.DataFrame({"time": self.time, "intensity": self.amplitude})

    def describe(self) -> str:
        return (
            f"{self.name}: {self.points} 点, "
            f"{self.t_start:.4f}~{self.t_end:.4f} ps, dt={self.dt:.6f} ps"
        )


# ---------------------------------------------------------------------------
# 格式识别
# ---------------------------------------------------------------------------

def _iter_head_lines(file_path: str, max_lines: int = 60):
    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i >= max_lines:
                break
            yield line.rstrip("\r\n")


def is_standard_txt(file_path: str) -> bool:
    """判断是否为本程序导出的标准两列 txt。"""
    try:
        for line in _iter_head_lines(file_path, 5):
            if not line.strip():
                continue
            return line.lstrip("#").strip().startswith("THz-STD")
    except Exception:
        return False
    return False


def is_thz_scan_txt(file_path: str) -> bool:
    """判断是否为 BT-FTS 系列仪器导出的时域扫描格式。"""
    try:
        for line in _iter_head_lines(file_path, 60):
            if "TD Values" in line or line.startswith("Scan Velocity"):
                return True
    except Exception:
        return False
    return False


def detect_source_format(file_path: str) -> str:
    """识别文件格式，返回 FORMAT_* 常量之一。"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return FORMAT_EXCEL
    if is_standard_txt(file_path):
        return FORMAT_STANDARD
    if is_thz_scan_txt(file_path):
        return FORMAT_THZ_SCAN
    return FORMAT_DELIMITED


# ---------------------------------------------------------------------------
# 数据起始行自动检测
# ---------------------------------------------------------------------------

def _try_float_pair(text: str) -> tuple[bool, float | None, float | None]:
    """尝试把一行文本解析为两个浮点数，返回 (成功, val1, val2)。"""
    parts = text.replace(",", "\t").split()
    if len(parts) < 2:
        return False, None, None
    try:
        return True, float(parts[0]), float(parts[1])
    except (ValueError, OverflowError):
        return False, None, None


def detect_data_start_row(
    file_path: str,
    max_probe: int = 30,
    min_consecutive: int = 2,
) -> int:
    """
    自动检测表格类文件的数据起始行（从 1 开始）。

    策略：逐行扫描，找到第一个连续 min_consecutive 行都能解析为两个数值的位置。
    对标准 txt 和 BT-FTS 扫描格式直接返回固定值（它们有自描述头）。

    返回:
        起始行号（>= 1），若无法检测则返回 1
    """
    # 标准格式和扫描格式不需要用户指定起始行
    if is_standard_txt(file_path):
        return 1  # read_standard_txt 自行处理注释头
    if is_thz_scan_txt(file_path):
        return 1  # _parse_thz_scan 自行定位 TD Values

    ext = os.path.splitext(file_path)[1].lower()

    # Excel 文件：用 pandas 试读前几行
    if ext in (".xlsx", ".xls"):
        for trial_start in range(max(0, max_probe - 10), max_probe + 1):
            try:
                df = pd.read_excel(
                    file_path,
                    skiprows=trial_start,
                    header=None,
                    nrows=min_consecutive,
                    engine="openpyxl",
                )
                if df.shape[0] >= min_consecutive and df.shape[1] >= 2:
                    converted = df.iloc[:, :2].apply(
                        pd.to_numeric, errors="coerce"
                    )
                    if not converted.isna().any().any():
                        return trial_start + 1
            except Exception:
                continue
        return 1

    # 文本文件：逐行探测
    consecutive = 0
    for i, line in enumerate(_iter_head_lines(file_path, max_probe)):
        if not line.strip() or line.startswith("#"):
            consecutive = 0
            continue
        ok, _v1, _v2 = _try_float_pair(line)
        if ok:
            consecutive += 1
            if consecutive >= min_consecutive:
                # 回退到连续数值段的起始行
                return i - consecutive + min_consecutive + 1  # 1-based
        else:
            consecutive = 0

    return 1


# ---------------------------------------------------------------------------
# 各来源格式的解析
# ---------------------------------------------------------------------------

def _base_name(file_path: str) -> str:
    return os.path.splitext(os.path.basename(file_path))[0]


def _common_metadata(file_path: str, source_format: str) -> dict[str, str]:
    return {
        "source_file": os.path.abspath(file_path),
        "source_format": source_format,
        "converted_at": datetime.now().isoformat(timespec="seconds"),
        "time_unit": "ps",
    }


def _parse_thz_scan(
    file_path: str,
    scan_mode: str = "each",
) -> list[StandardSignal]:
    """
    解析 BT-FTS 时域扫描文件。

    文件结构：若干 key<TAB>value 表头行 -> 空行 -> 含 'TD Values -->' 的列头行
    -> 其后每行为一次扫描（若干元数据列 + 一长串时域幅值）。

    时间轴由元数据列 x0[um] / dx[um] 推导：t[ps] = (x0 + i*dx) * 系数

    参数:
        scan_mode: 'each' 每条扫描生成一条信号；'average' 所有扫描平均为一条
    """
    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as fh:
        lines = [ln.rstrip("\r\n") for ln in fh]

    header_idx = None
    for i, line in enumerate(lines):
        if "TD Values" in line:
            header_idx = i
            break
    if header_idx is None:
        raise DataReadError(file_path, "未找到包含 'TD Values' 的列头")

    columns = [c.strip() for c in lines[header_idx].split("\t")]
    td_start = None
    for j, col in enumerate(columns):
        if col.startswith("TD Values"):
            td_start = j
            break
    if td_start is None:
        raise DataReadError(file_path, "未找到 'TD Values' 数据列")

    # 文件头部的 key<TAB>value 元数据
    file_meta: dict[str, str] = {}
    for line in lines[:header_idx]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].strip():
            key = parts[0].strip().rstrip(":")
            value = parts[1].strip()
            if key and value and len(value) <= 120:
                file_meta[f"src.{key}"] = value

    idx_x0 = columns.index("x0[um]") if "x0[um]" in columns else None
    idx_dx = columns.index("dx[um]") if "dx[um]" in columns else None

    data_lines = [ln for ln in lines[header_idx + 1:] if ln.strip()]
    if not data_lines:
        raise DataReadError(file_path, "时域扫描文件不包含数据行")

    base = _base_name(file_path)
    parsed: list[tuple[np.ndarray, np.ndarray, dict[str, str]]] = []

    for k, ln in enumerate(data_lines, start=1):
        parts = ln.rstrip("\t").split("\t")
        if len(parts) <= td_start:
            continue
        try:
            td = np.array(
                [float(v) for v in parts[td_start:] if v.strip() != ""],
                dtype=float,
            )
        except ValueError as exc:
            warning(f"{base} 第 {k} 条扫描存在非数值项，已跳过：{exc}")
            continue
        if td.size < 2:
            continue

        x0 = dx = None
        if idx_x0 is not None and idx_dx is not None:
            try:
                x0 = float(parts[idx_x0])
                dx = float(parts[idx_dx])
            except (ValueError, IndexError):
                x0 = dx = None

        if x0 is None or dx is None:
            time_ps = np.arange(td.size, dtype=float)
            warning(f"{base} 第 {k} 条扫描缺少 x0/dx，时间轴按采样点索引生成")
        else:
            time_ps = np.asarray(
                delay_um_to_ps(x0 + np.arange(td.size, dtype=float) * dx),
                dtype=float,
            )

        row_meta = dict(file_meta)
        row_meta["scan_index"] = str(k)
        # 保留该扫描行的前置元数据列，便于追溯
        for j in range(min(td_start, len(parts))):
            key = columns[j] if j < len(columns) else f"col{j}"
            value = parts[j].strip()
            if key and value:
                row_meta[f"col.{key}"] = value
        parsed.append((time_ps, td, row_meta))

    if not parsed:
        raise DataReadError(file_path, "没有解析到有效的时域数据")

    if scan_mode == "average" and len(parsed) > 1:
        n = min(t.size for t, _a, _m in parsed)
        amplitude = np.mean([a[:n] for _t, a, _m in parsed], axis=0)
        meta = _common_metadata(file_path, FORMAT_THZ_SCAN)
        meta.update(parsed[0][2])
        meta["scan_index"] = "average"
        meta["averaged_scans"] = str(len(parsed))
        return [
            StandardSignal(
                name=f"{base}_avg",
                time=parsed[0][0][:n],
                amplitude=amplitude,
                metadata=meta,
            )
        ]

    signals = []
    multi = len(parsed) > 1
    for k, (time_ps, td, row_meta) in enumerate(parsed, start=1):
        meta = _common_metadata(file_path, FORMAT_THZ_SCAN)
        meta.update(row_meta)
        name = f"{base}_scan{k}" if multi else base
        signals.append(
            StandardSignal(name=name, time=time_ps, amplitude=td, metadata=meta)
        )
    return signals


def _parse_two_column_table(file_path: str, start_row: int = 1) -> StandardSignal:
    """解析 Excel / 任意分隔符文本的前两列。"""
    ext = os.path.splitext(file_path)[1].lower()
    skip = max(0, int(start_row) - 1)

    if ext in (".xlsx", ".xls"):
        data = pd.read_excel(
            file_path, skiprows=skip, header=None, engine="openpyxl"
        )
        source_format = FORMAT_EXCEL
    else:
        source_format = FORMAT_DELIMITED
        data = None
        last_error: Exception | None = None
        for kwargs in (
            {"sep": None, "engine": "python"},
            {"sep": r"\s+", "engine": "python"},
            {"sep": ",", "engine": "python"},
            {"sep": "\t", "engine": "python"},
        ):
            try:
                candidate = pd.read_csv(
                    file_path,
                    skiprows=skip,
                    header=None,
                    comment="#",
                    skip_blank_lines=True,
                    **kwargs,
                )
                if candidate.shape[1] >= 2:
                    data = candidate
                    break
            except Exception as exc:  # noqa: BLE001 - 逐个尝试分隔符
                last_error = exc
        if data is None:
            raise DataReadError(
                file_path,
                f"无法解析文本文件（尝试了多种分隔符）：{last_error}",
            )

    if data.shape[1] < 2:
        raise DataReadError(file_path, "数据文件必须至少包含两列：时间和幅值")

    frame = data.iloc[:, :2].apply(pd.to_numeric, errors="coerce").dropna()
    if len(frame) < 2:
        raise DataReadError(
            file_path,
            "有效数值行不足，请检查“数据起始行”设置是否正确",
        )

    meta = _common_metadata(file_path, source_format)
    meta["start_row"] = str(int(start_row))
    return StandardSignal(
        name=_base_name(file_path),
        time=frame.iloc[:, 0].to_numpy(dtype=float),
        amplitude=frame.iloc[:, 1].to_numpy(dtype=float),
        metadata=meta,
    )


# ---------------------------------------------------------------------------
# 标准 txt 读写
# ---------------------------------------------------------------------------

def read_standard_txt(file_path: str) -> StandardSignal:
    """读取标准两列 txt，元数据从注释行还原。"""
    metadata: dict[str, str] = {}
    times: list[float] = []
    amplitudes: list[float] = []

    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                body = line.lstrip("#").strip()
                if not body or body.startswith("THz-STD"):
                    continue
                if ":" in body:
                    key, _sep, value = body.partition(":")
                    metadata[key.strip()] = value.strip()
                continue
            parts = line.replace(",", "\t").split()
            if len(parts) < 2:
                continue
            try:
                times.append(float(parts[0]))
                amplitudes.append(float(parts[1]))
            except ValueError:
                continue

    if len(times) < 2:
        raise DataReadError(file_path, "标准 txt 中没有解析到有效数据")

    name = metadata.get("name") or _base_name(file_path)
    metadata.setdefault("source_file", os.path.abspath(file_path))
    metadata.setdefault("source_format", FORMAT_STANDARD)
    metadata["standard_file"] = os.path.abspath(file_path)
    return StandardSignal(
        name=name,
        time=np.asarray(times, dtype=float),
        amplitude=np.asarray(amplitudes, dtype=float),
        metadata=metadata,
    )


def write_standard_txt(signal: StandardSignal, file_path: str) -> str:
    """把标准信号写为两列 txt，返回实际写出的路径。"""
    try:
        directory = os.path.dirname(os.path.abspath(file_path))
        if directory:
            os.makedirs(directory, exist_ok=True)

        header: dict[str, str] = {
            "name": signal.name,
            "points": str(signal.points),
            "time_unit": "ps",
            "t_start": f"{signal.t_start:.9g}",
            "t_end": f"{signal.t_end:.9g}",
            "dt": f"{signal.dt:.9g}",
        }
        header.update(signal.metadata)
        header["exported_at"] = datetime.now().isoformat(timespec="seconds")

        with open(file_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f"# {STANDARD_MAGIC}\n")
            for key, value in header.items():
                text = str(value).replace("\n", " ").replace("\r", " ")
                fh.write(f"# {key}: {text}\n")
            fh.write(f"# {TIME_COLUMN}\t{AMPLITUDE_COLUMN}\n")
            for t, a in zip(signal.time, signal.amplitude):
                fh.write(f"{NUMBER_FORMAT % t}\t{NUMBER_FORMAT % a}\n")

        info(f"标准数据已导出: {file_path} ({signal.points} 点)")
        return file_path
    except Exception as exc:  # noqa: BLE001
        raise SaveError(file_path, str(exc))


# ---------------------------------------------------------------------------
# 对外统一入口
# ---------------------------------------------------------------------------

def standardize_file(
    file_path: str,
    start_row: int = 0,
    scan_mode: str = "each",
) -> list[StandardSignal]:
    """
    把任意支持格式的文件转换为标准信号列表。

    参数:
        file_path: 源文件路径
        start_row: 纯表格类文件的数据起始行（从 1 开始）。
            设为 0 表示自动检测（默认，推荐）。
            仅对 Excel / 分隔符文本有效；标准 txt 和 BT-FTS 扫描格式自动忽略此参数。
        scan_mode: 多扫描文件的处理方式，'each' 拆分为多条，'average' 取平均

    返回:
        list[StandardSignal]：多扫描文件可能返回多条
    """
    if not os.path.exists(file_path):
        raise DataReadError(file_path, "文件不存在")

    # 自动检测起始行
    if start_row <= 0:
        start_row = detect_data_start_row(file_path)
        info(f"自动检测起始行: {os.path.basename(file_path)} -> 第 {start_row} 行")

    try:
        source_format = detect_source_format(file_path)
        if source_format == FORMAT_STANDARD:
            signals = [read_standard_txt(file_path)]
        elif source_format == FORMAT_THZ_SCAN:
            signals = _parse_thz_scan(file_path, scan_mode=scan_mode)
        else:
            signals = [_parse_two_column_table(file_path, start_row)]

        info(
            f"标准化完成: {os.path.basename(file_path)} "
            f"[{source_format}] -> {len(signals)} 条信号"
        )
        return signals
    except DataReadError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DataReadError(file_path, str(exc))


def standardize_files(
    file_paths,
    start_row: int = 1,
    scan_mode: str = "each",
) -> tuple[list[StandardSignal], list[str]]:
    """批量标准化，返回 (信号列表, 错误信息列表)。"""
    signals: list[StandardSignal] = []
    errors: list[str] = []
    for path in file_paths:
        try:
            signals.extend(standardize_file(path, start_row, scan_mode))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{os.path.basename(path)}: {exc}")
    return signals, errors


def make_unique_names(signals) -> None:
    """就地保证信号名称唯一（重名追加 _2、_3 ...）。"""
    seen: dict[str, int] = {}
    for signal in signals:
        base = signal.name
        if base not in seen:
            seen[base] = 1
            continue
        seen[base] += 1
        signal.name = f"{base}_{seen[base]}"


def export_standard_signals(signals, out_dir: str) -> list[str]:
    """把多条标准信号导出到目录，文件名取信号名，返回导出路径列表。"""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    used: set[str] = set()
    for signal in signals:
        stem = _safe_file_stem(signal.name)
        candidate = stem
        counter = 2
        while candidate.lower() in used:
            candidate = f"{stem}_{counter}"
            counter += 1
        used.add(candidate.lower())
        target = os.path.join(out_dir, f"{candidate}.txt")
        write_standard_txt(signal, target)
        signal.metadata["standard_file"] = os.path.abspath(target)
        paths.append(target)
    return paths


def _safe_file_stem(name: str) -> str:
    invalid = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in invalid else ch for ch in str(name)).strip()
    return cleaned or "signal"
