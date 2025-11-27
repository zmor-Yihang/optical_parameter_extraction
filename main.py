import sys
from PyQt6.QtWidgets import QApplication
from utils import setup_matplotlib
from gui import THzAnalyzerApp


def main():
    # 设置matplotlib中文支持
    setup_matplotlib()
    
    # 创建应用程序
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = THzAnalyzerApp()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
