# -*- coding: utf-8 -*-
"""开机自启（Windows 快捷方式；其他平台 stub）。"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
from typing import List, Optional, Tuple

logger = logging.getLogger("count_down_tool.autostart")

APP_SHORTCUT_NAME = "Count Down Tool.lnk"


def _project_dir() -> str:
    """项目根目录（services/ 的上一级）。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _prefer_pythonw(executable: str) -> str:
    """开发模式优先 pythonw，避免弹出控制台。"""
    if not executable:
        return executable
    base = os.path.basename(executable).lower()
    if base in ("python.exe", "python"):
        directory = os.path.dirname(executable)
        candidates = []
        if base == "python.exe":
            candidates.append(os.path.join(directory, "pythonw.exe"))
        else:
            candidates.append(os.path.join(directory, "pythonw"))
        # 同目录无 pythonw 时保持原可执行文件
        for cand in candidates:
            if os.path.isfile(cand):
                return cand
    return executable


def resolve_launch_command(
    frozen: Optional[bool] = None,
    executable: Optional[str] = None,
    script_path: Optional[str] = None,
    cwd: Optional[str] = None,
) -> Tuple[str, List[str], str]:
    """
    返回 (exe, args_list, working_directory)。
    frozen: sys.executable, [], dirname(exe)
    开发: sys.executable, [abspath(count_down_tool.py)], project_dir
    """
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    exe = executable if executable is not None else sys.executable
    project = cwd if cwd is not None else _project_dir()

    if frozen:
        work = os.path.dirname(os.path.abspath(exe))
        return exe, [], work

    script = script_path
    if script is None:
        script = os.path.join(project, "count_down_tool.py")
    script = os.path.abspath(script)
    launch_exe = _prefer_pythonw(exe)
    return launch_exe, [script], project


def startup_shortcut_path() -> str:
    """Windows 启动文件夹中的快捷方式路径。"""
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(
        appdata,
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs",
        "Startup",
        APP_SHORTCUT_NAME,
    )


def is_autostart_enabled() -> bool:
    """是否已启用开机自启。"""
    if platform.system() != "Windows":
        return False
    try:
        return os.path.isfile(startup_shortcut_path())
    except Exception:
        logger.debug("检测开机自启失败", exc_info=True)
        return False


def _create_shortcut_windows(lnk_path: str, target: str, args: List[str], workdir: str) -> bool:
    """用 PowerShell + WScript.Shell 创建 .lnk。"""
    parent = os.path.dirname(lnk_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    # 转义 PowerShell 单引号
    def _ps_quote(s: str) -> str:
        return "'" + str(s).replace("'", "''") + "'"

    arguments = " ".join(args) if args else ""
    script = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut({_ps_quote(lnk_path)}); "
        f"$s.TargetPath = {_ps_quote(target)}; "
        f"$s.Arguments = {_ps_quote(arguments)}; "
        f"$s.WorkingDirectory = {_ps_quote(workdir)}; "
        f"$s.Save()"
    )
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            logger.warning(
                "创建快捷方式失败: rc=%s stderr=%s",
                completed.returncode,
                (completed.stderr or "").strip(),
            )
            return False
        return os.path.isfile(lnk_path)
    except Exception:
        logger.exception("创建开机自启快捷方式异常")
        return False


def set_autostart(enabled: bool) -> bool:
    """
    启用/禁用开机自启。
    Windows：创建或删除 Startup 目录下快捷方式。
    其他平台：返回 False（不崩溃）。
    """
    if platform.system() != "Windows":
        logger.info("非 Windows 平台不支持开机自启")
        return False

    lnk = startup_shortcut_path()
    try:
        if not enabled:
            if os.path.isfile(lnk):
                os.remove(lnk)
            return not os.path.isfile(lnk)

        exe, args, workdir = resolve_launch_command()
        return _create_shortcut_windows(lnk, exe, args, workdir)
    except Exception:
        logger.exception("设置开机自启失败")
        return False
