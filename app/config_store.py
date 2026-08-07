# -*- coding: utf-8 -*-
"""配置 load/save 与 app 字段同步；Mini 尺寸/字色辅助。

进程内配置缓存 + RLock：
- 按配置文件路径缓存最新 dict，避免 save 每次整文件 load→merge 被并发/嵌套写覆盖；
- RLock 保护 load-merge-save 临界区，允许同线程嵌套；
- 显式 load_config 仍从磁盘读取并刷新缓存；save 优先基于内存缓存 merge。
"""

from __future__ import annotations

import copy
import logging
import os
import platform
import threading
from typing import Any, Dict, Optional, Tuple

from core.countdown_core import (
    load_config_dict,
    merge_config,
    merge_mini_position,
    merge_mini_size,
    merge_mini_text,
    normalize_mini_size,
    normalize_mini_text,
    normalize_startup_mode,
    resolve_mini_text_color,
    save_config_dict,
)
from core.themes import (
    DEFAULT_THEME_ID,
    is_valid_theme_id,
    resolve_theme,
    sanitize_theme_custom,
)
from services.autostart import is_autostart_enabled

logger = logging.getLogger("count_down_tool")

# 进程内缓存：path_key -> 配置 dict 深拷贝
_config_lock = threading.RLock()
_config_cache: Dict[str, Dict[str, Any]] = {}


def _path_key(path: str) -> str:
    """规范化配置路径作为缓存键。"""
    if not path:
        return ""
    try:
        return os.path.normcase(os.path.abspath(path))
    except (OSError, TypeError, ValueError):
        return str(path)


def _get_cached(path: str) -> Optional[Dict[str, Any]]:
    key = _path_key(path)
    if not key or key not in _config_cache:
        return None
    return copy.deepcopy(_config_cache[key])


def _set_cached(path: str, config: Dict[str, Any]) -> None:
    key = _path_key(path)
    if not key:
        return
    data = config if isinstance(config, dict) else {}
    _config_cache[key] = copy.deepcopy(data)


def _load_for_merge(path: str) -> Dict[str, Any]:
    """优先内存缓存；未命中则读盘并热缓存。调用方须已持有 _config_lock。"""
    cached = _get_cached(path)
    if cached is not None:
        return cached
    config = load_config_dict(path)
    if not isinstance(config, dict):
        config = {}
    _set_cached(path, config)
    return copy.deepcopy(config)


def _write_config(path: str, config: Dict[str, Any]) -> None:
    """原子落盘并刷新缓存。调用方须已持有 _config_lock。"""
    data = config if isinstance(config, dict) else {}
    save_config_dict(path, data)
    _set_cached(path, data)


def clear_config_cache(path: Optional[str] = None) -> None:
    """测试/调试：清空全部或指定路径的配置缓存。"""
    with _config_lock:
        if path is None:
            _config_cache.clear()
            return
        key = _path_key(path)
        _config_cache.pop(key, None)


def default_mini_size(app: Any) -> Tuple[int, int]:
    """当前平台 Mini 默认尺寸。"""
    if platform.system() == "Darwin":
        return (
            getattr(app, "MINI_WIDTH_MAC", 450),
            getattr(app, "MINI_HEIGHT_MAC", 90),
        )
    return app.MINI_WIDTH, app.MINI_HEIGHT


def mini_size_limits(app: Any) -> Tuple[int, int, int, int]:
    """Mini 可调尺寸上下限 (min_w, min_h, max_w, max_h)。"""
    if platform.system() == "Darwin":
        return (
            app.MINI_MIN_WIDTH_MAC,
            app.MINI_MIN_HEIGHT_MAC,
            app.MINI_MAX_WIDTH_MAC,
            app.MINI_MAX_HEIGHT_MAC,
        )
    return (
        app.MINI_MIN_WIDTH,
        app.MINI_MIN_HEIGHT,
        app.MINI_MAX_WIDTH,
        app.MINI_MAX_HEIGHT,
    )


def resolved_mini_size(app: Any) -> Tuple[int, int]:
    """用户保存尺寸或平台默认。"""
    min_w, min_h, max_w, max_h = mini_size_limits(app)
    normalized = normalize_mini_size(app._mini_size, min_w, min_h, max_w, max_h)
    if normalized:
        return normalized
    return default_mini_size(app)


def mini_text_fg(app: Any, role: str) -> str:
    """Mini 字色：从当前主题色板按角色解析 hex（不缓存）。"""
    return resolve_mini_text_color(app.COLORS, app._mini_text, role)


def _normalize_last_hms(h: Any, m: Any, s: Any) -> Tuple[str, str, str]:
    """规范化 last_hour/minute/second 为两位数字符串。"""

    def _one(val: Any, default: str, lo: int, hi: int) -> str:
        try:
            n = int(str(val).strip())
        except (TypeError, ValueError, AttributeError):
            return default
        if n < lo or n > hi:
            return default
        return f"{n:02d}"

    return (
        _one(h, "18", 0, 23),
        _one(m, "00", 0, 59),
        _one(s, "00", 0, 59),
    )


def load_config(app: Any) -> None:
    """从磁盘读取配置并写入 app 字段（ConfigHost 兼容 duck-type）。

    显式 load 始终读盘；成功后刷新进程内缓存。
    """
    with _config_lock:
        app._loaded_keys = set()
        try:
            config = load_config_dict(app._config_file)
            if not isinstance(config, dict):
                config = {}
            _set_cached(app._config_file, config)
            app._loaded_keys = set(config.keys())
            app._mini_pos = config.get("mini_position")
            min_w, min_h, max_w, max_h = mini_size_limits(app)
            app._mini_size = normalize_mini_size(
                config.get("mini_size"), min_w, min_h, max_w, max_h
            )
            if "transparent_mode" in config:
                app._transparent_mode = bool(config.get("transparent_mode"))
            lm = config.get("last_mode")
            if lm in ("full", "mini"):
                app._last_mode = lm
            app._startup_mode = normalize_startup_mode(config.get("startup_mode"))
            tid = config.get("theme_id")
            if is_valid_theme_id(tid):
                app._theme_id = tid
            else:
                app._theme_id = DEFAULT_THEME_ID
            app._theme_custom = sanitize_theme_custom(config.get("theme_custom"))
            app.COLORS = resolve_theme(app._theme_id, app._theme_custom)
            app._mini_text = normalize_mini_text(config.get("mini_text"))
            from services.sound import (
                normalize_sound_history,
                normalize_sound_id,
                normalize_sound_path,
                path_is_file_quick,
                prune_sound_history,
                touch_sound_history,
            )

            if "sound_muted" in config:
                app._sound_muted = bool(config.get("sound_muted"))
            sid = config.get("sound_id")
            if isinstance(sid, str) and sid:
                app._sound_id = normalize_sound_id(sid)
            app._sound_path = normalize_sound_path(config.get("sound_path", ""))
            # 仅当配置里根本没有 sound_history 字段时，才用 sound_path 迁移进历史
            # （用户「清空历史」后是显式 []，不可再自动塞回）
            # path_is_file_quick：避免失效网络盘在启动时卡住主线程
            history_dirty = False
            if "sound_history" not in config:
                history = []
                if app._sound_path and path_is_file_quick(app._sound_path):
                    history = touch_sound_history(history, app._sound_path)
                    history_dirty = bool(history)
            else:
                raw_history = normalize_sound_history(config.get("sound_history"))
                history = prune_sound_history(raw_history)
                # prune 掉失效/超时路径后写回，避免下次启动再探测挂死
                if history != raw_history:
                    history_dirty = True
            app._sound_history = history
            if history_dirty:
                try:
                    cfg = merge_config(config, sound_history=history)
                    _write_config(app._config_file, cfg)
                    config = cfg
                except (OSError, TypeError, ValueError):
                    logger.debug("回写 sound_history 配置失败", exc_info=True)
            if "check_update_on_start" in config:
                app._check_update_on_start = bool(config.get("check_update_on_start"))
            luc = config.get("last_update_check")
            app._last_update_check = luc if isinstance(luc, str) else ""
            ign = config.get("ignored_update_version")
            app._ignored_update_version = ign if isinstance(ign, str) else ""
            # 上次到期时分秒（容错非法值）
            app._last_hour, app._last_minute, app._last_second = _normalize_last_hms(
                config.get("last_hour"),
                config.get("last_minute"),
                config.get("last_second"),
            )
            real_autostart = is_autostart_enabled()
            app._autostart = real_autostart
            if config.get("autostart") is not None and bool(config.get("autostart")) != real_autostart:
                try:
                    cfg = merge_config(config, autostart=real_autostart)
                    _write_config(app._config_file, cfg)
                except (OSError, TypeError, ValueError):
                    logger.debug("回写 autostart 配置失败", exc_info=True)
        except (OSError, TypeError, ValueError, KeyError, AttributeError, ImportError):
            logger.exception("读取配置失败")
            app._mini_pos = None
            app._mini_size = None
            app._mini_text = {}
            app.COLORS = resolve_theme(app._theme_id, app._theme_custom)
            app._sound_muted = False
            app._sound_id = "soft"
            app._sound_path = ""
            app._sound_history = []
            app._check_update_on_start = True
            app._last_update_check = ""
            app._ignored_update_version = ""
            app._startup_mode = "remember"
            app._last_hour, app._last_minute, app._last_second = "18", "00", "00"


def save_config(app: Any) -> None:
    """将 app 字段写回配置文件（ConfigHost 兼容 duck-type）。

    基于内存中最新配置 dict merge，避免并发/嵌套 save 因整文件 reload 丢字段。
    同步写盘（tmp+replace），不依赖 Tk after，退出路径可直接调用。
    """
    with _config_lock:
        try:
            from services.sound import normalize_sound_history

            config = _load_for_merge(app._config_file)
            config = merge_mini_position(config, app._mini_pos)
            config = merge_mini_size(config, app._mini_size)
            config = merge_mini_text(config, app._mini_text)
            mode = "mini" if app._is_mini else "full"
            history = normalize_sound_history(getattr(app, "_sound_history", []))
            lh, lm, ls = _normalize_last_hms(
                getattr(app, "_last_hour", "18"),
                getattr(app, "_last_minute", "00"),
                getattr(app, "_last_second", "00"),
            )
            config = merge_config(
                config,
                transparent_mode=bool(app._transparent_mode),
                last_mode=mode,
                startup_mode=normalize_startup_mode(
                    getattr(app, "_startup_mode", "remember")
                ),
                theme_id=app._theme_id,
                autostart=bool(app._autostart),
                sound_muted=bool(getattr(app, "_sound_muted", False)),
                sound_id=str(getattr(app, "_sound_id", "soft") or "soft"),
                sound_path=str(getattr(app, "_sound_path", "") or ""),
                sound_history=history,
                check_update_on_start=bool(getattr(app, "_check_update_on_start", True)),
                last_update_check=str(getattr(app, "_last_update_check", "") or ""),
                ignored_update_version=str(getattr(app, "_ignored_update_version", "") or ""),
                last_hour=lh,
                last_minute=lm,
                last_second=ls,
            )
            if app._theme_custom is not None:
                config = merge_config(config, theme_custom=app._theme_custom)
            _write_config(app._config_file, config)
        except (OSError, TypeError, ValueError, KeyError, AttributeError, ImportError):
            logger.exception("保存配置失败")
