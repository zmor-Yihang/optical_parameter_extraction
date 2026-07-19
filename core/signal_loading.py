"""信号文件加载。"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from utils import info

from .data_io import read_data_file


ProgressReporter = Callable[[str], None]


@dataclass(frozen=True)
class LoadedSignal:
    """从文件加载的单个时域信号。"""

    name: str
    path: str
    time: np.ndarray
    amplitude: np.ndarray


@dataclass(frozen=True)
class LoadedMeasurementSet:
    """参考信号与一组样品信号。"""

    reference: LoadedSignal
    samples: tuple[LoadedSignal, ...]


def load_measurements(
    ref_file: str,
    sam_files: Sequence[str],
    sam_names: Sequence[str],
    start_row: int = 1,
    progress_reporter: ProgressReporter | None = None,
) -> LoadedMeasurementSet:
    """加载参考信号和样品信号，不执行预处理。"""
    if len(sam_files) != len(sam_names):
        raise ValueError("样品文件数量与样品名称数量不一致")

    report = progress_reporter or (lambda _message: None)

    report("读取参考信号...")
    reference = _load_signal(ref_file, "参考信号", start_row)
    info(f"参考信号读取完成，数据点数: {len(reference.time)}")

    samples = []
    for file_path, name in zip(sam_files, sam_names):
        report(f"读取样品 {name}...")
        sample = _load_signal(file_path, name, start_row)
        samples.append(sample)
        info(f"样品 {name} 读取完成")

    return LoadedMeasurementSet(reference=reference, samples=tuple(samples))


def _load_signal(file_path: str, name: str, start_row: int) -> LoadedSignal:
    data = read_data_file(file_path, start_row)
    time = data.iloc[:, 0].to_numpy(dtype=float, copy=True)
    amplitude = data.iloc[:, 1].to_numpy(dtype=float, copy=True)
    return LoadedSignal(
        name=name,
        path=file_path,
        time=time,
        amplitude=amplitude,
    )