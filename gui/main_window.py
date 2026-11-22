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
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QGroupBox,
    QMessageBox, QTabWidget, QListWidget, QListWidgetItem, QSplitter,
    QComboBox, QScrollArea, QDialog, QAbstractItemView,
    QFrame, QMenu, QToolButton,
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import (
    QAction, QColor, QIcon, QPainter, QPixmap,
    QDragEnterEvent, QDragMoveEvent, QDropEvent,
)

from config import load_config, save_config, update_thickness_history
from core import calculate_optical_params
from core.calculator import build_result_figures
from core.exceptions import DataReadError
from core.standard_format import (
    INPUT_FILE_FILTER,
    is_standard_txt,
    read_standard_txt,
    standardize_file,
    write_standard_txt,
)
from core.plotting import sample_color, short_display_name
from utils import info, warning, error
from utils.app_paths import get_resource_dir
from utils.matplotlib_setup import set_matplotlib_theme, apply_figure_theme
from core.version import APP_VERSION, UPDATE_URL
from core.updater import is_newer

from .worker import CalculationWorker, SaveWorker
from .update_checker import UpdateCheckWorker
from .log_handler import LogViewHandler, log_line_html
from .dialogs import HelpDialog, AboutDialog, UpdateDialog, LogDialog, FormatGuideDialog
from .status_bar import StatusBar
from .result_chart import ResultChart
from .icons import interface_icon, refresh_interface_icons, set_button_icon
from .styles import WHITE, apply_dark_theme, apply_light_theme


def _local_file_paths_from_mime(mime_data) -> list[str]:
    """从拖放 mime 数据中取出本地文件路径。"""
    if mime_data is None or not mime_data.hasUrls():
        return []
    return [
        url.toLocalFile()
        for url in mime_data.urls()
        if url.isLocalFile() and os.path.isfile(url.toLocalFile())
    ]


def _file_color_icon(color: str) -> QIcon:
    """用小圆点对应曲线色，文件名仍使用主题的深色文字。"""
    pixmap = QPixmap(24, 24)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("#878787"))
    painter.setBrush(QColor(color))
    painter.drawEllipse(2, 2, 8, 8)
    painter.end()
    return QIcon(pixmap)


class FileDropListWidget(QListWidget):
    """接受外部文件拖入的列表框，发出 filesDropped(paths)。"""

    filesDropped = pyqtSignal(list)
    fileCountChanged = pyqtSignal(int)
    hasSelectionChanged = pyqtSignal(bool)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAccessibleName(title)
        self.setAccessibleDescription("可拖入文件，或使用列表上方的添加按钮。")
        self.setIconSize(QSize(12, 12))
        self.setProperty("dropZone", True)
        self.setProperty("dragActive", False)
        self._hint = QLabel("将文件拖到这里", self.viewport())
        self._hint.setProperty("uiRole", "hint")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.itemSelectionChanged.connect(self._emit_selection_state)

    @pyqtSlot()
    def _emit_selection_state(self):
        self.hasSelectionChanged.emit(bool(self.selectedItems()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._hint.setGeometry(self.viewport().rect())

    def _refresh_style(self):
        self.style().unpolish(self)
        self.style().polish(self)
        self.viewport().update()
        self.update()

    def _notify_file_change(self):
        # Qt 销毁列表时也会重置模型，只在文件操作后更新界面。
        count = self.count()
        empty = count == 0
        self._hint.setVisible(empty)
        if self.property("dropZone") != empty:
            self.setProperty("dropZone", empty)
            self._refresh_style()
        self.fileCountChanged.emit(count)

    def _set_drag_active(self, active: bool):
        if self.property("dragActive") != active:
            self.setProperty("dragActive", active)
            self._refresh_style()

    def add_file(self, path: str, name: str, color: str):
        item = QListWidgetItem(_file_color_icon(color), short_display_name(name))
        item.setToolTip(path)
        self.addItem(item)
        self._notify_file_change()

    def clear(self):
        super().clear()
        self._notify_file_change()

    def takeItem(self, row: int) -> QListWidgetItem | None:
        item = super().takeItem(row)
        self._notify_file_change()
        return item

    def dragEnterEvent(self, event: QDragEnterEvent):
        if _local_file_paths_from_mime(event.mimeData()):
            self._set_drag_active(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if _local_file_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self._set_drag_active(False)
        paths = _local_file_paths_from_mime(event.mimeData())
        if not paths:
            event.ignore()
            return
        self.filesDropped.emit(paths)
        event.acceptProposedAction()


class THzAnalyzerApp(QMainWindow):
    """THz光学参数分析系统的主应用程序类"""
    
    def __init__(self):
        super().__init__()
        
        info("正在初始化THz分析系统...")
        
        # 加载配置，并在创建控件前恢复上次选择的主题。
        self.config = load_config()
        self._dark_theme = self.config.get("theme", "light") == "dark"
        self._apply_theme(self._dark_theme, persist=False)

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
        self._result_charts: tuple[ResultChart, ...] = ()
        
        # 计算工作线程
        self.calc_worker = None
        
        # 保存工作线程
        self.save_worker = None
        
        # 状态栏
        self.status_bar = None
        
        # 设置窗口
        self.setWindowTitle("THz 时域光谱分析系统")
        self.setMinimumSize(1080, 680)
        self.resize(1220, 800)
        # 打包后资源文件位于 _MEIPASS (onedir 下为 _internal)，开发环境为项目根目录
        icon_path = os.path.join(get_resource_dir(), "app.ico")
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 创建界面
        self._init_ui()
        
        # 将全局日志流接到运行日志窗口
        self._attach_log_handler()
        
        # 绑定窗口关闭事件
        self.closeEvent = self._on_closing

        info("THz分析系统初始化完成")

        # 启动后延迟执行静默更新检查（不阻塞界面初始化）
        QTimer.singleShot(3000, self._check_updates_auto)

    def _apply_theme(self, dark: bool, *, persist: bool = True) -> None:
        """切换 Qt、Matplotlib 和现有结果图的主题。"""
        self._dark_theme = bool(dark)
        app = QApplication.instance()
        if app is None:
            return
        if self._dark_theme:
            apply_dark_theme(app)
        else:
            apply_light_theme(app)
        set_matplotlib_theme(self._dark_theme)
        refresh_interface_icons(self, self._dark_theme)
        for chart in getattr(self, "_result_charts", ()):
            apply_figure_theme(chart.canvas.figure, self._dark_theme)
        if persist:
            self.config["theme"] = "dark" if self._dark_theme else "light"
            save_config(self.config)
        action = getattr(self, "theme_action", None)
        if action is not None and action.isChecked() != self._dark_theme:
            action.blockSignals(True)
            action.setChecked(self._dark_theme)
            action.blockSignals(False)

    def _init_ui(self):
        """初始化标题栏、左右工作区和底部状态栏。"""
        self._create_menu_bar()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        shell = QVBoxLayout(central_widget)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self._app_header = self._create_header()
        shell.addWidget(self._app_header)

        workspace = QWidget()
        workspace.setObjectName("workspace")
        workspace.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        main_layout = QVBoxLayout(workspace)
        main_layout.setContentsMargins(16, 14, 16, 4)
        main_layout.setSpacing(5)
        shell.addWidget(workspace, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(12)
        splitter.setChildrenCollapsible(False)
        self._settings_panel = self._create_left_panel()
        splitter.addWidget(self._settings_panel)
        splitter.addWidget(self._create_right_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([310, 900])
        main_layout.addWidget(splitter, 1)

        self.status_bar = StatusBar(self)
        main_layout.addWidget(self.status_bar)
        self.setAcceptDrops(True)

    def _create_header(self) -> QFrame:
        """创建紧凑的品牌栏，把垂直空间留给结果曲线。"""
        header = QFrame()
        header.setObjectName("appHeader")
        header.setFixedHeight(48)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(9)

        mark = QLabel()
        mark.setObjectName("brandMark")
        mark.setFixedSize(32, 32)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setPixmap(interface_icon("wave", 18, WHITE).pixmap(QSize(18, 18), 2.0))
        layout.addWidget(mark)

        brand = QHBoxLayout()
        brand.setSpacing(8)
        title = QLabel("THz 时域光谱分析系统")
        title.setObjectName("appTitle")
        brand.addWidget(title)
        separator = QLabel("·")
        separator.setProperty("uiRole", "hint")
        brand.addWidget(separator)
        subtitle = QLabel("光学参数提取工作台")
        subtitle.setProperty("uiRole", "hint")
        brand.addWidget(subtitle)
        layout.addLayout(brand)
        layout.addStretch()

        group = QLabel("NUAA THz Group")
        group.setProperty("uiRole", "hint")
        layout.addWidget(group)
        version = QLabel(f"v{APP_VERSION}")
        version.setProperty("uiRole", "count")
        layout.addWidget(version, alignment=Qt.AlignmentFlag.AlignVCenter)
        return header

    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单：仅退出
        file_menu = menubar.addMenu("文件")

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 日志菜单：查看运行日志
        log_menu = menubar.addMenu("日志")
        view_log_action = QAction("查看运行日志...", self)
        view_log_action.triggered.connect(self._show_log_dialog)
        log_menu.addAction(view_log_action)

        # 视图菜单：主题切换
        view_menu = menubar.addMenu("视图")
        self.theme_action = QAction("深色主题", self)
        self.theme_action.setCheckable(True)
        self.theme_action.setStatusTip("切换亮色 / 暗色界面")
        self.theme_action.setChecked(self._dark_theme)
        self.theme_action.toggled.connect(self._apply_theme)
        view_menu.addAction(self.theme_action)

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
    
    def _create_left_panel(self) -> QFrame:
        """建立可滚动的设置区，运行按钮固定在侧栏底部。"""
        panel = QFrame()
        panel.setProperty("uiRole", "card")
        panel.setMinimumWidth(282)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(1, 12, 1, 6)
        panel_layout.setSpacing(0)

        title = QLabel("分析设置")
        title.setProperty("uiRole", "panelTitle")
        title.setContentsMargins(14, 0, 14, 8)
        panel_layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("sidebarContent")
        left_layout = QVBoxLayout(content)
        left_layout.setContentsMargins(14, 0, 14, 10)
        left_layout.setSpacing(10)
        self._create_ref_file_section(left_layout)
        self._create_sam_file_section(left_layout)
        rule = QFrame()
        rule.setObjectName("sectionRule")
        rule.setFixedHeight(1)
        left_layout.addWidget(rule)
        self._create_parameter_section(left_layout)
        left_layout.addStretch()
        scroll.setWidget(content)
        panel_layout.addWidget(scroll, 1)

        footer = QFrame()
        footer.setObjectName("sidebarFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(14, 10, 14, 4)
        self.run_btn = QPushButton("运行分析")
        self.run_btn.setObjectName("runAnalysis")
        self.run_btn.setProperty("uiRole", "primary")
        set_button_icon(self.run_btn, "run", primary=True)
        self.run_btn.clicked.connect(self._run_analysis)
        footer_layout.addWidget(self.run_btn)
        panel_layout.addWidget(footer)
        return panel
    
    def _attach_log_handler(self):
        """把全局日志流接到运行日志窗口（经 Qt 信号跨线程安全投递），
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
    
    def _standardized_dir(self) -> str:
        """返回自动标准化临时目录（系统临时目录下，不污染项目目录）。

        仅存放分析用的中间标准 txt（由 write_standard_txt 在写入时自动创建）。
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
        try:
            if is_standard_txt(raw_path):
                signal = read_standard_txt(raw_path)
                signals = [signal]
            else:
                signals = standardize_file(raw_path)
        except DataReadError:
            raise
        except Exception as exc:
            raise DataReadError(raw_path, str(exc)) from exc

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

    def _file_section(self, title: str, on_add, count: QLabel | None = None) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(title)
        label.setProperty("uiRole", "sectionTitle")
        row.addWidget(label)
        if count is not None:
            row.addWidget(count)
        row.addStretch()
        add_btn = QPushButton("添加")
        add_btn.setAccessibleName(f"添加{title}")
        add_btn.setProperty("uiRole", "soft")
        set_button_icon(add_btn, "plus")
        add_btn.clicked.connect(on_add)
        row.addWidget(add_btn)
        layout.addLayout(row)
        return layout

    def _create_ref_file_section(self, parent_layout):
        layout = self._file_section("参考文件", self._select_ref_file)
        self.ref_list = FileDropListWidget("参考文件")
        self.ref_list.setFixedHeight(46)
        self.ref_list.filesDropped.connect(self._on_ref_files_dropped)
        layout.addWidget(self.ref_list)
        parent_layout.addLayout(layout)

    def _create_sam_file_section(self, parent_layout):
        self.sample_count = QLabel()
        self.sample_count.setProperty("uiRole", "count")
        layout = self._file_section("样品文件", self._add_sam_file, self.sample_count)
        self.sam_list = FileDropListWidget("样品文件")
        self.sam_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.sam_list.setFixedHeight(116)
        self.sam_list.filesDropped.connect(self._add_sample_files)
        layout.addWidget(self.sam_list)

        actions = QHBoxLayout()
        actions.setSpacing(5)
        actions.addStretch()
        delete_btn = QPushButton("删除选中")
        delete_btn.setProperty("uiRole", "plain")
        delete_btn.setEnabled(False)
        delete_btn.clicked.connect(self._delete_selected_file)
        self.sam_list.hasSelectionChanged.connect(delete_btn.setEnabled)
        actions.addWidget(delete_btn)
        self.clear_samples_btn = QPushButton("清空")
        self.clear_samples_btn.setProperty("uiRole", "plain")
        self.clear_samples_btn.clicked.connect(self._clear_sam_files)
        actions.addWidget(self.clear_samples_btn)
        layout.addLayout(actions)
        parent_layout.addLayout(layout)

        self.sam_list.fileCountChanged.connect(self._update_sample_count)
        self._update_sample_count(0)

    @pyqtSlot(int)
    def _update_sample_count(self, count: int):
        self.sample_count.setText(f"{count} 个")
        self.sample_count.setAccessibleName(f"已导入 {count} 个样品")
        self.clear_samples_btn.setEnabled(count > 0)
    
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
        self._set_reference_file(file_path)

    def _on_ref_files_dropped(self, file_paths: list[str]):
        """拖入参考框：始终作为参考文件；多个文件时取第一个。"""
        if not file_paths:
            return
        if len(file_paths) > 1:
            QMessageBox.information(
                self, "提示",
                f"参考文件只需 1 个，已使用「{os.path.basename(file_paths[0])}」。"
            )
        self._set_reference_file(file_paths[0])

    def _show_format_guide(self, failed_items: list[str] | None = None):
        """文件无法识别时，引导用户自行转换为标准 Excel / txt。"""
        dialog = FormatGuideDialog(failed_items, self)
        dialog.exec()

    def _set_reference_file(self, file_path: str):
        """将指定文件设为参考（自动标准化）。"""
        try:
            signals = self._auto_standardize(file_path)
        except DataReadError as exc:
            warning(str(exc))
            self._show_format_guide(
                [f"{os.path.basename(file_path)}：{exc.message}"]
            )
            return
        if not signals:
            self._show_format_guide([os.path.basename(file_path)])
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
        self.ref_list.add_file(self.ref_file, os.path.basename(self.ref_file), "black")
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
        self._add_sample_files(file_paths)

    def _add_sample_files(self, file_paths: list[str]):
        """将文件加入样品列表（自动标准化）。拖入样品框时无论几个都作为样品。"""
        if not file_paths:
            return

        self.config["last_open_dir"] = os.path.dirname(file_paths[0])
        added = 0
        failed = []
        for raw in file_paths:
            try:
                signals = self._auto_standardize(raw)
            except DataReadError as exc:
                warning(str(exc))
                failed.append(f"{os.path.basename(raw)}：{exc.message}")
                continue
            if not signals:
                failed.append(f"{os.path.basename(raw)}：无法解析")
                continue
            for signal in signals:
                path = signal.metadata.get("standard_file", raw)
                self.sam_files.append(path)
                self.sam_signals.append(signal)
                name = os.path.splitext(os.path.basename(path))[0]
                self.sam_names.append(name)
                idx = len(self.sam_names) - 1
                self.sam_list.add_file(path, name, sample_color(idx))
                self.per_sample_window_params[idx] = None
                self.per_sample_thickness[idx] = None
                added += 1

        if added:
            self._refresh_sample_list_colors()
            self._update_status(f"已添加 {added} 个样品文件（已自动标准化）", "ready")
            info(f"添加 {added} 个样品文件（自动标准化）")
        if failed:
            self._show_format_guide(failed)

    def _refresh_sample_list_colors(self):
        """按样品索引刷新列表颜色标识。"""
        for index in range(self.sam_list.count()):
            item = self.sam_list.item(index)
            if item is None:
                continue
            item.setIcon(_file_color_icon(sample_color(index)))
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
        self._refresh_window_params_indicator()
        self._update_status("样品文件列表已清空", "ready")
    
    def _create_parameter_section(self, parent_layout):
        """创建参数设置区域"""
        thickness_label = QLabel("样品厚度 (mm)")
        thickness_label.setProperty("uiRole", "sectionTitle")
        parent_layout.addWidget(thickness_label)

        # 默认厚度和逐样品设置并排，避免窄侧栏截断标题。
        thickness_layout = QHBoxLayout()
        thickness_layout.setSpacing(8)

        self.thickness_combo = QComboBox()
        self.thickness_combo.setEditable(True)
        self.thickness_combo.setAccessibleName("默认样品厚度（毫米）")
        self.thickness_combo.setMinimumWidth(68)
        self.thickness_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
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

        self.set_thickness_btn = QPushButton("按样品设置")
        self.set_thickness_btn.setToolTip("为每个样品单独设置厚度 (mm)，留空表示使用左侧全局默认值")
        self.set_thickness_btn.clicked.connect(self._open_thickness_dialog)
        thickness_layout.addWidget(self.set_thickness_btn)
        parent_layout.addLayout(thickness_layout)

        tukey_row = QHBoxLayout()
        tukey_row.setSpacing(8)
        tukey_label = QLabel("Tukey 窗函数")
        tukey_label.setProperty("uiRole", "sectionTitle")
        tukey_row.addWidget(tukey_label)

        self.use_window_switch = QPushButton("●")
        self.use_window_switch.setObjectName("windowToggle")
        self.use_window_switch.setAccessibleName("启用 Tukey 窗函数")
        self.use_window_switch.setToolTip("启用 Tukey 窗函数以抑制多次反射")
        self.use_window_switch.setFixedSize(38, 20)
        self.use_window_switch.setCheckable(True)
        self.use_window_switch.toggled.connect(self._toggle_window_params)
        tukey_row.addWidget(self.use_window_switch)
        tukey_row.addStretch()

        self.set_signal_window_btn = QPushButton("设置参数")
        self.set_signal_window_btn.setToolTip("为参考信号和各样品分别设置 Tukey 窗口")
        self.set_signal_window_btn.clicked.connect(self._open_signal_window_dialog)
        tukey_row.addWidget(self.set_signal_window_btn)
        parent_layout.addLayout(tukey_row)

        self.window_params_indicator = QLabel("窗口参数已设置")
        self.window_params_indicator.setProperty("uiRole", "hint")
        parent_layout.addWidget(self.window_params_indicator)
        self._toggle_window_params(self.use_window_switch.isChecked())

    def _busy_worker_running(self) -> bool:
        """计算或保存线程是否仍在运行。"""
        calc = getattr(self, "calc_worker", None)
        save = getattr(self, "save_worker", None)
        try:
            if calc is not None and calc.isRunning():
                return True
        except RuntimeError:
            self.calc_worker = None
        try:
            if save is not None and save.isRunning():
                return True
        except RuntimeError:
            self.save_worker = None
        return False

    def _set_analysis_busy(self, busy: bool):
        """计算/保存期间禁用会冲突的按钮，避免重复启动。"""
        results_available = not busy and self.results_data is not None
        self.run_btn.setEnabled(not busy)
        self.export_btn.setEnabled(results_available)
        self.focus_chart_btn.setEnabled(bool(self._result_charts))

    def _save_results(self):
        """保存光学参数结果（Excel，每个样品一个工作表）。"""
        self._save_with_worker("optical", "保存光学参数")

    def _save_time_data(self):
        """保存时域数据（Excel，每个文件一个工作表）。"""
        self._save_with_worker("time", "保存时域数据")

    def _save_freq_data(self):
        """保存频域数据（Excel，每个文件一个工作表）。"""
        self._save_with_worker("freq", "保存频域数据")

    def _save_with_worker(self, save_type: str, caption: str):
        """通过后台线程保存结果，避免阻塞界面。"""
        if self.results_data is None:
            QMessageBox.information(self, "提示", "请先运行分析")
            return
        if self._busy_worker_running():
            QMessageBox.information(self, "提示", "正在处理中，请稍候")
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
        self.save_worker.progress_updated.connect(self._on_progress_updated)
        self.save_worker.save_finished.connect(self._on_save_finished)
        self.save_worker.save_error.connect(self._on_save_error)
        self._set_analysis_busy(True)
        self._update_status("正在保存...", "working")
        if self.status_bar:
            self.status_bar.show_progress(True)
        self.save_worker.start()

    def _on_save_finished(self, saved_path: str):
        """保存完成回调。"""
        if self.status_bar:
            self.status_bar.show_progress(False)
        self._set_analysis_busy(False)
        self._update_status("保存完成", "success")

    def _on_save_error(self, message: str):
        """保存失败回调。"""
        if self.status_bar:
            self.status_bar.show_progress(False)
        self._set_analysis_busy(False)
        self._update_status("保存失败", "error")
        QMessageBox.critical(self, "保存失败", str(message))
        error(f"保存失败: {message}")

    def _create_right_panel(self) -> QFrame:
        """把图表和导出入口集中在结果区。"""
        panel = QFrame()
        panel.setProperty("uiRole", "card")
        root = QVBoxLayout(panel)
        root.setContentsMargins(14, 11, 14, 12)

        self.right_panel = QTabWidget()
        self.right_panel.setAccessibleName("分析结果")
        actions = QWidget()
        header = QHBoxLayout(actions)
        header.setContentsMargins(8, 0, 0, 8)
        header.setSpacing(8)

        self.focus_chart_btn = QPushButton("专注图表")
        self.focus_chart_btn.setProperty("uiRole", "soft")
        self.focus_chart_btn.setCheckable(True)
        self.focus_chart_btn.setToolTip("隐藏设置和应用标题，扩大曲线区")
        self.focus_chart_btn.toggled.connect(self._set_chart_focus)
        header.addWidget(self.focus_chart_btn)

        self.export_btn = QToolButton()
        self.export_btn.setObjectName("exportButton")
        self.export_btn.setText("导出 Excel")
        self.export_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.export_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        set_button_icon(self.export_btn, "download")
        self.export_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        export_menu = QMenu(self.export_btn)
        export_menu.addAction("保存光学参数", self._save_results)
        export_menu.addAction("保存时域数据", self._save_time_data)
        export_menu.addAction("保存频域数据", self._save_freq_data)
        self.export_btn.setMenu(export_menu)
        header.addWidget(self.export_btn)
        self.right_panel.setCornerWidget(actions)

        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tab3 = QWidget()
        for tab, name in (
            (self.tab1, "时域 / 频域"),
            (self.tab2, "光学参数"),
            (self.tab3, "介电特性"),
        ):
            tab.setObjectName("resultPage")
            layout = QVBoxLayout(tab)
            layout.setContentsMargins(0, 8, 0, 0)
            layout.setSpacing(6)
            layout.addWidget(self._create_empty_result(), 1)
            self.right_panel.addTab(tab, name)
        root.addWidget(self.right_panel, 1)
        self._set_analysis_busy(False)
        return panel

    def _set_chart_focus(self, focused: bool) -> None:
        self._settings_panel.setVisible(not focused)
        self._app_header.setVisible(not focused)
        self.focus_chart_btn.setText("退出专注" if focused else "专注图表")
        self.focus_chart_btn.setToolTip(
            "恢复左侧分析设置和应用标题" if focused else "隐藏设置和应用标题，扩大曲线区"
        )

    def _create_empty_result(self) -> QWidget:
        empty_state = QWidget()
        layout = QVBoxLayout(empty_state)
        layout.setSpacing(8)
        layout.addStretch()

        mark = QLabel()
        mark.setObjectName("emptyMark")
        mark.setFixedSize(48, 48)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setPixmap(interface_icon("chart", 26).pixmap(QSize(26, 26), 2.0))
        layout.addWidget(mark, alignment=Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("尚无分析结果")
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        hint = QLabel("添加参考文件和样品文件后，点击「运行分析」。")
        hint.setProperty("uiRole", "hint")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        layout.addStretch()
        return empty_state
    
    def _update_status(self, message: str, status_type: str = "ready"):
        """更新状态栏"""
        if self.status_bar:
            self.status_bar.set_status(message, status_type)
    
    def _toggle_window_params(self, enabled: bool):
        """切换窗函数参数设置。"""
        self.set_signal_window_btn.setEnabled(enabled)
        self._refresh_window_params_indicator()

    def _refresh_window_params_indicator(self):
        """窗函数开启且已保存过参数时显示「参数已设置」。"""
        has_params = (
            self.ref_window_params is not None
            or any(value is not None for value in self.per_sample_window_params.values())
        )
        enabled = bool(
            getattr(self, "use_window_switch", None) and self.use_window_switch.isChecked()
        )
        if hasattr(self, "window_params_indicator"):
            self.window_params_indicator.setVisible(enabled and has_params)
    
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
        info_label.setProperty("uiRole", "hint")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
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

        failures = []
        for key, path in targets:
            try:
                signal = load_standard_signal(path)
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
        info_label.setProperty("uiRole", "hint")
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
            if value is not None:
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
            
            self._refresh_window_params_indicator()
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

        if self._busy_worker_running():
            QMessageBox.information(self, "提示", "正在处理中，请稍候")
            return
        
        try:
            # 获取参数
            thickness = float(self.thickness_combo.currentText())
            if thickness <= 0:
                raise ValueError("样品厚度必须为正数")
            
            self.config = update_thickness_history(self.config, thickness)
            self.config["thickness"] = thickness
            save_config(self.config)  # 立即保存配置，避免异常退出时丢失
            
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
            
            # 显示进度条并启动计算（旧图保留到成功后再替换）
            self._set_analysis_busy(True)
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
        if self.status_bar:
            self.status_bar.show_progress(False)
        
        if result.success:
            try:
                self._update_status("正在生成图表...", "working")
                build_result_figures(result)
                self._display_charts(result.fig1, result.fig2, result.fig3)
            except Exception as exc:
                self._set_analysis_busy(False)
                self._update_status("图表生成失败", "error")
                QMessageBox.critical(self, "图表错误", str(exc))
                error(f"图表生成失败: {exc}")
                return

            self.results_data = result.data
            self._set_analysis_busy(False)
            self._update_status("计算完成", "success")
            info("计算完成")
        else:
            self._set_analysis_busy(False)
            self._update_status("计算失败", "error")
    
    def _on_calculation_error(self, error_message: str):
        """计算错误回调"""
        if self.status_bar:
            self.status_bar.show_progress(False)
        
        self._set_analysis_busy(False)
        self._update_status("计算失败", "error")
        QMessageBox.critical(self, "计算错误", error_message)
        error(f"计算错误: {error_message}")
    
    def _on_warning_occurred(self, warning_message: str):
        """警告回调"""
        QMessageBox.warning(self, "警告", warning_message)
        warning(warning_message)
    
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
        """替换分析结果，重算时保留用户正在看的指标。"""
        views = tuple(chart.views.currentIndex() for chart in self._result_charts) or (0, 0, 0)
        charts = tuple(
            ResultChart(figure, initial_view=index)
            for figure, index in zip((fig1, fig2, fig3), views, strict=True)
        )
        for tab, chart in zip((self.tab1, self.tab2, self.tab3), charts, strict=True):
            layout = tab.layout()
            previous = layout.takeAt(0).widget()
            previous.hide()
            previous.deleteLater()
            layout.addWidget(chart, 1)

        self._release_figures()
        self.fig1, self.fig2, self.fig3 = fig1, fig2, fig3
        self._result_charts = charts
    
    def _show_help_dialog(self):
        """显示帮助对话框"""
        dialog = HelpDialog(self)
        dialog.exec()
    
    def _show_about_dialog(self):
        """显示关于对话框"""
        dialog = AboutDialog(self)
        dialog.exec()

    def _check_updates_auto(self):
        """启动后自动检查更新：受自动检查开关控制，每次启动都检查，失败静默。"""
        if not self.config.get("auto_check_update", True):
            return
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
        self.update_worker.check_not_found.connect(
            lambda message: self._on_update_check_not_found(message, manual)
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

    def _on_update_check_not_found(self, message: str, manual: bool):
        """更新源尚未发布任何版本。"""
        self.config["last_update_check"] = datetime.now().isoformat(timespec="seconds")
        self._update_status("暂无可用更新", "ready")
        if manual:
            QMessageBox.information(self, "检查更新", message)
        else:
            info(f"自动更新检查: {message}")

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
        """拖到窗口空白处时允许放下（实际目标由参考/样品框处理更优先）。"""
        if _local_file_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if _local_file_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """拖到窗口空白处：单文件作为参考，多个文件作为样品。"""
        file_paths = _local_file_paths_from_mime(event.mimeData())
        if not file_paths:
            event.ignore()
            return
        if len(file_paths) == 1:
            self._set_reference_file(file_paths[0])
        else:
            self._add_sample_files(file_paths)
        event.acceptProposedAction()
    
    def _on_closing(self, event):
        """窗口关闭事件"""
        try:
            if not self._stop_background_workers():
                QMessageBox.information(self, "提示", "正在结束后台任务，请稍候再关闭")
                event.ignore()
                return
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

    def _stop_background_workers(self) -> bool:
        """请求停止后台线程；若短时间内仍未结束则阻止关闭。"""
        workers = []
        for attr in ("calc_worker", "save_worker", "update_worker"):
            worker = getattr(self, attr, None)
            if worker is None:
                continue
            try:
                if worker.isRunning():
                    workers.append(worker)
            except RuntimeError:
                continue
        for worker in workers:
            worker.requestInterruption()
            worker.wait(1500)
            try:
                if worker.isRunning():
                    return False
            except RuntimeError:
                continue
        return True


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
