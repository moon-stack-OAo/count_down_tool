# -*- coding: utf-8 -*-
"""对话框无边框 chrome：Windows 自绘标题栏，其它平台保持原生边框。"""

from __future__ import annotations

import platform
import tkinter as tk
from typing import Callable

from ui.widgets import init_circle_button, update_circle_button

# 自绘标题栏高度（与主窗风格一致，对话框略矮）
CHROME_TITLE_HEIGHT = 40


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
        except Exception:
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
    font_family = app.FONTS["label"][0]

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

    title_bar = tk.Frame(win, bg=c["title_bar"], height=height_title)
    title_bar.pack(fill=tk.X, side=tk.TOP)
    title_bar.pack_propagate(False)

    accent = tk.Frame(title_bar, bg=c["accent"], height=2)
    accent.pack(side=tk.BOTTOM, fill=tk.X)

    title_bar.bind("<Button-1>", _start_drag)
    title_bar.bind("<B1-Motion>", _on_drag)

    title_label = tk.Label(
        title_bar,
        text=f"  {title}",
        bg=c["title_bar"],
        fg=c["text"],
        font=app._font("label", 10, bold=True),
    )
    title_label.pack(side=tk.LEFT, fill=tk.Y)
    title_label.bind("<Button-1>", _start_drag)
    title_label.bind("<B1-Motion>", _on_drag)

    btn_frame = tk.Frame(title_bar, bg=c["title_bar"])
    btn_frame.pack(side=tk.RIGHT, padx=(0, 10))
    # 关闭按钮区不绑定拖动

    btn_size = 16
    close_btn = tk.Canvas(
        btn_frame,
        width=btn_size * 2,
        height=btn_size * 2,
        bg=c["title_bar"],
        highlightthickness=0,
        cursor="hand2" if close_enabled else "",
    )
    close_btn.pack(side=tk.RIGHT, padx=(6, 0))
    items = init_circle_button(
        close_btn,
        btn_size,
        btn_size,
        btn_size - 1,
        fill=c["btn_default"],
        text="×",
        text_color=c["text_dim"] if close_enabled else c.get("text_muted", c["text_dim"]),
        font_family=font_family,
        font_size=12,
    )

    if close_enabled:
        close_btn.bind(
            "<Enter>",
            lambda e: update_circle_button(
                close_btn,
                items,
                fill=c["btn_hover_close"],
                text_color=c["white"],
            ),
        )
        close_btn.bind(
            "<Leave>",
            lambda e: update_circle_button(
                close_btn,
                items,
                fill=c["btn_default"],
                text_color=c["text_dim"],
            ),
        )
        close_btn.bind("<Button-1>", _do_close)
    else:
        # 下载中：× 仅占位，不响应
        close_btn.bind("<Button-1>", lambda e: "break")

    win.bind("<Escape>", _do_close)
    try:
        win.protocol("WM_DELETE_WINDOW", on_close if close_enabled else (lambda: None))
    except tk.TclError:
        pass

    _apply_rounded_corners(win, app)
    return True


def _apply_rounded_corners(win: tk.Misc, app) -> None:
    """Windows 圆角；geometry 稳定后再设一次更稳。"""
    if platform.system() != "Windows":
        return
    radius = int(getattr(app, "CORNER_RADIUS", 16) or 16)
    try:
        from services.windows_native import set_window_rounded_corners
    except Exception:
        return

    def _set():
        try:
            if win.winfo_exists():
                set_window_rounded_corners(win, radius)
        except tk.TclError:
            pass
        except Exception:
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
    except Exception:
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
