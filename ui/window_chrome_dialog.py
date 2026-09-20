# -*- coding: utf-8 -*-
"""对话框窗口辅助：原生边框 + Esc 关闭 + 居中/置前。"""

from __future__ import annotations

import platform
import tkinter as tk
from typing import Callable


def use_borderless_chrome(
    win: tk.Toplevel,
    app,
    *,
    title: str,
    on_close: Callable[[], None],
    height_title: int = 0,
    close_enabled: bool = True,
) -> bool:
    """为对话框绑定 Esc / 关闭协议（系统原生边框，不再自绘无边框）。

    恒返回 False（兼容旧调用方按 borderless 分支计算尺寸）。
    title / height_title / app 保留仅为调用方签名兼容。
    """
    del app, title, height_title  # 签名兼容，原生边框下不使用

    def _do_close(_event=None):
        if not close_enabled:
            return "break"
        try:
            on_close()
        except (tk.TclError, AttributeError, RuntimeError):
            pass
        return "break"

    if close_enabled:
        try:
            win.bind("<Escape>", _do_close)
        except tk.TclError:
            pass
        try:
            win.protocol("WM_DELETE_WINDOW", on_close)
        except tk.TclError:
            pass
    return False


def chrome_title_height(applied: bool, height: int = 0) -> int:
    """尺寸计算用：已不再使用自绘标题栏，恒返回 0。"""
    del applied, height
    return 0


def center_dialog(win: tk.Misc, w: int, h: int, *, y_ratio: float = 1 / 3) -> None:
    """将对话框居中到当前显示器工作区（排除任务栏）。"""
    try:
        win.update_idletasks()
    except tk.TclError:
        return

    x = y = None
    try:
        from services.windows_native import get_work_area

        work = get_work_area(win)
        if work:
            ox, oy, aw, ah = work
            x = ox + max(0, (aw - w) // 2)
            y = oy + max(0, int((ah - h) * y_ratio))
    except (ImportError, OSError, AttributeError, TypeError, ValueError):
        pass

    if x is None:
        try:
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            x = max(0, (sw - w) // 2)
            y = max(0, int((sh - h) * y_ratio))
        except tk.TclError:
            return

    try:
        win.geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")
    except tk.TclError:
        return


def center_dialog_later(win: tk.Misc, w: int, h: int, *, y_ratio: float = 1 / 3) -> None:
    """立即居中，并在 idle/50ms 后再居中一次。"""
    center_dialog(win, w, h, y_ratio=y_ratio)

    def _again():
        try:
            if win.winfo_exists():
                center_dialog(win, w, h, y_ratio=y_ratio)
        except tk.TclError:
            pass

    try:
        win.after_idle(_again)
        win.after(50, _again)
        win.after(150, _again)
    except tk.TclError:
        pass


def ensure_dialog_visible(
    win: tk.Misc,
    w: int,
    h: int,
    *,
    y_ratio: float = 1 / 3,
    flash_topmost_ms: int = 450,
) -> None:
    """强制对话框可见：多次居中 + 短暂 topmost + Windows 置前。"""
    center_dialog_later(win, w, h, y_ratio=y_ratio)
    try:
        win.deiconify()
    except tk.TclError:
        pass
    try:
        win.lift()
        win.attributes("-topmost", True)
        win.focus_force()
    except tk.TclError:
        pass

    if platform.system() == "Windows":
        def _front():
            try:
                if not win.winfo_exists():
                    return
                from services.windows_native import force_window_to_front

                force_window_to_front(win)
            except (ImportError, OSError, AttributeError, tk.TclError):
                pass

        try:
            win.after(30, _front)
            win.after(120, _front)
        except tk.TclError:
            pass

    def _drop_topmost():
        try:
            if win.winfo_exists():
                win.attributes("-topmost", False)
                win.lift()
        except tk.TclError:
            pass

    try:
        win.after(max(100, int(flash_topmost_ms)), _drop_topmost)
        win.after(200, lambda: center_dialog(win, w, h, y_ratio=y_ratio))
        win.after(400, lambda: center_dialog(win, w, h, y_ratio=y_ratio))
    except tk.TclError:
        pass
