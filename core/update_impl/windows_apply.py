# -*- coding: utf-8 -*-
"""Windows 静默替换脚本与应用更新。"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from core.update_impl.extract import extract_windows_exe
from core.update_impl.util import current_executable_path


def _ps_single_quoted(path: str) -> str:
    """PowerShell 单引号字符串（内部 ' 写成 ''）。"""
    return "'" + (path or "").replace("'", "''") + "'"


def write_windows_replace_script(
    script_path: str,
    target_exe: str,
    source_exe: str,
    pid: int,
    zip_path: Optional[str] = None,
) -> str:
    """
    生成静默 PowerShell：等待 PID 退出 → 整目录同步（onedir）→ 校验 → 启动 → 清理。

    将 source 所在目录的全部内容复制到 target 所在目录（覆盖），
    避免只替换单个 onefile exe 后启动仍解压到 _MEI 导致缺 python3xx.dll。
    不再使用 bat + tasklist/find。
    返回 script_path。
    """
    target_abs = os.path.abspath(target_exe)
    source_abs = os.path.abspath(source_exe)
    target_dir = os.path.dirname(target_abs) or "."
    source_dir = os.path.dirname(source_abs) or "."
    zip_abs = os.path.abspath(zip_path) if zip_path else ""
    log_path = os.path.join(
        os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir(),
        "count_down_tool_update.log",
    )
    lines = [
        "$ErrorActionPreference = 'Stop'",
        f"$target = {_ps_single_quoted(target_abs)}",
        f"$source = {_ps_single_quoted(source_abs)}",
        f"$targetDir = {_ps_single_quoted(target_dir)}",
        f"$sourceDir = {_ps_single_quoted(source_dir)}",
        f"$pidWait = {int(pid)}",
        f"$zipPath = {_ps_single_quoted(zip_abs)}",
        f"$logPath = {_ps_single_quoted(log_path)}",
        "$self = $MyInvocation.MyCommand.Path",
        "function Write-UpdateLog([string]$msg) {",
        "  try {",
        "    $line = ('[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg)",
        "    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue",
        "  } catch {}",
        "}",
        "function Test-ExeReady([string]$path) {",
        "  if (-not (Test-Path -LiteralPath $path)) { return $false }",
        "  $item = Get-Item -LiteralPath $path -ErrorAction SilentlyContinue",
        "  if (-not $item -or $item.Length -lt 1024) { return $false }",
        "  try {",
        "    $fs = [System.IO.File]::Open($path, 'Open', 'Read', 'None')",
        "    try {",
        "      $buf = New-Object byte[] 2",
        "      $n = $fs.Read($buf, 0, 2)",
        "      if ($n -lt 2 -or $buf[0] -ne 0x4D -or $buf[1] -ne 0x5A) { return $false }",
        "    } finally { $fs.Close() }",
        "  } catch { return $false }",
        "  return $true",
        "}",
        "Write-UpdateLog 'update script start (onedir sync)'",
        "$deadline = (Get-Date).AddSeconds(120)",
        "while ((Get-Date) -lt $deadline) {",
        "  $p = Get-Process -Id $pidWait -ErrorAction SilentlyContinue",
        "  if (-not $p) { break }",
        "  Start-Sleep -Milliseconds 500",
        "}",
        "$nameDeadline = (Get-Date).AddSeconds(30)",
        "while ((Get-Date) -lt $nameDeadline) {",
        "  $left = @(Get-Process -Name 'count_down_tool' -ErrorAction SilentlyContinue |",
        "    Where-Object { $_.Id -ne $pidWait })",
        "  if ($left.Count -eq 0) { break }",
        "  Start-Sleep -Milliseconds 500",
        "}",
        "Start-Sleep -Seconds 2",
        "if (-not (Test-ExeReady $source)) {",
        "  Write-UpdateLog 'source exe not ready'",
        "  exit 2",
        "}",
        "if (-not (Test-Path -LiteralPath $sourceDir)) {",
        "  Write-UpdateLog 'source dir missing'",
        "  exit 2",
        "}",
        "if (-not (Test-Path -LiteralPath $targetDir)) {",
        "  New-Item -ItemType Directory -Path $targetDir -Force | Out-Null",
        "}",
        "$ss = (Get-Item -LiteralPath $source).Length",
        "Write-UpdateLog ('source size={0} dir={1}' -f $ss, $sourceDir)",
        "$ok = $false",
        "for ($i = 0; $i -lt 15; $i++) {",
        "  try {",
        "    # 整目录覆盖：exe + _internal/python*.dll 等一并同步",
        "    Copy-Item -Path (Join-Path $sourceDir '*') -Destination $targetDir -Recurse -Force",
        "    if (-not (Test-ExeReady $target)) { throw 'target exe not ready' }",
        "    $ts = (Get-Item -LiteralPath $target).Length",
        "    if ($ts -lt 1024) { throw 'target exe too small' }",
        "    $ok = $true",
        "    Write-UpdateLog ('dir sync ok target_size={0} attempt={1}' -f $ts, ($i + 1))",
        "    break",
        "  } catch {",
        "    Write-UpdateLog ('sync attempt {0} failed: {1}' -f ($i + 1), $_.Exception.Message)",
        "  }",
        "  Start-Sleep -Seconds 1",
        "}",
        "if (-not $ok) {",
        "  Write-UpdateLog 'dir sync failed'",
        "  exit 1",
        "}",
        "$readyDeadline = (Get-Date).AddSeconds(20)",
        "while ((Get-Date) -lt $readyDeadline) {",
        "  if (Test-ExeReady $target) { break }",
        "  Start-Sleep -Milliseconds 500",
        "}",
        "Start-Sleep -Seconds 2",
        "Write-UpdateLog 'starting new process'",
        "Start-Process -FilePath $target -WorkingDirectory $targetDir",
        "Start-Sleep -Seconds 2",
        # 清理临时源目录与 zip（勿删用户安装目录）
        "if ($sourceDir -and ($sourceDir -ne $targetDir)) {",
        "  try { Remove-Item -LiteralPath $sourceDir -Recurse -Force -ErrorAction SilentlyContinue } catch {}",
        "}",
        "if ($zipPath) {",
        "  try { Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue } catch {}",
        "}",
        "try { Remove-Item -LiteralPath $self -Force -ErrorAction SilentlyContinue } catch {}",
        "Write-UpdateLog 'update script done'",
        "exit 0",
    ]
    parent = os.path.dirname(script_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    # UTF-8 BOM：Windows PowerShell 5.1 更稳妥识别中文路径
    text = "\r\n".join(lines) + "\r\n"
    with open(script_path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(text)
    return os.path.abspath(script_path)


def launch_windows_replace_and_exit_prep(
    target_exe: str,
    new_exe: str,
    zip_path: Optional[str] = None,
) -> str:
    """
    启动静默替换脚本（不等待）。调用方应随后退出进程。
    返回脚本路径。
    """
    import subprocess

    work = tempfile.mkdtemp(prefix="cdt_update_")
    script = os.path.join(work, "apply_update.ps1")
    write_windows_replace_script(
        script,
        target_exe=os.path.abspath(target_exe),
        source_exe=os.path.abspath(new_exe),
        pid=os.getpid(),
        zip_path=os.path.abspath(zip_path) if zip_path else None,
    )
    # 仅 CREATE_NO_WINDOW：DETACHED_PROCESS 在部分环境下会导致
    # powershell -File 静默起不来（替换脚本不执行）。
    creation = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creation |= subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creation |= subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    startup = None
    try:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0  # SW_HIDE
    except (AttributeError, OSError, ValueError):
        startup = None
    # 用 -Command 执行脚本内容，避免 -File + 临时目录偶发策略问题
    # 仍 -WindowStyle Hidden，不弹控制台
    ps_cmd = (
        f"$ErrorActionPreference='Stop'; "
        f"& {_ps_single_quoted(os.path.abspath(script))}"
    )
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-Command",
            ps_cmd,
        ],
        cwd=work,
        close_fds=True,
        creationflags=creation,
        startupinfo=startup,
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
