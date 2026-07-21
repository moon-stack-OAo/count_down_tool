# -*- coding: utf-8 -*-
"""完整窗 chrome：居中、置前、任务栏/圆角、标题栏拖动。"""

from __future__ import annotations

import tkinter as tk

from services.windows_native import (
    force_window_to_front,
    get_work_area,
    set_taskbar_visible,
    set_window_rounded_corners,
)


def start_drag(app, event) -> None:
    """开始拖动完整窗（标题栏右侧控件区除外）。"""
    if event.x > app.TITLE_DRAG_EXCLUDE_RIGHT:
        return
    app._drag_x = event.x
    app._drag_y = event.y


def on_drag(app, event) -> None:
    """拖动完整窗。"""
    x = app.master.winfo_x() + (event.x - app._drag_x)
    y = app.master.winfo_y() + (event.y - app._drag_y)
    app.master.geometry(f"+{x}+{y}")


def center_window(app) -> None:
    """完整窗在当前显示器工作区内居中（排除任务栏；兼容 DPI）。"""
    try:
        app.master.update_idletasks()
    except tk.TclError:
        return
    width = app.WINDOW_WIDTH
    height = app.WINDOW_HEIGHT
    try:
        rw = app.master.winfo_reqwidth()
        rh = app.master.winfo_reqheight()
        if rw > 1 and rh > 1:
            width, height = rw, rh
    except tk.TclError:
        pass

    work = get_work_area(app.master)
    if work:
        ox, oy, aw, ah = work
        x = ox + max(0, (aw - width) // 2)
        y = oy + max(0, (ah - height) // 2)
    else:
        sw = app.master.winfo_screenwidth()
        sh = app.master.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
    try:
        app.master.geometry(
            f"{app.WINDOW_WIDTH}x{app.WINDOW_HEIGHT}+{int(x)}+{int(y)}"
        )
    except tk.TclError:
        pass


def center_window_later(app) -> None:
    """deiconify / 样式刷新后再居中一次，避免位置被系统改掉。"""
    center_window(app)
    try:
        app.master.after_idle(lambda: center_window(app))
        app.master.after(50, lambda: center_window(app))
    except tk.TclError:
        pass


def set_rounded_corners(app) -> None:
    set_window_rounded_corners(app.master, app.CORNER_RADIUS)


def set_taskbar(app) -> None:
    set_taskbar_visible(app.master)


def bring_full_to_front(app) -> None:
    """完整窗置顶激活；托盘回调场景下 Tk 的 lift 常被系统忽略。"""
    force_window_to_front(app.master)
    try:
        # 延迟再置前一次，覆盖 deiconify 后的异步焦点争夺
        app.master.after(50, lambda: force_window_to_front(app.master))
    except tk.TclError:
        pass
