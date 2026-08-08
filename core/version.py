"""
应用版本与更新源配置。

版本号唯一权威来源：pyproject.toml、installer.iss、界面显示均以此为准。
打包脚本（build_installer.ps1）也会读取 __version__ 注入安装包。
"""

APP_NAME = "THzAnalyzer"
APP_DISPLAY_NAME = "THz 时域光谱分析系统"

__version__ = "1.0.1"
VERSION = __version__
APP_VERSION = __version__

# GitHub Releases：发布新版本时，将 install.exe 与 version.json 作为 Release 资产上传，
# 以下 latest/download 链接会自动指向最新版本。
GITHUB_REPO = "zmor-Yihang/optical_parameter_extraction"
UPDATE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest/download/version.json"
INSTALLER_DOWNLOAD_URL = f"https://github.com/{GITHUB_REPO}/releases/latest/download/install.exe"
