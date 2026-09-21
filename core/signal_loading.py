"""信号文件加载。"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from utils import info

from .data_io import read_data_file
from .standard_format import StandardSignal


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
    progress_reporter: ProgressReporter | None = None,
    ref_signal: StandardSignal | None = None,
    sam_signals: Sequence[StandardSignal | None] | None = None,
) -> LoadedMeasurementSet:
    """加载参考信号和样品信号，不执行预处理。

    参数:
        ref_signal / sam_signals: 可选的、已在内存中标准化好的信号。
            传入的项直接复用，跳过磁盘读取与格式解析（避免重复标准化）；
            为 None 的项回退到按对应文件路径读取。
    """
    if len(sam_files) != len(sam_names):
        raise ValueError("样品文件数量与样品名称数量不一致")
    if sam_signals is not None and len(sam_signals) != len(sam_files):
        raise ValueError("内存样品信号数量与样品文件数量不一致")

    report = progress_reporter or (lambda _message: None)

    report("读取参考信号...")
    reference = _load_signal(
        ref_file,
        "参考信号",
        in_memory=ref_signal,
    )
    info(f"参考信号读取完成，数据点数: {len(reference.time)}")

    samples = []
    for index, (file_path, name) in enumerate(zip(sam_files, sam_names)):
        report(f"读取样品 {name}...")
        in_memory = None
        if sam_signals is not None and index < len(sam_signals):
            in_memory = sam_signals[index]
        sample = _load_signal(file_path, name, in_memory=in_memory)
        samples.append(sample)
        info(f"样品 {name} 读取完成")

    return LoadedMeasurementSet(reference=reference, samples=tuple(samples))


def _load_signal(
    file_path: str,
    name: str,
    in_memory: StandardSignal | None = None,
) -> LoadedSignal:
    if in_memory is not None:
        time, amplitude = in_memory.to_arrays()
    else:
        signal = read_data_file(file_path)
        time, amplitude = signal.to_arrays()
    return LoadedSignal(
        name=name,
        path=file_path,
        time=time,
        amplitude=amplitude,
    )
