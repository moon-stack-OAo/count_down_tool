# -*- coding: utf-8 -*-
"""设置中心外壳：单例、Tab 切换、公开入口。"""

from __future__ import annotations

import logging
import tkinter as tk

from core.countdown_core import APP_NAME
from ui.app_dialogs import show_error
from ui.design.themed import register_themed
from ui.design.tokens import (
    FONT_BODY,
    FONT_CAPTION,
    SETTINGS_ALPHA,
    SETTINGS_BESIDE_GAP,
    SETTINGS_HEIGHT,
    SETTINGS_WIDTH,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
)
from ui.settings.about_tab import build_about_section
from ui.settings.appearance import build_appearance_section
from ui.settings.layout import bind_wheel_tree, divider, make_scroll_page
from ui.settings.shift_tab import build_shift_section
from ui.settings.sound_tab import build_sound_section
from ui.settings.system_tab import build_system_section
from ui.time_picker import _picker_parent
from ui.window_chrome_dialog import ensure_dialog_visible

logger = logging.getLogger("count_down_tool")

_SETTINGS_TAB_KEYS = frozenset({"appearance", "sound", "shift", "system", "about"})
_TOAST_DEFAULT_MS = 2200


def close_settings(app) -> None:
    """关闭设置窗（recolor 失败回退或主动关闭时调用）。"""
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

    initial_tab: 可选 Tab 键 appearance / sound / shift / system / about；
    就地换肤失败关开后用于恢复原分区。
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


def show_settings_toast(
    app,
    message: str,
    *,
    kind: str = "ok",
    duration_ms: int = _TOAST_DEFAULT_MS,
) -> bool:
    """设置中心底部轻提示（不弹窗）。

    kind: ok / info / error（影响文字与左侧色条）。
    无提示时 toast 条隐藏，避免占底遮挡内容。
    设置窗未打开时返回 False，调用方可回退到 show_info。
    """
    win = getattr(app, "_settings_window", None)
    if win is None:
        return False
    try:
        if not win.winfo_exists():
            return False
    except tk.TclError:
        return False

    toast = getattr(win, "_settings_toast", None)
    toast_bar = getattr(win, "_settings_toast_bar", None)
    if toast is None:
        return False

    c = getattr(app, "COLORS", {}) or {}
    kind_l = (kind or "ok").lower()
    if kind_l == "error":
        fg = c["error"]
        bar_fg = c["error"]
    elif kind_l == "info":
        fg = c.get("text_dim", c["text"])
        bar_fg = c.get("accent", c.get("border", fg))
    else:
        fg = c.get("success", c.get("accent_glow", c["accent"]))
        bar_fg = c.get("success", c.get("accent", fg))

    text = (message or "").replace("\n", " ").strip()
    if len(text) > 80:
        text = text[:77] + "…"

    try:
        toast.config(text=text, fg=fg)
        accent = getattr(win, "_settings_toast_accent", None)
        if accent is not None:
            accent.config(bg=bar_fg)
        # 有文案时再显示底栏，避免空条遮挡
        if toast_bar is not None and not toast_bar.winfo_ismapped():
            toast_bar.pack(fill=tk.X, side=tk.BOTTOM)
    except tk.TclError:
        return False

    # 取消上一次自动清空
    prev = getattr(win, "_settings_toast_after", None)
    if prev is not None:
        try:
            win.after_cancel(prev)
        except (tk.TclError, ValueError):
            pass
        win._settings_toast_after = None  # type: ignore[attr-defined]

    def _clear():
        try:
            if getattr(app, "_settings_window", None) is win and win.winfo_exists():
                toast.config(text="")
                if toast_bar is not None and toast_bar.winfo_ismapped():
                    toast_bar.pack_forget()
        except tk.TclError:
            pass
        try:
            win._settings_toast_after = None  # type: ignore[attr-defined]
        except (tk.TclError, AttributeError):
            pass

    try:
        ms = max(800, int(duration_ms))
        win._settings_toast_after = win.after(ms, _clear)  # type: ignore[attr-defined]
    except (tk.TclError, ValueError, TypeError):
        pass
    return True


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
                    existing,
                    SETTINGS_WIDTH,
                    SETTINGS_HEIGHT,
                    anchor_win=_picker_parent(app),
                    gap=SETTINGS_BESIDE_GAP,
                    alpha=SETTINGS_ALPHA,
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
    register_themed(shell, bg="bg")
    shell.pack(fill=tk.BOTH, expand=True)

    tab_bar = tk.Frame(shell, bg=c.get("title_bar", c["bg"]))
    register_themed(tab_bar, bg="title_bar")
    tab_bar.pack(fill=tk.X, side=tk.TOP)

    # 底部轻提示：默认不 pack，有 toast 时再贴底，避免空条遮挡内容
    toast_bg = c.get("toast_bg", c.get("card", c["bg"]))
    toast_bar = tk.Frame(shell, bg=toast_bg)
    register_themed(toast_bar, bg="toast_bg")
    divider(toast_bar, c, pady=0, side=tk.TOP)
    toast_row = tk.Frame(toast_bar, bg=toast_bg)
    register_themed(toast_row, bg="toast_bg")
    toast_row.pack(fill=tk.X)
    toast_accent = tk.Frame(toast_row, bg=c.get("accent", c["border"]), width=3)
    register_themed(toast_accent, bg="accent")
    toast_accent.pack(side=tk.LEFT, fill=tk.Y)
    toast_lbl = tk.Label(
        toast_row,
        text="",
        font=app._font("label", FONT_CAPTION),
        bg=toast_bg,
        fg=c.get("text_muted", c["text_dim"]),
        anchor="w",
        padx=SPACE_MD,
        pady=SPACE_SM,
    )
    register_themed(toast_lbl, bg="toast_bg", fg="text_muted")
    toast_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
    win._settings_toast = toast_lbl  # type: ignore[attr-defined]
    win._settings_toast_bar = toast_bar  # type: ignore[attr-defined]
    win._settings_toast_after = None  # type: ignore[attr-defined]
    win._settings_toast_accent = toast_accent  # type: ignore[attr-defined]

    page_host = tk.Frame(shell, bg=c["bg"])
    register_themed(page_host, bg="bg")
    page_host.pack(fill=tk.BOTH, expand=True)

    tabs_spec = (
        ("appearance", "外观"),
        ("sound", "声音"),
        ("shift", "班次"),
        ("system", "系统"),
        ("about", "关于"),
    )
    pages: dict = {}
    tab_btns: dict = {}
    state = {"tab": start_tab}
    win._settings_tab = start_tab  # type: ignore[attr-defined]

    tab_indicators: dict = {}

    def _style_tab(key: str, active: bool, colors=None):
        btn = tab_btns.get(key)
        if btn is None:
            return
        palette = colors if isinstance(colors, dict) and colors else (
            getattr(app, "COLORS", None) or c
        )
        indicator = tab_indicators.get(key)
        try:
            if active:
                btn.config(
                    bg=palette.get("title_bar", palette["bg"]),
                    fg=palette["text"],
                    font=app._font("label", FONT_BODY, bold=True),
                )
                register_themed(btn, bg="title_bar", fg="text")
                if indicator is not None:
                    indicator.config(
                        bg=palette.get("tab_active", palette["accent"])
                    )
                    register_themed(indicator, bg="tab_active")
            else:
                btn.config(
                    bg=palette.get("title_bar", palette["bg"]),
                    fg=palette.get("muted", palette["text_muted"]),
                    font=app._font("label", FONT_BODY),
                )
                register_themed(btn, bg="title_bar", fg="text_muted")
                if indicator is not None:
                    indicator.config(bg=palette.get("title_bar", palette["bg"]))
                    register_themed(indicator, bg="title_bar")
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
        col = tk.Frame(tab_bar, bg=c.get("title_bar", c["bg"]))
        register_themed(col, bg="title_bar")
        col.pack(side=tk.LEFT)
        btn = tk.Label(
            col,
            text=label,
            font=app._font("label", FONT_BODY),
            bg=c.get("title_bar", c["bg"]),
            fg=c.get("muted", c["text_muted"]),
            padx=SPACE_LG,
            pady=SPACE_SM + 2,
            cursor="hand2",
        )
        register_themed(btn, bg="title_bar", fg="text_muted")
        btn.pack(side=tk.TOP)
        btn.bind("<Button-1>", lambda e, k=key: _show_tab(k))
        indicator = tk.Frame(
            col, bg=c.get("title_bar", c["bg"]), height=2
        )
        register_themed(indicator, bg="title_bar")
        indicator.pack(side=tk.TOP, fill=tk.X)
        tab_btns[key] = btn
        tab_indicators[key] = indicator

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

    def _restyle_tabs(colors=None):
        cur = state.get("tab") or win._settings_tab  # type: ignore[attr-defined]
        for k in tab_btns:
            _style_tab(k, k == cur, colors=colors)

    build_appearance_section(app, pages["appearance"]._settings_content, c, refreshers)
    build_sound_section(app, pages["sound"]._settings_content, c, refreshers, win)
    build_shift_section(app, pages["shift"]._settings_content, c, refreshers)
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
    # 强制可见：偏侧父窗 + 略透明 + 短暂 topmost，避免「点了没反应」
    ensure_dialog_visible(
        win,
        SETTINGS_WIDTH,
        SETTINGS_HEIGHT,
        anchor_win=parent,
        gap=SETTINGS_BESIDE_GAP,
        alpha=SETTINGS_ALPHA,
    )
    # 暴露刷新，供内部局部更新勾选 / 就地换肤后 Tab 态
    win._settings_refresh = _refresh_all  # type: ignore[attr-defined]
    win._settings_restyle_tabs = _restyle_tabs  # type: ignore[attr-defined]
    win._settings_tab_btns = tab_btns  # type: ignore[attr-defined]
