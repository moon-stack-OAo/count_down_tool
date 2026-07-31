# -*- coding: utf-8 -*-
"""结束提示音：系统铃与异步播放入口。"""

from __future__ import annotations

import logging
from typing import Optional

from services.sound.constants import _SYSTEM_BELL_INTERVAL_MS, _SYSTEM_BELL_TIMES

logger = logging.getLogger("count_down_tool")


def _pkg():
    import services.sound as m

    return m


def ring_system_bell(root) -> None:
    """系统铃一次（可从后台线程调度到主线程调用）。"""
    if root is None:
        return
    try:
        root.bell()
    except (RuntimeError, AttributeError):
        logger.debug("bell 失败", exc_info=True)


def ring_system_bell_times(root, times: int = _SYSTEM_BELL_TIMES) -> None:
    """系统铃循环 times 次（主线程 after 调度，不阻塞）。"""
    S = _pkg()
    if root is None or times <= 0:
        return
    n = int(times)
    with S._bell_lock:
        S._bell_gen += 1
        gen = S._bell_gen
    # 菜单「停止试听」可点时长 ≈ 间隔 * 次数
    S._mark_playing_until(n * (_SYSTEM_BELL_INTERVAL_MS / 1000.0) + 0.4)

    def _ring(left: int) -> None:
        with S._bell_lock:
            if gen != S._bell_gen:
                return
        if left <= 0:
            return
        S.ring_system_bell(root)
        if left > 1:
            try:
                root.after(_SYSTEM_BELL_INTERVAL_MS, lambda: _ring(left - 1))
            except (RuntimeError, AttributeError):
                for _ in range(left - 1):
                    with S._bell_lock:
                        if gen != S._bell_gen:
                            return
                    S.ring_system_bell(root)

    try:
        root.after(0, lambda: _ring(n))
    except (RuntimeError, AttributeError):
        for _ in range(n):
            with S._bell_lock:
                if gen != S._bell_gen:
                    return
            S.ring_system_bell(root)


def cancel_system_bell() -> None:
    """取消尚未响完的系统铃循环。"""
    S = _pkg()
    with S._bell_lock:
        S._bell_gen += 1


def play_finish_sound(
        root,
        *,
        muted: bool,
        sound_id: str,
        custom_path: str = "",
        play_gen: Optional[int] = None,
) -> bool:
    """结束提示：静音跳过；文件类完整播一次；系统铃循环三次。

    play_gen 非空时：若 generation 已被 stop/新任务取消，则不启动播放。
    返回 True 表示 pending 已交由主线程 _start 清理（异步 finally 勿再清），
    避免 Windows after 调度窗口期内 is_sound_playing 闪断。
    """
    S = _pkg()
    if muted:
        return False
    if S._is_play_cancelled(play_gen):
        return False
    mode, path = S.resolve_play_path(sound_id, custom_path)
    if mode == "file" and path:
        # 解密等可能较慢：prepare/开播前在 play_file 内再检查 generation
        if S._is_play_cancelled(play_gen):
            return False
        # Windows 经 after 调度：pending 由 play_file._start 清；同步路径此处清
        defer_pending = (
                root is not None and S.platform.system() == "Windows"
        )
        if S.play_file(
                path,
                play_gen=play_gen,
                root=root,
                clear_pending_on_start=defer_pending,
        ):
            if not defer_pending:
                S._clear_pending_play(play_gen)
            # defer 时 pending 仍由主线程 _start 负责
            return bool(defer_pending)
        if S._is_play_cancelled(play_gen):
            return False
        logger.debug("文件播放失败，回退系统铃: %s", path)
    if S._is_play_cancelled(play_gen):
        return False
    # 系统默认音效：循环三次
    S.ring_system_bell_times(root, _SYSTEM_BELL_TIMES)
    S._clear_pending_play(play_gen)
    return False


def _finish_async_pending(play_gen: Optional[int]) -> None:
    """异步任务结束时清 pending。

    仅清理「当前」任务的 pending；已被 cancel 的旧任务绝不能清掉新任务的 pending，
    否则会出现：第二次试听后 is_sound_playing 变 False → 停止试听仍灰、试听可连点叠播。
    """
    S = _pkg()
    if play_gen is not None and S._is_play_cancelled(play_gen):
        return
    S._clear_pending_play(play_gen)


def play_finish_sound_async(root, *, muted: bool, sound_id: str, custom_path: str = "") -> None:
    """在后台线程解析并启动播放，避免卡 UI。

    每次调用递增 generation；stop_playback 会取消尚未开播的旧任务。
    """
    S = _pkg()
    if muted:
        return
    play_gen = S._bump_play_gen()
    # 立刻停掉上一路，避免准备/解密期间新旧重叠
    S._halt_devices()
    S._set_pending_play()

    def _run():
        defer_pending = False
        try:
            if S._is_play_cancelled(play_gen):
                return
            defer_pending = bool(
                S.play_finish_sound(
                    root,
                    muted=muted,
                    sound_id=sound_id,
                    custom_path=custom_path,
                    play_gen=play_gen,
                )
            )
        finally:
            # 主线程 after 尚未执行时勿清 pending，否则停止试听会闪灰
            if not defer_pending:
                S._finish_async_pending(play_gen)

    try:
        S.threading.Thread(target=_run, daemon=True).start()
    except RuntimeError:
        # 线程创建失败时同步回退
        defer_pending = False
        try:
            defer_pending = bool(
                S.play_finish_sound(
                    root,
                    muted=muted,
                    sound_id=sound_id,
                    custom_path=custom_path,
                    play_gen=play_gen,
                )
            )
        finally:
            if not defer_pending:
                S._finish_async_pending(play_gen)
