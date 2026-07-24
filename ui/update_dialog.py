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

    win.protocol("WM_DELETE_WINDOW", lambda: _finish("later"))

    win.update_idletasks()
    w = max(UPDATE_DIALOG_WIDTH, win.winfo_reqwidth() + 24)
    h = max(UPDATE_DIALOG_MIN_HEIGHT, win.winfo_reqheight() + 16)
    if platform.system() == "Windows":
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
    # 下载中禁止关窗误操作（仍可协议关闭，避免卡死）
    win.protocol("WM_DELETE_WINDOW", lambda: None)

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
    h = max(140, win.winfo_reqheight() + 24)
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
    """主题化轻量提示（info / error）。简单场景也可用 messagebox。"""
    parent = _picker_parent(app)
    c = app.COLORS
    kind = (kind or "info").lower()
    if kind == "error":
        accent = c.get("error", "#FB7185")
        default_title = "出错了"
    else:
        accent = c.get("accent", "#38BDF8")
        default_title = "提示"

    win = tk.Toplevel(parent)
    win.title(f"{APP_NAME} · {title or default_title}")
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

    shell = tk.Frame(win, bg=c["bg"], padx=SPACE_LG, pady=SPACE_LG)
    shell.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        shell,
        text=title or default_title,
        font=app._font("button", 12, bold=True),
        bg=c["bg"],
        fg=accent,
    ).pack(anchor="w")
    tk.Label(
        shell,
        text=message or "",
        font=app._font("label", 9),
        bg=c["bg"],
        fg=c["text"],
        wraplength=UPDATE_DIALOG_WIDTH - 48,
        justify=tk.LEFT,
        anchor="w",
    ).pack(anchor="w", pady=(SPACE_SM, SPACE_LG))

    def _close():
        try:
            win.destroy()
        except tk.TclError:
            pass

    _pill(shell, "知道了", app=app, c=c, primary=True, command=_close).pack(
        side=tk.RIGHT
    )
    win.protocol("WM_DELETE_WINDOW", _close)
    win.update_idletasks()
    w = max(320, min(UPDATE_DIALOG_WIDTH, win.winfo_reqwidth() + 32))
    h = max(140, win.winfo_reqheight() + 16)
    _center(win, w, h)
    _activate_picker(win)


def _pill(parent, text, *, app, c, primary=True, command=None):
    bg = c["accent"] if primary else c["chip"]
    fg = c["bg"] if primary else c["text"]
    hover = c["accent_hover"] if primary else c.get("chip_hover", c["border"])
    btn = tk.Label(
        parent,
        text=text,
        font=app._font("label", 9, bold=True) if primary else app._font("label", 9),
        bg=bg,
        fg=fg,
        padx=14,
        pady=6,
        cursor="hand2",
    )
    if command:
        btn.bind("<Button-1>", lambda e: command())
    btn.bind("<Enter>", lambda e: btn.config(bg=hover))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn


def _center(win, w: int, h: int) -> None:
    try:
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 3)
        win.geometry(f"{int(w)}x{int(h)}+{x}+{y}")
    except tk.TclError:
        pass
