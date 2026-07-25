# -*- coding: utf-8 -*-
"""产品化更新对话框：发现更新 / 下载进度 / 轻量提示。"""

from __future__ import annotations

import logging
import platform
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from core.countdown_core import APP_NAME
from ui.design.tokens import (
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
    UPDATE_DIALOG_MIN_HEIGHT,
    UPDATE_DIALOG_WIDTH,
)
from ui.time_picker import _activate_picker, _picker_parent
from ui.window_chrome_dialog import center_dialog_later
from ui.window_chrome_dialog import CHROME_TITLE_HEIGHT, use_borderless_chrome

logger = logging.getLogger("count_down_tool")

# 主操作：install | download_only | browser | ignore | later
ActionCb = Optional[Callable[[str], None]]


def show_update_available(app, result, notes: str, on_action: ActionCb = None) -> None:
    """显示「发现新版本」对话框。

    on_action(action)：accept 后由 updater 处理 install/download/browser；
    action 为 ignore / later 时 updater 侧做对应处理。
    """
    parent = _picker_parent(app)
    c = app.COLORS
    ver = getattr(result, "latest_version", "") or "—"
    cur = getattr(result, "current_version", "") or "—"
    pk = getattr(result, "platform_key", "") or ""

    # 主按钮文案
    if pk == "windows" and getattr(result, "asset_url", None):
        from core import update as core_update

        if core_update.is_frozen_app():
            primary_text = "安装并重启"
            primary_action = "install"
        else:
            primary_text = "打开下载页"
            primary_action = "browser"
    elif pk == "darwin" and getattr(result, "asset_url", None):
        primary_text = "下载安装包"
        primary_action = "download_only"
    else:
        primary_text = "打开网页"
        primary_action = "browser"

    win = tk.Toplevel(parent)
    win.title(f"{APP_NAME} · 发现更新")
    win.configure(bg=c["bg"])
    win.resizable(False, False)
    try:
        win.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        if parent is not app.master or parent.winfo_viewable():
            win.transient(parent)
    except tk.TclError:
        pass

    closed = {"done": False}

    def _finish(action: str):
        if closed["done"]:
            return
        closed["done"] = True
        try:
            win.destroy()
        except tk.TclError:
            pass
        if on_action:
            try:
                on_action(action)
            except Exception:
                logger.exception("更新对话框回调失败")

    win.protocol("WM_DELETE_WINDOW", lambda: _finish("later"))
    borderless = use_borderless_chrome(
        win, app, title="发现更新", on_close=lambda: _finish("later")
    )

    shell = tk.Frame(win, bg=c["bg"], padx=SPACE_LG, pady=SPACE_LG)
    shell.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        shell,
        text="发现新版本",
        font=app._font("button", 13, bold=True),
        bg=c["bg"],
        fg=c["text"],
    ).pack(anchor="w")
    tk.Label(
        shell,
        text=f"{ver}  ←  当前 {cur}",
        font=app._font("label", 10),
        bg=c["bg"],
        fg=c["accent_glow"],
    ).pack(anchor="w", pady=(SPACE_XS, SPACE_MD))
    tk.Frame(shell, bg=c["accent"], height=2).pack(fill=tk.X, pady=(0, SPACE_MD))

    # 发布说明卡片
    notes_card = tk.Frame(
        shell,
        bg=c["card"],
        highlightbackground=c["border"],
        highlightthickness=1,
        padx=SPACE_MD,
        pady=SPACE_MD,
    )
    notes_card.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        notes_card,
        text="更新说明",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
    ).pack(fill=tk.X)

    notes_text = (notes or "").strip() or "（无发布说明）"
    # Text 便于长文滚动
    text = tk.Text(
        notes_card,
        height=8,
        wrap=tk.WORD,
        font=app._font("label", 9),
        bg=c["input_bg"],
        fg=c["text"],
        insertbackground=c["accent"],
        relief=tk.FLAT,
        bd=0,
        padx=SPACE_SM,
        pady=SPACE_SM,
        highlightthickness=1,
        highlightbackground=c["border"],
    )
    text.pack(fill=tk.BOTH, expand=True, pady=(SPACE_XS, 0))
    text.insert("1.0", notes_text)
    text.configure(state=tk.DISABLED)

    footer = tk.Frame(shell, bg=c["bg"])
    footer.pack(fill=tk.X, pady=(SPACE_LG, 0))

    _pill(
        footer,
        "忽略此版本",
        app=app,
        c=c,
        primary=False,
        command=lambda: _finish("ignore"),
    ).pack(side=tk.LEFT)

    _pill(
        footer,
        "稍后",
        app=app,
        c=c,
        primary=False,
        command=lambda: _finish("later"),
    ).pack(side=tk.RIGHT)

    _pill(
        footer,
        primary_text,
        app=app,
        c=c,
        primary=True,
        command=lambda: _finish(primary_action),
    ).pack(side=tk.RIGHT, padx=(0, SPACE_SM))

    win.update_idletasks()
    w = max(UPDATE_DIALOG_WIDTH, win.winfo_reqwidth() + 24)
    h = max(UPDATE_DIALOG_MIN_HEIGHT, win.winfo_reqheight() + 16)
    # 无边框后不再加系统标题栏余量；自绘标题栏高度已计入 reqheight
    if not borderless and platform.system() == "Windows":
        h += 28
        w += 12
    _center(win, w, h)
    _activate_picker(win)


def show_update_progress(app, title: str, message: str = "") -> tk.Toplevel:
    """显示下载/安装进度窗。返回 window，附带 progressbar 与 message_label。"""
    parent = _picker_parent(app)
    c = app.COLORS
    win = tk.Toplevel(parent)
    win.title(f"{APP_NAME} · {title}")
    win.configure(bg=c["bg"])
    win.resizable(False, False)
    try:
        win.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        if parent is not app.master or parent.winfo_viewable():
            win.transient(parent)
    except tk.TclError:
        pass
    # 下载中禁止关窗误操作（× / Esc / 协议均 no-op）
    win.protocol("WM_DELETE_WINDOW", lambda: None)
    borderless = use_borderless_chrome(
        win,
        app,
        title=title or "更新",
        on_close=lambda: None,
        close_enabled=False,
    )

    shell = tk.Frame(win, bg=c["bg"], padx=SPACE_LG, pady=SPACE_LG)
    shell.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        shell,
        text=title,
        font=app._font("button", 12, bold=True),
        bg=c["bg"],
        fg=c["text"],
    ).pack(anchor="w")

    msg_lbl = tk.Label(
        shell,
        text=message or "请稍候…",
        font=app._font("label", 9),
        bg=c["bg"],
        fg=c["text_muted"],
        wraplength=UPDATE_DIALOG_WIDTH - 48,
        justify=tk.LEFT,
        anchor="w",
    )
    msg_lbl.pack(anchor="w", pady=(SPACE_SM, SPACE_MD))

    # ttk Progressbar：先 indeterminate，有 total 后切 determinate
    style = ttk.Style(win)
    try:
        style.theme_use("clam")
        style.configure(
            "Update.Horizontal.TProgressbar",
            troughcolor=c["input_bg"],
            background=c["accent"],
            bordercolor=c["border"],
            lightcolor=c["accent"],
            darkcolor=c["accent"],
        )
    except tk.TclError:
        pass

    bar = ttk.Progressbar(
        shell,
        orient=tk.HORIZONTAL,
        length=UPDATE_DIALOG_WIDTH - 48,
        mode="indeterminate",
        style="Update.Horizontal.TProgressbar",
        maximum=100,
    )
    bar.pack(fill=tk.X, pady=(0, SPACE_SM))
    try:
        bar.start(12)
    except tk.TclError:
        pass

    pct_lbl = tk.Label(
        shell,
        text="",
        font=app._font("label", 9),
        bg=c["bg"],
        fg=c["text_dim"],
        anchor="e",
    )
    pct_lbl.pack(fill=tk.X)

    win._progress_bar = bar  # type: ignore[attr-defined]
    win._progress_msg = msg_lbl  # type: ignore[attr-defined]
    win._progress_pct = pct_lbl  # type: ignore[attr-defined]
    win._progress_mode = "indeterminate"  # type: ignore[attr-defined]

    win.update_idletasks()
    w = UPDATE_DIALOG_WIDTH
    # 自绘标题栏已计入 reqheight；无边框不再加系统标题栏余量
    min_h = 140 + (CHROME_TITLE_HEIGHT if borderless else 0)
    h = max(min_h, win.winfo_reqheight() + 24)
    _center(win, w, h)
    _activate_picker(win)
    return win


def update_progress(win, received: int, total: int) -> None:
    """更新进度条（须在主线程调用）。"""
    if win is None:
        return
    try:
        if not win.winfo_exists():
            return
    except tk.TclError:
        return

    bar = getattr(win, "_progress_bar", None)
    pct_lbl = getattr(win, "_progress_pct", None)
    if bar is None:
        return

    try:
        if total and total > 0:
            if getattr(win, "_progress_mode", "") != "determinate":
                try:
                    bar.stop()
                except tk.TclError:
                    pass
                bar.configure(mode="determinate", maximum=100)
                win._progress_mode = "determinate"  # type: ignore[attr-defined]
            ratio = min(100.0, max(0.0, (received / float(total)) * 100.0))
            bar["value"] = ratio
            if pct_lbl is not None:
                mb_r = received / (1024 * 1024)
                mb_t = total / (1024 * 1024)
                pct_lbl.config(text=f"{mb_r:.1f} / {mb_t:.1f} MB  ({ratio:.0f}%)")
        else:
            if pct_lbl is not None and received > 0:
                mb_r = received / (1024 * 1024)
                pct_lbl.config(text=f"已下载 {mb_r:.1f} MB")
    except tk.TclError:
        pass


def close_progress(win) -> None:
    """关闭进度窗。"""
    if win is None:
        return
    try:
        bar = getattr(win, "_progress_bar", None)
        if bar is not None:
            try:
                bar.stop()
            except tk.TclError:
                pass
        if win.winfo_exists():
            win.destroy()
    except tk.TclError:
        pass


def show_update_message(app, kind: str, message: str, title: str = "") -> None:
    """主题化轻量提示：委托统一 app_dialogs。"""
    from ui.app_dialogs import show_error, show_info

    kind = (kind or "info").lower()
    if kind == "error":
        show_error(app, message, title=title or "出错了")
    else:
        show_info(app, message, title=title or "提示")


def _pill(parent, text, *, app, c, primary=True, command=None):
    """兼容旧调用：委托统一 make_pill。"""
    from ui.widgets import make_pill

    return make_pill(parent, text, app=app, c=c, primary=primary, command=command)


def _center(win, w: int, h: int) -> None:
    """居中（含 overrideredirect 后补定位）。"""
    center_dialog_later(win, int(w), int(h))
