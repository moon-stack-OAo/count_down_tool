# -*- coding: utf-8 -*-
"""结束提示音：预设 / 自定义文件 / 系统铃；支持静音。

自定义音效会复制到用户配置目录 sounds/ 永久备份，并记录历史选择。
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import queue
import re
import shutil
import signal
import subprocess
import threading
import time
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


def _path_key(path: str) -> str:
    try:
        return os.path.normcase(os.path.abspath(path))
    except OSError:
        return path


def list_user_sound_files() -> List[str]:
    """列出用户 sounds 库内的普通文件（忽略 .tmp）。"""
    d = user_sounds_dir(create=False)
    if not d or not os.path.isdir(d):
        return []
    out: List[str] = []
    try:
        names = os.listdir(d)
    except OSError:
        return []
    for name in names:
        if not name or name.endswith(".tmp"):
            continue
        p = os.path.join(d, name)
        try:
            if os.path.isfile(p):
                out.append(p)
        except OSError:
            continue
    return out


def purge_orphan_sounds(history, current_path: str = "") -> int:
    """删除用户 sounds 库中不在历史且非当前路径的文件。返回删除数量。"""
    keep = set()
    for it in normalize_sound_history(history):
        p = it.get("path") or ""
        if p:
            keep.add(_path_key(p))
    cur = normalize_sound_path(current_path)
    if cur:
        keep.add(_path_key(cur))
    removed = 0
    for p in list_user_sound_files():
        if _path_key(p) in keep:
            continue
        try:
            os.remove(p)
            removed += 1
        except OSError:
            logger.debug("删除未使用音效失败: %s", p, exc_info=True)
    return removed


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
# 注意：MCI 设备与创建线程绑定，跨线程 stop/status 会返回 263 且无法掐断音频。
# 因此 open/play/stop/close/status 必须全部走专用工作线程。
_WIN_MCI_ALIAS = "cdt_finish_sound"
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
# 非 WAV 无法读时长时的保守估计（秒）；过长会导致「停止试听」长时间可点
_DEFAULT_AUDIO_SECONDS = 30.0
_PENDING_PREPARE_SECONDS = 120.0

# ---- Windows MCI 专用线程（线程亲和）----
_mci_cmd_q: Optional[queue.Queue] = None
_mci_thread: Optional[threading.Thread] = None
_mci_thread_lock = threading.Lock()
_mci_ready = threading.Event()


def _estimate_audio_seconds(path: str) -> float:
    """粗估时长（秒），用于菜单「停止」可点状态；失败则给保守上限。"""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".wav", ".wave"):
        try:
            import wave

            with wave.open(path, "rb") as w:
                rate = float(w.getframerate() or 1)
                return max(0.3, w.getnframes() / rate + 0.2)
        except Exception:
            pass
    return _DEFAULT_AUDIO_SECONDS


_AFINFO_DURATION_RE = re.compile(
    r"(?:estimated\s+duration|duration)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*sec",
    re.IGNORECASE,
)


def _parse_afinfo_duration(text: str) -> Optional[float]:
    """从 afinfo 输出解析时长（秒）。"""
    if not text:
        return None
    m = _AFINFO_DURATION_RE.search(text)
    if not m:
        return None
    try:
        sec = float(m.group(1))
    except ValueError:
        return None
    if sec <= 0:
        return None
    return max(0.3, sec + 0.2)


def _probe_macos_audio_seconds(path: str) -> float:
    """macOS：优先 afinfo 读真实时长，失败再粗估。"""
    try:
        r = subprocess.run(
            ["afinfo", path],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        blob = (r.stdout or "") + "\n" + (r.stderr or "")
        sec = _parse_afinfo_duration(blob)
        if sec is not None:
            return sec
    except Exception:
        logger.debug("afinfo 探测时长失败: %s", path, exc_info=True)
    return _estimate_audio_seconds(path)


def _bump_play_gen() -> int:
    """取消进行中的异步播放任务，返回新 generation。"""
    global _play_gen
    with _play_gen_lock:
        _play_gen += 1
        return _play_gen


def _is_play_cancelled(play_gen: Optional[int]) -> bool:
    if play_gen is None:
        return False
    with _play_gen_lock:
        return play_gen != _play_gen


def _set_pending_play(seconds: float = _PENDING_PREPARE_SECONDS) -> None:
    global _pending_until
    sec = max(0.3, float(seconds))
    with _play_proc_lock:
        _pending_until = max(_pending_until, time.monotonic() + sec)


def _clear_pending_play(play_gen: Optional[int] = None) -> None:
    """清除 pending；若指定 play_gen 则仅当仍是当前任务时清除。"""
    global _pending_until
    if play_gen is not None and _is_play_cancelled(play_gen):
        return
    with _play_proc_lock:
        _pending_until = 0.0


def _ensure_mci_worker() -> None:
    """启动 MCI 工作线程（仅 Windows，进程内一次）。"""
    global _mci_cmd_q, _mci_thread
    if platform.system() != "Windows":
        return
    with _mci_thread_lock:
        if _mci_thread is not None and _mci_thread.is_alive():
            return
        _mci_cmd_q = queue.Queue()
        _mci_ready.clear()

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
                except Exception:
                    return -1, ""
                return err, buf.value or ""

            _mci_ready.set()
            while True:
                item = _mci_cmd_q.get()
                if item is None:
                    # 退出前尽量关掉设备
                    try:
                        _send(f"stop {_WIN_MCI_ALIAS}")
                        _send(f"close {_WIN_MCI_ALIAS}")
                    except Exception:
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
                except Exception:
                    logger.debug("MCI worker 执行失败 op=%s", op, exc_info=True)
                    if result_box is not None:
                        result_box["ok"] = False
                finally:
                    if done_evt is not None:
                        done_evt.set()

        _mci_thread = threading.Thread(
            target=_worker, name="CdtMciWorker", daemon=True
        )
        _mci_thread.start()
    _mci_ready.wait(timeout=3.0)


def _mci_call(op: str, args: Optional[dict] = None, timeout: float = 5.0) -> dict:
    """向 MCI 工作线程投递命令并等待结果。"""
    _ensure_mci_worker()
    if _mci_cmd_q is None:
        return {"ok": False}
    result_box: dict = {}
    done_evt = threading.Event()
    _mci_cmd_q.put((op, args or {}, result_box, done_evt))
    if not done_evt.wait(timeout=timeout):
        logger.debug("MCI 命令超时 op=%s", op)
        return {"ok": False, "timeout": True}
    return result_box


def _mci_is_playing() -> bool:
    """查询 MCI 是否仍在 play（必须经专用线程）。"""
    if platform.system() != "Windows":
        return False
    try:
        r = _mci_call("status", timeout=1.0)
        return r.get("err", -1) == 0 and r.get("mode") == "playing"
    except Exception:
        return False


def is_sound_playing() -> bool:
    """是否仍在播放（菜单置灰用；进程结束 / 截止时间到 / MCI 停则视为否）。"""
    global _play_until, _use_mci, _pending_until
    now = time.monotonic()
    with _play_proc_lock:
        if _play_procs:
            _play_procs[:] = [p for p in _play_procs if p.poll() is None]
        alive = any(p.poll() is None for p in list(_play_procs))
        until = _play_until
        pending = _pending_until
        use_mci = _use_mci

    if alive:
        return True
    if use_mci and _mci_is_playing():
        return True
    if now < until:
        return True
    if now < pending:
        return True

    with _play_proc_lock:
        if not any(p.poll() is None for p in _play_procs):
            _play_until = 0.0
            _use_mci = False
            if time.monotonic() >= _pending_until:
                _pending_until = 0.0
    return False


def _kill_proc_tree(proc: subprocess.Popen) -> None:
    """尽量彻底结束播放进程（含 Windows 子进程树 / mac|linux 进程组）。"""
    if proc is None:
        return
    try:
        if proc.poll() is not None:
            return
    except Exception:
        return
    system = platform.system()
    if system == "Windows":
        try:
            # MediaPlayer/powershell 可能有子进程，仅 terminate 父进程会漏音
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=3,
            )
            return
        except Exception:
            logger.debug("taskkill 失败 pid=%s", getattr(proc, "pid", None), exc_info=True)
    elif system in ("Darwin", "Linux"):
        # start_new_session=True 时 afplay/ffplay 自成会话，killpg 可一并掐断
        pid = getattr(proc, "pid", None)
        if pid:
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
                try:
                    proc.wait(timeout=0.4)
                    return
                except Exception:
                    pass
                if proc.poll() is None:
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except Exception:
                        logger.debug(
                            "killpg SIGKILL 失败 pid=%s pgid=%s",
                            pid,
                            pgid,
                            exc_info=True,
                        )
                    try:
                        proc.wait(timeout=0.3)
                    except Exception:
                        pass
                    if proc.poll() is not None:
                        return
            except Exception:
                logger.debug(
                    "killpg 失败 pid=%s，回退 terminate/kill",
                    pid,
                    exc_info=True,
                )
    try:
        if proc.poll() is None:
            proc.terminate()
    except Exception:
        logger.debug("终止播放进程失败", exc_info=True)
    try:
        if proc.poll() is None:
            proc.kill()
    except Exception:
        logger.debug("强制结束播放进程失败", exc_info=True)


def _halt_devices() -> None:
    """停止底层播放设备/进程，不取消异步 generation（供 play_file 复用）。"""
    global _play_until, _use_mci
    cancel_system_bell()
    system = platform.system()
    if system == "Windows":
        try:
            import winsound

            # 连调两次：部分驱动首次 PURGE 不可靠
            winsound.PlaySound(None, winsound.SND_PURGE)
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            logger.debug("winsound 停止失败", exc_info=True)
        # 必须在创建 MCI 设备的同一线程 stop/close，否则错误 263 且音频不停
        try:
            _mci_call("halt", timeout=3.0)
        except Exception:
            logger.debug("MCI halt 失败", exc_info=True)

    with _play_proc_lock:
        procs = list(_play_procs)
        _play_procs.clear()
        _play_until = 0.0
        _use_mci = False

    for p in procs:
        _kill_proc_tree(p)


def stop_playback() -> None:
    """停止当前试听/结束音效（winsound / MCI / 外部播放进程 / 系统铃）。"""
    global _pending_until
    _bump_play_gen()
    with _play_proc_lock:
        _pending_until = 0.0
    # MCI 经专用线程 halt，与 play 同线程，可立刻掐断 mp3
    _halt_devices()


def play_file(path: str, play_gen: Optional[int] = None) -> bool:
    """异步播放一次完整文件。成功启动返回 True。先停掉上一路。

    play_gen 非空时：prepare（如 ncm 解密）结束后若已取消则不再开播。
    """
    play_path = prepare_playable_path(path)
    if not play_path:
        return False
    if _is_play_cancelled(play_gen):
        return False
    # 仅停设备，不 bump generation（避免取消正在执行的异步试听任务）
    _halt_devices()
    if _is_play_cancelled(play_gen):
        return False
    system = platform.system()
    try:
        if system == "Windows":
            ok = _play_windows(play_path)
        elif system == "Darwin":
            ok = _play_macos(play_path)
        else:
            ok = _play_linux(play_path)
        # 开播后必须再检查：stop 可能发生在 PlaySound/MCI 调用前后
        if _is_play_cancelled(play_gen):
            _halt_devices()
            return False
        return bool(ok)
    except Exception:
        logger.debug("播放文件失败: %s", path, exc_info=True)
        return False


def _track_proc(proc: subprocess.Popen) -> None:
    with _play_proc_lock:
        _play_procs.append(proc)


def _mark_playing_until(seconds: float) -> None:
    """标记一段时间内视为播放中（无进程句柄时）。"""
    global _play_until
    sec = max(0.3, float(seconds))
    with _play_proc_lock:
        _play_until = max(_play_until, time.monotonic() + sec)


def _mark_mci_playing() -> None:
    global _use_mci
    with _play_proc_lock:
        _use_mci = True


def _play_windows(path: str) -> bool:
    """
    Windows 播放优先级：
    1) WAV → winsound 异步
    2) 任意媒体 → winmm MCI（mp3/flac/m4a 等，不弹窗）
    3) PowerShell MediaPlayer（备用）
    4) startfile（最后回退，可能弹播放器窗口）
    """
    abs_path = os.path.abspath(path)
    est = _estimate_audio_seconds(abs_path)
    ext = os.path.splitext(abs_path)[1].lower()
    if ext in (".wav", ".wave"):
        try:
            import winsound

            winsound.PlaySound(abs_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            _mark_playing_until(est)
            return True
        except Exception:
            logger.debug("winsound 播放失败", exc_info=True)

    if _play_windows_mci(abs_path, est):
        return True
    if _play_windows_media_player(abs_path, est):
        return True
    try:
        os.startfile(abs_path)  # type: ignore[attr-defined]
        _mark_playing_until(est)
        return True
    except Exception:
        logger.debug("startfile 播放失败", exc_info=True)
        return False


def _play_windows_mci(path: str, est_seconds: float = 0.0) -> bool:
    """用 Windows MCI 打开并播放（mpegvideo 覆盖 mp3 等常见格式）。

    全部经专用线程，保证后续 stop 能在同一线程掐断。
    """
    try:
        abs_path = os.path.abspath(path)
        r = _mci_call("play", {"path": abs_path}, timeout=8.0)
        if not r.get("ok"):
            logger.debug(
                "MCI open/play 失败 err=%s path=%s", r.get("err"), path
            )
            return False
        mci_len = float(r.get("length") or 0.0)
        _mark_mci_playing()
        # MCI mode 查询偶发不准，始终用时长兜底，保证菜单「停止试听」可点
        _mark_playing_until(max(est_seconds, mci_len, 1.0))
        return True
    except Exception:
        logger.debug("MCI 播放异常", exc_info=True)
        return False


def _play_windows_media_player(path: str, est_seconds: float = 0.0) -> bool:
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
        # 进程存活为主；时长兜底防止 poll 异常
        _mark_playing_until(max(est_seconds, 1.0))
        return True
    except Exception:
        logger.debug("MediaPlayer 播放失败", exc_info=True)
        return False


def _play_macos(path: str) -> bool:
    """macOS：优先 afplay；失败时若有 ffplay 则回退。"""
    est = _probe_macos_audio_seconds(path)
    for cmd in (
        ["afplay", path],
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
            _mark_playing_until(est)
            return True
        except FileNotFoundError:
            logger.debug("mac 播放器不可用: %s", cmd[0])
            continue
        except Exception:
            logger.debug("mac 播放失败: %s", cmd[0], exc_info=True)
            continue
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
            _mark_playing_until(_estimate_audio_seconds(path))
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
    # 菜单「停止试听」可点时长 ≈ 间隔 * 次数
    _mark_playing_until(n * (_SYSTEM_BELL_INTERVAL_MS / 1000.0) + 0.4)

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
    play_gen: Optional[int] = None,
) -> None:
    """结束提示：静音跳过；文件类完整播一次；系统铃循环三次。

    play_gen 非空时：若 generation 已被 stop/新任务取消，则不启动播放。
    """
    if muted:
        return
    if _is_play_cancelled(play_gen):
        return
    mode, path = resolve_play_path(sound_id, custom_path)
    if mode == "file" and path:
        # 解密等可能较慢：prepare/开播前在 play_file 内再检查 generation
        if _is_play_cancelled(play_gen):
            return
        if play_file(path, play_gen=play_gen):
            _clear_pending_play(play_gen)
            return
        if _is_play_cancelled(play_gen):
            return
        logger.debug("文件播放失败，回退系统铃: %s", path)
    if _is_play_cancelled(play_gen):
        return
    # 系统默认音效：循环三次
    ring_system_bell_times(root, _SYSTEM_BELL_TIMES)
    _clear_pending_play(play_gen)


def _finish_async_pending(play_gen: Optional[int]) -> None:
    """异步任务结束时清 pending。

    仅清理「当前」任务的 pending；已被 cancel 的旧任务绝不能清掉新任务的 pending，
    否则会出现：第二次试听后 is_sound_playing 变 False → 停止试听仍灰、试听可连点叠播。
    """
    if play_gen is not None and _is_play_cancelled(play_gen):
        return
    _clear_pending_play(play_gen)


def play_finish_sound_async(root, *, muted: bool, sound_id: str, custom_path: str = "") -> None:
    """在后台线程解析并启动播放，避免卡 UI。

    每次调用递增 generation；stop_playback 会取消尚未开播的旧任务。
    """
    if muted:
        return
    play_gen = _bump_play_gen()
    # 立刻停掉上一路，避免准备/解密期间新旧重叠
    _halt_devices()
    _set_pending_play()

    def _run():
        try:
            if _is_play_cancelled(play_gen):
                return
            play_finish_sound(
                root,
                muted=muted,
                sound_id=sound_id,
                custom_path=custom_path,
                play_gen=play_gen,
            )
        finally:
            _finish_async_pending(play_gen)

    try:
        threading.Thread(target=_run, daemon=True).start()
    except Exception:
        try:
            play_finish_sound(
                root,
                muted=muted,
                sound_id=sound_id,
                custom_path=custom_path,
                play_gen=play_gen,
            )
        finally:
            _finish_async_pending(play_gen)
