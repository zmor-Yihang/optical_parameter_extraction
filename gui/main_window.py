#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
THz光学参数分析系统主窗口

重构版本 - 代码拆分为多个模块
"""

import os
import matplotlib
matplotlib.use('QtAgg')  # 使用Qt6兼容后端
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QFileDialog, QGroupBox, 
    QMessageBox, QTabWidget, QCheckBox, QGridLayout,
    QListWidget, QSplitter, QFrame, QComboBox, QScrollArea, 
    QStyle, QDialog
)
from PyQt6.QtCore import Qt, QPoint, QRect, QSize
from PyQt6.QtGui import QAction, QFont, QPalette, QColor

from config import load_config, save_config, update_thickness_history
from core import calculate_optical_params, CalculationError, SaveError
from utils.icon_helper import IconHelper
from utils import info, warning, error

from .widgets import AnimatedButton
from .worker import CalculationWorker, SaveWorker
from .dialogs import HelpDialog, AboutDialog
from .styles import get_main_window_style, get_menubar_style
from .status_bar import StatusBar


class THzAnalyzerApp(QMainWindow):
    """THz光学参数分析系统的主应用程序类"""
    
    def __init__(self):
        super().__init__()
        
        info("正在初始化THz分析系统...")
        
        # 加载配置
        self.config = load_config()
        
        # 存储选中的文件
        self.ref_file = ""
        self.sam_files = []
        self.sam_names = []
        
        # 存储窗函数参数
        self.ref_window_params = None
        self.per_sample_window_params = {}
        
        # 存储计算结果
        self.results_data = None
        
        # 存储弹出窗口的引用
        self.popup_windows = {}
        
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
        
        # 创建图标
        self._create_icons()
        
        # 创建界面
        self._init_ui()
        
        # 绑定窗口关闭事件
        self.closeEvent = self._on_closing

        self.start_row = self.config.get("start_row", 1)
        
        info("THz分析系统初始化完成")

    def _create_icons(self):
        """创建应用程序使用的图标"""
        style = QApplication.style()
        
        # 文件相关图标
        self.folder_icon = IconHelper.create_file_icon("#4A90E2", 16)
        self.file_icon = style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        self.add_icon = IconHelper.create_text_icon("+", "#FFFFFF", "#28A745", 16)
        self.delete_icon = IconHelper.create_text_icon("-", "#FFFFFF", "#DC3545", 16)
        self.clear_icon = IconHelper.create_text_icon("×", "#FFFFFF", "#6C757D", 16)
        
        # 操作相关图标
        self.run_icon = IconHelper.create_arrow_icon("right", "#FFFFFF", 18)
        self.save_icon = IconHelper.create_file_icon("#17A2B8", 18)
        self.settings_icon = style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        
        # 标签页图标
        self.chart_icon = IconHelper.create_chart_icon("#28A745", 16)
        self.data_icon = IconHelper.create_text_icon("D", "#FFFFFF", "#007BFF", 16)
        self.info_icon = IconHelper.create_text_icon("i", "#FFFFFF", "#6F42C1", 16)
        
        # 状态图标
        self.ready_icon = IconHelper.create_colored_icon("#28A745", 16)
        self.working_icon = IconHelper.create_colored_icon("#FFC107", 16)
        self.error_icon = IconHelper.create_colored_icon("#DC3545", 16)
        
        # 参数图标
        self.thickness_icon = IconHelper.create_text_icon("T", "#FFFFFF", "#6C757D", 16)
        self.row_icon = IconHelper.create_text_icon("R", "#FFFFFF", "#6C757D", 16)
        
        # 窗口图标
        self.window_icon = style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.setWindowIcon(self.window_icon)

    def _init_ui(self):
        """初始化用户界面"""
        self._setup_styles()
        self._create_menu_bar()
        
        # 创建中央窗口部件
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #F5F5F5;")
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
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#5C6BC0"))
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
        
        # 文件菜单
        file_menu = menubar.addMenu("📁 文件")
        
        exit_action = QAction("🚪 退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("❓ 帮助")
        
        user_guide_action = QAction("📖 使用说明", self)
        user_guide_action.setShortcut("F1")
        user_guide_action.triggered.connect(self._show_help_dialog)
        help_menu.addAction(user_guide_action)
        
        about_action = QAction("ℹ️ 关于", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)
    
    def _create_left_panel(self):
        """创建左侧控制面板"""
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)
        
        # 程序标题
        title_label = QLabel("🔬 THz 时域光谱分析系统")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont("微软雅黑", 14, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #333333; margin-bottom: 10px;")
        left_layout.addWidget(title_label)
        
        # 参数设置区
        param_group = self._create_param_group()
        left_layout.addWidget(param_group)
        left_layout.addStretch()
        
        # 版权信息
        version_label = QLabel("By NUAA THz Group v4.6.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #666666; font-size: 15px;")
        left_layout.addWidget(version_label)
    
    def _create_param_group(self):
        """创建参数设置组"""
        param_group = QGroupBox("  ⚙️ 参数设置")
        param_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #CCCCCC;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                background-color: #F0F0F0;
                color: #333333;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #333333;
            }
        """)
        param_layout = QVBoxLayout(param_group)
        param_layout.setSpacing(15)
        
        # 参考文件选择
        self._create_ref_file_section(param_layout)
        
        # 样品文件选择
        self._create_sam_file_section(param_layout)
        
        # 参数设置
        self._create_parameter_section(param_layout)
        
        # 按钮组
        self._create_button_section(param_layout)
        
        return param_group
    
    def _create_ref_file_section(self, parent_layout):
        """创建参考文件选择区域"""
        ref_layout = QVBoxLayout()
        ref_label = QLabel("📂 参考文件:")
        ref_label.setStyleSheet("font-weight: bold; color: #333333;")
        ref_layout.addWidget(ref_label)
        
        ref_input_layout = QHBoxLayout()
        self.ref_file_edit = QLineEdit()
        self.ref_file_edit.setReadOnly(True)
        self.ref_file_edit.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: #FFFFFF;
                color: #333333;
            }
            QLineEdit:focus {
                border: 1px solid #4A90E2;
            }
        """)
        ref_input_layout.addWidget(self.ref_file_edit)
        
        ref_btn = AnimatedButton("  添加文件")
        ref_btn.setIcon(self.folder_icon)
        ref_btn.setIconSize(QSize(16, 16))
        ref_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 10px;
                background-color: #E0E0E0;
                color: #333333;
                border-radius: 4px;
                border: 1px solid #CCCCCC;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #DDDDDD;
            }
            QPushButton:pressed {
                background-color: #CCCCCC;
            }
        """)
        ref_btn.clicked.connect(self._select_ref_file)
        ref_input_layout.addWidget(ref_btn)
        
        ref_layout.addLayout(ref_input_layout)
        parent_layout.addLayout(ref_layout)
    
    def _create_sam_file_section(self, parent_layout):
        """创建样品文件选择区域"""
        sam_layout = QVBoxLayout()
        sam_label = QLabel("📁 样品文件:")
        sam_label.setStyleSheet("font-weight: bold; color: #333333;")
        sam_layout.addWidget(sam_label)
        
        sam_list_layout = QHBoxLayout()
        self.sam_files_list = QListWidget()
        self.sam_files_list.setAcceptDrops(True)
        self.sam_files_list.setDragEnabled(True)
        self.sam_files_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 5px;
                background-color: #FFFFFF;
                min-height: 120px;
                color: #333333;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #EEEEEE;
            }
            QListWidget::item:selected {
                background-color: #4A90E2;
                color: #FFFFFF;
            }
            QListWidget::item:hover {
                background-color: #F0F0F0;
            }
        """)
        sam_list_layout.addWidget(self.sam_files_list)
        
        # 样品文件操作按钮
        sam_btn_layout = QVBoxLayout()
        sam_btn_style = """
            QPushButton {
                padding: 5px 10px;
                background-color: #F0F0F0;
                color: #333333;
                border-radius: 4px;
                border: 1px solid #CCCCCC;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: #E0E0E0;
                border: 1px solid #999999;
            }
            QPushButton:pressed {
                background-color: #DDDDDD;
            }
        """
        
        add_sam_btn = AnimatedButton("  添加文件")
        add_sam_btn.setIcon(self.add_icon)
        add_sam_btn.setIconSize(QSize(16, 16))
        add_sam_btn.setStyleSheet(sam_btn_style)
        add_sam_btn.clicked.connect(self._add_sam_file)
        
        del_sam_btn = AnimatedButton("  删除选中")
        del_sam_btn.setIcon(self.delete_icon)
        del_sam_btn.setIconSize(QSize(16, 16))
        del_sam_btn.setStyleSheet(sam_btn_style)
        del_sam_btn.clicked.connect(self._delete_selected_file)
        
        clear_sam_btn = AnimatedButton("  清空列表")
        clear_sam_btn.setIcon(self.clear_icon)
        clear_sam_btn.setIconSize(QSize(16, 16))
        clear_sam_btn.setStyleSheet(sam_btn_style)
        clear_sam_btn.clicked.connect(self._clear_sam_files)
        
        sam_btn_layout.addWidget(add_sam_btn)
        sam_btn_layout.addWidget(del_sam_btn)
        sam_btn_layout.addWidget(clear_sam_btn)
        sam_btn_layout.addStretch()
        
        sam_list_layout.addLayout(sam_btn_layout)
        sam_layout.addLayout(sam_list_layout)
        parent_layout.addLayout(sam_layout)
    
    def _create_parameter_section(self, parent_layout):
        """创建参数设置区域"""
        # Tukey窗函数设置
        tukey_group = QGroupBox("Tukey窗函数设置")
        tukey_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #F8F8F8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #333333;
            }
        """)
        tukey_layout = QVBoxLayout(tukey_group)
        
        # 开关
        switch_layout = QHBoxLayout()
        
        self.use_window_checkbox = QCheckBox()
        self.use_window_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 0px;
            }
            QCheckBox::indicator {
                width: 40px;
                height: 20px;
                border-radius: 10px;
                background-color: #CCCCCC;
                border: 2px solid #999999;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 2px solid #45a049;
            }
        """)
        switch_layout.addWidget(self.use_window_checkbox)
        
        self.window_status_label = QLabel("关")
        self.window_status_label.setStyleSheet("""
            QLabel {
                color: #999999;
                font-weight: bold;
                padding: 2px 5px;
                font-size: 9pt;
            }
        """)
        switch_layout.addWidget(self.window_status_label)
        
        switch_label = QLabel("启用Tukey窗函数")
        switch_label.setStyleSheet("color: #333333; font-weight: bold; margin-left: 5px;")
        switch_layout.addWidget(switch_label)
        switch_layout.addStretch()
        
        tukey_layout.addLayout(switch_layout)
        
        # 设置按钮
        signal_window_button_layout = QHBoxLayout()
        signal_window_label = QLabel("为每个信号设置窗函数参数:")
        signal_window_label.setStyleSheet("color: #333333; font-weight: bold;")
        signal_window_button_layout.addWidget(signal_window_label)
        
        self.set_signal_window_btn = AnimatedButton("  设置参数")
        self.set_signal_window_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border-radius: 4px;
                padding: 5px 10px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        self.set_signal_window_btn.clicked.connect(self._open_signal_window_dialog)
        self.set_signal_window_btn.setEnabled(False)
        signal_window_button_layout.addWidget(self.set_signal_window_btn)
        signal_window_button_layout.addStretch()
        
        tukey_layout.addLayout(signal_window_button_layout)
        
        # 参数指示
        self.window_params_indicator = QLabel("✓ 参数已设置")
        self.window_params_indicator.setStyleSheet("""
            QLabel {
                color: #28A745;
                font-weight: bold;
                padding: 5px;
                background-color: #E8F5E9;
                border-radius: 4px;
            }
        """)
        self.window_params_indicator.setVisible(False)
        tukey_layout.addWidget(self.window_params_indicator)
        
        parent_layout.addWidget(tukey_group)
        
        # 连接信号
        self.use_window_checkbox.toggled.connect(self._toggle_window_params)
        self.use_window_checkbox.setChecked(False)
        
        # 样品厚度设置
        thickness_layout = QHBoxLayout()
        
        thickness_label_layout = QHBoxLayout()
        thickness_icon_label = QLabel()
        thickness_icon_label.setPixmap(self.thickness_icon.pixmap(16, 16))
        thickness_label = QLabel("样品厚度 (mm):")
        thickness_label.setStyleSheet("font-weight: bold; color: #333333;")
        
        thickness_label_layout.addWidget(thickness_icon_label)
        thickness_label_layout.addWidget(thickness_label)
        thickness_label_layout.addStretch()
        thickness_label_layout.setSpacing(5)
        
        thickness_label_widget = QWidget()
        thickness_label_widget.setLayout(thickness_label_layout)
        thickness_layout.addWidget(thickness_label_widget)
        
        self.thickness_combo = QComboBox()
        self.thickness_combo.setEditable(True)
        self.thickness_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: #FFFFFF;
                color: #333333;
            }
        """)
        
        # 从配置读取历史厚度
        thickness_history = [str(x) for x in self.config.get("thickness_history", [0.5])]
        current_thickness = str(self.config.get("thickness", 0.5))
        if current_thickness in thickness_history:
            thickness_history.remove(current_thickness)
        self.thickness_combo.addItem(current_thickness)
        for t in thickness_history:
            self.thickness_combo.addItem(t)
        self.thickness_combo.setCurrentText(current_thickness)
        thickness_layout.addWidget(self.thickness_combo)
        thickness_layout.setSpacing(8)
        thickness_layout.setStretch(1, 1)
        
        # 起始行设置
        start_row_layout = QHBoxLayout()
        
        start_row_label_layout = QHBoxLayout()
        start_row_icon_label = QLabel()
        start_row_icon_label.setPixmap(self.row_icon.pixmap(16, 16))
        start_row_label = QLabel("数据起始行:")
        start_row_label.setStyleSheet("font-weight: bold; color: #333333;")
        
        start_row_label_layout.addWidget(start_row_icon_label)
        start_row_label_layout.addWidget(start_row_label)
        start_row_label_layout.addStretch()
        start_row_label_layout.setSpacing(5)
        
        start_row_label_widget = QWidget()
        start_row_label_widget.setLayout(start_row_label_layout)
        start_row_layout.addWidget(start_row_label_widget)
        
        self.start_row_combo = QComboBox()
        self.start_row_combo.addItems(["1", "2", "3"])
        self.start_row_combo.setEditable(True)
        self.start_row_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: #FFFFFF;
                color: #333333;
            }
        """)
        idx = ["1", "2", "3"].index(str(self.config.get("start_row", 1))) if str(self.config.get("start_row", 1)) in ["1", "2", "3"] else -1
        if idx >= 0:
            self.start_row_combo.setCurrentIndex(idx)
        else:
            self.start_row_combo.setEditText(str(self.config.get("start_row", 1)))
        start_row_layout.addWidget(self.start_row_combo)
        start_row_layout.setSpacing(8)
        start_row_layout.setStretch(1, 1)
        
        parent_layout.addLayout(start_row_layout)
        parent_layout.addLayout(thickness_layout)
    
    def _create_button_section(self, parent_layout):
        """创建按钮区域"""
        button_layout = QVBoxLayout()
        
        # 第一行按钮
        first_row_layout = QHBoxLayout()
        
        run_btn = AnimatedButton("  运行分析")
        run_btn.setIcon(self.run_icon)
        run_btn.setIconSize(QSize(18, 18))
        run_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                background-color: #198754;
                color: white;
                border-radius: 4px;
                border: none;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #157347;
            }
            QPushButton:pressed {
                background-color: #146c43;
            }
        """)
        run_btn.clicked.connect(self._run_analysis)
        
        self.save_btn = AnimatedButton("  保存结果")
        self.save_btn.setIcon(self.save_icon)
        self.save_btn.setIconSize(QSize(18, 18))
        self.save_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                background-color: #0D6EFD;
                color: white;
                border-radius: 4px;
                border: none;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #0B5ED7;
            }
            QPushButton:disabled {
                background-color: #EEEEEE;
                color: #999999;
            }
        """)
        self.save_btn.clicked.connect(self._save_results)
        self.save_btn.setEnabled(False)
        
        first_row_layout.addWidget(run_btn)
        first_row_layout.addWidget(self.save_btn)
        
        button_layout.addLayout(first_row_layout)
        
        # 弹出图表按钮 - 使用紧凑的流式布局
        popup_label = QLabel("弹出图表:")
        popup_label.setStyleSheet("color: #666666; font-size: 10px; margin-top: 5px;")
        button_layout.addWidget(popup_label)
        
        popup_btn_style = """
            QPushButton {
                padding: 3px 8px;
                background-color: #6F42C1;
                color: white;
                border-radius: 3px;
                border: none;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #5A32A3;
            }
            QPushButton:disabled {
                background-color: #DDDDDD;
                color: #999999;
            }
        """
        
        # 第一行：时域、频域、折射率、消光
        popup_row1 = QHBoxLayout()
        popup_row1.setSpacing(3)
        
        self.popup_time_btn = QPushButton("时域")
        self.popup_time_btn.setStyleSheet(popup_btn_style)
        self.popup_time_btn.clicked.connect(lambda: self._show_single_chart("time"))
        self.popup_time_btn.setEnabled(False)
        
        self.popup_freq_btn = QPushButton("频域")
        self.popup_freq_btn.setStyleSheet(popup_btn_style)
        self.popup_freq_btn.clicked.connect(lambda: self._show_single_chart("freq"))
        self.popup_freq_btn.setEnabled(False)
        
        self.popup_n_btn = QPushButton("n")
        self.popup_n_btn.setStyleSheet(popup_btn_style)
        self.popup_n_btn.setToolTip("折射率")
        self.popup_n_btn.clicked.connect(lambda: self._show_single_chart("refractive"))
        self.popup_n_btn.setEnabled(False)
        
        self.popup_k_btn = QPushButton("k")
        self.popup_k_btn.setStyleSheet(popup_btn_style)
        self.popup_k_btn.setToolTip("消光系数")
        self.popup_k_btn.clicked.connect(lambda: self._show_single_chart("extinction"))
        self.popup_k_btn.setEnabled(False)
        
        popup_row1.addWidget(self.popup_time_btn)
        popup_row1.addWidget(self.popup_freq_btn)
        popup_row1.addWidget(self.popup_n_btn)
        popup_row1.addWidget(self.popup_k_btn)
        
        button_layout.addLayout(popup_row1)
        
        # 第二行：吸收、介电实部、虚部、损耗
        popup_row2 = QHBoxLayout()
        popup_row2.setSpacing(3)
        
        self.popup_a_btn = QPushButton("α")
        self.popup_a_btn.setStyleSheet(popup_btn_style)
        self.popup_a_btn.setToolTip("吸收系数")
        self.popup_a_btn.clicked.connect(lambda: self._show_single_chart("absorption"))
        self.popup_a_btn.setEnabled(False)
        
        self.popup_er_btn = QPushButton("ε'")
        self.popup_er_btn.setStyleSheet(popup_btn_style)
        self.popup_er_btn.setToolTip("介电常数实部")
        self.popup_er_btn.clicked.connect(lambda: self._show_single_chart("epsilon_real"))
        self.popup_er_btn.setEnabled(False)
        
        self.popup_ei_btn = QPushButton("ε\"")
        self.popup_ei_btn.setStyleSheet(popup_btn_style)
        self.popup_ei_btn.setToolTip("介电常数虚部")
        self.popup_ei_btn.clicked.connect(lambda: self._show_single_chart("epsilon_imag"))
        self.popup_ei_btn.setEnabled(False)
        
        self.popup_tan_btn = QPushButton("tanδ")
        self.popup_tan_btn.setStyleSheet(popup_btn_style)
        self.popup_tan_btn.setToolTip("介电损耗")
        self.popup_tan_btn.clicked.connect(lambda: self._show_single_chart("tan_delta"))
        self.popup_tan_btn.setEnabled(False)
        
        popup_row2.addWidget(self.popup_a_btn)
        popup_row2.addWidget(self.popup_er_btn)
        popup_row2.addWidget(self.popup_ei_btn)
        popup_row2.addWidget(self.popup_tan_btn)
        
        button_layout.addLayout(popup_row2)
        parent_layout.addLayout(button_layout)
    
    def _create_right_panel(self):
        """创建右侧结果显示面板"""
        self.right_panel = QTabWidget()
        self.right_panel.setStyleSheet("""
            QTabWidget {
                background-color: #F0F0F0;
                border: 1px solid #CCCCCC;
                border-radius: 6px;
            }
            QTabWidget::pane {
                border: 1px solid #CCCCCC;
                border-radius: 6px;
                top: -1px;
                background-color: #F0F0F0;
            }
            QTabBar::tab {
                background-color: #E0E0E0;
                border: 1px solid #CCCCCC;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 12px;
                margin-right: 2px;
                color: #333333;
            }
            QTabBar::tab:selected {
                background-color: #F0F0F0;
                border-bottom: 1px solid #F0F0F0;
                color: #4A90E2;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background-color: #DDDDDD;
            }
        """)
        
        # 创建标签页
        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tab3 = QWidget()
        
        # 为每个标签页设置布局
        tab1_layout = QVBoxLayout(self.tab1)
        tab1_layout.setContentsMargins(10, 10, 10, 10)
        
        tab2_layout = QVBoxLayout(self.tab2)
        tab2_layout.setContentsMargins(10, 10, 10, 10)
        
        tab3_layout = QVBoxLayout(self.tab3)
        tab3_layout.setContentsMargins(10, 10, 10, 10)
        
        # 添加标签页
        self.right_panel.addTab(self.tab1, self.chart_icon, "📊 时域和频域信号")
        self.right_panel.addTab(self.tab2, self.data_icon, "📈 光学参数")
        self.right_panel.addTab(self.tab3, self.info_icon, "⚡ 介电特性")
    
    def _update_status(self, message: str, status_type: str = "ready"):
        """更新状态栏"""
        if self.status_bar:
            self.status_bar.set_status(message, status_type)
    
    def _toggle_window_params(self, enabled: bool):
        """切换窗函数参数"""
        if enabled:
            self.window_status_label.setText("开")
            self.window_status_label.setStyleSheet("QLabel { color: #4CAF50; font-weight: bold; padding: 2px 8px; }")
            self.set_signal_window_btn.setEnabled(True)
        else:
            self.window_status_label.setText("关")
            self.window_status_label.setStyleSheet("QLabel { color: #999999; font-weight: bold; padding: 2px 8px; }")
            self.set_signal_window_btn.setEnabled(False)
    
    def _select_ref_file(self):
        """选择参考文件"""
        initial_dir = self.config.get("last_open_dir", "")
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择参考文件", initial_dir,
            "数据文件 (*.xlsx *.xls *.txt);;Excel文件 (*.xlsx *.xls);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if file_path:
            self.ref_file = file_path
            self.config["last_open_dir"] = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            self.ref_file_edit.setText(file_name)
            self._update_status("已选择参考文件", "ready")
            info(f"选择参考文件: {file_path}")
    
    def _add_sam_file(self):
        """添加样品文件"""
        initial_dir = self.config.get("last_open_dir", "")
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择样品文件", initial_dir,
            "数据文件 (*.xlsx *.xls *.txt);;Excel文件 (*.xlsx *.xls);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if file_paths:
            self.config["last_open_dir"] = os.path.dirname(file_paths[0])
            
            for file_path in file_paths:
                self.sam_files.append(file_path)
                file_name = os.path.splitext(os.path.basename(file_path))[0]
                self.sam_names.append(file_name)
                self.sam_files_list.addItem(file_name)
                
                idx = len(self.sam_names) - 1
                self.per_sample_window_params[idx] = None
            
            self._update_status(f"已添加 {len(file_paths)} 个样品文件", "ready")
            info(f"添加 {len(file_paths)} 个样品文件")
    
    def _delete_selected_file(self):
        """删除选中的样品文件"""
        selected_items = self.sam_files_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要删除的样品文件")
            return
        
        for item in selected_items:
            row = self.sam_files_list.row(item)
            self.sam_files_list.takeItem(row)
            del self.sam_files[row]
            del self.sam_names[row]
            
            # 更新窗函数参数索引
            new_params = {}
            for k in list(self.per_sample_window_params.keys()):
                if k < row:
                    new_params[k] = self.per_sample_window_params[k]
                elif k > row:
                    new_params[k - 1] = self.per_sample_window_params[k]
            self.per_sample_window_params = new_params
        
        self._update_status("已删除选中的样品文件", "ready")
    
    def _clear_sam_files(self):
        """清空样品文件列表"""
        self.sam_files = []
        self.sam_names = []
        self.sam_files_list.clear()
        self.per_sample_window_params = {}
        self._update_status("样品文件列表已清空", "ready")
    
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
        quick_group = QGroupBox("快速设置 - 应用到所有样品")
        quick_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #4A90E2;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #F0F7FF;
            }
            QGroupBox::title {
                color: #4A90E2;
            }
        """)
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
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
        """)
        apply_btn.clicked.connect(self._apply_quick_params)
        quick_layout.addWidget(apply_btn)
        
        quick_layout.addStretch()
        main_layout.addWidget(quick_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_btn = QPushButton("确定")
        ok_btn.setStyleSheet("QPushButton { background-color: #28A745; color: white; border-radius: 4px; padding: 8px 20px; }")
        ok_btn.clicked.connect(lambda: self._save_window_params(dialog))
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("QPushButton { background-color: #6C757D; color: white; border-radius: 4px; padding: 8px 20px; }")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        main_layout.addLayout(button_layout)
        
        dialog.exec()
    
    def _create_signal_param_group(self, title: str, key: str, existing_params: dict = None):
        """创建单个信号的参数设置组"""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                margin-top: 6px;
                padding: 8px;
                background-color: #FAFAFA;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px;
                color: #333333;
            }
        """)
        
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
            use_window = self.use_window_checkbox.isChecked()
            self.config["use_window"] = use_window
            
            per_sample_params_list = []
            for i in range(len(self.sam_names)):
                if i in self.per_sample_window_params and self.per_sample_window_params[i] is not None:
                    per_sample_params_list.append(self.per_sample_window_params[i])
                else:
                    per_sample_params_list.append(None)
            
            # 创建计算工作线程
            self.calc_worker = CalculationWorker()
            self.calc_worker.set_parameters(
                ref_file=self.ref_file,
                sam_files=self.sam_files,
                sam_names=self.sam_names,
                thickness=thickness,
                start_row=start_row,
                use_window=use_window,
                ref_window_params=self.ref_window_params,
                per_sample_window_params=per_sample_params_list
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
        """计算完成回调"""
        # 隐藏进度条
        if self.status_bar:
            self.status_bar.show_progress(False)
        
        if result.success:
            self.results_data = result.data
            # 保存图表引用
            self.fig1 = result.fig1
            self.fig2 = result.fig2
            self.fig3 = result.fig3
            self._display_charts(result.fig1, result.fig2, result.fig3)
            self._update_status("计算完成", "success")
            # 启用所有按钮
            self._set_popup_buttons_enabled(True)
            info("计算完成")
        else:
            self._update_status("计算失败", "error")
            self._set_popup_buttons_enabled(False)
    
    def _set_popup_buttons_enabled(self, enabled: bool):
        """设置弹出图表按钮的启用状态"""
        self.save_btn.setEnabled(enabled)
        self.popup_time_btn.setEnabled(enabled)
        self.popup_freq_btn.setEnabled(enabled)
        self.popup_n_btn.setEnabled(enabled)
        self.popup_k_btn.setEnabled(enabled)
        self.popup_a_btn.setEnabled(enabled)
        self.popup_er_btn.setEnabled(enabled)
        self.popup_ei_btn.setEnabled(enabled)
        self.popup_tan_btn.setEnabled(enabled)
    
    def _on_calculation_error(self, error_message: str):
        """计算错误回调"""
        # 隐藏进度条
        if self.status_bar:
            self.status_bar.show_progress(False)
        
        self._update_status("计算失败", "error")
        QMessageBox.critical(self, "计算错误", error_message)
        error(f"计算错误: {error_message}")
    
    def _on_warning_occurred(self, warning_message: str):
        """警告回调"""
        QMessageBox.warning(self, "警告", warning_message)
        warning(warning_message)
    
    def _clear_tabs(self):
        """清除标签页中的图表"""
        for tab in [self.tab1, self.tab2, self.tab3]:
            layout = tab.layout()
            if layout:
                for i in reversed(range(layout.count())):
                    item = layout.itemAt(i)
                    if item:
                        widget = item.widget()
                        if widget:
                            widget.deleteLater()
    
    def _display_charts(self, fig1, fig2, fig3):
        """显示图表"""
        # 显示时域和频域图表
        canvas1 = FigureCanvas(fig1)
        toolbar1 = NavigationToolbar(canvas1, self.tab1)
        self.tab1.layout().addWidget(toolbar1)
        self.tab1.layout().addWidget(canvas1)
        
        # 显示光学参数图表
        canvas2 = FigureCanvas(fig2)
        toolbar2 = NavigationToolbar(canvas2, self.tab2)
        self.tab2.layout().addWidget(toolbar2)
        self.tab2.layout().addWidget(canvas2)
        
        # 显示介电特性图表
        canvas3 = FigureCanvas(fig3)
        toolbar3 = NavigationToolbar(canvas3, self.tab3)
        self.tab3.layout().addWidget(toolbar3)
        self.tab3.layout().addWidget(canvas3)
    
    def _show_single_chart(self, chart_type: str):
        """
        弹出显示单个图表
        
        Args:
            chart_type: 图表类型
        """
        if self.results_data is None:
            QMessageBox.warning(self, "警告", "没有可显示的数据，请先运行分析")
            return
        
        # 关闭已存在的同类型窗口
        if chart_type in self.popup_windows:
            try:
                self.popup_windows[chart_type].close()
            except:
                pass
        
        # 图表配置
        chart_config = {
            'time': {
                'title': '时域信号',
                'xlabel': '延迟 (ps)',
                'ylabel': '振幅',
                'data_key': None,  # 特殊处理
            },
            'freq': {
                'title': '频域信号',
                'xlabel': '频率 (THz)',
                'ylabel': '振幅 (dB)',
                'data_key': None,  # 特殊处理
            },
            'refractive': {
                'title': '折射率',
                'xlabel': '频率 (THz)',
                'ylabel': '折射率 n',
                'data_key': 'Nsam',
            },
            'extinction': {
                'title': '消光系数',
                'xlabel': '频率 (THz)',
                'ylabel': '消光系数 k',
                'data_key': 'Ksam',
            },
            'absorption': {
                'title': '吸收系数',
                'xlabel': '频率 (THz)',
                'ylabel': '吸收系数 (cm⁻¹)',
                'data_key': 'Asam',
            },
            'epsilon_real': {
                'title': '介电常数实部',
                'xlabel': '频率 (THz)',
                'ylabel': "介电常数实部 ε'",
                'data_key': 'Epsilon_real',
            },
            'epsilon_imag': {
                'title': '介电常数虚部',
                'xlabel': '频率 (THz)',
                'ylabel': 'ε"',
                'data_key': 'Epsilon_imag',
            },
            'tan_delta': {
                'title': '介电损耗',
                'xlabel': '频率 (THz)',
                'ylabel': 'tan δ',
                'data_key': 'TanDelta',
            },
        }
        
        if chart_type not in chart_config:
            return
        
        config = chart_config[chart_type]
        
        # 创建新窗口
        popup_window = QMainWindow()
        popup_window.setWindowTitle(config['title'])
        popup_window.setMinimumSize(900, 600)
        
        central_widget = QWidget()
        popup_window.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建图表
        fig = self._create_single_figure(chart_type, config)
        
        if fig is None:
            QMessageBox.warning(self, "警告", f"{config['title']}数据不可用")
            return
        
        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, popup_window)
        
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        
        # 保存窗口引用
        self.popup_windows[chart_type] = popup_window
        popup_window.show()
    
    def _create_single_figure(self, chart_type: str, config: dict):
        """创建单个图表"""
        colors = ['red', 'blue', 'green', 'purple', 'orange', 'brown', 'pink', 'gray', 'olive', 'cyan']
        
        fig = plt.figure(figsize=(10, 6))
        fig.patch.set_facecolor('#F5F5F5')
        
        ax = fig.add_subplot(1, 1, 1)
        ax.set_facecolor('#F8F8F8')
        
        F = self.results_data['F']
        sam_names = self.results_data['sam_names']
        
        # 特殊处理时域和频域信号（需要从fig1中提取）
        if chart_type == 'time':
            # 时域信号需要从原始图表中获取数据
            if self.fig1 is None:
                return None
            # 复制时域子图数据
            try:
                original_ax = self.fig1.axes[0]
                for line in original_ax.get_lines():
                    ax.plot(line.get_xdata(), line.get_ydata(), 
                           color=line.get_color(), 
                           linewidth=line.get_linewidth(),
                           label=line.get_label())
                ax.legend()
                ax.grid(True)
            except:
                return None
                
        elif chart_type == 'freq':
            # 频域信号
            if self.fig1 is None:
                return None
            try:
                original_ax = self.fig1.axes[1]
                for line in original_ax.get_lines():
                    ax.plot(line.get_xdata(), line.get_ydata(), 
                           color=line.get_color(), 
                           linewidth=line.get_linewidth(),
                           label=line.get_label())
                ax.legend()
                ax.grid(True)
                ax.set_xlim(0, 5)
            except:
                return None
        else:
            # 其他图表从results_data中获取
            data_key = config['data_key']
            if data_key not in self.results_data:
                return None
            
            data_list = self.results_data[data_key]
            for i, data in enumerate(data_list):
                ax.plot(F, data, color=colors[i % len(colors)], 
                       linewidth=2.5, label=sam_names[i])
            
            ax.legend(fontsize=10)
            ax.grid(True, alpha=0.3)
            ax.set_xlim(0, 5)
            ax.autoscale(axis='y')
        
        ax.set_xlabel(config['xlabel'], fontsize=12)
        ax.set_ylabel(config['ylabel'], fontsize=12)
        ax.set_title(config['title'], fontsize=14, fontweight='bold')
        
        fig.tight_layout()
        return fig
    
    def _save_results(self):
        """保存计算结果"""
        if self.results_data is None:
            QMessageBox.warning(self, "警告", "没有可保存的计算结果，请先运行分析")
            return
        
        # 检查是否正在保存
        if self.save_worker is not None and self.save_worker.isRunning():
            QMessageBox.warning(self, "警告", "正在保存中，请稍候...")
            return
        
        initial_dir = self.config.get("last_save_dir", "")
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存结果", initial_dir,
            "Excel文件 (*.xlsx);;所有文件 (*.*)"
        )
        
        if file_path:
            if not file_path.lower().endswith('.xlsx'):
                file_path += '.xlsx'
            
            self.config["last_save_dir"] = os.path.dirname(file_path)
            
            # 显示进度条
            self._update_status("正在保存结果...", "working")
            if self.status_bar:
                self.status_bar.show_progress(True)
            
            # 禁用保存按钮防止重复点击
            self.save_btn.setEnabled(False)
            
            # 创建保存工作线程
            self.save_worker = SaveWorker()
            self.save_worker.set_parameters(self.results_data, file_path)
            
            # 连接信号
            self.save_worker.progress_updated.connect(self._on_save_progress)
            self.save_worker.save_finished.connect(self._on_save_finished)
            self.save_worker.save_error.connect(self._on_save_error)
            
            # 启动保存
            self.save_worker.start()
            info("开始异步保存Excel")
    
    def _on_save_progress(self, current: int, total: int, message: str):
        """保存进度更新回调"""
        if self.status_bar:
            self.status_bar.update_progress(current, total, message)
    
    def _on_save_finished(self, file_path: str):
        """保存完成回调"""
        if self.status_bar:
            self.status_bar.show_progress(False)
        
        self.save_btn.setEnabled(True)
        self._update_status(f"结果已保存到: {os.path.basename(file_path)}", "success")
        QMessageBox.information(self, "保存成功", f"计算结果已保存到:\n{file_path}")
        info(f"结果已保存到: {file_path}")
    
    def _on_save_error(self, error_message: str):
        """保存错误回调"""
        if self.status_bar:
            self.status_bar.show_progress(False)
        
        self.save_btn.setEnabled(True)
        self._update_status("保存失败", "error")
        QMessageBox.critical(self, "保存错误", error_message)
        error(f"保存失败: {error_message}")
    
    def _show_help_dialog(self):
        """显示帮助对话框"""
        dialog = HelpDialog(self)
        dialog.exec()
    
    def _show_about_dialog(self):
        """显示关于对话框"""
        dialog = AboutDialog(self)
        dialog.exec()
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        """拖放事件"""
        urls = event.mimeData().urls()
        pos = event.position().toPoint()
        
        sam_files_rect = self.sam_files_list.geometry()
        sam_files_global_pos = self.sam_files_list.mapTo(self, QPoint(0, 0))
        sam_files_area = QRect(sam_files_global_pos, sam_files_rect.size())
        
        ref_edit_rect = self.ref_file_edit.geometry()
        ref_edit_global_pos = self.ref_file_edit.mapTo(self, QPoint(0, 0))
        ref_edit_area = QRect(ref_edit_global_pos, ref_edit_rect.size())
        
        if ref_edit_area.contains(pos):
            if urls:
                file_path = urls[0].toLocalFile()
                if os.path.isfile(file_path) and file_path.lower().endswith(('.xlsx', '.xls', '.txt')):
                    self.ref_file = file_path
                    self.ref_file_edit.setText(os.path.basename(file_path))
                    self._update_status("已选择参考文件", "ready")
        else:
            for url in urls:
                file_path = url.toLocalFile()
                if os.path.isfile(file_path) and file_path.lower().endswith(('.xlsx', '.xls', '.txt')):
                    self.sam_files.append(file_path)
                    file_name = os.path.splitext(os.path.basename(file_path))[0]
                    self.sam_names.append(file_name)
                    self.sam_files_list.addItem(file_name)
            
            if urls:
                self._update_status(f"已添加 {len(urls)} 个样品文件", "ready")
    
    def _on_closing(self, event):
        """窗口关闭事件"""
        try:
            # 关闭所有弹出窗口
            for window in self.popup_windows.values():
                try:
                    window.close()
                except:
                    pass
            
            # 清理状态栏资源
            if self.status_bar:
                self.status_bar.cleanup()
            
            save_config(self.config)
            plt.close('all')
            info("程序关闭")
            event.accept()
        except Exception as e:
            error(f"关闭程序时出错: {e}")
            event.accept()
