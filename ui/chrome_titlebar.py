# -*- coding: utf-8 -*-
"""自绘标题栏公共组件：主窗与对话框共用。

仅负责标题栏 UI（拖动区、底部分割线、圆形操作钮），不处理 overrideredirect。
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from ui.widgets import init_circle_button, update_circle_button

# 主窗 / 对话框默认高度
MAIN_TITLE_HEIGHT = 48
DIALOG_TITLE_HEIGHT = 40
CIRCLE_BTN_SIZE = 16


@dataclass
class TitleBarChrome:
    """build_title_bar 返回值。"""

    frame: tk.Frame
    title_label: tk.Label
    btn_frame: tk.Frame
    buttons: Dict[str, tk.Canvas] = field(default_factory=dict)


def build_title_bar(
    parent: tk.Misc,
    app,
    *,
    title: str,
    height: int = MAIN_TITLE_HEIGHT,
    on_drag_start: Optional[Callable[[Any], None]] = None,
    on_drag_motion: Optional[Callable[[Any], None]] = None,
    pack_side: str = tk.TOP,
) -> TitleBarChrome:
    """创建自绘标题栏骨架：底部分割线 + 标题 + 右侧按钮区。

    on_drag_start / on_drag_motion 绑定到标题栏与标题文字（按钮区不绑拖动）。
    调用方随后用 add_circle_button 按 pack(side=RIGHT) 顺序添加按钮。
    """
    c = app.COLORS
    title_bar = tk.Frame(parent, bg=c["title_bar"], height=height)
    title_bar.pack(fill=tk.X, side=pack_side)
    title_bar.pack_propagate(False)

    accent = tk.Frame(title_bar, bg=c["accent"], height=2)
    accent.pack(side=tk.BOTTOM, fill=tk.X)

    if on_drag_start is not None:
        title_bar.bind("<Button-1>", on_drag_start)
    if on_drag_motion is not None:
        title_bar.bind("<B1-Motion>", on_drag_motion)

    title_label = tk.Label(
        title_bar,
        text=title if title.startswith(" ") else f"  {title}",
        bg=c["title_bar"],
        fg=c["text"],
        font=app._font("label", 10, bold=True),
    )
    title_label.pack(side=tk.LEFT, fill=tk.Y)
    if on_drag_start is not None:
        title_label.bind("<Button-1>", on_drag_start)
    if on_drag_motion is not None:
        title_label.bind("<B1-Motion>", on_drag_motion)

    btn_frame = tk.Frame(title_bar, bg=c["title_bar"])
    btn_frame.pack(side=tk.RIGHT, padx=(0, 10))

    return TitleBarChrome(frame=title_bar, title_label=title_label, btn_frame=btn_frame)


def add_circle_button(
    btn_frame: tk.Misc,
    app,
    *,
    text: str,
    command: Optional[Callable[..., Any]] = None,
    hover_fill: Optional[str] = None,
    enabled: bool = True,
    font_size: int = 12,
    size: int = CIRCLE_BTN_SIZE,
    name: str = "",
    chrome: Optional[TitleBarChrome] = None,
) -> tk.Canvas:
    """在标题栏右侧按钮区添加圆形钮（pack side=RIGHT，先加的在最右）。

    hover_fill: 悬停填充色；默认用 accent。
    enabled=False 时仅占位，不响应点击/悬停。
    """
    c = app.COLORS
    font_family = app.FONTS["label"][0]
    fill_default = c["btn_default"]
    text_default = c["text_dim"] if enabled else c.get("text_muted", c["text_dim"])
    hover = hover_fill if hover_fill else c.get("accent", c["btn_default"])

    canvas = tk.Canvas(
        btn_frame,
        width=size * 2,
        height=size * 2,
        bg=c["title_bar"],
        highlightthickness=0,
        cursor="hand2" if enabled and command is not None else "",
    )
    canvas.pack(side=tk.RIGHT, padx=(6, 0))
    items = init_circle_button(
        canvas,
        size,
        size,
        size - 1,
        fill=fill_default,
        text=text,
        text_color=text_default,
        font_family=font_family,
        font_size=font_size,
    )

    if enabled and command is not None:
        canvas.bind(
            "<Enter>",
            lambda e: update_circle_button(
                canvas, items, fill=hover, text_color=c["white"]
            ),
        )
        canvas.bind(
            "<Leave>",
            lambda e: update_circle_button(
                canvas, items, fill=fill_default, text_color=c["text_dim"]
            ),
        )

        # 兼容 command() / command(event)
        def _invoke(_e=None, _cmd=command):
            try:
                _cmd(_e)
            except TypeError:
                _cmd()
            return "break"

        canvas.bind("<Button-1>", _invoke)
    elif not enabled:
        canvas.bind("<Button-1>", lambda e: "break")

    if chrome is not None and name:
        chrome.buttons[name] = canvas
    return canvas


def bind_drag_to_widget(
    widget: tk.Misc,
    on_drag_start: Optional[Callable[[Any], None]],
    on_drag_motion: Optional[Callable[[Any], None]],
) -> None:
    """给额外左侧控件绑定与标题栏相同的拖动（如需整段可拖时）。"""
    if on_drag_start is not None:
        widget.bind("<Button-1>", on_drag_start)
    if on_drag_motion is not None:
        widget.bind("<B1-Motion>", on_drag_motion)
