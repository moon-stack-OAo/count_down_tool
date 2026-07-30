# -*- coding: utf-8 -*-
"""运行日志：写入用户配置目录，便于打包后排查问题。"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

from core.countdown_core import __version__, user_log_path

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
# 单文件约 2MB，最多 3 个备份 → 约 8MB
_MAX_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 3

_configured = False


def _env_level(default: int = logging.INFO) -> int:
    """COUNT_DOWN_TOOL_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR"""
    raw = (os.environ.get("COUNT_DOWN_TOOL_LOG_LEVEL") or "").strip().upper()
    if not raw:
        return default
    return getattr(logging, raw, default)


def setup_app_logging(
    *,
    level: Optional[int] = None,
    log_path: Optional[str] = None,
    also_console: Optional[bool] = None,
) -> str:
    """配置根 logger：文件轮转 + 可选控制台。

    返回实际日志文件路径（失败时可能为空字符串）。
    可重复调用：仅首次生效。
    """
    global _configured
    if _configured:
        return log_path or user_log_path()

    resolved_level = level if level is not None else _env_level(logging.INFO)
    path = log_path or user_log_path()

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(resolved_level)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    file_ok = False

    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        fh = RotatingFileHandler(
            path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
            delay=False,
        )
        fh.setLevel(resolved_level)
        fh.setFormatter(formatter)
        root.addHandler(fh)
        file_ok = True
    except OSError:
        # 无法写盘时仍尽量控制台输出
        path = ""

    # 开发态 / 有控制台：同步输出；windowed 打包无控制台则跳过
    if also_console is None:
        also_console = not bool(getattr(sys, "frozen", False))
    if also_console:
        try:
            sh = logging.StreamHandler(sys.stderr)
            sh.setLevel(resolved_level)
            sh.setFormatter(formatter)
            root.addHandler(sh)
        except (OSError, ValueError, AttributeError):
            # 无可用 stderr（如部分 windowed 环境）时忽略
            pass

    _configured = True

    log = logging.getLogger("count_down_tool")
    if file_ok:
        log.info(
            "日志已启用 path=%s level=%s version=%s frozen=%s platform=%s",
            path,
            logging.getLevelName(resolved_level),
            __version__,
            bool(getattr(sys, "frozen", False)),
            sys.platform,
        )
    else:
        log.warning("无法创建日志文件，仅控制台（若可用）")

    return path


def reset_logging_for_tests() -> None:
    """测试用：重置配置状态。"""
    global _configured
    _configured = False
    root = logging.getLogger()
    for h in list(root.handlers):
        try:
            h.close()
        except (OSError, ValueError, AttributeError):
            pass
        root.removeHandler(h)
