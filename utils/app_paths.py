"""
应用路径工具模块

统一处理打包环境 (PyInstaller / Nuitka) 与开发环境下,
可执行程序目录、配置文件、日志目录的定位逻辑。
"""

import os
import sys


def is_frozen() -> bool:
    """判断当前是否运行于打包后的环境

    覆盖 PyInstaller(_MEIPASS)、Nuitka(__compiled__ / sys.frozen)等主流打包器。
    """
    if hasattr(sys, '_MEIPASS'):
        return True
    if '__compiled__' in globals():
        return True
    return bool(getattr(sys, 'frozen', False))


def get_app_base_dir() -> str:
    """返回应用可写数据目录的根路径

    - 打包环境: 可执行文件所在目录 (onedir / Nuitka standalone 下为安装目录)
    - 开发环境: 项目根目录 (由本文件路径向上两级)
    """
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
