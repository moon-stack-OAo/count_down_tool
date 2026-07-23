# -*- coding: utf-8 -*-
"""结束提示音：预设 / 自定义文件 / 系统铃；支持静音。

自定义音效会复制到用户配置目录 sounds/ 永久备份，并记录历史选择。
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import re
import shutil
import subprocess
import threading
from typing import Any, Dict, List, Optional, Tuple

from core.countdown_core import resource_path, user_config_dir

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

# 历史自定义音效条数上限
SOUND_HISTORY_MAX = 12

_PRESET_FILES = {
    SOUND_ID_SOFT: os.path.join("assets", "sounds", "soft.wav"),
    SOUND_ID_CHIME: os.path.join("assets", "sounds", "chime.wav"),
    SOUND_ID_ALERT: os.path.join("assets", "sounds", "alert.wav"),
}

_AUDIO_EXTS = (
    ".wav",
    ".wave",
    ".mp3",
    ".aiff",
    ".aif",
    ".m4a",
    ".aac",
    ".ogg",
    ".flac",
    ".ncm",
)

# 文件选择对话框用的扩展名字符串
AUDIO_FILETYPES = [
    ("音频文件", "*.wav *.wave *.mp3 *.aiff *.aif *.m4a *.aac *.ogg *.flac *.ncm"),
    ("网易云 NCM", "*.ncm"),
    ("WAV", "*.wav *.wave"),
    ("所有文件", "*.*"),
]


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


def user_sounds_dir(create: bool = True) -> str:
    """用户自定义音效永久目录：{config}/sounds。"""
    d = os.path.join(user_config_dir(create=create), "sounds")
    if create:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            logger.debug("创建 sounds 目录失败: %s", d, exc_info=True)
    return d


def sound_display_name(path: str, fallback: str = "") -> str:
    """用于菜单展示的文件名。"""
    if fallback and isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    if not path:
        return "未命名"
    base = os.path.basename(path.replace("\\", "/"))
    return base or "未命名"


def normalize_sound_history(value) -> List[Dict[str, str]]:
    """
    规范化历史列表：[{path, name}, ...]，最多 SOUND_HISTORY_MAX，
    去重（按绝对路径）、去掉空路径；不强制文件存在（由 prune 处理）。
    """
    if not isinstance(value, list):
        return []
    seen = set()
    out: List[Dict[str, str]] = []
    for item in value:
        path = ""
        name = ""
        if isinstance(item, str):
            path = item.strip()
        elif isinstance(item, dict):
            path = normalize_sound_path(item.get("path", ""))
            n = item.get("name")
            if isinstance(n, str):
                name = n.strip()
        if not path:
            continue
        try:
            key = os.path.normcase(os.path.abspath(path))
        except OSError:
            key = path
        if key in seen:
            continue
        seen.add(key)
        out.append({"path": path, "name": sound_display_name(path, name)})
        if len(out) >= SOUND_HISTORY_MAX:
            break
    return out


def prune_sound_history(history) -> List[Dict[str, str]]:
    """去掉不存在的文件。"""
    items = normalize_sound_history(history)
    kept: List[Dict[str, str]] = []
    for it in items:
        p = it.get("path") or ""
        if p and os.path.isfile(p):
            kept.append(it)
    return kept


def touch_sound_history(history, path: str, name: str = "") -> List[Dict[str, str]]:
    """将 path 置顶并写入/更新历史。"""
    path = normalize_sound_path(path)
    if not path:
        return normalize_sound_history(history)
    entry = {"path": path, "name": sound_display_name(path, name)}
    try:
        key = os.path.normcase(os.path.abspath(path))
    except OSError:
        key = path
    rest: List[Dict[str, str]] = []
    for it in normalize_sound_history(history):
        p = it.get("path") or ""
        try:
            k = os.path.normcase(os.path.abspath(p))
        except OSError:
            k = p
        if k == key:
            # 保留旧展示名（若新 name 为空）
            if not name and it.get("name"):
                entry["name"] = it["name"]
            continue
        rest.append(it)
    return ([entry] + rest)[:SOUND_HISTORY_MAX]


def _safe_stem(name: str) -> str:
    stem = os.path.splitext(os.path.basename(name or ""))[0]
    stem = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", stem, flags=re.UNICODE)
    stem = stem.strip("._") or "sound"
    return stem[:48]


def _import_dest_path(src_path: str, play_ext: str) -> str:
    """按源路径稳定生成目标文件名，便于重复导入复用。"""
    abs_src = os.path.abspath(src_path)
    digest = hashlib.sha1(abs_src.encode("utf-8", errors="ignore")).hexdigest()[:12]
    stem = _safe_stem(src_path)
    ext = play_ext if play_ext.startswith(".") else f".{play_ext}"
    return os.path.join(user_sounds_dir(True), f"{stem}_{digest}{ext}")


def import_custom_sound(src_path: str) -> Optional[Tuple[str, str]]:
    """
    将自定义音效导入用户 sounds 目录（永久备份）。
    .ncm 先解密再保存为 mp3/flac 等。
    返回 (stored_path, display_name)；失败返回 None。
    """
    src_path = normalize_sound_path(src_path)
    if not src_path or not os.path.isfile(src_path):
        return None
    if not is_audio_file(src_path):
        return None

    display = sound_display_name(src_path)
    abs_src = os.path.abspath(src_path)
    sounds_root = os.path.abspath(user_sounds_dir(True))

    # 已在用户库内：直接使用
    try:
        if os.path.commonpath([abs_src, sounds_root]) == sounds_root:
            return abs_src, display
    except ValueError:
        pass

    # ncm / 需转换：先得到可播放文件
    play_src = prepare_playable_path(src_path)
    if not play_src or not os.path.isfile(play_src):
        return None

    play_ext = os.path.splitext(play_src)[1].lower() or ".mp3"
    if play_ext == ".ncm":
        return None

    # 展示名：ncm 保留原名但扩展改为实际格式
    if os.path.splitext(src_path)[1].lower() == ".ncm":
        display = _safe_stem(src_path) + play_ext
    else:
        display = sound_display_name(src_path)

    dest = _import_dest_path(src_path, play_ext)
    try:
        # 已有同名目标且非空则复用
        if os.path.isfile(dest) and os.path.getsize(dest) > 0:
            # 源更新时覆盖
            try:
                if os.path.getmtime(play_src) <= os.path.getmtime(dest) + 0.001:
                    return dest, display
            except OSError:
                return dest, display
        parent = os.path.dirname(dest)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp = dest + ".tmp"
        shutil.copy2(play_src, tmp)
        os.replace(tmp, dest)
        return dest, display
    except Exception:
        logger.debug("导入自定义音效失败: %s -> %s", src_path, dest, exc_info=True)
        return None


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
    if ext == ".ncm":
        from services.ncm import is_ncm_file

        return is_ncm_file(path)
    return ext in _AUDIO_EXTS


def prepare_playable_path(path: str) -> Optional[str]:
    """将路径解析为系统可直接播放的文件（.ncm 先解密到缓存）。"""
    if not path or not os.path.isfile(path):
        return None
    ext = os.path.splitext(path)[1].lower()
    if ext == ".ncm":
        from services.ncm import resolve_ncm_play_path

        return resolve_ncm_play_path(path)
    return path


# Windows MCI 别名：同一时刻只保留一路结束音效
_WIN_MCI_ALIAS = "cdt_finish_sound"
_win_mci_lock = threading.Lock()
_play_proc_lock = threading.Lock()
_play_procs: List[subprocess.Popen] = []
_playing = False


def is_sound_playing() -> bool:
    """是否可能仍在播放（用于菜单；进程已退出则视为否）。"""
    global _playing
    with _play_proc_lock:
        alive = False
        for p in list(_play_procs):
            if p.poll() is None:
                alive = True
                break
        if not alive and _playing and platform.system() == "Windows":
            # MCI/winsound 无进程句柄，仅靠标志位
            return True
        if not alive:
            _playing = False
        return _playing or alive


def stop_playback() -> None:
    """停止当前试听/结束音效（winsound / MCI / 外部播放进程 / 系统铃）。"""
    global _playing
    cancel_system_bell()
    system = platform.system()
    if system == "Windows":
        try:
            import winsound

            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            logger.debug("winsound 停止失败", exc_info=True)
        with _win_mci_lock:
            try:
                _mci_send(f"stop {_WIN_MCI_ALIAS}")
            except Exception:
                pass
            try:
                _mci_send(f"close {_WIN_MCI_ALIAS}")
            except Exception:
                pass

    with _play_proc_lock:
        procs = list(_play_procs)
        _play_procs.clear()
        _playing = False

    for p in procs:
        try:
            if p.poll() is None:
                p.terminate()
        except Exception:
            logger.debug("终止播放进程失败", exc_info=True)
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass


def play_file(path: str) -> bool:
    """异步播放一次完整文件。成功启动返回 True。先停掉上一路。"""
    play_path = prepare_playable_path(path)
    if not play_path:
        return False
    stop_playback()
    system = platform.system()
    try:
        if system == "Windows":
            return _play_windows(play_path)
        if system == "Darwin":
            return _play_macos(play_path)
        return _play_linux(play_path)
    except Exception:
        logger.debug("播放文件失败: %s", path, exc_info=True)
        return False


def _track_proc(proc: subprocess.Popen) -> None:
    global _playing
    with _play_proc_lock:
        _play_procs.append(proc)
        _playing = True


def _mark_playing() -> None:
    global _playing
    with _play_proc_lock:
        _playing = True


def _play_windows(path: str) -> bool:
    """
    Windows 播放优先级：
    1) WAV → winsound 异步
    2) 任意媒体 → winmm MCI（mp3/flac/m4a 等，不弹窗）
    3) PowerShell MediaPlayer（备用）
    4) startfile（最后回退，可能弹播放器窗口）
    """
    abs_path = os.path.abspath(path)
    ext = os.path.splitext(abs_path)[1].lower()
    if ext in (".wav", ".wave"):
        try:
            import winsound

            winsound.PlaySound(abs_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            _mark_playing()
            return True
        except Exception:
            logger.debug("winsound 播放失败", exc_info=True)

    if _play_windows_mci(abs_path):
        return True
    if _play_windows_media_player(abs_path):
        return True
    try:
        os.startfile(abs_path)  # type: ignore[attr-defined]
        _mark_playing()
        return True
    except Exception:
        logger.debug("startfile 播放失败", exc_info=True)
        return False


def _mci_send(command: str) -> int:
    """调用 mciSendStringW，返回错误码（0 成功）。"""
    import ctypes

    buf = ctypes.create_unicode_buffer(256)
    return int(
        ctypes.windll.winmm.mciSendStringW(command, buf, 255, 0)  # type: ignore[attr-defined]
    )


def _play_windows_mci(path: str) -> bool:
    """用 Windows MCI 打开并播放（mpegvideo 覆盖 mp3 等常见格式）。"""
    try:
        mci_path = path.replace("\\", "/")
        with _win_mci_lock:
            try:
                _mci_send(f"close {_WIN_MCI_ALIAS}")
            except Exception:
                pass
            err = _mci_send(
                f'open "{mci_path}" type mpegvideo alias {_WIN_MCI_ALIAS}'
            )
            if err != 0:
                err = _mci_send(f'open "{mci_path}" alias {_WIN_MCI_ALIAS}')
            if err != 0:
                logger.debug("MCI open 失败 code=%s path=%s", err, path)
                return False
            err = _mci_send(f"play {_WIN_MCI_ALIAS}")
            if err != 0:
                logger.debug("MCI play 失败 code=%s", err)
                try:
                    _mci_send(f"close {_WIN_MCI_ALIAS}")
                except Exception:
                    pass
                return False
        _mark_playing()
        return True
    except Exception:
        logger.debug("MCI 播放异常", exc_info=True)
        return False


def _play_windows_media_player(path: str) -> bool:
    """后台 PowerShell + MediaPlayer 播一次（不弹窗）。"""
    try:
        ps_path = path.replace("'", "''")
        script = (
            f"$p = New-Object System.Windows.Media.MediaPlayer; "
            f"$p.Open([uri]'{ps_path}'); "
            f"$p.Volume = 1; "
            f"$p.Play(); "
            f"Start-Sleep -Milliseconds 400; "
            f"while ($p.NaturalDuration.HasTimeSpan -eq $false) {{ "
            f"  Start-Sleep -Milliseconds 50 }}; "
            f"$ms = [int]$p.NaturalDuration.TimeSpan.TotalMilliseconds; "
            f"if ($ms -lt 200) {{ $ms = 200 }}; "
            f"Start-Sleep -Milliseconds $ms; "
            f"$p.Close()"
        )
        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        proc = subprocess.Popen(
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
        _track_proc(proc)
        return True
    except Exception:
        logger.debug("MediaPlayer 播放失败", exc_info=True)
        return False


def _play_macos(path: str) -> bool:
    try:
        proc = subprocess.Popen(
            ["afplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _track_proc(proc)
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
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            _track_proc(proc)
            return True
        except FileNotFoundError:
            continue
        except Exception:
            logger.debug("linux 播放失败: %s", cmd[0], exc_info=True)
    return False


# 系统铃声重复次数与间隔（毫秒）
_SYSTEM_BELL_TIMES = 3
_SYSTEM_BELL_INTERVAL_MS = 400
_bell_gen = 0
_bell_lock = threading.Lock()


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
    global _bell_gen
    if root is None or times <= 0:
        return
    n = int(times)
    with _bell_lock:
        _bell_gen += 1
        gen = _bell_gen

    def _ring(left: int) -> None:
        with _bell_lock:
            if gen != _bell_gen:
                return
        if left <= 0:
            return
        ring_system_bell(root)
        if left > 1:
            try:
                root.after(_SYSTEM_BELL_INTERVAL_MS, lambda: _ring(left - 1))
            except Exception:
                for _ in range(left - 1):
                    with _bell_lock:
                        if gen != _bell_gen:
                            return
                    ring_system_bell(root)

    try:
        root.after(0, lambda: _ring(n))
    except Exception:
        for _ in range(n):
            with _bell_lock:
                if gen != _bell_gen:
                    return
            ring_system_bell(root)


def cancel_system_bell() -> None:
    """取消尚未响完的系统铃循环。"""
    global _bell_gen
    with _bell_lock:
        _bell_gen += 1


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
