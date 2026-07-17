# -*- coding: utf-8 -*-
"""倒计时纯逻辑模块（无 tkinter 依赖，便于单元测试）。"""

from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, Union

__version__ = "1.3.4"
APP_NAME = "倒计时工具"
APP_NAME_EN = "Count Down Tool"

# 配置目录名
_CONFIG_APP_DIR = "count_down_tool"

# 倒计时状态
STATE_IDLE = "idle"
STATE_RUNNING = "running"
STATE_PAUSED = "paused"
STATE_FINISHED = "finished"

VALID_STATES = (STATE_IDLE, STATE_RUNNING, STATE_PAUSED, STATE_FINISHED)

# 状态机动作
ACTION_START = "start"
ACTION_PAUSE = "pause"
ACTION_RESUME = "resume"
ACTION_FINISH = "finish"
ACTION_RESTART = "restart"
ACTION_RESET = "reset"
ACTION_START_FAIL = "start_fail"

# 按钮文案
BTN_START = "开始倒计时"
BTN_PAUSE = "暂停"
BTN_RESUME = "继续"
BTN_RESTART = "重新开始"

_BUTTON_TEXT = {
    STATE_IDLE: BTN_START,
    STATE_RUNNING: BTN_PAUSE,
    STATE_PAUSED: BTN_RESUME,
    STATE_FINISHED: BTN_RESTART,
}

# 合法转换：(当前状态, 动作) → 下一状态
_TRANSITIONS = {
    (STATE_IDLE, ACTION_START): STATE_RUNNING,
    (STATE_IDLE, ACTION_START_FAIL): STATE_IDLE,
    (STATE_IDLE, ACTION_RESET): STATE_IDLE,
    (STATE_RUNNING, ACTION_PAUSE): STATE_PAUSED,
    (STATE_RUNNING, ACTION_FINISH): STATE_FINISHED,
    (STATE_RUNNING, ACTION_RESET): STATE_IDLE,
    (STATE_RUNNING, ACTION_START_FAIL): STATE_IDLE,
    (STATE_PAUSED, ACTION_RESUME): STATE_RUNNING,
    (STATE_PAUSED, ACTION_RESET): STATE_IDLE,
    (STATE_FINISHED, ACTION_RESTART): STATE_RUNNING,
    (STATE_FINISHED, ACTION_START_FAIL): STATE_FINISHED,
    (STATE_FINISHED, ACTION_RESET): STATE_IDLE,
}


def button_text_for_state(state: str) -> str:
    """状态 → 主按钮文案。"""
    return _BUTTON_TEXT.get(state, BTN_START)


def next_state(action: str, state: str) -> str:
    """
    状态转换。未知转换保持原状态。
    start 校验失败用 ACTION_START_FAIL；running 回滚用 start_fail → idle。
    """
    key = (state, action)
    if key in _TRANSITIONS:
        return _TRANSITIONS[key]
    # 任意状态重置
    if action == ACTION_RESET:
        return STATE_IDLE
    return state


def toggle_action_for_state(state: str) -> str:
    """主按钮点击时，当前状态对应的动作。"""
    if state == STATE_IDLE:
        return ACTION_START
    if state == STATE_RUNNING:
        return ACTION_PAUSE
    if state == STATE_PAUSED:
        return ACTION_RESUME
    if state == STATE_FINISHED:
        return ACTION_RESTART
    return ACTION_START


def resource_path(
    name: str,
    frozen: Optional[bool] = None,
    meipass: Optional[str] = None,
    file_dir: Optional[str] = None,
) -> str:
    """解析资源路径；打包后优先使用 PyInstaller 的 _MEIPASS。"""
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        base = meipass if meipass is not None else getattr(sys, "_MEIPASS", None)
        if not base:
            base = file_dir if file_dir is not None else os.path.dirname(os.path.abspath(__file__))
    else:
        base = file_dir if file_dir is not None else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, name)


def user_config_dir(create: bool = True) -> str:
    """用户配置目录。"""
    if platform.system() == "Windows":
        root = os.environ.get("APPDATA", os.path.expanduser("~"))
        cfg_dir = os.path.join(root, _CONFIG_APP_DIR)
    else:
        cfg_dir = os.path.join(os.path.expanduser("~"), ".config", _CONFIG_APP_DIR)
    if create:
        os.makedirs(cfg_dir, exist_ok=True)
    return cfg_dir


def user_config_path() -> str:
    return os.path.join(user_config_dir(), "config.json")


def next_second_delay_ms(now: Optional[datetime] = None) -> int:
    """按墙钟对齐下一秒，避免 after(1000) 漂移。返回 1..1000。"""
    if now is None:
        now = datetime.now()
    delay = 1000 - (now.microsecond // 1000)
    if delay < 1:
        return 1
    if delay > 1000:
        return 1000
    return delay


def validate_hms(
    hour: Any, minute: Any, second: Any
) -> Tuple[bool, Optional[str]]:
    """
    校验时分秒。
    成功 (True, None)；失败 (False, 中文错误信息)。
    """
    try:
        for val, max_val in ((hour, 23), (minute, 59), (second, 59)):
            n = int(val)
            if n < 0 or n > max_val:
                return False, f"输入值应在 00-{max_val:02d} 之间"
        return True, None
    except (TypeError, ValueError):
        return False, "请输入有效数字"


def target_from_hms(
    hour: int,
    minute: int,
    second: int,
    now: Optional[datetime] = None,
) -> datetime:
    """今日该时刻；若已过则 +1 天。"""
    if now is None:
        now = datetime.now()
    target = now.replace(
        hour=int(hour),
        minute=int(minute),
        second=int(second),
        microsecond=0,
    )
    if target < now:
        target += timedelta(days=1)
    return target


def target_from_duration(
    hours: int,
    minutes: int,
    seconds: int,
    now: Optional[datetime] = None,
) -> Tuple[datetime, timedelta]:
    """相对时长 → (目标时刻, 时长)。"""
    if now is None:
        now = datetime.now()
    duration = timedelta(
        hours=int(hours),
        minutes=int(minutes),
        seconds=int(seconds),
    )
    return now + duration, duration


def format_remaining(total_seconds: int) -> str:
    """剩余秒数格式化为 HH:MM:SS。"""
    total = int(total_seconds)
    if total < 0:
        total = 0
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def progress_ratio(remaining_seconds: float, total_seconds: float) -> float:
    """
    倒计时进度比：已过 / 总时长，夹紧到 [0, 1]。
    remaining 为剩余秒数；total 为总时长秒数。
    total <= 0 时返回 1.0（视为已完成，避免除零）。
    """
    try:
        remaining = float(remaining_seconds)
        total = float(total_seconds)
    except (TypeError, ValueError):
        return 0.0
    if total <= 0:
        return 1.0
    ratio = 1.0 - (remaining / total)
    if ratio < 0.0:
        return 0.0
    if ratio > 1.0:
        return 1.0
    return ratio


def format_target_label(
    target: datetime,
    now: Optional[datetime] = None,
) -> str:
    """跨日显示「明日 HH:MM:SS」，否则「HH:MM:SS」。"""
    if now is None:
        now = datetime.now()
    day_hint = "明日 " if target.date() > now.date() else ""
    return f"{day_hint}{target.strftime('%H:%M:%S')}"


def parse_mini_geometry(geo: str) -> Optional[Tuple[int, int]]:
    """从 Tk geometry `WxH+X+Y` 或 `+X+Y` 解析位置。"""
    if not geo or not isinstance(geo, str):
        return None
    try:
        parts = geo.split("+")
        if len(parts) == 3:
            return int(parts[1]), int(parts[2])
        return None
    except (TypeError, ValueError):
        return None


def load_config_dict(path: str) -> Dict[str, Any]:
    """读取 JSON 配置；不存在或损坏时返回空 dict。"""
    try:
        if not path or not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            return loaded
        return {}
    except Exception:
        return {}


def merge_mini_position(
    config: Optional[Dict[str, Any]],
    mini_pos: Optional[Union[Tuple[int, int], list]],
) -> Dict[str, Any]:
    """合并 mini 位置到配置副本，不丢其它字段。"""
    result: Dict[str, Any] = dict(config) if isinstance(config, dict) else {}
    if mini_pos:
        result["mini_position"] = list(mini_pos)
    return result


def merge_config(
    config: Optional[Dict[str, Any]],
    **updates: Any,
) -> Dict[str, Any]:
    """
    合并配置字段到副本，不丢其它字段。
    值为 None 的 key 不写入（保留原值）。

    常用字段：
    - mini_position / transparent_mode / last_mode
    - autostart: Optional[bool]
    - theme_id: Optional[str]
    - theme_custom: Optional[dict]（仅 non-None 时写入；可传 {} 清空自定义色）
    """
    result: Dict[str, Any] = dict(config) if isinstance(config, dict) else {}
    for key, value in updates.items():
        if value is not None:
            result[key] = value
    return result


def save_config_dict(path: str, config: Dict[str, Any]) -> None:
    """写入 JSON 配置。"""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config if isinstance(config, dict) else {}, f, indent=2)


# ------------------------------------------------------------------
# 弱锁 / PID 检测（非 Windows 或无 fcntl 路径）
# ------------------------------------------------------------------


def is_process_alive(pid: int) -> bool:
    """
    判断 PID 是否仍存活。
    Windows：OpenProcess；其他：os.kill(pid, 0)。
    无效 pid 返回 False。
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    system = platform.system()
    if system == "Windows":
        try:
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, wintypes.DWORD(pid)
            )
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # 无权限但进程存在
        return True
    except OSError:
        return False


def read_lock_pid(path: str) -> Optional[int]:
    """从锁文件读取 PID；失败返回 None。"""
    try:
        if not path or not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return None
        return int(content.split()[0])
    except (TypeError, ValueError, OSError):
        return None


def write_lock_pid(path: str, pid: Optional[int] = None) -> None:
    """将 PID 写入锁文件（覆盖）。"""
    if pid is None:
        pid = os.getpid()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(int(pid)))
        f.flush()


def try_acquire_weak_lock(lock_path: str, pid: Optional[int] = None) -> bool:
    """
    弱锁获取：O_EXCL 创建；若已存在则检查 PID。
    死进程残留锁会删除后重试；活进程返回 False。
    成功写入当前 pid 并返回 True。
    """
    if pid is None:
        pid = os.getpid()
    parent = os.path.dirname(lock_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    def _create_exclusive() -> bool:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, str(int(pid)).encode("utf-8"))
            finally:
                os.close(fd)
            return True
        except FileExistsError:
            return False

    if _create_exclusive():
        return True

    existing = read_lock_pid(lock_path)
    if existing is not None and is_process_alive(existing):
        return False

    # 残留或损坏：删除后重试
    try:
        os.remove(lock_path)
    except OSError:
        pass
    return _create_exclusive()
