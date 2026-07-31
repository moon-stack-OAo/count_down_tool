# -*- coding: utf-8 -*-
"""结束提示音：预设 / 自定义文件 / 系统铃；支持静音。

自定义音效会复制到用户配置目录 sounds/ 永久备份，并记录历史选择。
"""

from __future__ import annotations

import os
import platform
import queue
import subprocess
import threading
from typing import List, Optional

from services.sound.backends import (
    _halt_devices,
    _kill_proc_tree,
    _play_linux,
    _play_macos,
    _play_windows,
    _play_windows_mci,
    _play_windows_media_player,
    play_file,
    stop_playback,
)
from services.sound.constants import (
    _AUDIO_EXTS,
    _DEFAULT_AUDIO_SECONDS,
    _PATH_EXIST_TIMEOUT_S,
    _PENDING_PREPARE_SECONDS,
    _PRESET_FILES,
    _SYSTEM_BELL_INTERVAL_MS,
    _SYSTEM_BELL_TIMES,
    _WIN_MCI_ALIAS,
    AUDIO_FILETYPES,
    SOUND_HISTORY_MAX,
    SOUND_ID_ALERT,
    SOUND_ID_CHIME,
    SOUND_ID_CUSTOM,
    SOUND_ID_SOFT,
    SOUND_ID_SYSTEM,
    SOUND_PRESETS,
)
from services.sound.finish import (
    _finish_async_pending,
    cancel_system_bell,
    play_finish_sound,
    play_finish_sound_async,
    ring_system_bell,
    ring_system_bell_times,
)
from services.sound.history import (
    _path_key,
    list_user_sound_files,
    normalize_sound_history,
    normalize_sound_id,
    normalize_sound_path,
    path_is_file_quick,
    prune_sound_history,
    purge_orphan_sounds,
    sound_display_name,
    touch_sound_history,
    user_sounds_dir,
)
from services.sound.playback_state import (
    _bump_play_gen,
    _clear_pending_play,
    _ensure_mci_worker,
    _is_play_cancelled,
    _mark_mci_playing,
    _mark_playing_until,
    _mci_call,
    _mci_is_playing,
    _set_pending_play,
    _track_proc,
    is_sound_playing,
)
from services.sound.probe import (
    _estimate_audio_seconds,
    _parse_afinfo_duration,
    _probe_macos_audio_seconds,
)
from services.sound.resolve import (
    _import_dest_path,
    _safe_stem,
    import_custom_sound,
    is_audio_file,
    prepare_playable_path,
    preset_path,
    resolve_play_path,
)

# ---- 进程内播放状态（唯一副本）----
_play_proc_lock = threading.Lock()
_play_procs: List[subprocess.Popen] = []
# 无进程句柄时的截止时间（monotonic），用于 winsound / 系统铃等
_play_until = 0.0
_use_mci = False
# 异步准备中（解密 ncm 等）视为播放中，便于菜单立刻启用「停止试听」
_pending_until = 0.0
# 递增 generation：stop / 新一次异步播放会使旧线程在真正开播前退出
_play_gen = 0
_play_gen_lock = threading.Lock()

# ---- Windows MCI 专用线程（线程亲和）----
_mci_cmd_q: Optional[queue.Queue] = None
_mci_thread: Optional[threading.Thread] = None
_mci_thread_lock = threading.Lock()
_mci_ready = threading.Event()

# 系统铃 generation
_bell_gen = 0
_bell_lock = threading.Lock()

# 供测试 monkeypatch：sound_mod.os / .platform / .subprocess / .threading
_ = (os, platform, subprocess, threading)

__all__ = [
    "SOUND_ID_SYSTEM",
    "SOUND_ID_SOFT",
    "SOUND_ID_CHIME",
    "SOUND_ID_ALERT",
    "SOUND_ID_CUSTOM",
    "SOUND_PRESETS",
    "SOUND_HISTORY_MAX",
    "AUDIO_FILETYPES",
    "normalize_sound_id",
    "normalize_sound_path",
    "user_sounds_dir",
    "sound_display_name",
    "normalize_sound_history",
    "path_is_file_quick",
    "prune_sound_history",
    "touch_sound_history",
    "list_user_sound_files",
    "purge_orphan_sounds",
    "import_custom_sound",
    "preset_path",
    "resolve_play_path",
    "is_audio_file",
    "prepare_playable_path",
    "is_sound_playing",
    "stop_playback",
    "play_file",
    "ring_system_bell",
    "ring_system_bell_times",
    "cancel_system_bell",
    "play_finish_sound",
    "play_finish_sound_async",
    "_play_windows",
    "_play_windows_mci",
    "_play_windows_media_player",
    "_play_macos",
    "_play_linux",
    "_parse_afinfo_duration",
    "_estimate_audio_seconds",
    "_probe_macos_audio_seconds",
    "_PATH_EXIST_TIMEOUT_S",
    "_AUDIO_EXTS",
    "_DEFAULT_AUDIO_SECONDS",
    "_PENDING_PREPARE_SECONDS",
    "_PRESET_FILES",
    "_SYSTEM_BELL_INTERVAL_MS",
    "_SYSTEM_BELL_TIMES",
    "_WIN_MCI_ALIAS",
    "_path_key",
    "_import_dest_path",
    "_safe_stem",
    "_bump_play_gen",
    "_set_pending_play",
    "_clear_pending_play",
    "_finish_async_pending",
    "_halt_devices",
    "_mark_playing_until",
    "_mark_mci_playing",
    "_is_play_cancelled",
    "_mci_is_playing",
    "_track_proc",
    "_kill_proc_tree",
    "_mci_call",
    "_ensure_mci_worker",
    "os",
    "platform",
    "subprocess",
    "threading",
]
