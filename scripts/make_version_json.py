#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
发布辅助脚本：一键生成 GitHub Releases 所需的 version.json。

用法（在项目根目录下执行）：
    uv run python scripts/make_version_json.py

前置条件：已运行 .\\build_installer.ps1，生成了 installer-output\\install.exe。
生成后请用编辑器打开 installer-output\\version.json，把 changelog 改成实际更新内容，
然后到 GitHub Releases 页面上传 install.exe 与 version.json 两个文件。
"""

import hashlib
import json
import os
import sys
import time

# 允许从项目根目录导入 core 包（脚本位于 scripts/ 子目录）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.version import APP_VERSION, INSTALLER_DOWNLOAD_URL  # noqa: E402


def sha256_of(path: str) -> str:
    """计算文件 SHA256（小写十六进制）。"""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    installer = os.path.join(root, "installer-output", "install.exe")
    if not os.path.isfile(installer):
        sys.exit(
            f"未找到安装包: {installer}\n"
            "请先在项目根目录运行 .\\build_installer.ps1 构建安装包。"
        )

    sha256 = sha256_of(installer)
    size_mb = os.path.getsize(installer) / (1024 * 1024)

    info = {
        "version": APP_VERSION,
        "download_url": INSTALLER_DOWNLOAD_URL,
        "release_date": time.strftime("%Y-%m-%d"),
        "changelog": "请填写本次更新的内容说明（每条一行）",
        "sha256": sha256,
        "required": False,
    }

    out_path = os.path.join(root, "installer-output", "version.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(info, fh, ensure_ascii=False, indent=2)

    print(f"已生成: {out_path}")
    print(f"版本: v{APP_VERSION}")
    print(f"安装包大小: {size_mb:.1f} MB")
    print(f"SHA256: {sha256}")
    print()
    print("下一步：用编辑器打开 version.json，把 changelog 改成实际更新内容，")
    print("然后将 install.exe 与 version.json 一起上传到 GitHub Releases。")


if __name__ == "__main__":
    main()
