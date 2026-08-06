# -*- coding: utf-8 -*-
"""设置窗布局：滚动页、滚轮、卡片。"""

from __future__ import annotations

import platform
import tkinter as tk

from ui.design.tokens import SPACE_MD, SPACE_SM
from ui.widgets import ThinScrollbar, make_pill, make_settings_card


def make_scroll_page(host: tk.Frame, app, c) -> tk.Frame:
    """单 Tab 页：Canvas + 细滚动条 + content 内边距。

    内容未超出视口时：scrollregion 锁在可视高度，禁止空滚；滚动条由 ThinScrollbar 自动收起。
    """
    page = tk.Frame(host, bg=c["bg"])
    canvas = tk.Canvas(page, bg=c["bg"], highlightthickness=0, bd=0)
    scrollbar = ThinScrollbar(
        page,
        command=canvas.yview,
        bg=c["bg"],
        trough=c.get("input_bg", c["card"]),
        thumb=c.get("border", c["text_muted"]),
        thumb_hover=c.get("text_muted", c["text_dim"]),
        width=6,
        pad=3,
    )
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    body = tk.Frame(canvas, bg=c["bg"])
    body_id = canvas.create_window((0, 0), window=body, anchor="nw")
    scroll_state = {"needed": False}

    def _content_height() -> int:
        try:
            body.update_idletasks()
            return max(int(body.winfo_reqheight()), 1)
        except tk.TclError:
            return 1

    def _sync_scroll(_e=None):
        """按内容与视口高度更新 scrollregion；不足一屏时不可滚。"""
        try:
            ch = max(int(canvas.winfo_height()), 1)
            bh = _content_height()
            needed = bh > ch + 1
            scroll_state["needed"] = needed
            if needed:
                canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), bh))
            else:
                # 锁在视口高度，yview 无法再偏移
                canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), ch))
                canvas.yview_moveto(0)
            # 触发滚动条 set，收起/展开宽度
            try:
                first, last = canvas.yview()
                scrollbar.set(first, last)
            except tk.TclError:
                pass
        except tk.TclError:
            pass

    def _on_canvas_configure(e):
        try:
            canvas.itemconfigure(body_id, width=e.width)
        except tk.TclError:
            pass
        _sync_scroll()

    body.bind("<Configure>", _sync_scroll)
    canvas.bind("<Configure>", _on_canvas_configure)

    def _wheel(e):
        if not scroll_state["needed"]:
            return
        try:
            if platform.system() == "Darwin":
                canvas.yview_scroll(int(-1 * e.delta), "units")
            else:
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        except tk.TclError:
            pass

    def _wheel_up(_e=None):
        if scroll_state["needed"]:
            try:
                canvas.yview_scroll(-1, "units")
            except tk.TclError:
                pass

    def _wheel_down(_e=None):
        if scroll_state["needed"]:
            try:
                canvas.yview_scroll(1, "units")
            except tk.TclError:
                pass

    canvas.bind("<MouseWheel>", _wheel)
    canvas.bind("<Button-4>", _wheel_up)
    canvas.bind("<Button-5>", _wheel_down)

    content = tk.Frame(body, bg=c["bg"])
    content.pack(fill=tk.BOTH, expand=True, padx=SPACE_MD, pady=(SPACE_MD, SPACE_SM))

    page._settings_canvas = canvas  # type: ignore[attr-defined]
    page._settings_content = content  # type: ignore[attr-defined]
    page._settings_wheel = _wheel  # type: ignore[attr-defined]
    page._settings_scroll_state = scroll_state  # type: ignore[attr-defined]
    page._settings_sync_scroll = _sync_scroll  # type: ignore[attr-defined]
    page._settings_wheel_up = _wheel_up  # type: ignore[attr-defined]
    page._settings_wheel_down = _wheel_down  # type: ignore[attr-defined]
    return page


def bind_wheel_tree(root: tk.Misc, canvas: tk.Canvas) -> None:
    """把滚轮事件绑到子树；仅内容溢出时滚动。"""
    page = None
    try:
        # canvas 的 master 即 page
        page = canvas.master
    except AttributeError:
        page = None
    scroll_state = getattr(page, "_settings_scroll_state", None) if page else None
    wheel = getattr(page, "_settings_wheel", None) if page else None
    wheel_up = getattr(page, "_settings_wheel_up", None) if page else None
    wheel_down = getattr(page, "_settings_wheel_down", None) if page else None

    def _wheel(e):
        if scroll_state is not None and not scroll_state.get("needed"):
            return
        if wheel:
            wheel(e)
            return
        try:
            if platform.system() == "Darwin":
                canvas.yview_scroll(int(-1 * e.delta), "units")
            else:
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        except tk.TclError:
            pass

    def _up(e):
        if scroll_state is not None and not scroll_state.get("needed"):
            return
        if wheel_up:
            wheel_up(e)
        else:
            try:
                canvas.yview_scroll(-1, "units")
            except tk.TclError:
                pass

    def _down(e):
        if scroll_state is not None and not scroll_state.get("needed"):
            return
        if wheel_down:
            wheel_down(e)
        else:
            try:
                canvas.yview_scroll(1, "units")
            except tk.TclError:
                pass

    def _bind(w):
        w.bind("<MouseWheel>", _wheel)
        w.bind("<Button-4>", _up)
        w.bind("<Button-5>", _down)
        for child in w.winfo_children():
            _bind(child)

    try:
        _bind(root)
    except tk.TclError:
        pass


def card(parent, c) -> tk.Frame:
    """设置分区卡片（委托通用 make_settings_card）。"""
    return make_settings_card(parent, c)


def pill(parent, text, *, app, c, primary=True, command=None):
    """兼容旧调用：委托统一 make_pill。"""
    return make_pill(parent, text, app=app, c=c, primary=primary, command=command)
