import sys
from PyQt6.QtWidgets import QApplication
from utils import setup_matplotlib, info
from gui import THzAnalyzerApp
from gui.styles import apply_light_theme


def main():
    # 初始化日志
    info("程序启动")
    
    # 设置matplotlib中文支持
    setup_matplotlib()
    
    # 创建应用程序并统一应用内窗口的外观
    app = QApplication(sys.argv)
    apply_light_theme(app)
    
    # 创建主窗口
    window = THzAnalyzerApp()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
