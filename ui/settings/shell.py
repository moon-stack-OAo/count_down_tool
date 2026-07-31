# -*- coding: utf-8 -*-
"""设置中心外壳：单例、Tab 切换、公开入口。"""

from __future__ import annotations

import logging
import tkinter as tk

from core.countdown_core import APP_NAME
from ui.app_dialogs import show_error
from ui.design.tokens import SETTINGS_HEIGHT, SETTINGS_WIDTH
from ui.settings.about_tab import build_about_section
from ui.settings.appearance import build_appearance_section
from ui.settings.layout import bind_wheel_tree, make_scroll_page
from ui.settings.sound_tab import build_sound_section
from ui.settings.system_tab import build_system_section
from ui.time_picker import _picker_parent
from ui.window_chrome_dialog import ensure_dialog_visible

logger = logging.getLogger("count_down_tool")

_SETTINGS_TAB_KEYS = frozenset({"appearance", "sound", "system", "about"})


def close_settings(app) -> None:
    """关闭设置窗（主题切换前调用，避免颜色过期的悬浮窗）。"""
    win = getattr(app, "_settings_window", None)
    if win is None:
        return
    try:
        if win.winfo_exists():
            win.destroy()
    except tk.TclError:
        pass
    app._settings_window = None


def show_settings(app, initial_tab: str | None = None) -> None:
    """打开设置中心（单例：已存在则置前）。失败时向用户提示。

    initial_tab: 可选 Tab 键 appearance / sound / system / about；
    主题重建后重开时用于恢复原分区。
    """
    try:
        _show_settings_impl(app, initial_tab=initial_tab)
    except Exception as exc:
        # 设置窗边界：任意构建失败都需提示用户，保留宽捕获
        logger.exception("打开设置中心失败")
        app._settings_window = None
        try:
            show_error(
                app,
                "无法打开设置中心。\n\n"
                f"详情：{exc}\n\n"
                "建议：结束所有倒计时进程后重试；"
                "若 exe 从压缩包拖出，请右键「解除锁定」或重新完整解压后再运行。",
            )
        except (tk.TclError, AttributeError, RuntimeError):
            logger.debug("设置失败提示也失败", exc_info=True)


def _normalize_settings_tab(tab: str | None) -> str:
    """非法或空 Tab 回退到外观。"""
    if tab and tab in _SETTINGS_TAB_KEYS:
        return tab
    return "appearance"


def get_settings_open_tab(app) -> str | None:
    """若设置窗打开则返回当前 Tab 键，否则 None。"""
    win = getattr(app, "_settings_window", None)
    if win is None:
        return None
    try:
        if not win.winfo_exists():
            return None
    except tk.TclError:
        return None
    tab = getattr(win, "_settings_tab", None)
    return _normalize_settings_tab(tab) if tab else "appearance"


def _show_settings_impl(app, initial_tab: str | None = None) -> None:
    """打开设置中心（单例：已存在则强制可见）。"""
    start_tab = _normalize_settings_tab(initial_tab)
    existing = getattr(app, "_settings_window", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                show_tab = getattr(existing, "_settings_show_tab", None)
                if initial_tab is not None and callable(show_tab):
                    try:
                        show_tab(start_tab)
                    except (tk.TclError, TypeError, ValueError):
                        pass
                ensure_dialog_visible(
                    existing, SETTINGS_WIDTH, SETTINGS_HEIGHT
                )
                return
        except tk.TclError:
            pass
        app._settings_window = None

    parent = _picker_parent(app)
    c = app.COLORS
    win = tk.Toplevel(parent)
    app._settings_window = win
    win.title(f"{APP_NAME} · 设置")
    win.configure(bg=c["bg"])
    win.geometry(f"{SETTINGS_WIDTH}x{SETTINGS_HEIGHT}")
    win.resizable(False, False)
    try:
        if parent is not app.master or parent.winfo_viewable():
            win.transient(parent)
    except tk.TclError:
        pass

    # 关闭时清单例并停试听
    def _on_close():
        try:
            from services.sound import stop_playback

            stop_playback()
        except (ImportError, OSError, AttributeError, RuntimeError):
            pass
        try:
            win.destroy()
        except tk.TclError:
            pass
        if getattr(app, "_settings_window", None) is win:
            app._settings_window = None

    win.protocol("WM_DELETE_WINDOW", _on_close)
    # 使用系统原生边框/标题栏（避免无边框窗在部分机器上不可见或难置前）
    try:
        win.bind("<Escape>", lambda e: (_on_close(), "break")[1])
    except tk.TclError:
        pass

    # ===== 顶栏 Tab + 单页可滚动内容 =====
    shell = tk.Frame(win, bg=c["bg"])
    shell.pack(fill=tk.BOTH, expand=True)

    tab_bar = tk.Frame(shell, bg=c.get("title_bar", c["bg"]))
    tab_bar.pack(fill=tk.X, side=tk.TOP)
    tk.Frame(shell, bg=c["accent"], height=2).pack(fill=tk.X, side=tk.TOP)

    page_host = tk.Frame(shell, bg=c["bg"])
    page_host.pack(fill=tk.BOTH, expand=True)

    tabs_spec = (
        ("appearance", "外观"),
        ("sound", "声音"),
        ("system", "系统"),
        ("about", "关于"),
    )
    pages: dict = {}
    tab_btns: dict = {}
    state = {"tab": start_tab}
    win._settings_tab = start_tab  # type: ignore[attr-defined]

    def _style_tab(key: str, active: bool):
        btn = tab_btns.get(key)
        if btn is None:
            return
        try:
            if active:
                btn.config(
                    bg=c["bg"],
                    fg=c.get("accent_glow", c["accent"]),
                    font=app._font("label", 10, bold=True),
                )
            else:
                btn.config(
                    bg=c.get("title_bar", c["bg"]),
                    fg=c["text_dim"],
                    font=app._font("label", 10),
                )
        except tk.TclError:
            pass

    def _show_tab(key: str):
        if key not in pages:
            return
        state["tab"] = key
        win._settings_tab = key  # type: ignore[attr-defined]
        for k, frame in pages.items():
            try:
                if k == key:
                    frame.pack(fill=tk.BOTH, expand=True)
                else:
                    frame.pack_forget()
            except tk.TclError:
                pass
            _style_tab(k, k == key)
        # 切页后滚回顶部，并按当前内容高度同步是否可滚
        try:
            pages[key]._settings_canvas.yview_moveto(0)  # type: ignore[attr-defined]
        except (tk.TclError, AttributeError):
            pass
        try:
            sync = getattr(pages[key], "_settings_sync_scroll", None)
            if sync:
                pages[key].after_idle(sync)
        except (tk.TclError, AttributeError, TypeError):
            pass

    win._settings_show_tab = _show_tab  # type: ignore[attr-defined]

    for key, label in tabs_spec:
        btn = tk.Label(
            tab_bar,
            text=label,
            font=app._font("label", 10),
            bg=c.get("title_bar", c["bg"]),
            fg=c["text_dim"],
            padx=16,
            pady=10,
            cursor="hand2",
        )
        btn.pack(side=tk.LEFT)
        btn.bind("<Button-1>", lambda e, k=key: _show_tab(k))
        tab_btns[key] = btn

        page = make_scroll_page(page_host, app, c)
        pages[key] = page

    # 状态刷新回调集合（主题/音效切换后局部更新勾选）
    refreshers = []

    def _refresh_all():
        for fn in list(refreshers):
            try:
                fn()
            except (tk.TclError, AttributeError, TypeError, ValueError, RuntimeError):
                logger.debug("设置窗刷新失败", exc_info=True)

    build_appearance_section(app, pages["appearance"]._settings_content, c, refreshers)
    build_sound_section(app, pages["sound"]._settings_content, c, refreshers, win)
    build_system_section(app, pages["system"]._settings_content, c, refreshers)
    build_about_section(app, pages["about"]._settings_content, c)

    _show_tab(start_tab)
    win.update_idletasks()
    for page in pages.values():
        bind_wheel_tree(page, page._settings_canvas)
        sync = getattr(page, "_settings_sync_scroll", None)
        if sync:
            try:
                page.after_idle(sync)
            except tk.TclError:
                pass
    # 强制可见：多次居中 + 短暂 topmost，避免「点了没反应」
    ensure_dialog_visible(win, SETTINGS_WIDTH, SETTINGS_HEIGHT)
    # 暴露刷新，供内部局部更新勾选
    win._settings_refresh = _refresh_all  # type: ignore[attr-defined]
