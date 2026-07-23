# -*- coding: utf-8 -*-
"""结束提示音：预设 / 自定义文件 / 系统铃；支持静音。"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import threading
from typing import Optional, Tuple

from core.countdown_core import resource_path

logger = logging.getLogger("count_down_tool")

# 配置值 sound_id：system | soft | chime | alert | custom
SOUND_ID_SYSTEM = "system"
SOUND_ID_SOFT = "soft"
SOUND_ID_CHIME = "chime"
SOUND_ID_ALERT = "alert"
SOUND_ID_CUSTOM = "custom"

SOUND_PRESETS = (
    (SOUND_ID_SYSTEM, "系统铃声"),
    (SOUND_ID_SOFT, "柔和提示"),
    (SOUND_ID_CHIME, "清脆钟声"),
    (SOUND_ID_ALERT, "紧急警报"),
)

_PRESET_FILES = {
    SOUND_ID_SOFT: os.path.join("assets", "sounds", "soft.wav"),
    SOUND_ID_CHIME: os.path.join("assets", "sounds", "chime.wav"),
    SOUND_ID_ALERT: os.path.join("assets", "sounds", "alert.wav"),
}

_AUDIO_EXTS = (".wav", ".wave", ".mp3", ".aiff", ".aif", ".m4a", ".aac", ".ogg", ".flac")


def normalize_sound_id(value) -> str:
    if not isinstance(value, str):
        return SOUND_ID_SOFT
    v = value.strip().lower()
    if v in (SOUND_ID_SYSTEM, SOUND_ID_SOFT, SOUND_ID_CHIME, SOUND_ID_ALERT, SOUND_ID_CUSTOM):
        return v
    return SOUND_ID_SOFT


def normalize_sound_path(value) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def preset_path(sound_id: str) -> Optional[str]:
    rel = _PRESET_FILES.get(sound_id)
    if not rel:
        return None
    path = resource_path(rel)
    return path if os.path.isfile(path) else None


def resolve_play_path(sound_id: str, custom_path: str = "") -> Tuple[str, Optional[str]]:
    """返回 (mode, path)。mode: mute 不在此处理；system | file。"""
    sid = normalize_sound_id(sound_id)
    if sid == SOUND_ID_SYSTEM:
        return "system", None
    if sid == SOUND_ID_CUSTOM:
        path = normalize_sound_path(custom_path)
        if path and os.path.isfile(path):
            return "file", path
        # 自定义失效时回退柔和预设
        fallback = preset_path(SOUND_ID_SOFT)
        if fallback:
            return "file", fallback
        return "system", None
    path = preset_path(sid)
    if path:
        return "file", path
    return "system", None


def is_audio_file(path: str) -> bool:
    if not path or not os.path.isfile(path):
        return False
    ext = os.path.splitext(path)[1].lower()
    return ext in _AUDIO_EXTS


def play_file(path: str) -> bool:
    """异步播放一次完整文件。成功启动返回 True。"""
    if not path or not os.path.isfile(path):
        return False
    system = platform.system()
    try:
        if system == "Windows":
            return _play_windows(path)
        if system == "Darwin":
            return _play_macos(path)
        return _play_linux(path)
    except Exception:
        logger.debug("播放文件失败: %s", path, exc_info=True)
        return False


def _play_windows(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".wav", ".wave"):
        try:
            import winsound

            # SND_FILENAME | SND_ASYNC：不阻塞主线程
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return True
        except Exception:
            logger.debug("winsound 播放失败", exc_info=True)
    # 非 wav 或 winsound 失败：用系统默认关联程序静默播放（尽量不弹窗）
    try:
        os.startfile(path)  # type: ignore[attr-defined]
        return True
    except Exception:
        logger.debug("startfile 播放失败", exc_info=True)
        return False


def _play_macos(path: str) -> bool:
    try:
        subprocess.Popen(
            ["afplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        logger.debug("afplay 失败", exc_info=True)
        return False


def _play_linux(path: str) -> bool:
    for cmd in (
        ["paplay", path],
        ["aplay", path],
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
    ):
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except FileNotFoundError:
            continue
        except Exception:
            logger.debug("linux 播放失败: %s", cmd[0], exc_info=True)
    return False


# 系统铃声重复次数与间隔（毫秒）
_SYSTEM_BELL_TIMES = 3
_SYSTEM_BELL_INTERVAL_MS = 400


def ring_system_bell(root) -> None:
    """系统铃一次（可从后台线程调度到主线程调用）。"""
    if root is None:
        return
    try:
        root.bell()
    except Exception:
        logger.debug("bell 失败", exc_info=True)


def ring_system_bell_times(root, times: int = _SYSTEM_BELL_TIMES) -> None:
    """系统铃循环 times 次（主线程 after 调度，不阻塞）。"""
    if root is None or times <= 0:
        return
    n = int(times)

    def _ring(left: int) -> None:
        if left <= 0:
            return
        ring_system_bell(root)
        if left > 1:
            try:
                root.after(_SYSTEM_BELL_INTERVAL_MS, lambda: _ring(left - 1))
            except Exception:
                # after 失败则同步连响剩余次数（尽量完成）
                for _ in range(left - 1):
                    ring_system_bell(root)

    try:
        root.after(0, lambda: _ring(n))
    except Exception:
        for _ in range(n):
            ring_system_bell(root)


def play_finish_sound(
    root,
    *,
    muted: bool,
    sound_id: str,
    custom_path: str = "",
) -> None:
    """结束提示：静音跳过；文件类完整播一次；系统铃循环三次。"""
    if muted:
        return
    mode, path = resolve_play_path(sound_id, custom_path)
    if mode == "file" and path:
        if play_file(path):
            return
        logger.debug("文件播放失败，回退系统铃: %s", path)
    # 系统默认音效：循环三次
    ring_system_bell_times(root, _SYSTEM_BELL_TIMES)


def play_finish_sound_async(root, *, muted: bool, sound_id: str, custom_path: str = "") -> None:
    """在后台线程解析并启动播放，避免卡 UI。"""
    if muted:
        return

    def _run():
        play_finish_sound(
            root, muted=muted, sound_id=sound_id, custom_path=custom_path,
        )

    try:
        threading.Thread(target=_run, daemon=True).start()
    except Exception:
        play_finish_sound(
            root, muted=muted, sound_id=sound_id, custom_path=custom_path,
        )
