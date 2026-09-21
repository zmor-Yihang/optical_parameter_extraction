"""
应用版本与更新源配置。

版本号唯一权威来源：config/release.json。
打包脚本（build_installer.ps1）会读取该文件注入安装包，并同步 pyproject.toml。
"""

import json
import os
import sys

APP_NAME = "THzAnalyzer"
APP_DISPLAY_NAME = "THz 时域光谱分析系统"

_DEFAULT_GITHUB_REPO = "zmor-Yihang/optical_parameter_extraction"
#: release.json 缺失时的后备版本号。需与 config/release.json 保持一致，
#: 否则打包遗漏该文件时程序会自称旧版本，导致升级后仍反复提示更新。
_DEFAULT_VERSION = "1.1.0"


def _resource_root() -> str:
    """开发环境为项目根目录；PyInstaller 打包后为 _MEIPASS。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_release_config() -> dict:
    path = os.path.join(_resource_root(), "config", "release.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("release.json 格式不正确")
        return data
    except Exception:
        return {}


_release = _load_release_config()

__version__ = str(_release.get("version") or _DEFAULT_VERSION).strip()
VERSION = __version__
APP_VERSION = __version__

GITHUB_REPO = str(_release.get("github_repo") or _DEFAULT_GITHUB_REPO).strip()
UPDATE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest/download/version.json"
INSTALLER_DOWNLOAD_URL = f"https://github.com/{GITHUB_REPO}/releases/latest/download/install.exe"
