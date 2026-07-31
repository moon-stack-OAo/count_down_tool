# -*- coding: utf-8 -*-
"""跨平台播放后端：Windows / macOS / Linux。"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
from typing import Optional

logger = logging.getLogger("count_down_tool")


def _pkg():
    import services.sound as m

    return m


def _kill_proc_tree(proc: subprocess.Popen) -> None:
    """尽量彻底结束播放进程（含 Windows 子进程树 / mac|linux 进程组）。"""
    S = _pkg()
    if proc is None:
        return
    try:
        if proc.poll() is not None:
            return
    except (OSError, ValueError, AttributeError):
        return
    system = S.platform.system()
    if system == "Windows":
        try:
            # MediaPlayer/powershell 可能有子进程，仅 terminate 父进程会漏音
            S.subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=3,
            )
            return
        except (OSError, subprocess.SubprocessError, TimeoutError):
            logger.debug("taskkill 失败 pid=%s", getattr(proc, "pid", None), exc_info=True)
    elif system in ("Darwin", "Linux"):
        # start_new_session=True 时 afplay/ffplay 自成会话，killpg 可一并掐断
        pid = getattr(proc, "pid", None)
        if pid:
            try:
                pgid = S.os.getpgid(pid)
                S.os.killpg(pgid, signal.SIGTERM)
                try:
                    proc.wait(timeout=0.4)
                    return
                except (OSError, subprocess.TimeoutExpired, ValueError):
                    pass
                if proc.poll() is None:
                    try:
                        S.os.killpg(pgid, signal.SIGKILL)
                    except OSError:
                        logger.debug(
                            "killpg SIGKILL 失败 pid=%s pgid=%s",
                            pid,
                            pgid,
                            exc_info=True,
                        )
                    try:
                        proc.wait(timeout=0.3)
                    except (OSError, subprocess.TimeoutExpired, ValueError):
                        pass
                    if proc.poll() is not None:
                        return
            except OSError:
                logger.debug(
                    "killpg 失败 pid=%s，回退 terminate/kill",
                    pid,
                    exc_info=True,
                )
    try:
        if proc.poll() is None:
            proc.terminate()
    except (OSError, ProcessLookupError, ValueError):
        logger.debug("终止播放进程失败", exc_info=True)
    try:
        if proc.poll() is None:
            proc.kill()
    except (OSError, ProcessLookupError, ValueError):
        logger.debug("强制结束播放进程失败", exc_info=True)


def _halt_devices() -> None:
    """停止底层播放设备/进程，不取消异步 generation（供 play_file 复用）。"""
    S = _pkg()
    S.cancel_system_bell()
    system = S.platform.system()
    if system == "Windows":
        try:
            import winsound

            # 连调两次：部分驱动首次 PURGE 不可靠
            winsound.PlaySound(None, winsound.SND_PURGE)
            winsound.PlaySound(None, winsound.SND_PURGE)
        except (ImportError, OSError, RuntimeError, AttributeError):
            # ImportError：非 Windows 或伪造成 Windows 的测试环境无 winsound
            logger.debug("winsound 停止失败", exc_info=True)
        # 必须在创建 MCI 设备的同一线程 stop/close，否则错误 263 且音频不停
        try:
            S._mci_call("halt", timeout=3.0)
        except (OSError, RuntimeError, TimeoutError, AttributeError):
            logger.debug("MCI halt 失败", exc_info=True)

    with S._play_proc_lock:
        procs = list(S._play_procs)
        S._play_procs.clear()
        S._play_until = 0.0
        S._use_mci = False

    for p in procs:
        S._kill_proc_tree(p)


def stop_playback() -> None:
    """停止当前试听/结束音效（winsound / MCI / 外部播放进程 / 系统铃）。"""
    S = _pkg()
    S._bump_play_gen()
    with S._play_proc_lock:
        S._pending_until = 0.0
    # MCI 经专用线程 halt，与 play 同线程，可立刻掐断 mp3
    S._halt_devices()


def play_file(
        path: str,
        play_gen: Optional[int] = None,
        root=None,
        *,
        clear_pending_on_start: bool = False,
) -> bool:
    """播放一次完整文件。成功启动（或已调度到主线程）返回 True。

    play_gen 非空时：prepare（如 ncm 解密）结束后若已取消则不再开播。
    root 非空时：Windows 在主线程开播（winsound/部分驱动在后台线程不可靠）。
    clear_pending_on_start：主线程实际开播成功/失败后再清 pending（调度窗口期内保持
    is_sound_playing，避免停止试听按钮闪断）。
    """
    S = _pkg()
    play_path = S.prepare_playable_path(path)
    if not play_path:
        return False
    if S._is_play_cancelled(play_gen):
        return False

    def _start() -> bool:
        if S._is_play_cancelled(play_gen):
            if clear_pending_on_start:
                S._clear_pending_play(play_gen)
            return False
        # 仅停设备，不 bump generation（避免取消正在执行的异步试听任务）
        S._halt_devices()
        if S._is_play_cancelled(play_gen):
            if clear_pending_on_start:
                S._clear_pending_play(play_gen)
            return False
        system = S.platform.system()
        ok = False
        try:
            if system == "Windows":
                ok = S._play_windows(play_path)
            elif system == "Darwin":
                ok = S._play_macos(play_path)
            else:
                ok = S._play_linux(play_path)
            if S._is_play_cancelled(play_gen):
                S._halt_devices()
                ok = False
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError, TypeError):
            logger.debug("播放文件失败: %s", path, exc_info=True)
            ok = False
        # 主线程实际开播后再清 pending（成功有 _play_until；失败也要释放停止按钮）
        if clear_pending_on_start:
            S._clear_pending_play(play_gen)
        return bool(ok)

    # Windows：尽量在 Tk 主线程开播，避免设置窗/托盘异步线程里 winsound 无声
    if root is not None and S.platform.system() == "Windows":
        try:
            # 调度后立刻返回 True，但不要清 pending——等 _start 内实际开播后再清
            root.after(0, _start)
            return True
        except (RuntimeError, AttributeError):
            logger.debug("调度主线程播放失败，回退同步", exc_info=True)
    return _start()


def _play_windows(path: str) -> bool:
    """
    Windows 播放优先级：
    1) WAV → winsound 异步
    2) 非 WAV → PowerShell MediaPlayer（解码质量更好，减少卡顿）
    3) MediaPlayer 失败 → winmm MCI 回退
    4) 再失败 → startfile（可能弹播放器窗口）
    """
    S = _pkg()
    abs_path = os.path.abspath(path)
    est = S._estimate_audio_seconds(abs_path)
    ext = os.path.splitext(abs_path)[1].lower()
    if ext in (".wav", ".wave"):
        try:
            import winsound

            winsound.PlaySound(abs_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            S._mark_playing_until(est)
            return True
        except (ImportError, OSError, RuntimeError, AttributeError):
            logger.debug("winsound 播放失败", exc_info=True)

    if S._play_windows_media_player(abs_path, est):
        return True
    if S._play_windows_mci(abs_path, est):
        return True
    try:
        os.startfile(abs_path)  # type: ignore[attr-defined]
        S._mark_playing_until(est)
        return True
    except OSError:
        logger.debug("startfile 播放失败", exc_info=True)
        return False


def _play_windows_mci(path: str, est_seconds: float = 0.0) -> bool:
    """用 Windows MCI 打开并播放（mpegvideo 覆盖 mp3 等常见格式）。

    全部经专用线程，保证后续 stop 能在同一线程掐断。
    超时会 bump gen；此处再校验，丢弃迟到结果。
    """
    S = _pkg()
    try:
        abs_path = os.path.abspath(path)
        # 记录调用前 generation：超时 bump 后迟到的 ok 不得标记播放中
        with S._play_gen_lock:
            gen_before = S._play_gen
        r = S._mci_call("play", {"path": abs_path}, timeout=8.0)
        if not r.get("ok"):
            logger.debug(
                "MCI open/play 失败 err=%s path=%s", r.get("err"), path
            )
            return False
        with S._play_gen_lock:
            if S._play_gen != gen_before:
                # 超时/stop 已作废本路，丢弃迟到 play
                try:
                    S._mci_call("halt", timeout=2.0)
                except (OSError, RuntimeError, TimeoutError, AttributeError):
                    pass
                return False
        mci_len = float(r.get("length") or 0.0)
        S._mark_mci_playing()
        # MCI mode 查询偶发不准，始终用时长兜底，保证菜单「停止试听」可点
        S._mark_playing_until(max(est_seconds, mci_len, 1.0))
        return True
    except (OSError, RuntimeError, TimeoutError, TypeError, ValueError, AttributeError):
        logger.debug("MCI 播放异常", exc_info=True)
        return False


def _play_windows_media_player(path: str, est_seconds: float = 0.0) -> bool:
    """后台 PowerShell + MediaPlayer 播一次（不弹窗）。

    优先于 MCI：对 mp3/flac/m4a 等解码更稳，减少一卡一卡。
    Open 后立刻 Play，同时轮询 NaturalDuration 以确定 Sleep 结束时间。
    """
    S = _pkg()
    try:
        ps_path = path.replace("'", "''")
        script = (
            f"$p = New-Object System.Windows.Media.MediaPlayer; "
            f"$rp = (Resolve-Path -LiteralPath '{ps_path}').Path; "
            f"$p.Open([Uri]::new($rp)); "
            f"$p.Volume = 1; "
            f"$p.Play(); "
            f"$sw = [Diagnostics.Stopwatch]::StartNew(); "
            f"while (-not $p.NaturalDuration.HasTimeSpan) {{ "
            f"  if ($sw.ElapsedMilliseconds -gt 8000) {{ break }}; "
            f"  Start-Sleep -Milliseconds 30 "
            f"}}; "
            f"$ms = if ($p.NaturalDuration.HasTimeSpan) {{ "
            f"  [int]$p.NaturalDuration.TimeSpan.TotalMilliseconds "
            f"}} else {{ 30000 }}; "
            f"if ($ms -lt 200) {{ $ms = 200 }}; "
            f"$left = $ms - [int]$sw.ElapsedMilliseconds; "
            f"if ($left -gt 0) {{ Start-Sleep -Milliseconds $left }}; "
            f"$p.Stop(); $p.Close()"
        )
        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        proc = S.subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        S._track_proc(proc)
        # 进程存活为主；时长兜底防止 poll 异常
        S._mark_playing_until(max(est_seconds, 1.0))
        return True
    except (OSError, subprocess.SubprocessError, TypeError, ValueError):
        logger.debug("MediaPlayer 播放失败", exc_info=True)
        return False


def _play_macos(path: str) -> bool:
    """macOS：优先 afplay；失败时若有 ffplay 则回退。"""
    S = _pkg()
    est = S._probe_macos_audio_seconds(path)
    for cmd in (
            ["afplay", path],
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
    ):
        try:
            proc = S.subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            S._track_proc(proc)
            S._mark_playing_until(est)
            return True
        except FileNotFoundError:
            logger.debug("mac 播放器不可用: %s", cmd[0])
            continue
        except (OSError, subprocess.SubprocessError, ValueError):
            logger.debug("mac 播放失败: %s", cmd[0], exc_info=True)
            continue
    return False


def _play_linux(path: str) -> bool:
    S = _pkg()
    for cmd in (
            ["paplay", path],
            ["aplay", path],
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
    ):
        try:
            proc = S.subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            S._track_proc(proc)
            S._mark_playing_until(S._estimate_audio_seconds(path))
            return True
        except FileNotFoundError:
            continue
        except (OSError, subprocess.SubprocessError, ValueError):
            logger.debug("linux 播放失败: %s", cmd[0], exc_info=True)
    return False
