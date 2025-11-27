import os
import math
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QLineEdit, QPushButton, QFileDialog, QGroupBox, 
                            QMessageBox, QTabWidget, QCheckBox, QGridLayout,
                            QListWidget, QSplitter, QFrame, QComboBox, QGraphicsOpacityEffect, QScrollArea, QStyle)
from PyQt6.QtCore import Qt, QPoint, QRect, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QAction, QFont, QPalette, QColor, QPainter, QLinearGradient, QBrush

from config import load_config, save_config, update_thickness_history
from core import calculate_optical_params, save_results_to_excel
from utils.icon_helper import IconHelper


class AnimatedBackgroundWidget(QWidget):
    """动态背景组件，显示浅蓝色到浅紫色的渐变动画效果"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_angle)
        self.timer.start(50)  # 50ms更新一次
        
    def update_angle(self):
        """更新角度并重绘"""
        self.angle = (self.angle + 2) % 360
        self.update()
        
    def paintEvent(self, event):
        """绘制渐变背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 创建线性渐变
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        
        # 定义基础颜色
        base_color1 = QColor(173, 216, 230)  # 浅蓝色
        base_color2 = QColor(216, 191, 216)  # 浅紫色
        base_color3 = QColor(230, 230, 250)  # 淡紫色
        
        # 根据角度调整颜色
        angle_rad = self.angle * 3.14159 / 180
        r1 = int(173 + 50 * (1 + math.sin(angle_rad)) / 2)
        g1 = int(216 + 30 * (1 + math.sin(angle_rad + 2.094)) / 2)
        b1 = int(230 + 20 * (1 + math.sin(angle_rad + 4.188)) / 2)
        
        r2 = int(216 + 30 * (1 + math.sin(angle_rad + 1.047)) / 2)
        g2 = int(191 + 40 * (1 + math.sin(angle_rad + 3.141)) / 2)
        b2 = int(216 + 30 * (1 + math.sin(angle_rad + 5.235)) / 2)
        
        r3 = int(230 + 20 * (1 + math.sin(angle_rad + 2.094)) / 2)
        g3 = int(230 + 20 * (1 + math.sin(angle_rad + 4.188)) / 2)
        b3 = int(250 + 5 * (1 + math.sin(angle_rad + 0)) / 2)
        
        color1 = QColor(r1, g1, b1)
        color2 = QColor(r2, g2, b2)
        color3 = QColor(r3, g3, b3)
        
        # 设置渐变色
        gradient.setColorAt(0, color1)
        gradient.setColorAt(0.5, color2)
        gradient.setColorAt(1, color3)
        
        # 绘制
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())


class AnimatedButton(QPushButton):
    """带动画效果的按钮"""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._opacity = 1.0
        self.setup_animations()
    
    def setup_animations(self):
        """设置动画效果"""
        # 透明度动画
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
    
    def enterEvent(self, event):
        """鼠标进入事件"""
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.8)
        self.fade_animation.start()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开事件"""
        self.fade_animation.setStartValue(0.8)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()
        super().leaveEvent(event)


class THzAnalyzerApp(QMainWindow):
    """THz光学参数分析系统的主应用程序类"""
    
    def __init__(self):
        super().__init__()
        
        # 加载配置
        self.config = load_config()
        
        # 存储选中的文件
        self.ref_file = ""
        self.sam_files = []
        self.sam_names = []
        
        # 存储参考信号的窗函数参数
        self.ref_window_params = None  # None表示未设置，使用默认值
        
        # 存储每个样品的窗函数参数
        self.per_sample_window_params = {}  # key: 样品索引或名称, value: 窗函数参数字典
        
        # 存储计算结果
        self.results_data = None
        
        # 存储吸收系数弹出窗口的引用
        self.absorption_window = None
        
        # 设置窗口
        self.setWindowTitle("THz 时域光谱分析系统")
        self.setMinimumSize(1200, 800)
        
        # 创建图标
        self.create_icons()
        
        # 创建界面
        self.init_ui()
        
        # 绑定窗口关闭事件，保存配置
        self.closeEvent = self.on_closing

        self.start_row = self.config.get("start_row", 1)

    def create_icons(self):
        """创建应用程序使用的图标"""
        # 使用QApplication的内置图标风格
        style = QApplication.style()
        
        # 文件相关图标 - 使用自定义图标
        self.folder_icon = IconHelper.create_file_icon("#4A90E2", 16)
        self.file_icon = style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        self.add_icon = IconHelper.create_text_icon("+", "#FFFFFF", "#28A745", 16)
        self.delete_icon = IconHelper.create_text_icon("-", "#FFFFFF", "#DC3545", 16)
        self.clear_icon = IconHelper.create_text_icon("×", "#FFFFFF", "#6C757D", 16)
        
        # 操作相关图标 - 使用自定义图标
        self.run_icon = IconHelper.create_arrow_icon("right", "#FFFFFF", 18)
        self.save_icon = IconHelper.create_file_icon("#17A2B8", 18)
        self.settings_icon = style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        
        # 标签页图标 - 使用自定义图标
        self.chart_icon = IconHelper.create_chart_icon("#28A745", 16)
        self.data_icon = IconHelper.create_text_icon("D", "#FFFFFF", "#007BFF", 16)
        self.info_icon = IconHelper.create_text_icon("i", "#FFFFFF", "#6F42C1", 16)
        
        # 状态图标 - 使用自定义图标
        self.ready_icon = IconHelper.create_colored_icon("#28A745", 16)
        self.working_icon = IconHelper.create_colored_icon("#FFC107", 16)
        self.error_icon = IconHelper.create_colored_icon("#DC3545", 16)
        
        # 参数图标 - 使用自定义图标
        self.thickness_icon = IconHelper.create_text_icon("T", "#FFFFFF", "#6C757D", 16)
        self.row_icon = IconHelper.create_text_icon("R", "#FFFFFF", "#6C757D", 16)
        
        # 窗口图标
        self.window_icon = style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.setWindowIcon(self.window_icon)

    def init_ui(self):
        """初始化用户界面"""
        # 设置应用程序样式
        self.setup_styles()
        
        # 创建菜单栏
        self._create_menu_bar()
        
        # 创建中央窗口部件
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #F5F5F5;")  # 浅灰色背景
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)
        main_layout.addWidget(splitter)
        
        # 创建左右面板
        self._create_left_panel()
        self._create_right_panel()
        
        # 添加左右面板到分割器
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        
        # 设置分割器初始大小
        splitter.setSizes([300, 900])
        
        # 设置拖放支持
        self.setAcceptDrops(True)
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #F8F8F8;
                color: #333333;
                border-bottom: 1px solid #CCCCCC;
            }
            QMenuBar::item {
                padding: 5px 10px;
                background-color: transparent;
            }
            QMenuBar::item:selected {
                background-color: #E0E0E0;
            }
            QMenu {
                background-color: #FFFFFF;
                color: #333333;
                border: 1px solid #CCCCCC;
            }
            QMenu::item {
                padding: 5px 30px 5px 20px;
            }
            QMenu::item:selected {
                background-color: #E0E0E0;
            }
        """)
        
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
        user_guide_action.triggered.connect(self.show_help_dialog)
        help_menu.addAction(user_guide_action)
        
        about_action = QAction("ℹ️ 关于", self)
        about_action.triggered.connect(self.show_about_dialog)
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
        
        # 状态标签
        self.status_label = QLabel()
        self.status_label.setAccessibleName("status")  # 为样式表识别添加标识
        self.status_label.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Sunken)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setStyleSheet("""
            background-color: #F0F0F0; 
            padding: 8px; 
            border-radius: 4px; 
            border: 1px solid #CCCCCC;
            color: #333333;
        """)
        self.update_status("就绪", "ready")
        left_layout.addWidget(self.status_label)
        
        # 参数设置区
        param_group = self._create_param_group()
        left_layout.addWidget(param_group)
        left_layout.addStretch()
        
        # 版权信息
        version_label = QLabel("By NUAA THz Group v4.5.1")
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
        ref_btn.clicked.connect(self.select_ref_file)
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
        add_sam_btn.clicked.connect(self.add_sam_file)
        
        del_sam_btn = AnimatedButton("  删除选中")
        del_sam_btn.setIcon(self.delete_icon)
        del_sam_btn.setIconSize(QSize(16, 16))
        del_sam_btn.setStyleSheet(sam_btn_style)
        del_sam_btn.clicked.connect(self.delete_selected_file)
        
        clear_sam_btn = AnimatedButton("  清空列表")
        clear_sam_btn.setIcon(self.clear_icon)
        clear_sam_btn.setIconSize(QSize(16, 16))
        clear_sam_btn.setStyleSheet(sam_btn_style)
        clear_sam_btn.clicked.connect(self.clear_sam_files)
        
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
        
        # 添加开关样式的按钮
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
            QCheckBox::indicator:hover {
                border: 2px solid #666666;
            }
            QCheckBox::indicator:checked:hover {
                border: 2px solid #3d8b40;
            }
        """)
        switch_layout.addWidget(self.use_window_checkbox)
        
        # 状态标签
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
        
        # 设置每个信号的窗函数参数按钮
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
            QPushButton:pressed {
                background-color: #2E5FA3;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        self.set_signal_window_btn.clicked.connect(self.open_signal_window_dialog)
        self.set_signal_window_btn.setEnabled(False)  # 初始状态禁用
        signal_window_button_layout.addWidget(self.set_signal_window_btn)
        signal_window_button_layout.addStretch()
        
        tukey_layout.addLayout(signal_window_button_layout)
        
        # 参数设置状态指示标签
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
        self.window_params_indicator.setVisible(False)  # 初始时隐藏
        tukey_layout.addWidget(self.window_params_indicator)
        
        parent_layout.addWidget(tukey_group)
        
        # 所有窗函数组件创建完成后,连接信号并设置初始状态
        self.use_window_checkbox.toggled.connect(self.toggle_window_params)
        # 初始状态设为不开启
        self.use_window_checkbox.setChecked(False)
        
        # 样品厚度设置
        thickness_layout = QHBoxLayout()
        
        # 创建带图标的标签布局
        thickness_label_layout = QHBoxLayout()
        thickness_icon_label = QLabel()
        thickness_icon_label.setPixmap(self.thickness_icon.pixmap(16, 16))
        thickness_label = QLabel("样品厚度 (mm):")
        thickness_label.setStyleSheet("font-weight: bold; color: #333333;")
        
        thickness_label_layout.addWidget(thickness_icon_label)
        thickness_label_layout.addWidget(thickness_label)
        thickness_label_layout.addStretch()
        thickness_label_layout.setSpacing(5)
        
        # 创建一个容器widget来包含图标和标签
        thickness_label_widget = QWidget()
        thickness_label_widget.setLayout(thickness_label_layout)
        
        thickness_layout.addWidget(thickness_label_widget)
        
        self.thickness_combo = QComboBox()
        self.thickness_combo.setEditable(True)
        # 设置组合框样式
        self.thickness_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: #FFFFFF;
                color: #333333;
            }
            QComboBox::drop-down {
                border: none;
                background-color: #F0F0F0;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 12px;
                height: 12px;
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
        
        # 创建带图标的标签布局
        start_row_label_layout = QHBoxLayout()
        start_row_icon_label = QLabel()
        start_row_icon_label.setPixmap(self.row_icon.pixmap(16, 16))
        start_row_label = QLabel("数据起始行:")
        start_row_label.setStyleSheet("font-weight: bold; color: #333333;")
        
        start_row_label_layout.addWidget(start_row_icon_label)
        start_row_label_layout.addWidget(start_row_label)
        start_row_label_layout.addStretch()
        start_row_label_layout.setSpacing(5)
        
        # 创建一个容器widget来包含图标和标签
        start_row_label_widget = QWidget()
        start_row_label_widget.setLayout(start_row_label_layout)
        
        start_row_layout.addWidget(start_row_label_widget)
        
        self.start_row_combo = QComboBox()
        self.start_row_combo.addItems(["1", "2", "3"])
        self.start_row_combo.setEditable(True)
        # 设置组合框样式
        self.start_row_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: #FFFFFF;
                color: #333333;
            }
            QComboBox::drop-down {
                border: none;
                background-color: #F0F0F0;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 12px;
                height: 12px;
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
        run_btn.clicked.connect(self.run_analysis)
        
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
            QPushButton:pressed {
                background-color: #0A58CA;
            }
            QPushButton:disabled {
                background-color: #EEEEEE;
                color: #999999;
            }
        """)
        self.save_btn.clicked.connect(self.save_results)
        self.save_btn.setEnabled(False)
        
        first_row_layout.addWidget(run_btn)
        first_row_layout.addWidget(self.save_btn)
        
        # 第二行按钮
        second_row_layout = QHBoxLayout()
        
        self.show_absorption_btn = AnimatedButton("  弹出吸收系数图")
        self.show_absorption_btn.setIcon(self.chart_icon)
        self.show_absorption_btn.setIconSize(QSize(18, 18))
        self.show_absorption_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                background-color: #6F42C1;
                color: white;
                border-radius: 4px;
                border: none;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #5A32A3;
            }
            QPushButton:pressed {
                background-color: #4A2890;
            }
            QPushButton:disabled {
                background-color: #EEEEEE;
                color: #999999;
            }
        """)
        self.show_absorption_btn.clicked.connect(self.show_absorption_plot)
        self.show_absorption_btn.setEnabled(False)
        
        second_row_layout.addWidget(self.show_absorption_btn)
        
        button_layout.addLayout(first_row_layout)
        button_layout.addLayout(second_row_layout)
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
            QTabBar::tab:!selected {
                margin-top: 2px;
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
        
        # 添加标签页到标签控件
        self.right_panel.addTab(self.tab1, self.chart_icon, "📊 时域和频域信号")
        self.right_panel.addTab(self.tab2, self.data_icon, "📈 光学参数")
        self.right_panel.addTab(self.tab3, self.info_icon, "⚡ 介电特性")
    
    def setup_styles(self):
        """设置全局样式"""
        # 设置应用程序图标和标题
        self.setWindowTitle("THz 时域光谱分析系统")
        
        # 设置亮色主题窗口背景色
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#FFFFFF"))        # 白色主窗口背景
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#444444"))    # 深灰色主窗口文字
        palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))          # 白色输入框背景
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F8F8F8"))  # 浅灰色交替背景
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#FFFFCC"))   # 浅黄色工具提示背景
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#444444"))   # 深灰色工具提示文字
        palette.setColor(QPalette.ColorRole.Text, QColor("#444444"))          # 深灰色文本颜色
        palette.setColor(QPalette.ColorRole.Button, QColor("#F8F8F8"))        # 浅灰色按钮背景
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#444444"))    # 深灰色按钮文字
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#5C6BC0"))     # 紫蓝色高亮背景
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF")) # 白色高亮文字
        self.setPalette(palette)
        
        # 设置全局字体
        app_font = QFont("微软雅黑", 9)
        QApplication.setFont(app_font)
        
        # 设置全局样式表
        self.setStyleSheet("""
            /* 主窗口样式 */
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:0.5 #F8F8F8, stop:1 #FFFFFF);
            }
            
            /* 组合框样式 */
            QComboBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F0F0F0);
                border: 2px solid #CCCCCC;
                border-radius: 6px;
                padding: 6px;
                color: #333333;
                min-width: 6em;
                font-weight: 500;
            }
            QComboBox:focus {
                border: 2px solid #4A90E2;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F8F8F8);
            }
            QComboBox:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F8F8F8);
                border: 2px solid #999999;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left-width: 2px;
                border-left-color: #CCCCCC;
                border-left-style: solid;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #F0F0F0, stop:1 #E0E0E0);
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #333333;
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F0F0F0);
                border: 2px solid #CCCCCC;
                color: #333333;
                selection-background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4A90E2, stop:1 #3A80D2);
                selection-color: #FFFFFF;
                border-radius: 4px;
            }
            
            /* 分组框样式 */
            QGroupBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.9), stop:1 rgba(240, 240, 240, 0.9));
                border: 2px solid #CCCCCC;
                border-radius: 8px;
                margin-top: 1ex;
                font-weight: bold;
                color: #333333;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #4A90E2;
                font-size: 11px;
            }
            
            /* 列表控件样式 */
            QListWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F8F8F8);
                border: 2px solid #CCCCCC;
                border-radius: 6px;
                color: #333333;
                selection-background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4A90E2, stop:1 #3A80D2);
                alternate-background-color: #F0F0F0;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #EEEEEE;
            }
            QListWidget::item:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #F8F8F8, stop:1 #EEEEEE);
            }
            
            /* 输入框样式 */
            QLineEdit {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F8F8F8);
                border: 2px solid #CCCCCC;
                border-radius: 6px;
                padding: 6px;
                color: #333333;
                font-size: 10px;
            }
            QLineEdit:focus {
                border: 2px solid #4A90E2;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F0F0F0);
            }
            
            /* 标签页样式 */
            QTabWidget {
                background: transparent;
            }
            QTabWidget::pane {
                border: 2px solid #CCCCCC;
                border-radius: 6px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.9), stop:1 rgba(248, 248, 248, 0.9));
            }
            QTabBar::tab {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #F0F0F0, stop:1 #E0E0E0);
                border: 2px solid #CCCCCC;
                border-bottom: none;
                border-radius: 6px 6px 0 0;
                padding: 8px 16px;
                margin-right: 2px;
                color: #666666;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4A90E2, stop:1 #3A80D2);
                color: #FFFFFF;
                border-color: #4A90E2;
            }
            QTabBar::tab:hover:!selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #F8F8F8, stop:1 #F0F0F0);
                color: #333333;
            }
            
            /* 分割器样式 */
            QSplitter::handle {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #CCCCCC, stop:0.5 #DDDDDD, stop:1 #CCCCCC);
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4A90E2, stop:0.5 #5A9AE2, stop:1 #4A90E2);
            }
            
            /* 状态标签样式 */
            QLabel[accessibleName="status"] {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.9), stop:1 rgba(240, 240, 240, 0.9));
                border: 2px solid #CCCCCC;
                border-radius: 6px;
                padding: 8px;
                color: #333333;
            }
        """)
    
    def toggle_window_params(self, enabled):
        """切换窗函数参数输入框的启用状态"""
        # 更新状态标签
        if enabled:
            self.window_status_label.setText("开")
            self.window_status_label.setStyleSheet("""
                QLabel {
                    color: #4CAF50;
                    font-weight: bold;
                    padding: 2px 8px;
                }
            """)
            self.set_signal_window_btn.setEnabled(True)
        else:
            self.window_status_label.setText("关")
            self.window_status_label.setStyleSheet("""
                QLabel {
                    color: #999999;
                    font-weight: bold;
                    padding: 2px 8px;
                }
            """)
            self.set_signal_window_btn.setEnabled(False)
    
    def _update_window_params_indicator(self):
        """更新窗函数参数设置状态指示"""
        # 检查是否有任何信号设置了自定义参数
        has_custom_params = False
        
        # 检查参考信号
        if self.ref_window_params is not None:
            has_custom_params = True
        
        # 检查样品信号
        if not has_custom_params:
            for idx, params in self.per_sample_window_params.items():
                if params is not None:
                    has_custom_params = True
                    break
        
        # 更新指示标签的显示
        if has_custom_params:
            self.window_params_indicator.setText("✓ 参数已设置")
            self.window_params_indicator.setStyleSheet("""
                QLabel {
                    color: #28A745;
                    font-weight: bold;
                    padding: 5px;
                    background-color: #E8F5E9;
                    border-radius: 4px;
                }
            """)
            self.window_params_indicator.setVisible(True)
        else:
            self.window_params_indicator.setVisible(False)
    
    def open_signal_window_dialog(self):
        """打开每个信号（包括参考和样品）的窗函数参数设置对话框"""
        if not self.ref_file and not self.sam_names:
            QMessageBox.warning(self, "警告", "请先选择参考文件或添加样品文件")
            return
        
        # 创建对话框
        dialog = QMainWindow()
        dialog.setWindowTitle("Tukey窗函数参数设置")
        dialog.setMinimumSize(900, 750)
        
        central_widget = QWidget()
        dialog.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 顶部工具栏 - 快速设置区域
        toolbar_group = QGroupBox("🚀 快速设置")
        toolbar_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #4A90E2;
                border-radius: 6px;
                margin-top: 10px;
                padding: 15px;
                background-color: #E8F4FD;
                font-weight: bold;
                font-size: 11pt;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: #4A90E2;
            }
        """)
        toolbar_layout = QVBoxLayout(toolbar_group)
        
        # 参考信号快速设置
        ref_quick_group = QGroupBox("📍 参考信号参数")
        ref_quick_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #28A745;
                border-radius: 4px;
                margin-top: 8px;
                padding: 10px;
                background-color: #F0F8F4;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #28A745;
            }
        """)
        ref_quick_layout = QHBoxLayout(ref_quick_group)
        
        # 参考信号 - 起始时间
        ref_quick_layout.addWidget(QLabel("起始时间:"))
        self.quick_ref_t_start = QLineEdit("0.0")
        self.quick_ref_t_start.setFixedWidth(70)
        self.quick_ref_t_start.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 2px solid #CCCCCC;
                border-radius: 4px;
                background-color: #FFFFFF;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 2px solid #28A745;
            }
        """)
        ref_quick_layout.addWidget(self.quick_ref_t_start)
        ref_quick_layout.addWidget(QLabel("ps"))
        
        ref_quick_layout.addSpacing(10)
        
        # 参考信号 - 结束时间
        ref_quick_layout.addWidget(QLabel("结束时间:"))
        self.quick_ref_t_end = QLineEdit("30.0")
        self.quick_ref_t_end.setFixedWidth(70)
        self.quick_ref_t_end.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 2px solid #CCCCCC;
                border-radius: 4px;
                background-color: #FFFFFF;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 2px solid #28A745;
            }
        """)
        ref_quick_layout.addWidget(self.quick_ref_t_end)
        ref_quick_layout.addWidget(QLabel("ps"))
        
        ref_quick_layout.addSpacing(10)
        
        # 参考信号 - alpha参数
        ref_quick_layout.addWidget(QLabel("α参数:"))
        self.quick_ref_alpha = QLineEdit("0.5")
        self.quick_ref_alpha.setFixedWidth(70)
        self.quick_ref_alpha.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 2px solid #CCCCCC;
                border-radius: 4px;
                background-color: #FFFFFF;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 2px solid #28A745;
            }
        """)
        ref_quick_layout.addWidget(self.quick_ref_alpha)
        
        ref_quick_layout.addSpacing(15)
        
        # 参考信号应用按钮
        apply_ref_btn = AnimatedButton("  应用")
        apply_ref_btn.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                border-radius: 4px;
                padding: 6px 16px;
                border: none;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        apply_ref_btn.clicked.connect(self._apply_quick_params_to_ref)
        ref_quick_layout.addWidget(apply_ref_btn)
        
        ref_quick_layout.addStretch()
        
        toolbar_layout.addWidget(ref_quick_group)
        
        # 样品信号快速设置
        sam_quick_group = QGroupBox("📦 样品信号参数（应用到所有样品）")
        sam_quick_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #007BFF;
                border-radius: 4px;
                margin-top: 8px;
                padding: 10px;
                background-color: #E8F4FD;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #007BFF;
            }
        """)
        sam_quick_layout = QHBoxLayout(sam_quick_group)
        
        # 样品信号 - 起始时间
        sam_quick_layout.addWidget(QLabel("起始时间:"))
        self.quick_sam_t_start = QLineEdit("0.0")
        self.quick_sam_t_start.setFixedWidth(70)
        self.quick_sam_t_start.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 2px solid #CCCCCC;
                border-radius: 4px;
                background-color: #FFFFFF;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 2px solid #007BFF;
            }
        """)
        sam_quick_layout.addWidget(self.quick_sam_t_start)
        sam_quick_layout.addWidget(QLabel("ps"))
        
        sam_quick_layout.addSpacing(10)
        
        # 样品信号 - 结束时间
        sam_quick_layout.addWidget(QLabel("结束时间:"))
        self.quick_sam_t_end = QLineEdit("30.0")
        self.quick_sam_t_end.setFixedWidth(70)
        self.quick_sam_t_end.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 2px solid #CCCCCC;
                border-radius: 4px;
                background-color: #FFFFFF;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 2px solid #007BFF;
            }
        """)
        sam_quick_layout.addWidget(self.quick_sam_t_end)
        sam_quick_layout.addWidget(QLabel("ps"))
        
        sam_quick_layout.addSpacing(10)
        
        # 样品信号 - alpha参数
        sam_quick_layout.addWidget(QLabel("α参数:"))
        self.quick_sam_alpha = QLineEdit("0.5")
        self.quick_sam_alpha.setFixedWidth(70)
        self.quick_sam_alpha.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 2px solid #CCCCCC;
                border-radius: 4px;
                background-color: #FFFFFF;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 2px solid #007BFF;
            }
        """)
        sam_quick_layout.addWidget(self.quick_sam_alpha)
        
        sam_quick_layout.addSpacing(15)
        
        # 样品信号应用按钮
        apply_sam_btn = AnimatedButton("  应用到所有样品")
        apply_sam_btn.setStyleSheet("""
            QPushButton {
                background-color: #007BFF;
                color: white;
                border-radius: 4px;
                padding: 6px 16px;
                border: none;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #0056B3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        apply_sam_btn.clicked.connect(self._apply_quick_params_to_samples)
        sam_quick_layout.addWidget(apply_sam_btn)
        
        sam_quick_layout.addStretch()
        
        toolbar_layout.addWidget(sam_quick_group)
        
        layout.addWidget(toolbar_group)
        
        # 添加说明标签
        info_label = QLabel("💡 提示：使用上方快速设置可分别为参考信号和样品信号一键应用参数，也可在下方单独调整")
        info_label.setStyleSheet("color: #666666; margin: 5px 0; font-style: italic;")
        layout.addWidget(info_label)
        
        # 创建滚动区域 - 单独设置
        scroll_area = QWidget()
        scroll_layout = QVBoxLayout(scroll_area)
        
        # 为每个信号创建参数输入框
        self.signal_window_inputs = {}
        
        # 首先添加参考信号
        if self.ref_file:
            ref_name = os.path.splitext(os.path.basename(self.ref_file))[0]
            
            # 创建参考信号框
            ref_group = QGroupBox(f"📍 参考信号: {ref_name}")
            ref_group.setStyleSheet("""
                QGroupBox {
                    border: 2px solid #28A745;
                    border-radius: 4px;
                    margin-top: 8px;
                    padding-top: 8px;
                    background-color: #F0F8F4;
                    font-weight: bold;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #28A745;
                }
            """)
            ref_layout = QGridLayout(ref_group)
            
            # 起始时间
            ref_layout.addWidget(QLabel("起始时间 (ps):"), 0, 0)
            t_start_input = QLineEdit()
            t_start_input.setStyleSheet("""
                QLineEdit {
                    padding: 5px;
                    border: 1px solid #CCCCCC;
                    border-radius: 4px;
                    background-color: #FFFFFF;
                    color: #333333;
                }
            """)
            if self.ref_window_params is not None:
                t_start_input.setText(str(self.ref_window_params.get('t_start', 0.0)))
            else:
                t_start_input.setText("0.0")
            ref_layout.addWidget(t_start_input, 0, 1)
            
            # 结束时间
            ref_layout.addWidget(QLabel("结束时间 (ps):"), 0, 2)
            t_end_input = QLineEdit()
            t_end_input.setStyleSheet("""
                QLineEdit {
                    padding: 5px;
                    border: 1px solid #CCCCCC;
                    border-radius: 4px;
                    background-color: #FFFFFF;
                    color: #333333;
                }
            """)
            if self.ref_window_params is not None:
                t_end_input.setText(str(self.ref_window_params.get('t_end', 30.0)))
            else:
                t_end_input.setText("30.0")
            ref_layout.addWidget(t_end_input, 0, 3)
            
            # alpha参数
            ref_layout.addWidget(QLabel("α参数 (0-1):"), 1, 0)
            alpha_input = QLineEdit()
            alpha_input.setStyleSheet("""
                QLineEdit {
                    padding: 5px;
                    border: 1px solid #CCCCCC;
                    border-radius: 4px;
                    background-color: #FFFFFF;
                    color: #333333;
                }
            """)
            if self.ref_window_params is not None:
                alpha_input.setText(str(self.ref_window_params.get('alpha', 0.5)))
            else:
                alpha_input.setText("0.5")
            ref_layout.addWidget(alpha_input, 1, 1)
            
            # 存储输入框引用 - 使用特殊键"ref"表示参考信号
            self.signal_window_inputs['ref'] = {
                't_start': t_start_input,
                't_end': t_end_input,
                'alpha': alpha_input
            }
            
            scroll_layout.addWidget(ref_group)
        
        # 然后添加样品
        for i, sam_name in enumerate(self.sam_names):
            # 创建样品框
            sample_group = QGroupBox(f"📦 样品 {i+1}: {sam_name}")
            sample_group.setStyleSheet("""
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
            sample_layout = QGridLayout(sample_group)
            
            # 起始时间
            sample_layout.addWidget(QLabel("起始时间 (ps):"), 0, 0)
            t_start_input = QLineEdit()
            t_start_input.setStyleSheet("""
                QLineEdit {
                    padding: 5px;
                    border: 1px solid #CCCCCC;
                    border-radius: 4px;
                    background-color: #FFFFFF;
                    color: #333333;
                }
            """)
            if i in self.per_sample_window_params and self.per_sample_window_params[i] is not None:
                t_start_input.setText(str(self.per_sample_window_params[i].get('t_start', 0.0)))
            else:
                t_start_input.setText("0.0")
            sample_layout.addWidget(t_start_input, 0, 1)
            
            # 结束时间
            sample_layout.addWidget(QLabel("结束时间 (ps):"), 0, 2)
            t_end_input = QLineEdit()
            t_end_input.setStyleSheet("""
                QLineEdit {
                    padding: 5px;
                    border: 1px solid #CCCCCC;
                    border-radius: 4px;
                    background-color: #FFFFFF;
                    color: #333333;
                }
            """)
            if i in self.per_sample_window_params and self.per_sample_window_params[i] is not None:
                t_end_input.setText(str(self.per_sample_window_params[i].get('t_end', 30.0)))
            else:
                t_end_input.setText("30.0")
            sample_layout.addWidget(t_end_input, 0, 3)
            
            # alpha参数
            sample_layout.addWidget(QLabel("α参数 (0-1):"), 1, 0)
            alpha_input = QLineEdit()
            alpha_input.setStyleSheet("""
                QLineEdit {
                    padding: 5px;
                    border: 1px solid #CCCCCC;
                    border-radius: 4px;
                    background-color: #FFFFFF;
                    color: #333333;
                }
            """)
            if i in self.per_sample_window_params and self.per_sample_window_params[i] is not None:
                alpha_input.setText(str(self.per_sample_window_params[i].get('alpha', 0.5)))
            else:
                alpha_input.setText("0.5")
            sample_layout.addWidget(alpha_input, 1, 1)
            
            # 存储输入框引用
            self.signal_window_inputs[i] = {
                't_start': t_start_input,
                't_end': t_end_input,
                'alpha': alpha_input
            }
            
            scroll_layout.addWidget(sample_group)
        
        scroll_layout.addStretch()
        
        # 创建QScrollArea并放入
        scroll_area_outer = QScrollArea()
        scroll_area_outer.setWidget(scroll_area)
        scroll_area_outer.setWidgetResizable(True)
        scroll_area_outer.setStyleSheet("""
            QScrollArea {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: #FAFAFA;
            }
        """)
        layout.addWidget(scroll_area_outer)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        reset_btn = AnimatedButton("  重置全部")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFC107;
                color: #333333;
                border-radius: 4px;
                padding: 8px 16px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FFB300;
            }
        """)
        reset_btn.clicked.connect(self._reset_all_params)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        confirm_btn = AnimatedButton("  确定")
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                border-radius: 4px;
                padding: 8px 20px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        confirm_btn.clicked.connect(lambda: self._save_signal_window_params(dialog))
        button_layout.addWidget(confirm_btn)
        
        cancel_btn = AnimatedButton("  取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6C757D;
                color: white;
                border-radius: 4px;
                padding: 8px 20px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        cancel_btn.clicked.connect(dialog.close)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        dialog.show()
    
    def _save_signal_window_params(self, dialog):
        """保存每个信号（参考+样品）的窗函数参数"""
        try:
            for key, inputs in self.signal_window_inputs.items():
                t_start = float(inputs['t_start'].text())
                t_end = float(inputs['t_end'].text())
                alpha = float(inputs['alpha'].text())
                
                # 验证参数
                if alpha < 0 or alpha > 1:
                    if key == 'ref':
                        raise ValueError("参考信号的α参数必须在0到1之间")
                    else:
                        raise ValueError(f"样品{key+1}的α参数必须在0到1之间")
                if t_end <= t_start:
                    if key == 'ref':
                        raise ValueError("参考信号的结束时间必须大于起始时间")
                    else:
                        raise ValueError(f"样品{key+1}的结束时间必须大于起始时间")
                
                params = {
                    't_start': t_start,
                    't_end': t_end,
                    'alpha': alpha
                }
                
                # 根据key类型保存参数
                if key == 'ref':
                    self.ref_window_params = params
                else:
                    self.per_sample_window_params[key] = params
            
            dialog.close()
            
            # 更新参数标记显示
            self._update_window_params_indicator()
        except ValueError as e:
            QMessageBox.warning(None, "参数错误", str(e))
    
    def _apply_quick_params_to_ref(self):
        """应用快速设置面板的参数到参考信号"""
        try:
            t_start = float(self.quick_ref_t_start.text())
            t_end = float(self.quick_ref_t_end.text())
            alpha = float(self.quick_ref_alpha.text())
            
            # 验证参数
            if alpha < 0 or alpha > 1:
                raise ValueError("α参数必须在0到1之间")
            if t_end <= t_start:
                raise ValueError("结束时间必须大于起始时间")
            
            # 应用到参考信号
            if 'ref' in self.signal_window_inputs:
                self.signal_window_inputs['ref']['t_start'].setText(str(t_start))
                self.signal_window_inputs['ref']['t_end'].setText(str(t_end))
                self.signal_window_inputs['ref']['alpha'].setText(str(alpha))
                self.update_status("已将参数应用到参考信号", "ready")
            else:
                QMessageBox.warning(None, "警告", "未找到参考信号")
        except ValueError as e:
            QMessageBox.warning(None, "参数错误", str(e))
        except Exception as e:
            QMessageBox.warning(None, "错误", f"应用参数失败: {str(e)}")
    
    def _apply_quick_params_to_samples(self):
        """应用快速设置面板的参数到所有样品信号"""
        try:
            t_start = float(self.quick_sam_t_start.text())
            t_end = float(self.quick_sam_t_end.text())
            alpha = float(self.quick_sam_alpha.text())
            
            # 验证参数
            if alpha < 0 or alpha > 1:
                raise ValueError("α参数必须在0到1之间")
            if t_end <= t_start:
                raise ValueError("结束时间必须大于起始时间")
            
            # 应用到所有样品信号（不包括参考信号）
            count = 0
            for key in self.signal_window_inputs:
                if key != 'ref':  # 跳过参考信号
                    self.signal_window_inputs[key]['t_start'].setText(str(t_start))
                    self.signal_window_inputs[key]['t_end'].setText(str(t_end))
                    self.signal_window_inputs[key]['alpha'].setText(str(alpha))
                    count += 1
            
            if count > 0:
                self.update_status(f"已将参数应用到 {count} 个样品信号", "ready")
            else:
                QMessageBox.warning(None, "警告", "没有找到样品信号")
        except ValueError as e:
            QMessageBox.warning(None, "参数错误", str(e))
        except Exception as e:
            QMessageBox.warning(None, "错误", f"应用参数失败: {str(e)}")
    
    def _reset_all_params(self):
        """重置所有参数为默认值"""
        reply = QMessageBox.question(
            None, 
            "确认重置", 
            "确定要将所有信号的参数重置为默认值吗？\n(起始时间=0.0, 结束时间=30.0, α=0.5)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for key in self.signal_window_inputs:
                self.signal_window_inputs[key]['t_start'].setText("0.0")
                self.signal_window_inputs[key]['t_end'].setText("30.0")
                self.signal_window_inputs[key]['alpha'].setText("0.5")
            
            # 同时重置快速设置面板
            self.quick_ref_t_start.setText("0.0")
            self.quick_ref_t_end.setText("30.0")
            self.quick_ref_alpha.setText("0.5")
            self.quick_sam_t_start.setText("0.0")
            self.quick_sam_t_end.setText("30.0")
            self.quick_sam_alpha.setText("0.5")
    
    def _apply_template_to_all_samples(self, template_key):
        """将模板参数应用到所有样品信号"""
        try:
            # 获取模板参数
            if template_key == 'ref':
                # 使用参考信号参数作为模板
                if template_key not in self.signal_window_inputs:
                    QMessageBox.warning(None, "警告", "参考信号参数不可用")
                    return
                
                template_inputs = self.signal_window_inputs['ref']
                t_start = float(template_inputs['t_start'].text())
                t_end = float(template_inputs['t_end'].text())
                alpha = float(template_inputs['alpha'].text())
            else:
                # 使用某个样品作为模板
                if template_key not in self.signal_window_inputs:
                    QMessageBox.warning(None, "警告", f"样品 {template_key+1} 的参数不可用")
                    return
                
                template_inputs = self.signal_window_inputs[template_key]
                t_start = float(template_inputs['t_start'].text())
                t_end = float(template_inputs['t_end'].text())
                alpha = float(template_inputs['alpha'].text())
            
            # 验证模板参数
            if alpha < 0 or alpha > 1:
                raise ValueError("模板的α参数必须在0到1之间")
            if t_end <= t_start:
                raise ValueError("模板的结束时间必须大于起始时间")
            
            # 应用到所有样品
            count = 0
            for i in range(len(self.sam_names)):
                if i in self.signal_window_inputs and i != template_key:
                    self.signal_window_inputs[i]['t_start'].setText(str(t_start))
                    self.signal_window_inputs[i]['t_end'].setText(str(t_end))
                    self.signal_window_inputs[i]['alpha'].setText(str(alpha))
                    count += 1
            
            if count > 0:
                self.update_status(f"已将模板参数应用到 {count} 个样品", "ready")
        except ValueError as e:
            QMessageBox.warning(None, "参数错误", str(e))
        except Exception as e:
            QMessageBox.warning(None, "错误", f"应用模板失败: {str(e)}")
        

    def update_status(self, message, status_type="ready"):
        """更新状态标签的文本和图标"""
        if status_type == "ready":
            icon = self.ready_icon
        elif status_type == "working":
            icon = self.working_icon
        elif status_type == "error":
            icon = self.error_icon
        else:
            icon = self.ready_icon
        
        # 设置图标和文本
        pixmap = icon.pixmap(16, 16)
        self.status_label.setPixmap(pixmap)
        self.status_label.setText(f"  {message}")
    
    def dragEnterEvent(self, event):
        """实现拖拽文件进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        """实现文件拖放事件"""
        urls = event.mimeData().urls()
        drop_widget = self.childAt(event.position().toPoint())
        pos = event.position().toPoint()
        
        # 获取样品文件列表和参考文件编辑框的全局坐标和大小
        sam_files_rect = self.sam_files_list.geometry()
        sam_files_global_pos = self.sam_files_list.mapTo(self, QPoint(0, 0))
        sam_files_area = QRect(sam_files_global_pos, sam_files_rect.size())
        
        # 获取样品文件列表组标签的坐标和大小
        sam_label_rect = QRect(sam_files_area.x(), sam_files_area.y() - 30, 
                               sam_files_area.width(), 30)
        
        # 扩展样品文件区域包括标签
        sam_files_area = sam_files_area.united(sam_label_rect)
        
        # 获取参考文件编辑框及其标签的全局坐标和大小
        ref_edit_rect = self.ref_file_edit.geometry()
        ref_edit_global_pos = self.ref_file_edit.mapTo(self, QPoint(0, 0))
        ref_edit_area = QRect(ref_edit_global_pos, ref_edit_rect.size())
        
        # 判断拖放位置
        if sam_files_area.contains(pos) or isinstance(drop_widget, QListWidget):
            # 添加到样品文件
            for url in urls:
                file_path = url.toLocalFile()
                if os.path.isfile(file_path) and file_path.lower().endswith(('.xlsx', '.xls', '.txt')):
                    self.sam_files.append(file_path)
                    file_name = os.path.splitext(os.path.basename(file_path))[0]
                    self.sam_names.append(file_name)
                    self.sam_files_list.addItem(file_name)
            
            if urls:
                self.update_status(f"已添加 {len(urls)} 个样品文件", "ready")
        elif ref_edit_area.contains(pos) or isinstance(drop_widget, QLineEdit):
            # 添加到参考文件
            if urls:
                file_path = urls[0].toLocalFile()
                if os.path.isfile(file_path) and file_path.lower().endswith(('.xlsx', '.xls', '.txt')):
                    self.ref_file = file_path
                    self.ref_file_edit.setText(os.path.basename(file_path))
                    self.update_status(f"已选择参考文件", "ready")
        else:
            # 默认作为样品文件添加
            for url in urls:
                file_path = url.toLocalFile()
                if os.path.isfile(file_path) and file_path.lower().endswith(('.xlsx', '.xls', '.txt')):
                    self.sam_files.append(file_path)
                    file_name = os.path.splitext(os.path.basename(file_path))[0]
                    self.sam_names.append(file_name)
                    self.sam_files_list.addItem(file_name)
            
            if urls:
                self.update_status(f"已添加 {len(urls)} 个样品文件", "ready")
    
    def select_ref_file(self):
        """选择参考文件"""
        initial_dir = self.config.get("last_open_dir", "")
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择参考文件",
            initial_dir,
            "数据文件 (*.xlsx *.xls *.txt);;Excel文件 (*.xlsx *.xls);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if file_path:
            self.ref_file = file_path
            self.config["last_open_dir"] = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            self.ref_file_edit.setText(file_name)
            self.update_status(f"已选择参考文件", "ready")
    
    def add_sam_file(self):
        """添加样品文件"""
        initial_dir = self.config.get("last_open_dir", "")
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择样品文件",
            initial_dir,
            "数据文件 (*.xlsx *.xls *.txt);;Excel文件 (*.xlsx *.xls);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if file_paths:
            self.config["last_open_dir"] = os.path.dirname(file_paths[0])
            
            for file_path in file_paths:
                self.sam_files.append(file_path)
                file_name = os.path.splitext(os.path.basename(file_path))[0]
                self.sam_names.append(file_name)
                self.sam_files_list.addItem(file_name)
                
                # 为新添加的样品初始化窗函数参数为None（表示使用全局参数）
                idx = len(self.sam_names) - 1
                self.per_sample_window_params[idx] = None
            
            self.update_status(f"已添加 {len(file_paths)} 个样品文件", "ready")
    
    def delete_selected_file(self):
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
            
            # 删除对应的窗函数参数并重新索引
            # 删除被删除行及以后行的索引
            new_params = {}
            for k in list(self.per_sample_window_params.keys()):
                if k < row:
                    new_params[k] = self.per_sample_window_params[k]
                elif k > row:
                    new_params[k - 1] = self.per_sample_window_params[k]
            self.per_sample_window_params = new_params
        
        self._update_window_params_indicator()
        self.update_status("已删除选中的样品文件", "ready")
    def clear_sam_files(self):
        """清空样品文件列表"""
        self.sam_files = []
        self.sam_names = []
        self.sam_files_list.clear()
        self.per_sample_window_params = {}
        self._update_window_params_indicator()
        self.update_status("样品文件列表已清空", "ready")
    
    def run_analysis(self):
        """运行THz光学参数分析"""
        if not self.ref_file:
            QMessageBox.warning(self, "警告", "请先选择参考文件")
            return
        
        if not self.sam_files:
            QMessageBox.warning(self, "警告", "请添加至少一个样品文件")
            return
        
        try:
            # 获取样品厚度
            try:
                thickness = float(self.thickness_combo.currentText())
                if thickness <= 0:
                    raise ValueError
            except Exception:
                QMessageBox.warning(self, "警告", "样品厚度必须为正数")
                return
                
            # 获取起始行
            try:
                start_row = int(self.start_row_combo.currentText())
                if start_row < 1:
                    raise ValueError
            except Exception:
                QMessageBox.warning(self, "警告", "数据起始行必须为大于等于1的整数")
                return
                
            self.config["start_row"] = start_row
            
            # 更新厚度历史记录
            self.config = update_thickness_history(self.config, thickness)
            self.config["thickness"] = thickness
            
            # 清除之前的图表
            self._clear_tabs()
            
            self.update_status("正在计算，请稍候...", "working")
            QApplication.processEvents()
            
            # 获取窗函数参数
            use_window = self.use_window_checkbox.isChecked()
            
            # 保存窗函数启用状态到配置
            self.config["use_window"] = use_window
            
            # 构建每个样品的窗函数参数列表
            per_sample_params_list = []
            for i in range(len(self.sam_names)):
                if i in self.per_sample_window_params and self.per_sample_window_params[i] is not None:
                    per_sample_params_list.append(self.per_sample_window_params[i])
                else:
                    per_sample_params_list.append(None)
            
            fig1, fig2, fig3, self.results_data = calculate_optical_params(
                self.ref_file, self.sam_files, self.sam_names, thickness, start_row,
                use_window, self.ref_window_params, per_sample_params_list
            )
            
            if fig1 and fig2 and fig3 and self.results_data:
                # 显示图表
                self._display_charts(fig1, fig2, fig3)
                self.update_status("计算完成", "ready")
                self.save_btn.setEnabled(True)
                self.show_absorption_btn.setEnabled(True)
            else:
                self.update_status("计算失败", "error")
                self.save_btn.setEnabled(False)
                self.show_absorption_btn.setEnabled(False)
                
        except ValueError as e:
            QMessageBox.critical(self, "输入错误", f"请输入有效的值: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理过程中出错: {str(e)}")
    
    def _clear_tabs(self):
        """清除标签页中的图表"""
        for tab in [self.tab1, self.tab2, self.tab3]:
            for i in range(tab.layout().count()):
                item = tab.layout().itemAt(i)
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
    
    def show_absorption_plot(self):
        """弹出显示吸收系数图表的独立窗口"""
        if self.results_data is None:
            QMessageBox.warning(self, "警告", "没有可显示的数据，请先运行分析")
            return
        
        # 如果窗口已经存在，先关闭
        if self.absorption_window is not None:
            try:
                self.absorption_window.close()
            except:
                pass
        
        # 创建新窗口
        self.absorption_window = QMainWindow()
        self.absorption_window.setWindowTitle("吸收系数图表")
        self.absorption_window.setMinimumSize(900, 600)
        
        # 创建中心部件
        central_widget = QWidget()
        self.absorption_window.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建吸收系数图表
        fig = plt.figure(figsize=(10, 6))
        fig.patch.set_facecolor('#F5F5F5')
        
        ax = fig.add_subplot(1, 1, 1)
        ax.set_facecolor('#F8F8F8')
        
        # 定义颜色
        colors = ['red', 'blue', 'green', 'purple', 'orange', 'brown', 'pink', 'gray', 'olive', 'cyan']
        
        # 绘制每个样品的吸收系数
        F = self.results_data['F']
        all_Asam = self.results_data['Asam']
        sam_names = self.results_data['sam_names']
        
        for i in range(len(all_Asam)):
            ax.plot(F, all_Asam[i], color=colors[i % len(colors)], linewidth=2.5, label=sam_names[i])
        
        ax.set_xlabel('频率 (THz)', fontsize=12)
        ax.set_ylabel('吸收系数 (cm^-1)', fontsize=12)
        ax.set_title('吸收系数对比', fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 5)
        ax.autoscale(axis='y')
        
        fig.tight_layout()
        
        # 创建画布和工具栏
        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, self.absorption_window)
        
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        
        # 显示窗口
        self.absorption_window.show()
    
    def save_results(self):
        """保存计算结果到Excel文件"""
        if self.results_data is None:
            QMessageBox.warning(self, "警告", "没有可保存的计算结果，请先运行分析")
            return
            
        initial_dir = self.config.get("last_save_dir", "")
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存结果",
            initial_dir,
            "Excel文件 (*.xlsx);;所有文件 (*.*)"
        )
        
        if file_path:
            if not file_path.lower().endswith('.xlsx'):
                file_path += '.xlsx'
                
            self.config["last_save_dir"] = os.path.dirname(file_path)
            
            self.update_status("正在保存结果...", "working")
            QApplication.processEvents()
            
            if save_results_to_excel(self.results_data, file_path):
                self.update_status(f"结果已保存到: {os.path.basename(file_path)}", "ready")
                QMessageBox.information(self, "保存成功", f"计算结果已保存到:\n{file_path}")
            else:
                self.update_status("保存失败", "error")
    
    def show_help_dialog(self):
        """显示帮助对话框"""
        from PyQt6.QtWidgets import QDialog, QTextBrowser
        
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("📖 使用说明")
        help_dialog.setMinimumSize(650, 550)
        help_dialog.setStyleSheet("QDialog { background-color: #FFFFFF; }")
        
        layout = QVBoxLayout(help_dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setStyleSheet("QTextBrowser { border: none; background-color: #FFFFFF; font-size: 10pt; }")
        
        help_html = """
<h2 style="color: #2C3E50; text-align: center; margin-bottom: 20px;">THz 时域光谱分析系统 - 使用指南</h2>

<h3 style="color: #3498DB;">📋 基本流程</h3>
<ol style="line-height: 1.8; margin-left: 20px;">
    <li><b>选择参考文件</b>：点击"添加文件"按钮选择参考信号文件（空气或无样品的参考测量）
        <ul style="margin-left: 15px; margin-top: 5px;">
            <li>支持格式：Excel (.xlsx, .xls) 和文本文件 (.txt)</li>
            <li>数据格式：第一列为时间(ps)，第二列为电场振幅</li>
        </ul>
    </li>
    <li><b>添加样品文件</b>：点击"添加文件"或拖放文件到列表区域
        <ul style="margin-left: 15px; margin-top: 5px;">
            <li>支持批量添加多个样品文件</li>
            <li>可随时删除或清空样品列表</li>
        </ul>
    </li>
    <li><b>设置参数</b>：
        <ul style="margin-left: 15px; margin-top: 5px;">
            <li><b>数据起始行</b>：指定数据从文件的第几行开始（跳过表头）</li>
            <li><b>样品厚度</b>：输入样品的厚度值（单位：mm），支持历史记录</li>
        </ul>
    </li>
    <li><b>Tukey窗函数</b>（可选）：开启开关后可设置窗函数参数，用于去除多次反射</li>
    <li><b>运行分析</b>：点击"运行分析"按钮开始计算光学参数</li>
    <li><b>保存结果</b>：分析完成后，点击"保存结果"将数据导出为Excel文件</li>
</ol>

<h3 style="color: #3498DB;">🔧 Tukey窗函数设置</h3>
<p style="line-height: 1.8; margin-left: 10px;">
Tukey窗函数用于截取时域信号的特定区域，去除多次反射干扰：<br><br>
• <b>起始时间 (ps)</b>：窗函数作用的起始时间点，应在主脉冲之前<br>
• <b>结束时间 (ps)</b>：窗函数作用的结束时间点，应在第一次反射脉冲之前<br>
• <b>α参数 (0-1)</b>：控制窗函数边缘的平滑程度
</p>
<ul style="line-height: 1.6; margin-left: 30px;">
    <li>α=0：矩形窗，边缘陡峭，频域旁瓣大</li>
    <li>α=1：汉宁窗，边缘平滑，频域旁瓣小</li>
    <li>推荐值：0.3-0.7，兼顾时域截断和频域特性</li>
</ul>
<p style="line-height: 1.8; margin-left: 10px;">
<b>快速设置</b>：可分别为参考信号和样品信号设置不同的窗函数参数
</p>

<h3 style="color: #3498DB;">📊 结果查看</h3>
<p style="line-height: 1.8; margin-left: 10px;">
分析完成后，右侧面板显示三个标签页：
</p>
<p style="line-height: 1.6; margin-left: 10px;">
• <b>时域和频域信号</b>：上图为时域信号波形，下图为频域幅度谱(dB)<br>
• <b>光学参数</b>：折射率n(ω)、消光系数k(ω)、吸收系数α(ω)<br>
• <b>介电特性</b>：介电常数实部ε'、虚部ε''、介电损耗tanδ<br>
• <b>弹出吸收系数图</b>：点击按钮可在独立窗口中查看吸收系数
</p>

<h3 style="color: #3498DB;">💡 快捷操作</h3>
<p style="line-height: 1.8; margin-left: 10px;">
• <b>拖放文件</b>：直接拖放文件到样品文件列表区域<br>
• <b>F1</b>：打开本帮助对话框<br>
• <b>Ctrl+Q</b>：退出程序<br>
• <b>图表工具栏</b>：每个图表下方有导航工具栏，支持缩放、平移、保存图片<br>
• <b>自动保存</b>：程序会自动保存参数设置到配置文件
</p>

<h3 style="color: #3498DB;">⚠️ 注意事项</h3>
<p style="line-height: 1.8; margin-left: 10px;">
• <b>数据格式</b>：第一列为时间数据(ps)，第二列为电场振幅数据<br>
• <b>数据一致性</b>：参考文件和样品文件的时间采样点数应一致<br>
• <b>厚度单位</b>：样品厚度必须使用毫米(mm)为单位<br>
• <b>频率范围</b>：默认显示0-5 THz范围，可通过工具栏调整
</p>
"""
        
        text_browser.setHtml(help_html)
        layout.addWidget(text_browser)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_btn = AnimatedButton("确定")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498DB;
                color: white;
                border-radius: 4px;
                padding: 8px 30px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980B9;
            }
        """)
        ok_btn.clicked.connect(help_dialog.accept)
        button_layout.addWidget(ok_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        help_dialog.exec()
    
    def show_about_dialog(self):
        """显示关于对话框"""
        from PyQt6.QtWidgets import QDialog, QTextBrowser
        
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle("ℹ️ 关于")
        about_dialog.setMinimumSize(500, 420)
        about_dialog.setStyleSheet("QDialog { background-color: #FFFFFF; }")
        
        layout = QVBoxLayout(about_dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setStyleSheet("QTextBrowser { border: none; background-color: #FFFFFF; font-size: 10pt; }")
        
        about_html = """
<div style="text-align: center;">
    <h2 style="color: #2C3E50; margin-bottom: 10px;">🔬 THz 时域光谱分析系统</h2>
    <p style="color: #7F8C8D; font-size: 12pt;">太赫兹光学参数提取工具</p>
</div>

<hr style="border: 1px solid #EEEEEE; margin: 15px 0;">

<table style="width: 100%; margin: 10px 0;">
    <tr><td style="width: 100px; color: #666666;"><b>版本</b></td><td>v4.5.1</td></tr>
    <tr><td style="color: #666666;"><b>更新日期</b></td><td>2025年11月29日</td></tr>
    <tr><td style="color: #666666;"><b>开发框架</b></td><td>Python 3 + PyQt6 + Matplotlib</td></tr>
</table>

<h3 style="color: #3498DB; margin-top: 20px;">✨ 主要功能</h3>
<ul style="line-height: 1.8; margin-left: 10px;">
    <li><b>时域/频域分析</b>：THz时域信号的FFT变换与频谱分析</li>
    <li><b>光学参数提取</b>：基于传输函数法计算折射率n、消光系数k、吸收系数α</li>
    <li><b>介电特性计算</b>：计算复介电常数ε'、ε''及介电损耗tanδ</li>
    <li><b>Tukey窗函数</b>：可调参数的窗函数，去除多次反射干扰</li>
    <li><b>批量处理</b>：支持同时分析多个样品，自动对比显示</li>
    <li><b>结果导出</b>：将计算结果保存为Excel格式</li>
</ul>

<h3 style="color: #3498DB; margin-top: 15px;">🔬 技术原理</h3>
<p style="line-height: 1.6; margin-left: 10px; color: #555555;">
本软件基于THz-TDS（太赫兹时域光谱）技术，通过比较参考信号和样品信号的传输函数，利用相位信息提取折射率，利用幅度信息提取消光系数和吸收系数。
</p>

<hr style="border: 1px solid #EEEEEE; margin: 15px 0;">

<div style="text-align: center; margin-top: 15px;">
    <p style="color: #3498DB; font-weight: bold; font-size: 11pt;">南京航空航天大学</p>
    <p style="color: #666666;">高电压与绝缘技术实验室</p>
    <p style="color: #888888; font-size: 9pt; margin-top: 5px;">Nanjing University of Aeronautics and Astronautics</p>
</div>

<p style="text-align: center; margin-top: 20px; color: #999999; font-size: 9pt;">
© 2025 THz光学参数分析系统. All rights reserved.
</p>
"""
        
        text_browser.setHtml(about_html)
        layout.addWidget(text_browser)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_btn = AnimatedButton("确定")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498DB;
                color: white;
                border-radius: 4px;
                padding: 8px 30px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980B9;
            }
        """)
        ok_btn.clicked.connect(about_dialog.accept)
        button_layout.addWidget(ok_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        about_dialog.exec()
    
    def on_closing(self, event):
        """窗口关闭事件，保存配置"""
        try:
            save_config(self.config)
            plt.close('all')
            event.accept()
        except Exception as e:
            print(f"关闭程序时出错: {e}")
            event.accept()
