# -*- coding: utf-8 -*-
"""对话框窗口辅助：原生边框 + Esc 关闭 + 居中/偏侧/置前。"""

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


def apply_dialog_alpha(win: tk.Misc, alpha: float) -> None:
    """设置对话框轻度透明；平台不支持则静默跳过。"""
    try:
        a = float(alpha)
    except (TypeError, ValueError):
        return
    if a <= 0 or a > 1:
        return
    try:
        win.attributes("-alpha", a)
    except tk.TclError:
        pass


def _work_area_or_screen(win: tk.Misc):
    """返回工作区 (ox, oy, aw, ah)；失败则用整屏。"""
    try:
        from services.windows_native import get_work_area

        work = get_work_area(win)
        if work:
            return work
    except (ImportError, OSError, AttributeError, TypeError, ValueError):
        pass
    try:
        return (0, 0, int(win.winfo_screenwidth()), int(win.winfo_screenheight()))
    except tk.TclError:
        return None


def _anchor_geometry(anchor_win: tk.Misc | None):
    """读取锚点窗屏幕坐标与尺寸；不可用则返回 None。"""
    if anchor_win is None:
        return None
    try:
        if not anchor_win.winfo_exists():
            return None
        ax = int(anchor_win.winfo_rootx())
        ay = int(anchor_win.winfo_rooty())
        aw = max(1, int(anchor_win.winfo_width()))
        ah = max(1, int(anchor_win.winfo_height()))
        return ax, ay, aw, ah
    except (tk.TclError, TypeError, ValueError):
        return None


def center_dialog(win: tk.Misc, w: int, h: int, *, y_ratio: float = 1 / 3) -> None:
    """将对话框居中到当前显示器工作区（排除任务栏）。"""
    try:
        win.update_idletasks()
    except tk.TclError:
        return

    area = _work_area_or_screen(win)
    if area is None:
        return
    ox, oy, aw, ah = area
    x = ox + max(0, (aw - w) // 2)
    y = oy + max(0, int((ah - h) * y_ratio))

    try:
        win.geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")
    except tk.TclError:
        return


def place_dialog_beside(
    win: tk.Misc,
    anchor_win: tk.Misc | None,
    w: int,
    h: int,
    *,
    gap: int = 16,
    y_ratio: float = 1 / 3,
) -> None:
    """相对锚点窗偏侧放置：优先右侧，放不下则左侧，再夹入工作区。

    无有效锚点时回退为居中（与 center_dialog 一致）。
    """
    try:
        win.update_idletasks()
    except tk.TclError:
        return

    anchor = _anchor_geometry(anchor_win)
    if anchor is None:
        center_dialog(win, w, h, y_ratio=y_ratio)
        return

    area = _work_area_or_screen(win)
    if area is None:
        return
    ox, oy, aw, ah = area
    ax, ay, a_w, _a_h = anchor
    g = max(0, int(gap))

    x_right = ax + a_w + g
    x_left = ax - int(w) - g
    max_x = ox + max(0, aw - int(w))

    if x_right <= max_x:
        x = x_right
    elif x_left >= ox:
        x = x_left
    else:
        # 两侧都放不下：夹进工作区，尽量靠近锚点右侧意图
        x = max(ox, min(x_right, max_x))

    # 垂直：与锚点顶对齐，超出则夹入工作区
    max_y = oy + max(0, ah - int(h))
    y = max(oy, min(ay, max_y))

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


def place_dialog_beside_later(
    win: tk.Misc,
    anchor_win: tk.Misc | None,
    w: int,
    h: int,
    *,
    gap: int = 16,
    y_ratio: float = 1 / 3,
) -> None:
    """立即偏侧放置，并在 idle/短延迟后再放置一次（应对几何未就绪）。"""
    place_dialog_beside(win, anchor_win, w, h, gap=gap, y_ratio=y_ratio)

    def _again():
        try:
            if win.winfo_exists():
                place_dialog_beside(
                    win, anchor_win, w, h, gap=gap, y_ratio=y_ratio
                )
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
    anchor_win: tk.Misc | None = None,
    gap: int = 16,
    alpha: float | None = None,
) -> None:
    """强制对话框可见：偏侧（有锚点）或居中 + 短暂 topmost + Windows 置前。

    alpha 非空时一并设置轻度透明（与 topmost 无关，关闭后无需清理）。
    """
    if alpha is not None:
        apply_dialog_alpha(win, alpha)

    if anchor_win is not None:
        place_dialog_beside_later(
            win, anchor_win, w, h, gap=gap, y_ratio=y_ratio
        )

        def _place():
            place_dialog_beside(
                win, anchor_win, w, h, gap=gap, y_ratio=y_ratio
            )
    else:
        center_dialog_later(win, w, h, y_ratio=y_ratio)

        def _place():
            center_dialog(win, w, h, y_ratio=y_ratio)

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

    # 短暂 topmost 后可能被部分平台冲掉 alpha，置前后再补一次
    if alpha is not None:
        apply_dialog_alpha(win, alpha)

    if platform.system() == "Windows":
        def _front():
            try:
                if not win.winfo_exists():
                    return
                from services.windows_native import force_window_to_front

                force_window_to_front(win)
            except (ImportError, OSError, AttributeError, tk.TclError):
                pass
            if alpha is not None:
                apply_dialog_alpha(win, alpha)

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
                if alpha is not None:
                    apply_dialog_alpha(win, alpha)
        except tk.TclError:
            pass

    try:
        win.after(max(100, int(flash_topmost_ms)), _drop_topmost)
        win.after(200, _place)
        win.after(400, _place)
    except tk.TclError:
        pass
