# -*- coding: utf-8 -*-
"""主题应用：优先就地换色，失败则重建主界面（保留业务状态）。"""

from __future__ import annotations

import logging

from core.countdown_core import STATE_FINISHED, button_text_for_state
from core.themes import resolve_theme
from services.tray import refresh_tray_menu

logger = logging.getLogger("count_down_tool")


def _ui_ready_for_recolor(app) -> bool:
    """主窗关键控件是否已建好，可走就地换肤。"""
    master = getattr(app, "master", None)
    if master is None:
        return False
    try:
        if not master.winfo_exists():
            return False
        children = master.winfo_children()
    except Exception:
        return False
    if not children:
        return False
    # 至少有倒计时标签或进度条之一
    for attr in ("countdown_label", "progress_canvas", "btn_start", "_main_frame"):
        w = getattr(app, attr, None)
        if w is None:
            continue
        try:
            if w.winfo_exists():
                return True
        except Exception:
            continue
    return False


def _restore_runtime_ui(app, *, saved_h, saved_m, saved_s, saved_countdown, saved_target) -> None:
    """恢复时分秒、倒计时文案、按钮/进度/锁定（重建与 recolor 共用）。"""
    import tkinter as tk

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
        try:
            app.btn_start.config(text=button_text_for_state(app._state))
        except tk.TclError:
            pass
    if app.countdown_label:
        try:
            if app._state == STATE_FINISHED and saved_countdown:
                app.countdown_label.config(text=saved_countdown, style="Success.TLabel")
            else:
                app.countdown_label.config(
                    text=saved_countdown or "--:--:--",
                    style="Countdown.TLabel",
                )
        except tk.TclError:
            pass
    try:
        app._on_time_changed()
    except (tk.TclError, AttributeError, TypeError, ValueError):
        logger.debug("主题切换后刷新目标时间失败", exc_info=True)

    if hasattr(app, "_apply_primary_button_style"):
        app._apply_primary_button_style()
    app._apply_input_lock()
    app._refresh_progress_bar()


def _rebuild_full_ui(app, *, was_mini, saved_h, saved_m, saved_s, saved_countdown, saved_target) -> None:
    """旧路径：destroy 全部子控件后 `_setup_ui` 重建。"""
    import tkinter as tk

    if was_mini:
        app._destroy_mini_window()
    for child in list(app.master.winfo_children()):
        try:
            child.destroy()
        except tk.TclError:
            logger.debug("销毁子控件失败", exc_info=True)
    app.btn_start = None
    app.current_time_label = None
    app.target_time_label = None
    app.countdown_label = None
    app.error_label = None
    app.progress_canvas = None
    app._time_spinboxes = []
    app._preset_chips = []
    app._main_frame = None
    app._countdown_card = None

    app._setup_ui()
    _restore_runtime_ui(
        app,
        saved_h=saved_h,
        saved_m=saved_m,
        saved_s=saved_s,
        saved_countdown=saved_countdown,
        saved_target=saved_target,
    )

    if was_mini:
        app._is_mini = True
        app._create_mini_window()


def _settings_window_open(app) -> bool:
    """设置窗是否存在且仍有效。"""
    import tkinter as tk

    win = getattr(app, "_settings_window", None)
    if win is None:
        return False
    try:
        return bool(win.winfo_exists())
    except tk.TclError:
        return False


def recolor_settings_window(app, colors=None) -> int:
    """对已打开的设置窗就地换色；成功返回换色控件数，失败返回 0。

    不关窗、不改几何；换色后刷新 Tab 态与各分区 refreshers。
    """
    import tkinter as tk

    from ui.design.themed import recolor_widget_tree, resolve_colors

    win = getattr(app, "_settings_window", None)
    if win is None:
        return 0
    try:
        if not win.winfo_exists():
            return 0
    except tk.TclError:
        return 0

    c = resolve_colors(app, colors)
    if not c:
        return 0
    n = 0
    try:
        win.configure(bg=c.get("bg", "#0F1419"))
        n = recolor_widget_tree(win, c)
    except (tk.TclError, AttributeError, TypeError, KeyError, RuntimeError):
        logger.debug("设置窗就地换色失败", exc_info=True)
        return 0

    restyle = getattr(win, "_settings_restyle_tabs", None)
    if callable(restyle):
        try:
            restyle(c)
        except (tk.TclError, TypeError, AttributeError, ValueError):
            logger.debug("设置窗 Tab 重样式失败", exc_info=True)

    refresh = getattr(win, "_settings_refresh", None)
    if callable(refresh):
        try:
            refresh()
        except (tk.TclError, TypeError, AttributeError, ValueError, RuntimeError):
            logger.debug("设置窗 refreshers 失败", exc_info=True)
    return n


def _reopen_settings_preserving_tab(app, tab: str | None) -> None:
    """关后重开设置窗并恢复 Tab（recolor 失败回退）。"""
    import tkinter as tk

    try:
        from ui.settings_window import close_settings, show_settings

        close_settings(app)
        show_settings(app, initial_tab=tab)
    except (tk.TclError, AttributeError, ImportError, RuntimeError):
        logger.debug("设置窗关开回退失败", exc_info=True)


def refresh_theme_colors(app, *, save: bool = False) -> int:
    """按当前 theme_id + theme_custom 就地换色（不改 theme_id、不关设置窗）。

    用于自定义色预览/应用。返回主窗换色控件数；失败时尽量不抛。
    """
    import tkinter as tk

    from ui.design.themed import recolor_app

    app.COLORS = resolve_theme(app._theme_id, app._theme_custom)
    colors = app.COLORS
    n = 0
    try:
        app.master.configure(bg=colors["bg"])
    except (tk.TclError, AttributeError):
        logger.debug("刷新主窗背景失败", exc_info=True)
    try:
        app._setup_styles()
    except (tk.TclError, AttributeError, TypeError, ValueError):
        logger.debug("刷新 ttk 样式失败", exc_info=True)

    if _ui_ready_for_recolor(app):
        try:
            n = recolor_app(app, colors)
        except (tk.TclError, AttributeError, TypeError, KeyError, RuntimeError):
            logger.debug("自定义色就地换色失败", exc_info=True)
            n = 0
        try:
            if hasattr(app, "_apply_primary_button_style"):
                app._apply_primary_button_style()
            if hasattr(app, "_refresh_progress_bar"):
                app._refresh_progress_bar()
        except (tk.TclError, AttributeError, TypeError, ValueError):
            logger.debug("自定义色后刷新按钮/进度失败", exc_info=True)

    if _settings_window_open(app):
        try:
            recolor_settings_window(app, colors)
        except (tk.TclError, AttributeError, TypeError, KeyError, RuntimeError):
            logger.debug("自定义色设置窗换色失败", exc_info=True)

    if save:
        try:
            app._save_config()
        except (OSError, TypeError, ValueError, AttributeError):
            logger.debug("保存主题自定义色失败", exc_info=True)
    return n


def apply_theme(app, theme_id: str) -> None:
    """切换预设主题：主窗 + 设置窗优先就地换色，失败再重建/关开。"""
    # 同 theme_id 且已有色表：跳过，避免闪烁
    if theme_id == app._theme_id and app.COLORS:
        return
    import tkinter as tk

    from ui.design.themed import recolor_app

    settings_tab = None
    settings_was_open = False
    try:
        from ui.settings_window import get_settings_open_tab

        settings_tab = get_settings_open_tab(app)
        settings_was_open = settings_tab is not None
    except (tk.TclError, AttributeError, ImportError):
        logger.debug("探测设置窗失败", exc_info=True)

    saved_h = saved_m = saved_s = None
    try:
        if getattr(app, "hour_var", None) is not None:
            saved_h = app.hour_var.get()
            saved_m = app.minute_var.get()
            saved_s = app.second_var.get()
    except (tk.TclError, AttributeError, TypeError, ValueError):
        pass
    saved_countdown = app.countdown_text
    saved_target = app.target_time
    was_mini = app._is_mini

    app._theme_id = theme_id
    app.COLORS = resolve_theme(app._theme_id, app._theme_custom)
    colors = app.COLORS
    app.master.configure(bg=colors["bg"])
    app._setup_styles()

    used_recolor = False
    if _ui_ready_for_recolor(app):
        try:
            n = recolor_app(app, colors)
            if n > 0:
                used_recolor = True
                logger.debug("主题就地换色控件数=%s", n)
        except (tk.TclError, AttributeError, TypeError, KeyError, RuntimeError):
            logger.debug("就地换色失败，回退重建", exc_info=True)
            used_recolor = False

    if used_recolor:
        _restore_runtime_ui(
            app,
            saved_h=saved_h,
            saved_m=saved_m,
            saved_s=saved_s,
            saved_countdown=saved_countdown,
            saved_target=saved_target,
        )
        # Mini：本步仍重建（透明色键逻辑不动）
        if was_mini:
            try:
                app._destroy_mini_window()
            except (tk.TclError, AttributeError):
                logger.debug("销毁 Mini 失败", exc_info=True)
            app._is_mini = True
            app._create_mini_window()
    else:
        _rebuild_full_ui(
            app,
            was_mini=was_mini,
            saved_h=saved_h,
            saved_m=saved_m,
            saved_s=saved_s,
            saved_countdown=saved_countdown,
            saved_target=saved_target,
        )

    # 设置窗：优先就地换色；失败再关开保留 Tab
    if settings_was_open and _settings_window_open(app):
        settings_ok = False
        try:
            sn = recolor_settings_window(app, colors)
            settings_ok = sn > 0
            logger.debug("设置窗就地换色控件数=%s", sn)
        except (tk.TclError, AttributeError, TypeError, KeyError, RuntimeError):
            logger.debug("设置窗就地换色异常，将关开", exc_info=True)
            settings_ok = False
        if not settings_ok:
            _reopen_settings_preserving_tab(app, settings_tab)
    elif settings_was_open:
        # 窗已不在（极少见）：按 Tab 重开
        _reopen_settings_preserving_tab(app, settings_tab)

    app._save_config()
    refresh_tray_menu(app)
