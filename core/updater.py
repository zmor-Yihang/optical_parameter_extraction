"""
在线更新核心模块：获取远程版本信息、语义化版本比较、下载安装包并校验。

仅依赖标准库，可在 GUI 后台线程中安全调用；所有网络/IO 异常统一包装为 UpdateError。
"""

import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from utils import info
from core.version import APP_VERSION


class UpdateError(Exception):
    """更新流程中的错误（网络失败、数据格式错误、校验失败等）。"""


class UpdateNotFoundError(UpdateError):
    """更新源不可用（如 GitHub Releases 尚未发布任何版本，返回 HTTP 404）。

    通常意味着当前没有可用的更新，不应视为程序错误。
    """


@dataclass
class UpdateInfo:
    """远程更新信息（对应更新源的 version.json）。"""

    version: str = ""
    download_url: str = ""
    release_date: str = ""
    changelog: str = ""
    sha256: str = ""
    required: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "UpdateInfo":
        return cls(
            version=str(data.get("version", "")).strip(),
            download_url=str(data.get("download_url", "")).strip(),
            release_date=str(data.get("release_date", "")).strip(),
            changelog=str(data.get("changelog", "")).strip(),
            sha256=str(data.get("sha256", "")).strip(),
            required=bool(data.get("required", False)),
        )


_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


def parse_version(version: str) -> tuple:
    """将形如 4.6.1 的版本号解析为可比较元组；无法解析时返回 (0, 0, 0)。"""
    match = _VERSION_RE.match(version.strip())
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())


def is_newer(local: str, remote: str) -> bool:
    """判断 remote 是否比 local 新（语义化版本比较）。"""
    return parse_version(remote) > parse_version(local)


def _request(url: str, timeout: int):
    """构造带 User-Agent 的 urllib 请求。"""
    req = urllib.request.Request(
        url, headers={"User-Agent": f"THzAnalyzer-Updater/{APP_VERSION}"}
    )
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_update_info(source_url: str, timeout: int = 10) -> UpdateInfo:
    """从更新源拉取 version.json 并解析为 UpdateInfo。

    - HTTP 404（更新源尚未发布）抛 UpdateNotFoundError；
    - 其他 HTTP 错误 / 网络错误抛 UpdateError。
    """
    try:
        with _request(source_url, timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateNotFoundError(
                "尚未在 GitHub Releases 发布任何更新版本。"
            ) from exc
        raise UpdateError(f"更新服务器返回 HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise UpdateError(f"无法连接更新服务器: {exc.reason}") from exc
    except Exception as exc:
        raise UpdateError(f"无法获取更新信息: {exc}") from exc

    if not isinstance(payload, dict):
        raise UpdateError("更新源返回的数据格式不正确")

    update_info = UpdateInfo.from_dict(payload)
    if not update_info.version or not update_info.download_url:
        raise UpdateError("更新源返回的数据缺少 version 或 download_url 字段")
    return update_info


def download_file(
    url: str,
    dest_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    chunk_size: int = 64 * 1024,
) -> str:
    """流式下载文件到 dest_path，并通过 progress_callback(已下载字节, 总字节) 回报进度。"""
    try:
        with _request(url, 30) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            downloaded = 0
            with open(dest_path, "wb") as fh:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)
    except Exception as exc:
        raise UpdateError(f"下载失败: {exc}") from exc
    info(f"更新包下载完成: {dest_path}")
    return dest_path


def sha256_of(path: str) -> str:
    """计算文件 SHA256 校验值（十六进制小写）。"""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
