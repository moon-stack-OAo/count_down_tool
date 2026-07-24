# -*- coding: utf-8 -*-
"""自动更新：查 GitHub Release、下载；Windows 可替换 exe，macOS 仅下载。"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

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

ProgressCb = Optional[Callable[[int, int], None]]  # received, total(-1 if unknown)


@dataclass(frozen=True)
class ReleaseInfo:
    """最新 Release 摘要。"""

    version: str
    tag_name: str
    body: str
    html_url: str
    assets: Tuple[Dict[str, Any], ...]


@dataclass(frozen=True)
class UpdateCheckResult:
    """版本检查结果。"""

    current_version: str
    latest_version: str
    has_update: bool
    release: Optional[ReleaseInfo]
    asset_name: Optional[str]
    asset_url: Optional[str]
    asset_size: int
    platform_key: str  # windows | darwin | other
    error: Optional[str] = None


def parse_version(text: str) -> Tuple[int, int, int]:
    """将 v1.2.3 / 1.2.3-beta 等解析为 (major, minor, patch)。"""
    s = (text or "").strip()
    if s.lower().startswith("v"):
        s = s[1:]
    parts: List[int] = []
    for chunk in s.split("."):
        m = re.match(r"(\d+)", chunk)
        parts.append(int(m.group(1)) if m else 0)
        if len(parts) >= 3:
            break
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def is_newer_version(remote: str, local: str) -> bool:
    """remote 是否严格大于 local。"""
    return parse_version(remote) > parse_version(local)


def normalize_tag_version(tag: str) -> str:
    t = (tag or "").strip()
    if t.lower().startswith("v"):
        t = t[1:]
    return t


def platform_key(system: Optional[str] = None) -> str:
    s = system or platform.system()
    if s == "Windows":
        return "windows"
    if s == "Darwin":
        return "darwin"
    return "other"


def platform_asset_suffix(
    system: Optional[str] = None,
    machine: Optional[str] = None,
) -> Optional[str]:
    """
    返回 Release 附件后缀（不含版本前缀）。
    例：win64.zip / mac-arm64.zip / mac-x86_64.zip
    """
    sys_name = system or platform.system()
    mach = (machine or platform.machine() or "").lower()
    if sys_name == "Windows":
        return "win64.zip"
    if sys_name == "Darwin":
        if mach in ("arm64", "aarch64"):
            return "mac-arm64.zip"
        return "mac-x86_64.zip"
    return None


def expected_asset_name(version: str, system: Optional[str] = None, machine: Optional[str] = None) -> Optional[str]:
    suffix = platform_asset_suffix(system, machine)
    if not suffix:
        return None
    ver = normalize_tag_version(version)
    return f"count_down_tool-{ver}-{suffix}"


def select_asset(
    assets: Sequence[Dict[str, Any]],
    version: str,
    system: Optional[str] = None,
    machine: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """按平台从 assets 中选中 zip；优先精确文件名，再按后缀匹配。"""
    want = expected_asset_name(version, system, machine)
    suffix = platform_asset_suffix(system, machine)
    if not suffix:
        return None
    by_name = {str(a.get("name") or ""): a for a in assets if isinstance(a, dict)}
    if want and want in by_name:
        return by_name[want]
    # 宽松：名字以正确后缀结尾
    for name, asset in by_name.items():
        if name.endswith(suffix) and name.startswith("count_down_tool-"):
            return asset
    return None


def _http_get_json(url: str, timeout: float = 15.0) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("GitHub API 返回非对象 JSON")
    return data


def fetch_latest_release(timeout: float = 15.0) -> ReleaseInfo:
    """请求 GitHub releases/latest。"""
    data = _http_get_json(GITHUB_API_LATEST, timeout=timeout)
    tag = str(data.get("tag_name") or "")
    version = normalize_tag_version(tag)
    assets_raw = data.get("assets") or []
    assets: List[Dict[str, Any]] = [
        a for a in assets_raw if isinstance(a, dict)
    ]
    return ReleaseInfo(
        version=version,
        tag_name=tag,
        body=str(data.get("body") or ""),
        html_url=str(data.get("html_url") or GITHUB_RELEASES_PAGE),
        assets=tuple(assets),
    )


def check_for_update(
    current_version: str,
    system: Optional[str] = None,
    machine: Optional[str] = None,
    timeout: float = 15.0,
    ignored_version: Optional[str] = None,
) -> UpdateCheckResult:
    """
    检查是否有新版本。
    ignored_version 非空且等于 latest 时 has_update=False（用户忽略此版本）。
    """
    pk = platform_key(system)
    try:
        release = fetch_latest_release(timeout=timeout)
    except Exception as exc:
        logger.info("检查更新失败: %s", exc)
        return UpdateCheckResult(
            current_version=current_version,
            latest_version="",
            has_update=False,
            release=None,
            asset_name=None,
            asset_url=None,
            asset_size=0,
            platform_key=pk,
            error=str(exc),
        )

    newer = is_newer_version(release.version, current_version)
    if ignored_version and normalize_tag_version(ignored_version) == release.version:
        newer = False

    asset = select_asset(release.assets, release.version, system, machine) if newer else None
    name = str(asset.get("name") or "") if asset else None
    url = str(asset.get("browser_download_url") or "") if asset else None
    size = int(asset.get("size") or 0) if asset else 0

    # 有新版本但本平台无包：仍 has_update，但 asset 为空，UI 引导打开网页
    return UpdateCheckResult(
        current_version=current_version,
        latest_version=release.version,
        has_update=newer,
        release=release,
        asset_name=name or None,
        asset_url=url or None,
        asset_size=size,
        platform_key=pk,
        error=None,
    )


def download_file(
    url: str,
    dest_path: str,
    timeout: float = 60.0,
    progress: ProgressCb = None,
) -> str:
    """下载到 dest_path，返回绝对路径。"""
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)) or ".", exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = -1
        try:
            total = int(resp.headers.get("Content-Length") or -1)
        except (TypeError, ValueError):
            total = -1
        received = 0
        chunk = 64 * 1024
        with open(dest_path, "wb") as out:
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                out.write(buf)
                received += len(buf)
                if progress:
                    progress(received, total)
    return os.path.abspath(dest_path)


def extract_windows_exe(zip_path: str, dest_dir: str) -> str:
    """从 win zip 中取出 count_down_tool.exe，返回 exe 绝对路径。"""
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        exe_name = None
        for n in names:
            base = os.path.basename(n.replace("\\", "/"))
            if base.lower() == "count_down_tool.exe":
                exe_name = n
                break
        if not exe_name:
            raise FileNotFoundError("zip 中未找到 count_down_tool.exe")
        target = os.path.join(dest_dir, "count_down_tool.exe")
        with zf.open(exe_name) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
    return os.path.abspath(target)


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


def write_windows_replace_script(
    script_path: str,
    target_exe: str,
    source_exe: str,
    pid: int,
    zip_path: Optional[str] = None,
) -> str:
    """
    生成 bat：等待 PID 退出 → 覆盖 exe → 启动 → 清理。
    返回 script_path。
    """
    # 用短路径风格避免引号问题；全部加引号
    lines = [
        "@echo off",
        "setlocal",
        f'set "TARGET={target_exe}"',
        f'set "SOURCE={source_exe}"',
        f"set PID={int(pid)}",
        ":waitloop",
        'tasklist /FI "PID eq %PID%" 2>NUL | find "%PID%" >NUL',
        "if not errorlevel 1 (",
        "  timeout /t 1 /nobreak >NUL",
        "  goto waitloop",
        ")",
        "timeout /t 1 /nobreak >NUL",
        'copy /Y "%SOURCE%" "%TARGET%" >NUL',
        "if errorlevel 1 (",
        "  echo Update failed: cannot copy executable.",
        "  pause",
        "  exit /b 1",
        ")",
        'start "" "%TARGET%"',
        'del /f /q "%SOURCE%" >NUL 2>&1',
    ]
    if zip_path:
        lines.append(f'del /f /q "{zip_path}" >NUL 2>&1')
    lines.extend(
        [
            'del /f /q "%~f0" >NUL 2>&1',
            "endlocal",
        ]
    )
    parent = os.path.dirname(script_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(script_path, "w", encoding="gbk", errors="replace", newline="\r\n") as f:
        f.write("\r\n".join(lines) + "\r\n")
    return os.path.abspath(script_path)


def launch_windows_replace_and_exit_prep(
    target_exe: str,
    new_exe: str,
    zip_path: Optional[str] = None,
) -> str:
    """
    启动替换脚本（不等待）。调用方应随后退出进程。
    返回脚本路径。
    """
    import subprocess

    work = tempfile.mkdtemp(prefix="cdt_update_")
    script = os.path.join(work, "apply_update.bat")
    write_windows_replace_script(
        script,
        target_exe=os.path.abspath(target_exe),
        source_exe=os.path.abspath(new_exe),
        pid=os.getpid(),
        zip_path=os.path.abspath(zip_path) if zip_path else None,
    )
    # CREATE_NO_WINDOW + DETACHED 避免卡在控制台
    creation = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creation |= subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    if hasattr(subprocess, "DETACHED_PROCESS"):
        creation |= subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
    subprocess.Popen(
        ["cmd.exe", "/c", script],
        cwd=work,
        close_fds=True,
        creationflags=creation,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return script


def apply_windows_update_from_zip(zip_path: str, target_exe: Optional[str] = None) -> str:
    """
    解压 zip 并启动替换脚本。返回脚本路径；调用方需退出应用。
    """
    target = target_exe or current_executable_path()
    work = tempfile.mkdtemp(prefix="cdt_new_exe_")
    new_exe = extract_windows_exe(zip_path, work)
    return launch_windows_replace_and_exit_prep(target, new_exe, zip_path=zip_path)


def truncate_release_notes(body: str, max_len: int = 600) -> str:
    text = (body or "").strip()
    if not text:
        return "（无更新说明）"
    # 去掉过长 markdown 噪声
    text = re.sub(r"\r\n", "\n", text)
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text
