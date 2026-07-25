# -*- coding: utf-8 -*-
"""统一主题弹窗：info / error / confirm，保证盖过设置窗置顶。"""

from __future__ import annotations

import logging
import platform
import tkinter as tk
from typing import Optional

from core.countdown_core import APP_NAME
from ui.design.tokens import SPACE_LG, SPACE_MD, SPACE_SM
from ui.widgets import make_pill
from ui.window_chrome_dialog import center_dialog_later, use_borderless_chrome

logger = logging.getLogger("count_down_tool")

_DIALOG_WIDTH = 400


def _dialog_parent(app, parent=None):
    """优先设置窗，其次可见主/Mini 窗。"""
    if parent is not None:
        try:
            if parent.winfo_exists():
                return parent
        except tk.TclError:
            pass
    sw = getattr(app, "_settings_window", None)
    if sw is not None:
        try:
            if sw.winfo_exists():
                return sw
        except tk.TclError:
            pass
    if getattr(app, "_is_mini", False):
        mini = getattr(app, "mini_window", None)
        if mini is not None:
            try:
                if mini.winfo_exists():
                    return mini
            except tk.TclError:
                pass
    return app.master


def _activate(win: tk.Misc) -> None:
    try:
        win.lift()
        win.attributes("-topmost", True)
        win.focus_force()
    except tk.TclError:
        pass
    if platform.system() == "Windows":
        try:
            import ctypes

            win.update_idletasks()
            frame = win.wm_frame()
            hwnd = int(frame, 16) if frame else int(win.winfo_id())
            user32 = ctypes.windll.user32
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        except Exception:
            logger.debug("弹窗置前失败", exc_info=True)


def _set_topmost(win: Optional[tk.Misc], value: bool) -> None:
    if win is None:
        return
    try:
        if win.winfo_exists():
            win.attributes("-topmost", bool(value))
    except tk.TclError:
        pass


class _TopmostGuard:
    """打开系统对话框前临时取消设置/主弹窗置顶，结束后恢复。"""

    def __init__(self, *windows):
        self._windows = [w for w in windows if w is not None]
        self._prev = []

    def __enter__(self):
        for w in self._windows:
            try:
                if w.winfo_exists():
                    prev = bool(w.attributes("-topmost"))
                    self._prev.append((w, prev))
                    if prev:
                        w.attributes("-topmost", False)
                else:
                    self._prev.append((w, False))
            except tk.TclError:
                self._prev.append((w, False))
        return self

    def __exit__(self, *exc):
        for w, prev in self._prev:
            try:
                if w.winfo_exists() and prev:
                    w.attributes("-topmost", True)
                    w.lift()
            except tk.TclError:
                pass
        return False


def temporary_release_topmost(*windows) -> _TopmostGuard:
    """with temporary_release_topmost(settings_win): filedialog..."""
    return _TopmostGuard(*windows)


class _WithdrawGuard:
    """打开系统对话框前隐藏无边框窗（Windows overrideredirect 会盖住文件框）。"""

    def __init__(self, *windows):
        self._windows = [w for w in windows if w is not None]
        self._hidden = []

    def __enter__(self):
        for w in self._windows:
            try:
                if not w.winfo_exists():
                    continue
                # 无论是否 viewable 都尝试隐藏；并确保不置顶
                try:
                    w.attributes("-topmost", False)
                except tk.TclError:
                    pass
                try:
                    w.withdraw()
                except tk.TclError:
                    pass
                self._hidden.append(w)
            except tk.TclError:
                pass
        try:
            for w in self._windows:
                w.update_idletasks()
            # 让 WM 先处理 hide，再弹系统对话框
            if self._windows:
                self._windows[0].update()
        except Exception:
            pass
        return self

    def __exit__(self, *exc):
        for w in self._hidden:
            try:
                if w.winfo_exists():
                    try:
                        w.attributes("-topmost", False)
                    except tk.TclError:
                        pass
                    w.deiconify()
                    w.lift()
            except tk.TclError:
                pass
        return False


def temporary_withdraw(*windows) -> _WithdrawGuard:
    """with temporary_withdraw(settings_win): filedialog.askopenfilename(...)"""
    return _WithdrawGuard(*windows)


def _show_message(
    app,
    kind: str,
    message: str,
    *,
    title: str = "",
    parent=None,
) -> None:
    """非阻塞主题提示（info / error）。"""
    parent = _dialog_parent(app, parent)
    c = app.COLORS
    kind = (kind or "info").lower()
    if kind == "error":
        accent = c.get("error", "#FB7185")
        default_title = "出错了"
    else:
        accent = c.get("accent", "#38BDF8")
        default_title = "提示"
    display_title = title or default_title

    win = tk.Toplevel(parent)
    win.title(f"{APP_NAME} · {display_title}")
    win.configure(bg=c["bg"])
    win.resizable(False, False)
    try:
        win.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        win.transient(parent)
    except tk.TclError:
        pass

    def _close(_e=None):
        try:
            win.destroy()
        except tk.TclError:
            pass
        return "break"

    win.protocol("WM_DELETE_WINDOW", _close)
    use_borderless_chrome(win, app, title=display_title, on_close=_close)

    shell = tk.Frame(win, bg=c["bg"], padx=SPACE_LG, pady=SPACE_LG)
    shell.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        shell,
        text=display_title,
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
        wraplength=_DIALOG_WIDTH - 48,
        justify=tk.LEFT,
        anchor="w",
    ).pack(anchor="w", pady=(SPACE_SM, SPACE_LG))

    make_pill(shell, "知道了", app=app, c=c, primary=True, command=_close).pack(side=tk.RIGHT)

    win.update_idletasks()
    w = max(320, min(_DIALOG_WIDTH, win.winfo_reqwidth() + 32))
    h = max(140, win.winfo_reqheight() + 16)
    center_dialog_later(win, int(w), int(h))
    _activate(win)
    # 再抬一次，压过设置窗
    try:
        win.after(30, lambda: _activate(win))
        win.after(120, lambda: _activate(win))
    except tk.TclError:
        pass


def show_info(app, message: str, *, title: str = "", parent=None) -> None:
    _show_message(app, "info", message, title=title or "提示", parent=parent)


def show_error(app, message: str, *, title: str = "", parent=None) -> None:
    _show_message(app, "error", message, title=title or "出错了", parent=parent)


def ask_yes_no(
    app,
    message: str,
    *,
    title: str = "请确认",
    yes_text: str = "确定",
    no_text: str = "取消",
    danger: bool = False,
    parent=None,
) -> bool:
    """模态确认，返回 True=确定。"""
    parent = _dialog_parent(app, parent)
    c = app.COLORS
    result = {"ok": False}

    win = tk.Toplevel(parent)
    win.title(f"{APP_NAME} · {title}")
    win.configure(bg=c["bg"])
    win.resizable(False, False)
    try:
        win.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        win.transient(parent)
        win.grab_set()
    except tk.TclError:
        pass

    def _finish(ok: bool):
        result["ok"] = ok
        try:
            win.grab_release()
        except tk.TclError:
            pass
        try:
            win.destroy()
        except tk.TclError:
            pass

    win.protocol("WM_DELETE_WINDOW", lambda: _finish(False))
    use_borderless_chrome(win, app, title=title, on_close=lambda: _finish(False))

    shell = tk.Frame(win, bg=c["bg"], padx=SPACE_LG, pady=SPACE_LG)
    shell.pack(fill=tk.BOTH, expand=True)

    accent = c.get("error", "#FB7185") if danger else c.get("accent", "#38BDF8")
    tk.Label(
        shell,
        text=title,
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
        wraplength=_DIALOG_WIDTH - 48,
        justify=tk.LEFT,
        anchor="w",
    ).pack(anchor="w", pady=(SPACE_SM, SPACE_LG))

    row = tk.Frame(shell, bg=c["bg"])
    row.pack(fill=tk.X)
    make_pill(
        row,
        yes_text,
        app=app,
        c=c,
        primary=not danger,
        danger=danger,
        command=lambda: _finish(True),
    ).pack(side=tk.RIGHT, padx=(SPACE_SM, 0))
    make_pill(
        row, no_text, app=app, c=c, primary=False, command=lambda: _finish(False)
    ).pack(side=tk.RIGHT)

    win.update_idletasks()
    w = max(320, min(_DIALOG_WIDTH, win.winfo_reqwidth() + 32))
    h = max(160, win.winfo_reqheight() + 16)
    center_dialog_later(win, int(w), int(h))
    _activate(win)
    try:
        win.after(30, lambda: _activate(win))
    except tk.TclError:
        pass
    try:
        parent.wait_window(win)
    except tk.TclError:
        pass
    return bool(result["ok"])
