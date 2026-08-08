#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
THz光学参数分析系统主窗口
"""

import logging
import os
import shutil
import tempfile
from datetime import datetime

import matplotlib
matplotlib.use('QtAgg')  # 使用Qt6兼容后端
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QGroupBox,
    QMessageBox, QTabWidget, QListWidget, QListWidgetItem, QSplitter,
    QComboBox, QScrollArea, QDialog, QStyle,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QFont, QPalette, QColor, QBrush

from config import load_config, save_config, update_thickness_history
from core import calculate_optical_params
from core.calculator import build_result_figures
from core.standard_format import (
    INPUT_FILE_FILTER,
    standardize_file,
    write_standard_txt,
    is_standard_txt,
    read_standard_txt,
)
from core.plotting import (
    enable_curve_hover,
    enable_responsive_fonts,
    sample_color,
    short_display_name,
)
from utils import info, warning, error
from core.version import APP_VERSION, UPDATE_URL
from core.updater import is_newer

from .worker import CalculationWorker, SaveWorker
from .update_checker import UpdateCheckWorker
from .log_handler import LogViewHandler, log_line_html
from .dialogs import HelpDialog, AboutDialog, UpdateDialog, LogDialog
from .styles import get_main_window_style, get_menubar_style
from .status_bar import StatusBar
from .axis_range import AxisRangeBar
from .subplot_window import SubplotDetailWindow


class THzAnalyzerApp(QMainWindow):
    """THz光学参数分析系统的主应用程序类"""
    
    def __init__(self):
        super().__init__()
        
        info("正在初始化THz分析系统...")
        
        # 加载配置
        self.config = load_config()

        # 清理上次运行遗留的自动标准化临时文件
        self._cleanup_standardized_tmp()

        # 存储选中的文件
        self.ref_file = ""
        self.sam_files = []
        self.sam_names = []
        # 已标准化的内存信号（StandardSignal），与 ref_file / sam_files 一一对应，
        # 计算时直接复用，避免二次标准化
        self.ref_signal = None
        self.sam_signals = []
        
        # 存储窗函数参数
        self.ref_window_params = None
        self.per_sample_window_params = {}

        # 每个样品的单独厚度 (mm)，None 表示使用全局「样品厚度」
        self.per_sample_thickness: dict[int, float | None] = {}
        
        # 存储计算结果
        self.results_data = None
        
        # 存储图表数据的引用
        self.fig1 = None
        self.fig2 = None
        self.fig3 = None
        
        # 计算工作线程
        self.calc_worker = None
        
        # 保存工作线程
        self.save_worker = None
        
        # 状态栏
        self.status_bar = None
        
        # 设置窗口
        self.setWindowTitle("THz 时域光谱分析系统")
        self.setMinimumSize(1200, 800)
        self.setWindowIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        
        # 创建界面
        self._init_ui()
        
        # 将全局日志流接到左下角日志面板
        self._attach_log_handler()
        
        # 绑定窗口关闭事件
        self.closeEvent = self._on_closing

        info("THz分析系统初始化完成")

        # 启动后延迟执行静默更新检查（不阻塞界面初始化）
        QTimer.singleShot(3000, self._check_updates_auto)

    def _init_ui(self):
        """初始化用户界面"""
        self._setup_styles()
        self._create_menu_bar()
        
        # 创建中央窗口部件
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #FFFFFF;")
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 5)
        main_layout.setSpacing(5)
        
        # 创建水平分割器（左右面板）
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)
        
        # 创建左右面板
        self._create_left_panel()
        self._create_right_panel()
        
        # 添加左右面板到分割器
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([300, 900])
        
        main_layout.addWidget(splitter, 1)
        
        # 创建底部状态栏
        self.status_bar = StatusBar(self)
        main_layout.addWidget(self.status_bar)
        
        # 设置拖放支持
        self.setAcceptDrops(True)
    
    def _setup_styles(self):
        """设置全局样式"""
        self.setWindowTitle("THz 时域光谱分析系统")
        
        # 设置亮色主题窗口背景色
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#FFFFFF"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#444444"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F8F8F8"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#FFFFCC"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#444444"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#444444"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#F8F8F8"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#444444"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#5B7C99"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        self.setPalette(palette)
        
        # 设置全局字体
        app_font = QFont("微软雅黑", 9)
        QApplication.setFont(app_font)
        
        # 设置全局样式表
        self.setStyleSheet(get_main_window_style())
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        menubar.setStyleSheet(get_menubar_style())
        
        # 文件菜单：仅退出
        file_menu = menubar.addMenu("文件")

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 工具菜单：导出当前参考/样品为标准格式
        tool_menu = menubar.addMenu("工具")

        export_action = QAction("导出标准格式...", self)
        export_action.triggered.connect(self._export_standard_files)
        tool_menu.addAction(export_action)

        # 日志菜单：查看运行日志
        log_menu = menubar.addMenu("日志")
        view_log_action = QAction("查看运行日志...", self)
        view_log_action.triggered.connect(self._show_log_dialog)
        log_menu.addAction(view_log_action)

        # 帮助菜单：使用说明与关于
        help_menu = menubar.addMenu("帮助")

        user_guide_action = QAction("使用说明", self)
        user_guide_action.triggered.connect(self._show_help_dialog)
        help_menu.addAction(user_guide_action)

        check_update_action = QAction("检查更新...", self)
        check_update_action.triggered.connect(lambda: self._check_for_updates(True))
        help_menu.addAction(check_update_action)

        about_action = QAction("关于本软件", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)
    
    def _create_left_panel(self):
        """创建左侧控制面板"""
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)
        
        # 程序标题
        title_label = QLabel("THz 时域光谱分析系统")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont("微软雅黑", 12, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #333333; margin-bottom: 6px;")
        left_layout.addWidget(title_label)
        
        # 参数设置区
        param_group = self._create_param_group()
        left_layout.addWidget(param_group)
        left_layout.addStretch()
    
    def _attach_log_handler(self):
        """把全局日志流接到主窗口（经 Qt 信号跨线程安全投递），
        日志窗口未打开时暂存在内存缓存中。
        注意：handler 不设置 parent，避免主窗口销毁时 Qt 删除其 C++
        对象，导致 logging.shutdown() 在退出时访问已删除对象而报错。"""
        self._pending_logs = []
        self.log_handler = LogViewHandler()
        self.log_handler.message_appended.connect(self._append_log_message)
        logging.getLogger("THzAnalyzer").addHandler(self.log_handler)
    
    def _append_log_message(self, message: str, level: str):
        """在主线程处理一条日志：日志窗口已打开则实时追加，否则缓存。"""
        html = log_line_html(message, level)
        dialog = getattr(self, "log_dialog", None)
        if dialog is not None and dialog.isVisible():
            dialog.append_html(html)
            return
        self._pending_logs.append(html)
        if len(self._pending_logs) > 1000:
            del self._pending_logs[: len(self._pending_logs) - 1000]
    
    def _show_log_dialog(self):
        """打开（或激活）运行日志窗口，并灌入缓存的日志。"""
        if getattr(self, "log_dialog", None) is None:
            self.log_dialog = LogDialog(self)
        if not self.log_dialog.isVisible():
            for html in self._pending_logs:
                self.log_dialog.append_html(html)
            self._pending_logs = []
        self.log_dialog.show()
        self.log_dialog.raise_()
        self.log_dialog.activateWindow()
    
    def _show_subplot_details(self):
        """弹出非模态窗口，展示每个结果子图的标题、图表与关键指标摘要。"""
        figures = {
            "时域和频域": getattr(self, "fig1", None),
            "光学参数": getattr(self, "fig2", None),
            "介电特性": getattr(self, "fig3", None),
        }
        if all(figure is None for figure in figures.values()):
            QMessageBox.information(self, "提示", "请先运行分析生成图表")
            return
        self.subplot_window = SubplotDetailWindow(figures, self)
        self.subplot_window.show()
        info("已打开子图详情窗口")

    def _create_param_group(self):
        """创建参数设置组"""
        param_group = QGroupBox("参数设置")
        param_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 8px;
                background-color: #FAFAFA;
                color: #333333;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: #555555;
            }
        """)
        param_layout = QVBoxLayout(param_group)
        param_layout.setSpacing(12)
        
        # 参考文件选择（直接选，代码自动标准化）
        self._create_ref_file_section(param_layout)
        
        # 样品文件选择（直接选，代码自动标准化）
        self._create_sam_file_section(param_layout)
        
        # 参数设置
        self._create_parameter_section(param_layout)
        
        # 按钮组
        self._create_button_section(param_layout)
        
        return param_group
    
    def _standardized_dir(self) -> str:
        """返回自动标准化临时目录（系统临时目录下，不污染项目目录）。

        仅存放分析用的中间标准 txt（由 write_standard_txt 在写入时自动创建）；
        需要保留的标准文件通过“工具 → 导出标准格式”导出到用户指定位置。
        """
        return os.path.join(tempfile.gettempdir(), "THzAnalyzer_standardized")

    def _cleanup_standardized_tmp(self):
        """清理上次运行遗留的自动标准化临时文件。"""
        tmp_dir = os.path.join(tempfile.gettempdir(), "THzAnalyzer_standardized")
        try:
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)
        except OSError:
            pass

    def _auto_standardize(self, raw_path: str) -> list:
        """
        把原始文件自动标准化为内存中的 StandardSignal 列表，并写出对应标准 txt。

        返回的每个信号均通过 metadata["standard_file"] 记录其临时 txt 路径，
        计算时可直接复用内存信号，避免二次标准化。已是标准 txt 则原样读入。
        """
        if is_standard_txt(raw_path):
            signal = read_standard_txt(raw_path)
            return [signal]

        signals = standardize_file(raw_path, 0)
        if not signals:
            return []
        out_dir = self._standardized_dir()
        stem = os.path.splitext(os.path.basename(raw_path))[0]
        for i, sig in enumerate(signals):
            suffix = f"_{i + 1}" if len(signals) > 1 else ""
            target = os.path.join(out_dir, f"{stem}{suffix}.txt")
            path = write_standard_txt(sig, target)
            sig.metadata["standard_file"] = os.path.abspath(path)
        return signals

    def _append_ref_list_item(self, file_path: str, name: str, color: str):
        item = QListWidgetItem(short_display_name(name))
        item.setForeground(QBrush(QColor(color)))
        item.setToolTip(file_path)
        self.ref_list.addItem(item)

    def _append_sam_list_item(self, file_path: str, name: str, color: str):
        item = QListWidgetItem(short_display_name(name))
        item.setForeground(QBrush(QColor(color)))
        item.setToolTip(file_path)
        self.sam_list.addItem(item)

    def _export_standard_files(self):
        """直接导出参考框与样品框中的标准 txt 到用户选择的目录。

        不经过任何界面配置：点击后弹出目录选择框，
        将当前参考文件与全部样品文件复制为标准格式 txt 到该目录。
        """
        if not self.ref_file:
            QMessageBox.warning(self, "提示", "请先选择参考文件")
            return
        if not self.sam_files:
            QMessageBox.warning(self, "提示", "请先添加样品文件")
            return

        initial_dir = (
            self.config.get("last_save_dir")
            or self.config.get("last_open_dir")
            or os.getcwd()
        )
        out_dir = QFileDialog.getExistingDirectory(
            self, "选择标准格式导出目录", initial_dir
        )
        if not out_dir:
            return

        self.config["last_save_dir"] = out_dir

        try:
            os.makedirs(out_dir, exist_ok=True)
            exported = []
            for src in [self.ref_file, *self.sam_files]:
                if not src or not os.path.isfile(src):
                    continue
                stem = os.path.splitext(os.path.basename(src))[0] or "signal"
                target = _unique_dest(os.path.join(out_dir, f"{stem}.txt"))
                shutil.copy2(src, target)
                exported.append(target)
        except OSError as exc:
            error(f"导出标准格式失败: {exc}")
            QMessageBox.critical(self, "导出失败", str(exc))
            return

        info(f"导出标准格式 {len(exported)} 个文件到 {out_dir}")
        QMessageBox.information(
            self, "导出成功",
            f"已导出 {len(exported)} 个标准 txt 到：\n{out_dir}"
        )
    
    def _create_ref_file_section(self, parent_layout):
        """创建参考文件选择区域（框高度与右侧按钮一致）"""
        group = QGroupBox("参考文件")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        content = QHBoxLayout()
        content.setSpacing(6)

        btn_col = QVBoxLayout()
        add_ref_btn = QPushButton("添加")
        add_ref_btn.clicked.connect(self._select_ref_file)
        btn_col.addWidget(add_ref_btn)
        btn_col.addStretch()

        # 参考仅 1 条，框高度与按钮一致，保留水平滚动条
        self.ref_list = QListWidget()
        self.ref_list.setFixedHeight(add_ref_btn.sizeHint().height() + 20)
        self.ref_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        content.addWidget(self.ref_list, 1)
        content.addLayout(btn_col)

        layout.addLayout(content)
        parent_layout.addWidget(group)

    def _create_sam_file_section(self, parent_layout):
        """创建样品文件选择区域（框初始高度 = 右侧按钮列高度）"""
        group = QGroupBox("样品文件")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        content = QHBoxLayout()
        content.setSpacing(6)

        btn_col = QVBoxLayout()
        add_sam_btn = QPushButton("添加")
        add_sam_btn.clicked.connect(self._add_sam_file)
        del_sam_btn = QPushButton("删除")
        del_sam_btn.clicked.connect(self._delete_selected_file)
        clear_sam_btn = QPushButton("清空")
        clear_sam_btn.clicked.connect(self._clear_sam_files)
        btn_col.addWidget(add_sam_btn)
        btn_col.addWidget(del_sam_btn)
        btn_col.addWidget(clear_sam_btn)
        btn_col.addStretch()

        # 框初始高度 = 三个按钮总高（含间距）；内容多时增高，最高 240 后滚动
        btn_h = add_sam_btn.sizeHint().height()
        spacing = btn_col.spacing() if btn_col.spacing() >= 0 else 6
        col_h = 3 * btn_h + 2 * spacing
        self.sam_list = QListWidget()
        self.sam_list.setMinimumHeight(col_h)
        self.sam_list.setMaximumHeight(240)
        content.addWidget(self.sam_list, 1)
        content.addLayout(btn_col)

        layout.addLayout(content)
        parent_layout.addWidget(group)
    
    def _select_ref_file(self):
        """选择参考文件（直接选原始/标准文件，代码自动标准化）"""
        initial_dir = self.config.get("last_open_dir", "")
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()

        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择参考文件（原始或标准 txt）", initial_dir, INPUT_FILE_FILTER
        )
        if not file_path:
            return

        signals = self._auto_standardize(file_path)
        if not signals:
            QMessageBox.warning(self, "提示", "无法解析该文件，请检查格式")
            return

        if len(signals) > 1:
            QMessageBox.information(
                self, "提示",
                f"该文件包含 {len(signals)} 条扫描，已自动取第 1 条作为参考。"
            )

        self.ref_signal = signals[0]
        self.ref_file = self.ref_signal.metadata.get("standard_file", file_path)
        self.config["last_open_dir"] = os.path.dirname(file_path)
        self.ref_list.clear()
        self._append_ref_list_item(self.ref_file, os.path.basename(self.ref_file), "#2E7D32")
        self._update_status("已选择参考文件（已自动标准化）", "ready")
        info(f"选择参考文件（自动标准化）: {self.ref_file}")

    def _add_sam_file(self):
        """添加样品文件（直接选原始/标准文件，代码自动标准化）"""
        initial_dir = self.config.get("last_open_dir", "")
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()

        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择样品文件（原始或标准 txt）", initial_dir, INPUT_FILE_FILTER
        )
        if not file_paths:
            return

        self.config["last_open_dir"] = os.path.dirname(file_paths[0])
        added = 0
        for raw in file_paths:
            signals = self._auto_standardize(raw)
            for signal in signals:
                path = signal.metadata.get("standard_file", raw)
                self.sam_files.append(path)
                self.sam_signals.append(signal)
                name = os.path.splitext(os.path.basename(path))[0]
                self.sam_names.append(name)
                self._append_sam_list_item(path, name, sample_color(len(self.sam_list) - 1))
                idx = len(self.sam_names) - 1
                self.per_sample_window_params[idx] = None
                self.per_sample_thickness[idx] = None
                added += 1

        if added:
            self._refresh_sample_list_colors()
            self._update_status(f"已添加 {added} 个样品文件（已自动标准化）", "ready")
            info(f"添加 {added} 个样品文件（自动标准化）")

    def _refresh_sample_list_colors(self):
        """按样品索引刷新列表颜色标识。"""
        for index in range(self.sam_list.count()):
            item = self.sam_list.item(index)
            if item is None:
                continue
            item.setForeground(QBrush(QColor(sample_color(index))))
            if index < len(self.sam_names):
                item.setText(short_display_name(self.sam_names[index]))
            if index < len(self.sam_files):
                item.setToolTip(self.sam_files[index])

    def _delete_selected_file(self):
        """删除选中的样品文件"""
        selected_items = self.sam_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要删除的样品文件")
            return

        # selectedItems() 是选中时刻的快照，正序逐个 takeItem 会导致后续
        # 行号与实际条目错位（误删/漏删）。改为先收集行号、降序删除。
        rows = sorted(
            (self.sam_list.row(item) for item in selected_items),
            reverse=True,
        )
        for row in rows:
            if row < 0 or row >= len(self.sam_files):
                continue
            self.sam_list.takeItem(row)
            del self.sam_files[row]
            del self.sam_names[row]
            del self.sam_signals[row]
            self.per_sample_window_params = _shift_indexed_dict(
                self.per_sample_window_params, row
            )
            self.per_sample_thickness = _shift_indexed_dict(
                self.per_sample_thickness, row
            )

        self._refresh_sample_list_colors()
        self._update_status("已删除选中的样品文件", "ready")

    def _clear_sam_files(self):
        """清空样品文件列表"""
        self.sam_files = []
        self.sam_names = []
        self.sam_signals = []
        self.sam_list.clear()
        self.per_sample_window_params = {}
        self.per_sample_thickness = {}
        self.set_thickness_btn.setText("按样品设置")
        self.set_thickness_btn.setToolTip(
            "为每个样品单独设置厚度 (mm)，留空表示使用左侧全局默认值"
        )
        self._update_status("样品文件列表已清空", "ready")
    
    def _create_parameter_section(self, parent_layout):
        """创建参数设置区域"""
        # Tukey窗函数设置（横着排列：启用 + 开关 + 按信号设置参数 + 设置 + 指示）
        tukey_group = QGroupBox("Tukey 窗函数")
        tukey_layout = QHBoxLayout(tukey_group)
        tukey_layout.setSpacing(8)

        tukey_layout.addWidget(QLabel("启用"))
        tukey_layout.addSpacing(6)

        # 左右拨动开关
        self.use_window_switch = QPushButton()
        self.use_window_switch.setFixedSize(36, 16)
        self.use_window_switch.setCheckable(True)
        self.use_window_switch.setChecked(False)
        self.use_window_switch.clicked.connect(
            lambda: self._toggle_window_params(self.use_window_switch.isChecked())
        )
        self._style_window_switch(False)
        tukey_layout.addWidget(self.use_window_switch)

        tukey_layout.addSpacing(12)
        signal_window_label = QLabel("按信号设置参数")
        signal_window_label.setStyleSheet("color: #555555;")
        tukey_layout.addWidget(signal_window_label)

        self.set_signal_window_btn = QPushButton("设置")
        self.set_signal_window_btn.clicked.connect(self._open_signal_window_dialog)
        self.set_signal_window_btn.setEnabled(False)
        tukey_layout.addWidget(self.set_signal_window_btn)

        self.window_params_indicator = QLabel("参数已设置")
        self.window_params_indicator.setStyleSheet("color: #2E7D32; padding: 0 4px;")
        self.window_params_indicator.setVisible(False)
        tukey_layout.addWidget(self.window_params_indicator)

        tukey_layout.addStretch()
        parent_layout.addWidget(tukey_group)
        
        # 连接信号
        self._toggle_window_params(False)
        
        # 样品厚度设置（全局默认 + 按样品单独设置合并为一行）
        thickness_layout = QHBoxLayout()
        thickness_label = QLabel("样品厚度 (mm)")
        thickness_label.setStyleSheet("font-weight: bold; color: #444444;")
        thickness_layout.addWidget(thickness_label)
        
        self.thickness_combo = QComboBox()
        self.thickness_combo.setEditable(True)
        self.thickness_combo.setToolTip(
            "全局默认厚度（mm）。留空使用此值的样品，可通过「按样品设置」单独覆盖。"
        )
        
        thickness_history = [str(x) for x in self.config.get("thickness_history", [0.5])]
        current_thickness = str(self.config.get("thickness", 0.5))
        if current_thickness in thickness_history:
            thickness_history.remove(current_thickness)
        self.thickness_combo.addItem(current_thickness)
        for t in thickness_history:
            self.thickness_combo.addItem(t)
        self.thickness_combo.setCurrentText(current_thickness)
        thickness_layout.addWidget(self.thickness_combo, 1)
        thickness_layout.setSpacing(8)

        self.set_thickness_btn = QPushButton("按样品设置")
        self.set_thickness_btn.setToolTip("为每个样品单独设置厚度 (mm)，留空表示使用左侧全局默认值")
        self.set_thickness_btn.clicked.connect(self._open_thickness_dialog)
        thickness_layout.addWidget(self.set_thickness_btn)
        thickness_layout.addStretch()
        parent_layout.addLayout(thickness_layout)
        
        # 起始行设置
        start_row_layout = QHBoxLayout()
        start_row_label = QLabel("数据起始行")
        start_row_label.setStyleSheet("font-weight: bold; color: #444444;")
        start_row_layout.addWidget(start_row_label)
        
        self.start_row_combo = QComboBox()
        self.start_row_combo.addItems(["1", "2", "3"])
        self.start_row_combo.setEditable(True)
        idx = ["1", "2", "3"].index(str(self.config.get("start_row", 1))) if str(self.config.get("start_row", 1)) in ["1", "2", "3"] else -1
        if idx >= 0:
            self.start_row_combo.setCurrentIndex(idx)
        else:
            self.start_row_combo.setEditText(str(self.config.get("start_row", 1)))
        start_row_layout.addWidget(self.start_row_combo, 1)
        start_row_layout.setSpacing(8)
        
        parent_layout.addLayout(start_row_layout)
    
    def _create_button_section(self, parent_layout):
        """创建按钮区域"""
        button_layout = QVBoxLayout()

        run_row = QHBoxLayout()
        run_btn = QPushButton("运行分析")
        run_btn.clicked.connect(self._run_analysis)
        run_row.addWidget(run_btn)
        button_layout.addLayout(run_row)

        save_row = QHBoxLayout()
        self.save_btn = QPushButton("保存结果")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_results)
        save_row.addWidget(self.save_btn)
        self.save_tf_btn = QPushButton("保存时频域数据")
        self.save_tf_btn.setEnabled(False)
        self.save_tf_btn.clicked.connect(self._save_time_freq_data)
        save_row.addWidget(self.save_tf_btn)
        button_layout.addLayout(save_row)

        detail_row = QHBoxLayout()
        self.detail_btn = QPushButton("查看子图详情")
        self.detail_btn.setEnabled(False)
        self.detail_btn.setToolTip(
            "弹出窗口查看每个子图的放大图表与关键指标摘要，\n"
            "支持子图切换，窗口可拖动、可调整大小"
        )
        self.detail_btn.clicked.connect(self._show_subplot_details)
        detail_row.addWidget(self.detail_btn)
        button_layout.addLayout(detail_row)

        parent_layout.addLayout(button_layout)

    def _set_popup_buttons_enabled(self, enabled: bool):
        """启用/禁用结果保存按钮（无结果或出错时禁用）。"""
        if hasattr(self, "save_btn"):
            self.save_btn.setEnabled(enabled)
        if hasattr(self, "save_tf_btn"):
            self.save_tf_btn.setEnabled(enabled)
        if hasattr(self, "detail_btn"):
            self.detail_btn.setEnabled(enabled)

    def _save_results(self):
        """保存光学参数结果（Excel，每个样品一个工作表）。"""
        self._save_with_worker("optical", "保存光学参数结果")

    def _save_time_freq_data(self):
        """保存时域/频域数据（Excel，每个文件一个工作表）。"""
        self._save_with_worker("time_freq", "保存时域/频域数据")

    def _save_with_worker(self, save_type: str, caption: str):
        """通过后台线程保存结果，避免阻塞界面。"""
        if self.results_data is None:
            QMessageBox.information(self, "提示", "请先运行分析")
            return
        initial_dir = self.config.get("last_save_dir", "")
        file_path, _ = QFileDialog.getSaveFileName(
            self, caption, initial_dir, "Excel 文件 (*.xlsx)"
        )
        if not file_path:
            return
        self.config["last_save_dir"] = os.path.dirname(file_path)

        self.save_worker = SaveWorker(self)
        self.save_worker.set_parameters(self.results_data, file_path, save_type)
        self.save_worker.save_finished.connect(self._on_save_finished)
        self.save_worker.save_error.connect(self._on_save_error)
        self._update_status("正在保存...", "working")
        if self.status_bar:
            self.status_bar.show_progress(True)
        self.save_worker.start()

    def _on_save_finished(self, saved_path: str):
        """保存完成回调。"""
        if self.status_bar:
            self.status_bar.show_progress(False)
        self._update_status("保存完成", "success")
        QMessageBox.information(self, "保存成功", f"结果已保存到：\n{saved_path}")

    def _on_save_error(self, message: str):
        """保存失败回调。"""
        if self.status_bar:
            self.status_bar.show_progress(False)
        self._update_status("保存失败", "error")
        QMessageBox.critical(self, "保存失败", str(message))
        error(f"保存失败: {message}")

    def _create_right_panel(self):
        """创建右侧结果显示面板"""
        self.right_panel = QTabWidget()
        
        # 创建标签页
        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tab3 = QWidget()
        
        tab1_layout = QVBoxLayout(self.tab1)
        tab1_layout.setContentsMargins(8, 8, 8, 8)
        
        tab2_layout = QVBoxLayout(self.tab2)
        tab2_layout.setContentsMargins(8, 8, 8, 8)
        
        tab3_layout = QVBoxLayout(self.tab3)
        tab3_layout.setContentsMargins(8, 8, 8, 8)
        
        self.right_panel.addTab(self.tab1, "时域和频域")
        self.right_panel.addTab(self.tab2, "光学参数")
        self.right_panel.addTab(self.tab3, "介电特性")
    
    def _update_status(self, message: str, status_type: str = "ready"):
        """更新状态栏"""
        if self.status_bar:
            self.status_bar.set_status(message, status_type)
    
    def _style_window_switch(self, enabled: bool):
        """更新左右拨动开关的外观（开=绿色右移，关=灰色左移）"""
        if enabled:
            self.use_window_switch.setStyleSheet(
                "QPushButton {"
                "  background-color: #2E7D32;"
                "  border: none;"
                "  border-radius: 8px;"
                "  color: #FFFFFF;"
                "  font-size: 9px;"
                "  text-align: right;"
                "  padding-right: 2px;"
                "}"
            )
        else:
            self.use_window_switch.setStyleSheet(
                "QPushButton {"
                "  background-color: #B0B0B0;"
                "  border: none;"
                "  border-radius: 8px;"
                "  color: #FFFFFF;"
                "  font-size: 9px;"
                "  text-align: left;"
                "  padding-left: 2px;"
                "}"
            )
        # 用圆点字符表示滑块位置
        self.use_window_switch.setText("●")

    def _toggle_window_params(self, enabled: bool):
        """切换窗函数参数（左右拨动开关）"""
        self._style_window_switch(enabled)
        self.set_signal_window_btn.setEnabled(enabled)
    
    def _open_signal_window_dialog(self):
        """打开窗函数参数设置对话框"""
        if not self.ref_file and not self.sam_names:
            QMessageBox.warning(self, "警告", "请先选择参考文件或添加样品文件")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Tukey窗函数参数设置")
        dialog.setMinimumSize(550, 500)
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # 说明标签
        info_label = QLabel("为每个信号单独设置Tukey窗函数参数，或使用快速设置应用到所有样品")
        info_label.setStyleSheet("color: #666666; font-size: 10px; margin-bottom: 5px;")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(8)
        
        # 存储编辑框引用
        self._window_param_edits = {}
        
        # 参考信号参数
        if self.ref_file:
            ref_group = self._create_signal_param_group(
                "参考信号", 
                "ref",
                self.ref_window_params
            )
            scroll_layout.addWidget(ref_group)
        
        # 每个样品信号参数
        for i, name in enumerate(self.sam_names):
            existing_params = self.per_sample_window_params.get(i)
            sam_group = self._create_signal_param_group(
                f"样品: {name}", 
                f"sam_{i}",
                existing_params
            )
            scroll_layout.addWidget(sam_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll, 1)
        
        # 快速设置区域
        quick_group = QGroupBox("快速设置（应用到所有样品）")
        quick_layout = QHBoxLayout(quick_group)
        quick_layout.setSpacing(8)
        
        quick_layout.addWidget(QLabel("起始:"))
        self.quick_t_start = QLineEdit("0.0")
        self.quick_t_start.setFixedWidth(60)
        quick_layout.addWidget(self.quick_t_start)
        
        quick_layout.addWidget(QLabel("结束:"))
        self.quick_t_end = QLineEdit("30.0")
        self.quick_t_end.setFixedWidth(60)
        quick_layout.addWidget(self.quick_t_end)
        
        quick_layout.addWidget(QLabel("α:"))
        self.quick_alpha = QLineEdit("0.5")
        self.quick_alpha.setFixedWidth(50)
        quick_layout.addWidget(self.quick_alpha)
        
        apply_btn = QPushButton("应用到所有样品")
        apply_btn.clicked.connect(self._apply_quick_params)
        quick_layout.addWidget(apply_btn)

        auto_btn = QPushButton("自动定位")
        auto_btn.setToolTip(
            "读取各信号文件，按主脉冲位置自动填写窗口范围\n"
            "（峰前 3 ps、峰后 25 ps、α=0.15）"
        )
        auto_btn.clicked.connect(self._auto_locate_window_params)
        quick_layout.addWidget(auto_btn)
        
        quick_layout.addStretch()
        main_layout.addWidget(quick_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(lambda: self._save_window_params(dialog))
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        main_layout.addLayout(button_layout)
        
        dialog.exec()
    
    def _create_signal_param_group(self, title: str, key: str, existing_params: dict = None):
        """创建单个信号的参数设置组"""
        group = QGroupBox(title)
        
        layout = QHBoxLayout(group)
        layout.setSpacing(8)
        
        # 默认值
        t_start = existing_params.get('t_start', 0.0) if existing_params else 0.0
        t_end = existing_params.get('t_end', 30.0) if existing_params else 30.0
        alpha = existing_params.get('alpha', 0.5) if existing_params else 0.5
        
        layout.addWidget(QLabel("起始(ps):"))
        t_start_edit = QLineEdit(str(t_start))
        t_start_edit.setFixedWidth(70)
        layout.addWidget(t_start_edit)
        
        layout.addWidget(QLabel("结束(ps):"))
        t_end_edit = QLineEdit(str(t_end))
        t_end_edit.setFixedWidth(70)
        layout.addWidget(t_end_edit)
        
        layout.addWidget(QLabel("α:"))
        alpha_edit = QLineEdit(str(alpha))
        alpha_edit.setFixedWidth(50)
        layout.addWidget(alpha_edit)
        
        layout.addStretch()
        
        # 保存编辑框引用
        self._window_param_edits[key] = {
            't_start': t_start_edit,
            't_end': t_end_edit,
            'alpha': alpha_edit
        }
        
        return group
    
    def _auto_locate_window_params(self):
        """按主脉冲位置自动填写每个信号的窗口范围。

        固定的 0–30 ps 对厚样品是危险的：样品越厚主脉冲越靠后，很容易落进
        Tukey 窗的渐变区被压低，而界面上看不出异常。这里直接读文件定位峰位。
        """
        from core.data_io import load_standard_signal
        from core.window_functions import suggest_window_params

        targets = []
        if self.ref_file and 'ref' in self._window_param_edits:
            targets.append(('ref', self.ref_file))
        for i, path in enumerate(self.sam_files):
            key = f'sam_{i}'
            if key in self._window_param_edits:
                targets.append((key, path))

        if not targets:
            QMessageBox.warning(self, "警告", "没有可定位的信号文件")
            return

        try:
            start_row = int(self.start_row_combo.currentText())
        except (ValueError, AttributeError):
            start_row = 1

        failures = []
        for key, path in targets:
            try:
                signal = load_standard_signal(path, start_row)
                params = suggest_window_params(signal.time, signal.amplitude)
                edits = self._window_param_edits[key]
                edits['t_start'].setText(f"{params['t_start']:.2f}")
                edits['t_end'].setText(f"{params['t_end']:.2f}")
                edits['alpha'].setText(f"{params['alpha']:.2f}")
            except Exception as exc:
                failures.append(f"{os.path.basename(path)}: {exc}")

        if failures:
            QMessageBox.warning(
                self, "部分文件定位失败", "\n".join(failures[:5])
            )
        else:
            self._update_status("已按主脉冲位置自动定位窗口", "ready")

    def _open_thickness_dialog(self):
        """为每个样品单独设置厚度 (mm)。

        留空表示使用左侧「样品厚度」的全局默认值；删除样品后对应设置自动失效。
        """
        if not self.sam_names:
            QMessageBox.warning(self, "提示", "请先添加样品文件")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("样品厚度设置")
        dialog.setMinimumSize(480, 420)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        try:
            default_mm = float(self.thickness_combo.currentText())
        except ValueError:
            default_mm = 0.5
        info_label = QLabel(
            f"为每个样品单独设置厚度（单位 mm）。留空表示使用左侧"
            f"「样品厚度」的全局值 {default_mm:g} mm。"
        )
        info_label.setStyleSheet("color: #666666; font-size: 10px;")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        rows_layout = QVBoxLayout(scroll_widget)
        rows_layout.setSpacing(8)

        edits: dict[int, QLineEdit] = {}
        for i, name in enumerate(self.sam_names):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"样品 {i + 1}: {short_display_name(name)}"), 1)
            edit = QLineEdit()
            edit.setFixedWidth(90)
            edit.setPlaceholderText("默认")
            edit.setAlignment(Qt.AlignmentFlag.AlignRight)
            value = self.per_sample_thickness.get(i)
            if value:
                edit.setText(f"{value:g}")
            row.addWidget(edit)
            row.addWidget(QLabel("mm"))
            rows_layout.addLayout(row)
            edits[i] = edit
        rows_layout.addStretch()
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll, 1)

        # 快速设置：统一填为同一厚度
        quick_group = QGroupBox("快速设置（应用到所有样品）")
        quick_layout = QHBoxLayout(quick_group)
        quick_layout.setContentsMargins(8, 6, 8, 6)
        quick_layout.addWidget(QLabel("厚度 (mm):"))
        quick_edit = QLineEdit()
        quick_edit.setFixedWidth(80)
        quick_layout.addWidget(quick_edit)
        apply_all_btn = QPushButton("应用到所有样品")
        quick_layout.addWidget(apply_all_btn)
        quick_layout.addStretch()
        main_layout.addWidget(quick_group)

        def _apply_all():
            text = quick_edit.text().strip()
            if not text:
                return
            try:
                value = float(text)
                if value <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(dialog, "错误", "请输入有效的正数厚度")
                return
            for edit in edits.values():
                edit.setText(f"{value:g}")

        apply_all_btn.clicked.connect(_apply_all)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        main_layout.addLayout(button_layout)

        def _save():
            for i, edit in edits.items():
                text = edit.text().strip()
                if not text:
                    self.per_sample_thickness[i] = None
                    continue
                try:
                    value = float(text)
                    if value <= 0:
                        raise ValueError
                    self.per_sample_thickness[i] = value
                except ValueError:
                    QMessageBox.warning(
                        dialog,
                        "参数错误",
                        f"样品「{self.sam_names[i]}」的厚度必须为正数",
                    )
                    return
            custom_count = sum(
                1 for value in self.per_sample_thickness.values() if value is not None
            )
            if custom_count:
                details = "、".join(
                    f"{self.sam_names[i]}({value:g} mm)"
                    for i, value in self.per_sample_thickness.items()
                    if value is not None
                )
                self.set_thickness_btn.setText("按样品设置 ⓘ")
                self.set_thickness_btn.setToolTip(
                    f"已为 {custom_count} 个样品单独设置厚度：\n{details}"
                )
            else:
                self.set_thickness_btn.setText("按样品设置")
                self.set_thickness_btn.setToolTip(
                    "为每个样品单独设置厚度 (mm)，留空表示使用左侧全局默认值"
                )
            dialog.accept()
            info("样品厚度设置已保存")

        ok_btn.clicked.connect(_save)
        cancel_btn.clicked.connect(dialog.reject)
        dialog.exec()

    def _apply_quick_params(self):
        """应用快速设置到所有样品"""
        try:
            t_start = self.quick_t_start.text()
            t_end = self.quick_t_end.text()
            alpha = self.quick_alpha.text()
            
            # 验证
            float(t_start)
            float(t_end)
            float(alpha)
            
            # 应用到所有样品
            for key, edits in self._window_param_edits.items():
                if key.startswith('sam_'):
                    edits['t_start'].setText(t_start)
                    edits['t_end'].setText(t_end)
                    edits['alpha'].setText(alpha)
            
            self._update_status("已应用到所有样品", "ready")
            
        except ValueError:
            QMessageBox.warning(self, "错误", "请输入有效的数值")
    
    def _save_window_params(self, dialog):
        """保存窗函数参数"""
        try:
            # 保存参考信号参数
            if 'ref' in self._window_param_edits:
                edits = self._window_param_edits['ref']
                t_start = float(edits['t_start'].text())
                t_end = float(edits['t_end'].text())
                alpha = float(edits['alpha'].text())
                
                if alpha < 0 or alpha > 1:
                    raise ValueError("参考信号的α参数必须在0到1之间")
                if t_end <= t_start:
                    raise ValueError("参考信号的结束时间必须大于起始时间")
                
                self.ref_window_params = {'t_start': t_start, 't_end': t_end, 'alpha': alpha}
            
            # 保存每个样品信号参数
            for i in range(len(self.sam_names)):
                key = f'sam_{i}'
                if key in self._window_param_edits:
                    edits = self._window_param_edits[key]
                    t_start = float(edits['t_start'].text())
                    t_end = float(edits['t_end'].text())
                    alpha = float(edits['alpha'].text())
                    
                    if alpha < 0 or alpha > 1:
                        raise ValueError(f"样品 {self.sam_names[i]} 的α参数必须在0到1之间")
                    if t_end <= t_start:
                        raise ValueError(f"样品 {self.sam_names[i]} 的结束时间必须大于起始时间")
                    
                    self.per_sample_window_params[i] = {'t_start': t_start, 't_end': t_end, 'alpha': alpha}
            
            self.window_params_indicator.setVisible(True)
            dialog.accept()
            info("窗函数参数已保存")
            
        except ValueError as e:
            QMessageBox.warning(self, "参数错误", str(e))
    
    def _run_analysis(self):
        """运行THz光学参数分析"""
        if not self.ref_file:
            QMessageBox.warning(self, "警告", "请先选择参考文件")
            return
        
        if not self.sam_files:
            QMessageBox.warning(self, "警告", "请添加至少一个样品文件")
            return
        
        try:
            # 获取参数
            thickness = float(self.thickness_combo.currentText())
            if thickness <= 0:
                raise ValueError("样品厚度必须为正数")
            
            start_row = int(self.start_row_combo.currentText())
            if start_row < 1:
                raise ValueError("数据起始行必须为大于等于1的整数")
            
            self.config["start_row"] = start_row
            self.config = update_thickness_history(self.config, thickness)
            self.config["thickness"] = thickness
            
            # 清除之前的图表
            self._clear_tabs()
            
            # 获取窗函数参数
            use_window = self.use_window_switch.isChecked()
            self.config["use_window"] = use_window
            
            per_sample_params_list = []
            for i in range(len(self.sam_names)):
                if i in self.per_sample_window_params and self.per_sample_window_params[i] is not None:
                    per_sample_params_list.append(self.per_sample_window_params[i])
                else:
                    per_sample_params_list.append(None)

            per_sample_thickness_list = [
                self.per_sample_thickness.get(i) for i in range(len(self.sam_names))
            ]
            
            # 创建计算工作线程（传入内存信号，复用已标准化结果，避免二次标准化）
            self.calc_worker = CalculationWorker()
            self.calc_worker.set_parameters(
                ref_file=self.ref_file,
                sam_files=self.sam_files,
                sam_names=self.sam_names,
                thickness=thickness,
                start_row=start_row,
                use_window=use_window,
                ref_window_params=self.ref_window_params,
                per_sample_window_params=per_sample_params_list,
                per_sample_thickness=per_sample_thickness_list,
                ref_signal=self.ref_signal,
                sam_signals=list(self.sam_signals),
            )
            
            # 连接信号
            self.calc_worker.progress_updated.connect(self._on_progress_updated)
            self.calc_worker.calculation_finished.connect(self._on_calculation_finished)
            self.calc_worker.calculation_error.connect(self._on_calculation_error)
            self.calc_worker.warning_occurred.connect(self._on_warning_occurred)
            
            # 显示进度条并启动计算
            self._update_status("正在计算，请稍候...", "working")
            if self.status_bar:
                self.status_bar.show_progress(True)
            self.calc_worker.start()
            
            info("开始异步计算")
            
        except ValueError as e:
            QMessageBox.critical(self, "输入错误", str(e))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理过程中出错: {str(e)}")
    
    def _on_progress_updated(self, current: int, total: int, message: str):
        """进度更新回调"""
        if self.status_bar:
            self.status_bar.update_progress(current, total, message)
    
    def _on_calculation_finished(self, result):
        """计算完成回调（主线程）：在此生成图表，避免 worker 线程创建 Figure。"""
        # 隐藏进度条
        if self.status_bar:
            self.status_bar.show_progress(False)
        
        if result.success:
            try:
                self._update_status("正在生成图表...", "working")
                build_result_figures(result)
            except Exception as exc:
                self._update_status("图表生成失败", "error")
                QMessageBox.critical(self, "图表错误", str(exc))
                error(f"图表生成失败: {exc}")
                self._set_popup_buttons_enabled(False)
                return

            self.results_data = result.data
            # 保存图表引用
            self.fig1 = result.fig1
            self.fig2 = result.fig2
            self.fig3 = result.fig3
            self._display_charts(result.fig1, result.fig2, result.fig3)
            self._set_popup_buttons_enabled(True)
            self._update_status("计算完成", "success")
            info("计算完成")
        else:
            self._update_status("计算失败", "error")
    
    def _on_calculation_error(self, error_message: str):
        """计算错误回调"""
        # 隐藏进度条
        if self.status_bar:
            self.status_bar.show_progress(False)
        
        self._set_popup_buttons_enabled(False)
        self._update_status("计算失败", "error")
        QMessageBox.critical(self, "计算错误", error_message)
        error(f"计算错误: {error_message}")
    
    def _on_warning_occurred(self, warning_message: str):
        """警告回调"""
        QMessageBox.warning(self, "警告", warning_message)
        warning(warning_message)
    
    def _clear_tabs(self):
        """清除标签页中的图表，并释放上一轮的 Figure。"""
        for tab in [self.tab1, self.tab2, self.tab3]:
            layout = tab.layout()
            if layout:
                for i in reversed(range(layout.count())):
                    item = layout.itemAt(i)
                    if item:
                        widget = item.widget()
                        if widget:
                            widget.setParent(None)
                            widget.deleteLater()
        self._release_figures()

    def _release_figures(self):
        """显式清空并丢弃已持有的 Figure。

        绘图层已改为直接实例化 Figure（不再经 pyplot），因此不会被 pyplot 的
        全局管理器持有；这里主动清掉引用，避免多次计算后旧图数据滞留内存。
        """
        for attr in ("fig1", "fig2", "fig3"):
            figure = getattr(self, attr, None)
            if figure is not None:
                try:
                    figure.clear()
                except Exception:
                    pass
                setattr(self, attr, None)
    
    def _display_charts(self, fig1, fig2, fig3):
        """显示图表"""
        # 显示时域和频域图表
        canvas1 = FigureCanvas(fig1)
        enable_responsive_fonts(canvas1)
        enable_curve_hover(canvas1)
        toolbar1 = NavigationToolbar(canvas1, self.tab1)
        self.tab1.layout().addWidget(toolbar1)
        self.tab1.layout().addWidget(canvas1)
        self.tab1.layout().addWidget(AxisRangeBar(canvas1))
        
        # 显示光学参数图表
        canvas2 = FigureCanvas(fig2)
        enable_responsive_fonts(canvas2)
        enable_curve_hover(canvas2)
        toolbar2 = NavigationToolbar(canvas2, self.tab2)
        self.tab2.layout().addWidget(toolbar2)
        self.tab2.layout().addWidget(canvas2)
        self.tab2.layout().addWidget(AxisRangeBar(canvas2))
        
        # 显示介电特性图表
        canvas3 = FigureCanvas(fig3)
        enable_responsive_fonts(canvas3)
        enable_curve_hover(canvas3)
        toolbar3 = NavigationToolbar(canvas3, self.tab3)
        self.tab3.layout().addWidget(toolbar3)
        self.tab3.layout().addWidget(canvas3)
        self.tab3.layout().addWidget(AxisRangeBar(canvas3))
    
    def _show_help_dialog(self):
        """显示帮助对话框"""
        dialog = HelpDialog(self)
        dialog.exec()
    
    def _show_about_dialog(self):
        """显示关于对话框"""
        dialog = AboutDialog(self)
        dialog.exec()

    def _check_updates_auto(self):
        """启动后自动检查更新：受自动检查开关与 24 小时频率限制，失败静默。"""
        if not self.config.get("auto_check_update", True):
            return
        last_check = self.config.get("last_update_check", "")
        if last_check:
            try:
                last_dt = datetime.fromisoformat(last_check)
                if (datetime.now() - last_dt).total_seconds() < 24 * 3600:
                    return
            except ValueError:
                pass
        self._check_for_updates(manual=False)

    def _check_for_updates(self, manual: bool):
        """检查是否有新版本。

        manual=True（帮助菜单触发）时，无更新或失败会弹窗提示；
        manual=False（启动自动检查）时静默处理，仅在发现新版本时提示。
        """
        if getattr(self, "update_worker", None) is not None and self.update_worker.isRunning():
            self._update_status("正在检查更新...", "working")
            return
        self.update_worker = UpdateCheckWorker(
            self.config.get("update_source") or UPDATE_URL,
            APP_VERSION,
        )
        self.update_worker.check_finished.connect(
            lambda update_info: self._on_update_check_finished(update_info, manual)
        )
        self.update_worker.check_error.connect(
            lambda message: self._on_update_check_error(message, manual)
        )
        self._update_status("正在检查更新...", "working")
        self.update_worker.start()

    def _on_update_check_finished(self, update_info, manual: bool):
        """更新检查完成回调。"""
        self.config["last_update_check"] = datetime.now().isoformat(timespec="seconds")
        if is_newer(APP_VERSION, update_info.version):
            self._update_status(f"发现新版本 v{update_info.version}", "success")
            self._show_update_dialog(update_info)
        else:
            self._update_status("已是最新版本", "ready")
            if manual:
                QMessageBox.information(
                    self, "检查更新", f"当前已是最新版本 v{APP_VERSION}"
                )

    def _on_update_check_error(self, message: str, manual: bool):
        """更新检查失败回调。"""
        self.config["last_update_check"] = datetime.now().isoformat(timespec="seconds")
        self._update_status("更新检查失败", "error")
        if manual:
            QMessageBox.warning(self, "检查更新", f"更新检查失败：\n{message}")
        else:
            warning(f"自动更新检查失败: {message}")

    def _show_update_dialog(self, update_info):
        """显示新版本提示对话框。"""
        dialog = UpdateDialog(update_info, self)
        dialog.install_requested.connect(self._quit_for_update)
        dialog.exec()

    def _quit_for_update(self):
        """安装程序已启动，保存配置并关闭主窗口（由 closeEvent 完成收尾）。"""
        try:
            save_config(self.config)
        finally:
            self.close()
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        """拖放事件：自动标准化并添加到参考/样品列表
        - 拖入 1 个文件：作为参考文件
        - 拖入多个文件：全部作为样品文件
        """
        if not event.mimeData().hasUrls():
            return
        urls = event.mimeData().urls()
        file_paths = [
            u.toLocalFile() for u in urls
            if u.isLocalFile() and os.path.isfile(u.toLocalFile())
        ]
        if not file_paths:
            return

        self.config["last_open_dir"] = os.path.dirname(file_paths[0])

        if len(file_paths) == 1:
            # 单文件 -> 参考
            signals = self._auto_standardize(file_paths[0])
            if not signals:
                QMessageBox.warning(self, "提示", "无法解析该文件，请检查格式")
                event.acceptProposedAction()
                return
            if len(signals) > 1:
                QMessageBox.information(
                    self, "提示",
                    f"该文件包含 {len(signals)} 条扫描，已自动取第 1 条作为参考。"
                )
            self.ref_signal = signals[0]
            self.ref_file = self.ref_signal.metadata.get("standard_file", file_paths[0])
            self.ref_list.clear()
            self._append_ref_list_item(
                self.ref_file, os.path.basename(self.ref_file), "#2E7D32"
            )
            self._update_status("已拖拽添加参考文件（已自动标准化）", "ready")
            info(f"拖拽添加参考文件（自动标准化）: {self.ref_file}")
        else:
            # 多文件 -> 样品
            added = 0
            for raw in file_paths:
                signals = self._auto_standardize(raw)
                for signal in signals:
                    path = signal.metadata.get("standard_file", raw)
                    self.sam_files.append(path)
                    self.sam_signals.append(signal)
                    name = os.path.splitext(os.path.basename(path))[0]
                    self.sam_names.append(name)
                    self._append_sam_list_item(
                        path, name, sample_color(len(self.sam_list) - 1)
                    )
                    self.per_sample_window_params[len(self.sam_names) - 1] = None
                    self.per_sample_thickness[len(self.sam_names) - 1] = None
                    added += 1
            if added:
                self._refresh_sample_list_colors()
                self._update_status(
                    f"已拖拽添加 {added} 个样品文件（已自动标准化）", "ready"
                )
                info(f"拖拽添加 {added} 个样品文件（自动标准化）")

        event.acceptProposedAction()
    
    def _on_closing(self, event):
        """窗口关闭事件"""
        try:
            # 先从日志器移除界面 handler 并断开信号，避免窗口销毁后仍被写入
            if getattr(self, "log_handler", None) is not None:
                logger = logging.getLogger("THzAnalyzer")
                logger.removeHandler(self.log_handler)
                try:
                    self.log_handler.message_appended.disconnect(self._append_log_message)
                except (TypeError, RuntimeError):
                    pass
                self.log_handler = None
            save_config(self.config)
            self._release_figures()
            plt.close('all')
            info("程序关闭")
            event.accept()
        except Exception as e:
            error(f"关闭程序时出错: {e}")
            event.accept()


def _unique_dest(path: str) -> str:
    """若目标文件已存在，自动追加 _2/_3 序号，返回可用的新路径。"""
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    counter = 2
    while os.path.exists(f"{stem}_{counter}{ext}"):
        counter += 1
    return f"{stem}_{counter}{ext}"


def _shift_indexed_dict(mapping: dict, removed_index: int) -> dict:
    """删除第 removed_index 项后重排整数键字典（大于 removed_index 的键减 1）。

    用于样品删除后同步重建逐样品窗参数 / 厚度配置的索引映射。
    """
    shifted = {}
    for key, value in mapping.items():
        if key < removed_index:
            shifted[key] = value
        elif key > removed_index:
            shifted[key - 1] = value
    return shifted
