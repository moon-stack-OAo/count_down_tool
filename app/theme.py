# -*- coding: utf-8 -*-
"""主题应用：切换预设并重建主界面（保留业务状态）。"""

from __future__ import annotations

import logging
from core.countdown_core import STATE_FINISHED, button_text_for_state
from core.themes import resolve_theme
from services.tray import refresh_tray_menu

logger = logging.getLogger("count_down_tool")


def apply_theme(app, theme_id: str) -> None:
    """切换预设主题并重建主界面（保留业务状态）。"""
    if theme_id == app._theme_id and app.COLORS:
        pass
    # 保存 UI 输入与倒计时显示
    saved_h = saved_m = saved_s = None
    try:
        if getattr(app, "hour_var", None) is not None:
            saved_h = app.hour_var.get()
            saved_m = app.minute_var.get()
            saved_s = app.second_var.get()
    except Exception:
        pass
    saved_countdown = app.countdown_text
    saved_target = app.target_time
    was_mini = app._is_mini

    app._theme_id = theme_id
    app.COLORS = resolve_theme(app._theme_id, app._theme_custom)
    app.master.configure(bg=app.COLORS["bg"])
    app._setup_styles()

    # Mini 先正规销毁（保存位置），再清空主界面
    if was_mini:
        app._destroy_mini_window()
    for child in list(app.master.winfo_children()):
        try:
            child.destroy()
        except Exception:
            logger.debug("销毁子控件失败", exc_info=True)
    app.btn_start = None
    app.current_time_label = None
    app.target_time_label = None
    app.countdown_label = None
    app.error_label = None
    app.progress_canvas = None
    app._time_spinboxes = []
    app._preset_chips = []

    app._setup_ui()

    # 恢复输入与显示
    app._applying_preset = True
    try:
        if saved_h is not None:
            app.hour_var.set(saved_h)
            app.minute_var.set(saved_m)
            app.second_var.set(saved_s)
    finally:
        app._applying_preset = False

    app.target_time = saved_target
    app.countdown_text = saved_countdown
    if app.btn_start:
        app.btn_start.config(text=button_text_for_state(app._state))
    if app.countdown_label:
        if app._state == STATE_FINISHED and saved_countdown:
            app.countdown_label.config(text=saved_countdown, style="Success.TLabel")
        else:
            app.countdown_label.config(
                text=saved_countdown or "--:--:--",
                style="Countdown.TLabel",
            )
    try:
        app._on_time_changed()
    except Exception:
        logger.debug("主题切换后刷新目标时间失败", exc_info=True)

    # 主题重建后按状态恢复锁定与进度
    app._apply_input_lock()
    app._refresh_progress_bar()

    # Mini 开着则按新颜色重建
    if was_mini:
        app._is_mini = True
        app._create_mini_window()

    app._save_config()
    refresh_tray_menu(app)
