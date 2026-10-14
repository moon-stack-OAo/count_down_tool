# -*- coding: utf-8 -*-
"""更新模块公共常量与路径工具。"""

from __future__ import annotations

import logging
import os
import re
import sys
import tempfile
import urllib.parse
from typing import Callable, Optional

logger = logging.getLogger("count_down_tool.update")

# 与 origin 一致；公开仓库无需 token
GITHUB_OWNER = "moon-stack-OAo"
GITHUB_REPO = "count_down_tool"
GITHUB_API_LATEST = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
GITHUB_RELEASES_PAGE = (
    f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
USER_AGENT = f"{GITHUB_REPO}-updater"

# 主程序文件名（Windows onedir / onefile）
WINDOWS_EXE_NAME = "count_down_tool.exe"

# 解压白名单：仅允许安装包合理路径（防 Zip Slip / 脏包）
_EXTRACT_ALLOWED_ROOT_FILES = frozenset(
    {
        WINDOWS_EXE_NAME.lower(),
        "readme.txt",
        "readme.md",
        "license",
        "license.txt",
        "license.md",
    }
)
_EXTRACT_ALLOWED_TOP_DIRS = frozenset({"_internal", "docs"})

ProgressCb = Optional[Callable[[int, int], None]]  # received, total(-1 if unknown)

# 更新包与校验文件最终 URL（含重定向后）只允许这些主机，且必须 https。
_ALLOWED_UPDATE_HOSTS = frozenset(
    {
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
        "github-releases.githubusercontent.com",
    }
)


class UpdateUrlNotAllowedError(ValueError):
    """下载或校验 URL 的协议/主机不在白名单内。"""


def assert_allowed_update_url(url: str) -> str:
    """
    校验更新相关 URL：必须 https，且主机在 GitHub 发布资产白名单内。
    返回规范化后的 URL；拒绝则抛 UpdateUrlNotAllowedError。
    """
    raw = (url or "").strip()
    if not raw:
        raise UpdateUrlNotAllowedError("更新 URL 为空")
    try:
        parts = urllib.parse.urlsplit(raw)
    except (TypeError, ValueError) as exc:
        raise UpdateUrlNotAllowedError(f"更新 URL 无法解析: {raw!r}") from exc
    scheme = (parts.scheme or "").lower()
    host = (parts.hostname or "").lower()
    if scheme != "https" or not host or host not in _ALLOWED_UPDATE_HOSTS:
        raise UpdateUrlNotAllowedError(
            f"拒绝非白名单更新 URL（仅允许 https 且主机为 GitHub 发布资产）: {raw}"
        )
    if parts.username or parts.password:
        raise UpdateUrlNotAllowedError(f"拒绝带用户信息的更新 URL: {raw}")
    return raw

def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def current_executable_path() -> str:
    """打包后为 exe/.app 内可执行路径；开发态为 python。"""
    return os.path.abspath(sys.executable)


def default_download_dir() -> str:
    """用户下载目录；失败则用临时目录。"""
    home = os.path.expanduser("~")
    for name in ("Downloads", "下载"):
        p = os.path.join(home, name)
        if os.path.isdir(p):
            return p
    return tempfile.gettempdir()

def truncate_release_notes(body: str, max_len: int = 600) -> str:
    text = (body or "").strip()
    if not text:
        return "（无更新说明）"
    # 去掉过长 markdown 噪声
    text = re.sub(r"\r\n", "\n", text)
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text
