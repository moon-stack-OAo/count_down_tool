# -*- coding: utf-8 -*-
"""播放 generation / pending / MCI worker 状态与控制。"""

from __future__ import annotations

import logging
import queue
import time
from typing import Optional, Tuple

from services.sound.constants import (
    _PENDING_PREPARE_SECONDS,
    _WIN_MCI_ALIAS,
)

logger = logging.getLogger("count_down_tool")


def _pkg():
    import services.sound as m

    return m


def _bump_play_gen() -> int:
    """取消进行中的异步播放任务，返回新 generation。"""
    S = _pkg()
    with S._play_gen_lock:
        S._play_gen += 1
        return S._play_gen


def _is_play_cancelled(play_gen: Optional[int]) -> bool:
    if play_gen is None:
        return False
    S = _pkg()
    with S._play_gen_lock:
        return play_gen != S._play_gen


def _set_pending_play(seconds: float = _PENDING_PREPARE_SECONDS) -> None:
    S = _pkg()
    sec = max(0.3, float(seconds))
    with S._play_proc_lock:
        S._pending_until = max(S._pending_until, time.monotonic() + sec)


def _clear_pending_play(play_gen: Optional[int] = None) -> None:
    """清除 pending；若指定 play_gen 则仅当仍是当前任务时清除。"""
    S = _pkg()
    if play_gen is not None and S._is_play_cancelled(play_gen):
        return
    with S._play_proc_lock:
        S._pending_until = 0.0


def _ensure_mci_worker() -> None:
    """启动 MCI 工作线程（仅 Windows，进程内一次）。"""
    S = _pkg()
    if S.platform.system() != "Windows":
        return
    with S._mci_thread_lock:
        if S._mci_thread is not None and S._mci_thread.is_alive():
            return
        S._mci_cmd_q = queue.Queue()
        S._mci_ready.clear()

        def _worker() -> None:
            import ctypes

            def _send(cmd: str) -> Tuple[int, str]:
                buf = ctypes.create_unicode_buffer(256)
                try:
                    err = int(
                        ctypes.windll.winmm.mciSendStringW(  # type: ignore[attr-defined]
                            cmd, buf, 255, 0
                        )
                    )
                except (OSError, AttributeError, TypeError, ValueError):
                    return -1, ""
                return err, buf.value or ""

            S._mci_ready.set()
            while True:
                item = S._mci_cmd_q.get()
                if item is None:
                    # 退出前尽量关掉设备
                    try:
                        _send(f"stop {_WIN_MCI_ALIAS}")
                        _send(f"close {_WIN_MCI_ALIAS}")
                    except (OSError, AttributeError, TypeError, ValueError):
                        pass
                    break
                op, args, result_box, done_evt = item
                try:
                    if op == "halt":
                        _send(f"stop {_WIN_MCI_ALIAS}")
                        _send(f"seek {_WIN_MCI_ALIAS} to start")
                        _send(f"close {_WIN_MCI_ALIAS}")
                        if result_box is not None:
                            result_box["ok"] = True
                    elif op == "play":
                        path = args.get("path", "")
                        mci_path = path.replace("\\", "/")
                        _send(f"close {_WIN_MCI_ALIAS}")
                        err, _ = _send(
                            f'open "{mci_path}" type mpegvideo alias {_WIN_MCI_ALIAS}'
                        )
                        if err != 0:
                            err, _ = _send(
                                f'open "{mci_path}" alias {_WIN_MCI_ALIAS}'
                            )
                        if err != 0:
                            if result_box is not None:
                                result_box["ok"] = False
                                result_box["err"] = err
                        else:
                            err, _ = _send(f"play {_WIN_MCI_ALIAS}")
                            if err != 0:
                                _send(f"close {_WIN_MCI_ALIAS}")
                                if result_box is not None:
                                    result_box["ok"] = False
                                    result_box["err"] = err
                            else:
                                # 读时长（毫秒）
                                length_sec = 0.0
                                err_l, raw = _send(
                                    f"status {_WIN_MCI_ALIAS} length"
                                )
                                if err_l == 0 and raw.strip():
                                    try:
                                        val = float(raw.strip())
                                        if val > 1000:
                                            length_sec = max(0.3, val / 1000.0 + 0.3)
                                        else:
                                            length_sec = max(0.3, val + 0.3)
                                    except ValueError:
                                        pass
                                if result_box is not None:
                                    result_box["ok"] = True
                                    result_box["length"] = length_sec
                    elif op == "status":
                        err, val = _send(f"status {_WIN_MCI_ALIAS} mode")
                        if result_box is not None:
                            result_box["err"] = err
                            result_box["mode"] = (val or "").strip().lower()
                    else:
                        if result_box is not None:
                            result_box["ok"] = False
                except (OSError, AttributeError, TypeError, ValueError, KeyError):
                    logger.debug("MCI worker 执行失败 op=%s", op, exc_info=True)
                    if result_box is not None:
                        result_box["ok"] = False
                finally:
                    if done_evt is not None:
                        done_evt.set()

        S._mci_thread = S.threading.Thread(
            target=_worker, name="CdtMciWorker", daemon=True
        )
        S._mci_thread.start()
    S._mci_ready.wait(timeout=3.0)


def _mci_call(op: str, args: Optional[dict] = None, timeout: float = 5.0) -> dict:
    """向 MCI 工作线程投递命令并等待结果。

    超时则 bump generation，使迟到的 play 结果被上层丢弃（避免卡死线程后叠播）。
    """
    S = _pkg()
    S._ensure_mci_worker()
    if S._mci_cmd_q is None:
        return {"ok": False}
    result_box: dict = {}
    done_evt = S.threading.Event()
    S._mci_cmd_q.put((op, args or {}, result_box, done_evt))
    if not done_evt.wait(timeout=timeout):
        logger.debug("MCI 命令超时 op=%s", op)
        # 超时：作废进行中的播放代数，迟到的 play 不应再标记为播放中
        if op == "play":
            S._bump_play_gen()
        return {"ok": False, "timeout": True}
    return result_box


def _mci_is_playing() -> bool:
    """查询 MCI 是否仍在 play（必须经专用线程）。"""
    S = _pkg()
    if S.platform.system() != "Windows":
        return False
    try:
        r = S._mci_call("status", timeout=1.0)
        return r.get("err", -1) == 0 and r.get("mode") == "playing"
    except Exception:
        return False


def is_sound_playing() -> bool:
    """是否仍在播放（菜单置灰用；进程结束 / 截止时间到 / MCI 停则视为否）。"""
    S = _pkg()
    now = time.monotonic()
    with S._play_proc_lock:
        if S._play_procs:
            S._play_procs[:] = [p for p in S._play_procs if p.poll() is None]
        alive = any(p.poll() is None for p in list(S._play_procs))
        until = S._play_until
        pending = S._pending_until
        use_mci = S._use_mci

    if alive:
        return True
    # MCI：时长窗口内直接视为播放中，避免频繁 status 查询干扰播放线程
    if use_mci:
        if now < until:
            return True
        if S._mci_is_playing():
            return True
    elif now < until:
        return True
    if now < pending:
        return True

    with S._play_proc_lock:
        if not any(p.poll() is None for p in S._play_procs):
            S._play_until = 0.0
            S._use_mci = False
            if time.monotonic() >= S._pending_until:
                S._pending_until = 0.0
    return False


def _track_proc(proc) -> None:
    S = _pkg()
    with S._play_proc_lock:
        S._play_procs.append(proc)


def _mark_playing_until(seconds: float) -> None:
    """标记一段时间内视为播放中（无进程句柄时）。"""
    S = _pkg()
    sec = max(0.3, float(seconds))
    with S._play_proc_lock:
        S._play_until = max(S._play_until, time.monotonic() + sec)


def _mark_mci_playing() -> None:
    S = _pkg()
    with S._play_proc_lock:
        S._use_mci = True
