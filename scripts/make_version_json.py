#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
发布辅助脚本：生成 GitHub Releases 所需的 version.json。

通常不需要手动运行：build_installer.ps1 在编译安装程序后会自动调用本脚本。
需要单独重新生成时（在项目根目录下执行）：
    uv run python scripts/make_version_json.py
    uv run python scripts/make_version_json.py --changelog "- 新增 xxx;- 修复 xxx"

版本号与下载地址来自项目根目录的 release.json（经 core.version 读取）。
前置条件：installer-output\\install.exe 已存在（由 build_installer.ps1 生成）。

changelog 取值优先级：
    1. --changelog 参数
    2. 已存在的 installer-output\\version.json 中同版本的 changelog（避免重新构建时覆盖已写好的说明）
    3. 占位提示文本（需手动补充）
生成后到 GitHub Releases 页面上传 install.exe 与 version.json 两个文件。
"""

import argparse
import hashlib
import json
import os
import sys
import time

# 允许从项目根目录导入 core 包（脚本位于 scripts/ 子目录）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.version import APP_VERSION, INSTALLER_DOWNLOAD_URL  # noqa: E402

#: changelog 未提供时的占位文本，同时也是"是否已人工填写"的判断依据
PLACEHOLDER_CHANGELOG = "请填写本次更新的内容说明（每条一行）"


def sha256_of(path: str) -> str:
    """计算文件 SHA256（小写十六进制）。"""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="生成 GitHub Releases 所需的 version.json"
    )
    parser.add_argument(
        "--changelog",
        default="",
        help="本次更新说明，多条可用 ';' 或 '\\n' 分隔；缺省时沿用已有 version.json 中的内容",
    )
    return parser.parse_args()


def read_existing_changelog(out_path: str, version: str) -> str:
    """读取已有 version.json 中同版本的 changelog（版本变化或仍是占位文本时返回空串）。"""
    try:
        with open(out_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    if str(data.get("version", "")).strip() != version:
        return ""
    changelog = str(data.get("changelog", "")).strip()
    if not changelog or changelog == PLACEHOLDER_CHANGELOG:
        return ""
    return changelog


def normalize_changelog(text: str) -> str:
    """把命令行传入的说明整理为多行文本（支持 ';' 与 '\\n' 作为分隔符）。"""
    text = text.strip().replace("\\n", "\n")
    lines = [line.strip() for line in text.split(";")]
    return "\n".join(line for line in lines if line)


def main():
    args = parse_args()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    installer = os.path.join(root, "installer-output", "install.exe")
    if not os.path.isfile(installer):
        sys.exit(
            f"未找到安装包: {installer}\n"
            "请先在项目根目录运行 .\\build_installer.ps1 构建安装包。"
        )

    out_path = os.path.join(root, "installer-output", "version.json")

    changelog = normalize_changelog(args.changelog)
    changelog_source = "--changelog 参数"
    if not changelog:
        changelog = read_existing_changelog(out_path, APP_VERSION)
        changelog_source = f"沿用已有 version.json（v{APP_VERSION}）"
    if not changelog:
        changelog = PLACEHOLDER_CHANGELOG
        changelog_source = "占位文本，需手动补充"

    sha256 = sha256_of(installer)
    size_mb = os.path.getsize(installer) / (1024 * 1024)

    info = {
        "version": APP_VERSION,
        "download_url": INSTALLER_DOWNLOAD_URL,
        "release_date": time.strftime("%Y-%m-%d"),
        "changelog": changelog,
        "sha256": sha256,
        "required": False,
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(info, fh, ensure_ascii=False, indent=2)

    print(f"已生成: {out_path}")
    print(f"版本: v{APP_VERSION}")
    print(f"安装包大小: {size_mb:.1f} MB")
    print(f"SHA256: {sha256}")
    print(f"更新说明来源: {changelog_source}")
    if changelog == PLACEHOLDER_CHANGELOG:
        print()
        print("下一步：用编辑器打开 version.json，把 changelog 改成实际更新内容，")
        print("然后将 install.exe 与 version.json 一起上传到 GitHub Releases。")
    else:
        print(f"更新说明: {changelog}")
        print()
        print("下一步：将 install.exe 与 version.json 一起上传到 GitHub Releases。")


if __name__ == "__main__":
    main()
