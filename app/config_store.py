# -*- coding: utf-8 -*-
"""配置 load/save 与 app 字段同步；Mini 尺寸/字色辅助。"""

from __future__ import annotations

import logging
import platform
from typing import Tuple

from core.countdown_core import (
    load_config_dict,
    merge_config,
    merge_mini_position,
    merge_mini_size,
    merge_mini_text,
    normalize_mini_size,
    normalize_mini_text,
    resolve_mini_text_color,
    save_config_dict,
)
from core.themes import resolve_theme
from services.autostart import is_autostart_enabled

logger = logging.getLogger("count_down_tool")


def default_mini_size(app) -> Tuple[int, int]:
    """当前平台 Mini 默认尺寸。"""
    if platform.system() == "Darwin":
        return (
            getattr(app, "MINI_WIDTH_MAC", 450),
            getattr(app, "MINI_HEIGHT_MAC", 90),
        )
    return app.MINI_WIDTH, app.MINI_HEIGHT


def mini_size_limits(app) -> Tuple[int, int, int, int]:
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


def resolved_mini_size(app) -> Tuple[int, int]:
    """用户保存尺寸或平台默认。"""
    min_w, min_h, max_w, max_h = mini_size_limits(app)
    normalized = normalize_mini_size(app._mini_size, min_w, min_h, max_w, max_h)
    if normalized:
        return normalized
    return default_mini_size(app)


def mini_text_fg(app, role: str) -> str:
    """Mini 字色：从当前主题色板按角色解析 hex（不缓存）。"""
    return resolve_mini_text_color(app.COLORS, app._mini_text, role)


def load_config(app) -> None:
    """从磁盘读取配置并写入 app 字段。"""
    app._loaded_keys = set()
    try:
        config = load_config_dict(app._config_file)
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
        tid = config.get("theme_id")
        if isinstance(tid, str) and tid:
            app._theme_id = tid
        custom = config.get("theme_custom")
        app._theme_custom = custom if isinstance(custom, dict) else None
        app.COLORS = resolve_theme(app._theme_id, app._theme_custom)
        app._mini_text = normalize_mini_text(config.get("mini_text"))
        from services.sound import normalize_sound_id, normalize_sound_path

        if "sound_muted" in config:
            app._sound_muted = bool(config.get("sound_muted"))
        sid = config.get("sound_id")
        if isinstance(sid, str) and sid:
            app._sound_id = normalize_sound_id(sid)
        app._sound_path = normalize_sound_path(config.get("sound_path", ""))
        real_autostart = is_autostart_enabled()
        app._autostart = real_autostart
        if config.get("autostart") is not None and bool(config.get("autostart")) != real_autostart:
            try:
                cfg = merge_config(config, autostart=real_autostart)
                save_config_dict(app._config_file, cfg)
            except Exception:
                logger.debug("回写 autostart 配置失败", exc_info=True)
    except Exception:
        logger.exception("读取配置失败")
        app._mini_pos = None
        app._mini_size = None
        app._mini_text = {}
        app.COLORS = resolve_theme(app._theme_id, app._theme_custom)
        app._sound_muted = False
        app._sound_id = "soft"
        app._sound_path = ""


def save_config(app) -> None:
    """将 app 字段写回配置文件。"""
    try:
        config = load_config_dict(app._config_file)
        config = merge_mini_position(config, app._mini_pos)
        config = merge_mini_size(config, app._mini_size)
        config = merge_mini_text(config, app._mini_text)
        mode = "mini" if app._is_mini else "full"
        config = merge_config(
            config,
            transparent_mode=bool(app._transparent_mode),
            last_mode=mode,
            theme_id=app._theme_id,
            autostart=bool(app._autostart),
            sound_muted=bool(getattr(app, "_sound_muted", False)),
            sound_id=str(getattr(app, "_sound_id", "soft") or "soft"),
            sound_path=str(getattr(app, "_sound_path", "") or ""),
        )
        if app._theme_custom is not None:
            config = merge_config(config, theme_custom=app._theme_custom)
        save_config_dict(app._config_file, config)
    except Exception:
        logger.exception("保存配置失败")
