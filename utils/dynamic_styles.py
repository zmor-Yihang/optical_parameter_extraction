from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QSequentialAnimationGroup
from PyQt5.QtWidgets import QGraphicsOpacityEffect, QGraphicsDropShadowEffect
from PyQt5.QtGui import QColor

class AnimationConfig:
    """动画配置类"""
    
    # 动画持续时间
    FAST_ANIMATION = 150
    NORMAL_ANIMATION = 300
    SLOW_ANIMATION = 500
    
    # 缓动曲线
    EASE_IN_OUT = QEasingCurve.InOutQuad
    EASE_OUT = QEasingCurve.OutQuad
    EASE_IN = QEasingCurve.InQuad
    BOUNCE = QEasingCurve.OutBounce
    
    # 透明度值
    OPACITY_NORMAL = 1.0
    OPACITY_HOVER = 0.8
    OPACITY_PRESSED = 0.6
    OPACITY_DISABLED = 0.4

class ThemeColors:
    """主题颜色配置"""
    
    # 主色调
    PRIMARY_DARK = "#1a1a1a"
    PRIMARY_MEDIUM = "#2d2d2d"
    PRIMARY_LIGHT = "#3d3d3d"
    
    # 强调色
    ACCENT_BLUE = "#4A90E2"
    ACCENT_BLUE_HOVER = "#5A9AE2"
    ACCENT_BLUE_PRESSED = "#3A80D2"
    
    # 文本颜色
    TEXT_PRIMARY = "#E0E0E0"
    TEXT_SECONDARY = "#B0B0B0"
    TEXT_DISABLED = "#808080"
    
    # 状态颜色
    SUCCESS_COLOR = "#198754"
    WARNING_COLOR = "#FFC107"
    ERROR_COLOR = "#DC3545"
    INFO_COLOR = "#17A2B8"
    
    # 边框颜色
    BORDER_NORMAL = "#555555"
    BORDER_FOCUS = "#4A90E2"
    BORDER_HOVER = "#6A90E2"

class DynamicStyles:
    """动态样式生成器"""
    
    @staticmethod
    def get_animated_button_style():
        """获取动画按钮样式"""
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4A90E2, stop:1 #3A80D2);
                border: 2px solid transparent;
                border-radius: 8px;
                padding: 10px 20px;
                color: #FFFFFF;
                font-weight: 600;
                font-size: 11px;
                text-align: center;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5A9AE2, stop:1 #4A90E2);
                border: 2px solid #6A90E2;
                transform: scale(1.02);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3A80D2, stop:1 #2A70C2);
                border: 2px solid #4A90E2;
                transform: scale(0.98);
            }
            QPushButton:disabled {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #555555, stop:1 #444444);
                color: #888888;
                border: 2px solid #444444;
            }
        """
    
    @staticmethod
    def get_success_button_style():
        """获取成功按钮样式"""
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #198754, stop:1 #157347);
                border: 2px solid transparent;
                border-radius: 8px;
                padding: 10px 20px;
                color: #FFFFFF;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #20a55a, stop:1 #198754);
                border: 2px solid #28a745;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #157347, stop:1 #146c43);
            }
        """
    
    @staticmethod
    def get_danger_button_style():
        """获取危险按钮样式"""
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #DC3545, stop:1 #C82333);
                border: 2px solid transparent;
                border-radius: 8px;
                padding: 10px 20px;
                color: #FFFFFF;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #E2474F, stop:1 #DC3545);
                border: 2px solid #E85D75;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #C82333, stop:1 #B21E2F);
            }
        """
    
    @staticmethod
    def get_glass_panel_style():
        """获取玻璃面板样式"""
        return """
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(45, 45, 45, 0.9), stop:1 rgba(25, 25, 25, 0.9));
                border: 2px solid rgba(85, 85, 85, 0.8);
                border-radius: 12px;
                backdrop-filter: blur(10px);
            }
        """

class EffectFactory:
    """特效工厂类"""
    
    @staticmethod
    def create_shadow_effect(color=QColor(0, 0, 0, 60), blur_radius=10, offset=(3, 3)):
        """创建阴影效果"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setColor(color)
        shadow.setBlurRadius(blur_radius)
        shadow.setOffset(offset[0], offset[1])
        return shadow
    
    @staticmethod
    def create_opacity_effect(opacity=1.0):
        """创建透明度效果"""
        effect = QGraphicsOpacityEffect()
        effect.setOpacity(opacity)
        return effect
    
    @staticmethod
    def create_fade_animation(widget, start_opacity=1.0, end_opacity=0.0, duration=AnimationConfig.NORMAL_ANIMATION):
        """创建淡入淡出动画"""
        effect = EffectFactory.create_opacity_effect(start_opacity)
        widget.setGraphicsEffect(effect)
        
        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(duration)
        animation.setStartValue(start_opacity)
        animation.setEndValue(end_opacity)
        animation.setEasingCurve(AnimationConfig.EASE_IN_OUT)
        
        return animation
    
    @staticmethod
    def create_pulse_animation(widget, min_opacity=0.6, max_opacity=1.0, duration=AnimationConfig.SLOW_ANIMATION):
        """创建脉冲动画"""
        effect = EffectFactory.create_opacity_effect(max_opacity)
        widget.setGraphicsEffect(effect)
        
        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(duration)
        animation.setStartValue(max_opacity)
        animation.setEndValue(min_opacity)
        animation.setEasingCurve(AnimationConfig.EASE_IN_OUT)
        
        # 创建循环动画
        animation.finished.connect(lambda: animation.setDirection(
            QPropertyAnimation.Backward if animation.direction() == QPropertyAnimation.Forward 
            else QPropertyAnimation.Forward
        ))
        animation.finished.connect(animation.start)
        
        return animation

class AnimationUtils:
    """动画工具类"""
    
    @staticmethod
    def create_sequential_animations(*animations):
        """创建顺序动画组"""
        group = QSequentialAnimationGroup()
        for animation in animations:
            group.addAnimation(animation)
        return group
    
    @staticmethod
    def create_parallel_animations(*animations):
        """创建并行动画组"""
        group = QParallelAnimationGroup()
        for animation in animations:
            group.addAnimation(animation)
        return group
    
    @staticmethod
    def apply_hover_effect(widget, hover_opacity=AnimationConfig.OPACITY_HOVER):
        """为控件应用悬停效果"""
        # 这里可以添加鼠标进入和离开事件的处理
        pass

# 导出所有配置类
__all__ = [
    'AnimationConfig',
    'ThemeColors', 
    'DynamicStyles',
    'EffectFactory',
    'AnimationUtils'
]
