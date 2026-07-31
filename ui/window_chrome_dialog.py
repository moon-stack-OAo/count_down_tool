# -*- coding: utf-8 -*-
"""对话框无边框 chrome：Windows 自绘标题栏，其它平台保持原生边框。"""

from __future__ import annotations

import platform
import tkinter as tk
from typing import Callable

from ui.chrome_titlebar import (
    DIALOG_TITLE_HEIGHT,
    add_circle_button,
    build_title_bar,
)

# 自绘标题栏高度（与主窗风格一致，对话框略矮）
CHROME_TITLE_HEIGHT = DIALOG_TITLE_HEIGHT


def use_borderless_chrome(
    win: tk.Toplevel,
    app,
    *,
    title: str,
    on_close: Callable[[], None],
    height_title: int = CHROME_TITLE_HEIGHT,
    close_enabled: bool = True,
) -> bool:
    """为对话框应用 Windows 无边框 + 自绘标题栏。

    Windows: overrideredirect + 标题栏（可拖动 / 关闭 / Esc），返回 True。
    非 Windows: 不改边框，仅绑定 Esc（若可关闭），返回 False。
    """

    def _do_close(_event=None):
        if not close_enabled:
            return "break"
        try:
            on_close()
        except (tk.TclError, AttributeError, RuntimeError):
            pass
        return "break"

    if platform.system() != "Windows":
        if close_enabled:
            try:
                win.bind("<Escape>", _do_close)
            except tk.TclError:
                pass
        return False

    c = app.COLORS

    try:
        win.overrideredirect(True)
    except tk.TclError:
        return False

    # 对话框独立拖动状态（勿复用主窗 _start_drag / _on_drag）
    drag = {"ox": 0, "oy": 0}

    def _start_drag(event):
        try:
            drag["ox"] = event.x_root - win.winfo_x()
            drag["oy"] = event.y_root - win.winfo_y()
        except tk.TclError:
            pass

    def _on_drag(event):
        try:
            x = event.x_root - drag["ox"]
            y = event.y_root - drag["oy"]
            win.geometry(f"+{int(x)}+{int(y)}")
        except tk.TclError:
            pass

    chrome = build_title_bar(
        win,
        app,
        title=title,
        height=height_title,
        on_drag_start=_start_drag,
        on_drag_motion=_on_drag,
    )
    add_circle_button(
        chrome.btn_frame,
        app,
        text="×",
        command=_do_close if close_enabled else None,
        hover_fill=c["btn_hover_close"],
        enabled=close_enabled,
        font_size=12,
        name="close",
        chrome=chrome,
    )

    win.bind("<Escape>", _do_close)
    try:
        win.protocol("WM_DELETE_WINDOW", on_close if close_enabled else (lambda: None))
    except tk.TclError:
        pass

    _apply_rounded_corners(win, app)
    # overrideredirect 后默认不进 Alt+Tab / 任务栏，补 APPWINDOW 样式
    _apply_taskbar_visible(win)
    return True


def _apply_taskbar_visible(win: tk.Misc) -> None:
    """无边框窗加入 Alt+Tab / 任务栏（失败静默）。"""
    if platform.system() != "Windows":
        return
    try:
        from services.windows_native import set_taskbar_visible
    except ImportError:
        return

    def _set():
        try:
            if win.winfo_exists():
                set_taskbar_visible(win)
        except (tk.TclError, OSError, AttributeError, ValueError, TypeError):
            pass

    _set()
    try:
        win.after(50, _set)
        win.after(200, _set)
    except tk.TclError:
        pass


def _apply_rounded_corners(win: tk.Misc, app) -> None:
    """Windows 圆角；geometry 稳定后再设一次更稳。"""
    if platform.system() != "Windows":
        return
    radius = int(getattr(app, "CORNER_RADIUS", 16) or 16)
    try:
        from services.windows_native import set_window_rounded_corners
    except ImportError:
        return

    def _set():
        try:
            if win.winfo_exists():
                set_window_rounded_corners(win, radius)
        except (tk.TclError, OSError, AttributeError, ValueError, TypeError):
            pass

    _set()
    try:
        win.after(50, _set)
        win.after(200, _set)
    except tk.TclError:
        pass


def chrome_title_height(applied: bool, height: int = CHROME_TITLE_HEIGHT) -> int:
    """尺寸计算用：已应用自绘标题栏时返回高度，否则 0。"""
    return height if applied else 0


def center_dialog(win: tk.Misc, w: int, h: int, *, y_ratio: float = 1 / 3) -> None:
    """将对话框居中到当前显示器工作区（排除任务栏）。

    Windows overrideredirect 后系统常把窗放到 0,0，需在 geometry 稳定后调用，
    并建议 after_idle / after(50) 再补一次。
    """
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
    """立即居中，并在 idle/50ms 后再居中一次（兼容无边框窗）。"""
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
    """强制对话框可见：多次居中 + 短暂 topmost + Windows 置前。

    用于设置中心等无边框窗，避免落在 0,0 / 副屏外 / 主窗后面导致「点了没反应」。
    """
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
        # 再补两次居中，覆盖 DPI / 异步布局
        win.after(200, lambda: center_dialog(win, w, h, y_ratio=y_ratio))
        win.after(400, lambda: center_dialog(win, w, h, y_ratio=y_ratio))
    except tk.TclError:
        pass
