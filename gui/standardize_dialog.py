#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
阶段一：数据标准化对话框

把各种格式的原始测量文件统一转换为两列数据（时间 ps / 幅值），
支持导出为标准 txt，并指定其中一条为参考数据、若干条为样品数据，
交给阶段二（光学参数计算）使用。
"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout
)

from core.standard_format import (
    INPUT_FILE_FILTER, SUPPORTED_INPUT_EXTENSIONS, export_standard_signals,
    make_unique_names, write_standard_txt,
)
from utils import info, error

from .worker import StandardizeWorker


ROLE_UNUSED = "未使用"
ROLE_REFERENCE = "参考"
ROLE_SAMPLE = "样品"
ROLE_CHOICES = (ROLE_UNUSED, ROLE_REFERENCE, ROLE_SAMPLE)

COLUMNS = ("角色", "名称", "点数", "时间范围 (ps)", "Δt (ps)", "来源格式", "源文件")


class StandardizeDialog(QDialog):
    """原始数据 -> 统一两列数据的转换与选择对话框。"""

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config if config is not None else {}

        #: 已标准化的信号（与表格行一一对应）
        self.signals = []

        #: 点击“应用到分析”后的输出，供主窗口读取
        self.reference_file = ""
        self.reference_name = ""
        self.sample_files = []
        self.sample_names = []
        self.exported_dir = ""

        self._worker = None

        self.setWindowTitle("第一步：数据标准化（统一为两列 时间/幅值）")
        self.setMinimumSize(980, 620)
        self.setAcceptDrops(True)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; }")

        self._setup_ui()
        self._update_summary()

    # ------------------------------------------------------------------
    # 界面
    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        tip = QLabel(
            "支持 BT-FTS 时域扫描 txt、Excel、CSV 及任意分隔符两列文本；"
            "多扫描文件可拆分为多条信号。转换结果统一为：第一列时间(ps)，第二列幅值。"
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #666666;")
        layout.addWidget(tip)

        layout.addLayout(self._create_import_row())
        layout.addWidget(self._create_table(), 1)
        layout.addLayout(self._create_output_row())

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("color: #555555;")
        layout.addWidget(self.summary_label)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        layout.addLayout(self._create_button_row())

    def _create_import_row(self):
        row = QHBoxLayout()
        row.setSpacing(8)

        import_btn = QPushButton("导入原始数据")
        import_btn.clicked.connect(self._import_files)
        row.addWidget(import_btn)

        remove_btn = QPushButton("移除选中")
        remove_btn.clicked.connect(self._remove_selected)
        row.addWidget(remove_btn)

        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._clear_all)
        row.addWidget(clear_btn)

        row.addSpacing(16)
        row.addWidget(QLabel("数据起始行:"))
        self.start_row_spin = QSpinBox()
        self.start_row_spin.setRange(0, 1000)
        self.start_row_spin.setValue(0)  # 0 = 自动检测（默认）
        self.start_row_spin.setSpecialValueText("自动检测")
        self.start_row_spin.setToolTip(
            "0 = 自动检测（推荐，自动跳过表头）；\n"
            "仅对 Excel / 纯文本表格有效；\n"
            "标准 txt 和 BT-FTS 扫描格式会自动忽略此参数"
        )
        row.addWidget(self.start_row_spin)

        row.addSpacing(12)
        row.addWidget(QLabel("多扫描文件:"))
        self.scan_mode_combo = QComboBox()
        self.scan_mode_combo.addItem("每条扫描单独一条信号", "each")
        self.scan_mode_combo.addItem("所有扫描取平均", "average")
        saved_mode = self.config.get("scan_mode", "each")
        index = self.scan_mode_combo.findData(saved_mode)
        if index >= 0:
            self.scan_mode_combo.setCurrentIndex(index)
        row.addWidget(self.scan_mode_combo)

        row.addStretch()
        return row

    def _create_table(self):
        group = QGroupBox("标准化后的信号（在“角色”列指定参考 / 样品）")
        group_layout = QVBoxLayout(group)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.itemChanged.connect(self._on_item_changed)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in range(2, len(COLUMNS) - 1):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(COLUMNS) - 1, QHeaderView.ResizeMode.Stretch)

        group_layout.addWidget(self.table)
        return group

    def _create_output_row(self):
        row = QHBoxLayout()
        row.setSpacing(8)

        row.addWidget(QLabel("标准 txt 输出目录:"))
        self.out_dir_edit = QLineEdit(self._default_output_dir())
        row.addWidget(self.out_dir_edit, 1)

        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self._browse_output_dir)
        row.addWidget(browse_btn)

        # 导出入口：把标准化结果写出为两列标准 txt
        export_btn = QPushButton("导出为 TXT")
        export_btn.setToolTip(
            "把标准化结果写出为两列标准 txt，可独立使用或供主界面直接选择"
        )
        export_btn.clicked.connect(self._export_txt)
        row.addWidget(export_btn)

        return row

    def _create_button_row(self):
        row = QHBoxLayout()
        row.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.reject)
        row.addWidget(close_btn)
        return row

    # ------------------------------------------------------------------
    # 导入
    # ------------------------------------------------------------------
    def _default_output_dir(self):
        candidate = self.config.get("standardized_dir", "")
        if candidate:
            return candidate
        base = self.config.get("last_save_dir") or self.config.get("last_open_dir")
        if base and os.path.isdir(base):
            return os.path.join(base, "standardized")
        return os.path.join(os.getcwd(), "standardized")

    def _initial_dir(self):
        candidate = self.config.get("last_open_dir", "")
        if candidate and os.path.isdir(candidate):
            return candidate
        return os.getcwd()

    def _import_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择原始数据文件", self._initial_dir(), INPUT_FILE_FILTER
        )
        if file_paths:
            self._standardize(file_paths)

    def _standardize(self, file_paths):
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(self, "提示", "正在转换中，请稍候…")
            return

        self.config["last_open_dir"] = os.path.dirname(file_paths[0])
        if not self.out_dir_edit.text().strip():
            self.out_dir_edit.setText(
                os.path.join(os.path.dirname(file_paths[0]), "standardized")
            )

        self.progress.setVisible(True)
        self.progress.setRange(0, len(file_paths))
        self.progress.setValue(0)
        self.progress.setFormat("正在解析… %v/%m")

        self._worker = StandardizeWorker(self)
        self._worker.set_parameters(
            file_paths,
            start_row=self.start_row_spin.value(),
            scan_mode=self.scan_mode_combo.currentData(),
        )
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.standardize_finished.connect(self._on_standardize_finished)
        self._worker.standardize_error.connect(self._on_standardize_error)
        self._worker.start()

    def _on_progress(self, current, total, message):
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(current)
        self.progress.setFormat(f"{message} %v/%m")

    def _on_standardize_finished(self, signals, errors):
        self.progress.setVisible(False)

        for signal in signals:
            self.signals.append(signal)
        make_unique_names(self.signals)
        self._rebuild_table()

        if errors:
            QMessageBox.warning(
                self, "部分文件转换失败", "以下文件未能转换：\n\n" + "\n".join(errors)
            )
        if signals:
            info(f"标准化新增 {len(signals)} 条信号")

    def _on_standardize_error(self, message):
        self.progress.setVisible(False)
        error(f"标准化失败: {message}")
        QMessageBox.critical(self, "转换失败", message)

    # ------------------------------------------------------------------
    # 表格维护
    # ------------------------------------------------------------------
    def _rebuild_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        for row, signal in enumerate(self.signals):
            self.table.insertRow(row)

            combo = QComboBox()
            combo.addItems(ROLE_CHOICES)
            combo.setCurrentText(self._suggest_role(row, signal))
            combo.currentTextChanged.connect(
                lambda text, r=row: self._on_role_changed(r, text)
            )
            self.table.setCellWidget(row, 0, combo)

            name_item = QTableWidgetItem(signal.name)
            name_item.setToolTip("双击可修改名称，将用于图例与结果列名")
            self.table.setItem(row, 1, name_item)

            self._set_readonly_cell(row, 2, str(signal.points))
            self._set_readonly_cell(
                row, 3, f"{signal.t_start:.4f} ~ {signal.t_end:.4f}"
            )
            self._set_readonly_cell(row, 4, f"{signal.dt:.6f}")
            self._set_readonly_cell(row, 5, signal.source_format)

            source = signal.source_path
            item = QTableWidgetItem(os.path.basename(source))
            item.setToolTip(source)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 6, item)

        self.table.blockSignals(False)
        self._update_summary()

    def _set_readonly_cell(self, row, col, text):
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, col, item)

    def _suggest_role(self, row, signal):
        """首次填表时给出建议角色：文件名含 reference/ref 的作为参考。"""
        existing = signal.metadata.get("role")
        if existing in ROLE_CHOICES:
            return existing

        lowered = f"{signal.name} {signal.source_path}".lower()
        if "reference" in lowered or "_ref" in lowered:
            if not self._has_reference():
                signal.metadata["role"] = ROLE_REFERENCE
                return ROLE_REFERENCE
        role = ROLE_SAMPLE if self._has_reference() else (
            ROLE_REFERENCE if row == 0 else ROLE_SAMPLE
        )
        signal.metadata["role"] = role
        return role

    def _has_reference(self):
        return any(
            signal.metadata.get("role") == ROLE_REFERENCE for signal in self.signals
        )

    def _on_role_changed(self, row, text):
        if row >= len(self.signals):
            return
        if text == ROLE_REFERENCE:
            # 参考数据唯一
            for index, signal in enumerate(self.signals):
                if index != row and signal.metadata.get("role") == ROLE_REFERENCE:
                    signal.metadata["role"] = ROLE_SAMPLE
                    widget = self.table.cellWidget(index, 0)
                    if widget is not None:
                        widget.blockSignals(True)
                        widget.setCurrentText(ROLE_SAMPLE)
                        widget.blockSignals(False)
        self.signals[row].metadata["role"] = text
        self._update_summary()

    def _on_item_changed(self, item):
        if item.column() != 1:
            return
        row = item.row()
        if row < len(self.signals):
            new_name = item.text().strip()
            if new_name:
                self.signals[row].name = new_name
            else:
                item.setText(self.signals[row].name)

    def _selected_rows(self):
        return sorted({index.row() for index in self.table.selectedIndexes()})

    def _remove_selected(self):
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "提示", "请先选择要移除的行")
            return
        for row in reversed(rows):
            if row < len(self.signals):
                del self.signals[row]
        self._rebuild_table()

    def _clear_all(self):
        self.signals = []
        self._rebuild_table()

    def _update_summary(self):
        reference = [s for s in self.signals if s.metadata.get("role") == ROLE_REFERENCE]
        samples = [s for s in self.signals if s.metadata.get("role") == ROLE_SAMPLE]
        self.summary_label.setText(
            f"共 {len(self.signals)} 条信号　|　参考 {len(reference)} 条　|　"
            f"样品 {len(samples)} 条"
        )

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------
    def _browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "选择输出目录", self.out_dir_edit.text() or self._initial_dir()
        )
        if directory:
            self.out_dir_edit.setText(directory)

    def _resolve_output_dir(self):
        out_dir = self.out_dir_edit.text().strip()
        if not out_dir:
            QMessageBox.warning(self, "提示", "请先指定输出目录")
            return ""
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "目录错误", f"无法创建目录：\n{exc}")
            return ""
        self.config["standardized_dir"] = out_dir
        return out_dir

    def _export_txt(self):
        """预处理导出：仅把标准化结果写出标准 txt，与分析流程完全解耦。"""
        if not self.signals:
            QMessageBox.information(self, "提示", "请先导入并转换数据")
            return

        out_dir = self._resolve_output_dir()
        if not out_dir:
            return

        rows = self._selected_rows()
        targets = [self.signals[r] for r in rows] if rows else list(self.signals)

        try:
            paths = export_standard_signals(targets, out_dir)
        except Exception as exc:  # noqa: BLE001
            error(f"导出标准 txt 失败: {exc}")
            QMessageBox.critical(self, "导出失败", str(exc))
            return

        self.exported_dir = out_dir
        QMessageBox.information(
            self, "导出成功",
            f"已导出 {len(paths)} 个标准 txt 到：\n{out_dir}\n\n"
            f"这些标准文件可直接在主界面作为参考/样品选择使用。"
        )

    def _apply_to_analysis(self):
        """分析入口：把标记为参考/样品的信号导出为标准 txt，并以其磁盘路径交给第二步。

        导出与分析分离：此处总是先把数据落盘为标准 txt，再读取这些文件路径返回，
        保证第二阶段计算严格基于可追溯的标准文件，而非内存对象。
        """
        reference = None
        samples = []
        for signal in self.signals:
            role = signal.metadata.get("role")
            if role == ROLE_REFERENCE:
                reference = signal
            elif role == ROLE_SAMPLE:
                samples.append(signal)

        if reference is None:
            QMessageBox.warning(self, "提示", "请先在“角色”列指定一条参考数据")
            return
        if not samples:
            QMessageBox.warning(self, "提示", "请至少指定一条样品数据")
            return

        out_dir = self._resolve_output_dir()
        if not out_dir:
            return

        try:
            ref_path = write_standard_txt(
                reference, os.path.join(out_dir, f"{_safe_stem(reference.name)}.txt")
            )
            reference.metadata["standard_file"] = os.path.abspath(ref_path)
            sample_paths = export_standard_signals(samples, out_dir)
        except Exception as exc:  # noqa: BLE001
            error(f"导出标准 txt 失败: {exc}")
            QMessageBox.critical(self, "导出失败", str(exc))
            return

        # 第二阶段输入一律来自导出的标准 txt 文件（物理分离）
        self.reference_file = os.path.abspath(ref_path)
        self.reference_name = reference.name
        self.sample_files = [os.path.abspath(p) for p in sample_paths]
        self.sample_names = [signal.name for signal in samples]
        self.exported_dir = out_dir

        info(
            f"阶段一完成：参考 {reference.name}，样品 {len(samples)} 条，输出 {out_dir}"
        )
        self.accept()

    # ------------------------------------------------------------------
    # 拖放
    # ------------------------------------------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path) and path.lower().endswith(
                SUPPORTED_INPUT_EXTENSIONS
            ):
                paths.append(path)
        if paths:
            self._standardize(paths)


def _safe_stem(name):
    invalid = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in invalid else ch for ch in str(name)).strip()
    return cleaned or "reference"
