# -*- coding: utf-8 -*-
"""通用 UI 小部件。"""

import tkinter as tk


class RoundedFrame(tk.Canvas):
    """圆角卡片容器"""

    def __init__(self, parent, bg_color="#1A2332", border_color="#2A3A4E",
                 corner_radius=14, border_width=1, **kwargs):
        super().__init__(parent, highlightthickness=0, bg=parent["bg"], **kwargs)
        self._bg_color = bg_color
        self._border_color = border_color
        self._radius = corner_radius
        self._border_width = border_width
        self.bind("<Configure>", self._draw)

    def _draw(self, event=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w > 1 and h > 1:
            self._draw_rounded_rect(0, 0, w, h, self._radius,
                                    self._bg_color, self._border_color,
                                    width=self._border_width)

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, fill_color, outline_color, width=1):
        points = [
            x1 + radius, y1, x2 - radius, y1,
            x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2,
            x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius,
            x1, y1 + radius, x1, y1,
        ]
        self.create_polygon(points, smooth=True, fill=fill_color,
                            outline=outline_color, width=width)


def init_circle_button(canvas, cx, cy, r, fill="#64748B", outline="", text="",
                       text_color="#F1F5F9", font_family="Segoe UI", font_size=10):
    """在 canvas 上绘制圆形按钮，返回 (oval_id, text_id)。"""
    oval_id = canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 fill=fill, outline=outline, width=0)
    text_id = None
    if text:
        text_id = canvas.create_text(cx, cy, text=text, fill=text_color,
                                     font=(font_family, font_size))
    return (oval_id, text_id)


def update_circle_button(canvas, item_ids, fill=None, text=None, text_color=None):
    """更新圆形按钮外观。"""
    oval_id, text_id = item_ids
    if fill is not None:
        canvas.itemconfig(oval_id, fill=fill)
    if text_id is not None:
        if text_color is not None:
            canvas.itemconfig(text_id, fill=text_color)
        if text is not None:
            canvas.itemconfig(text_id, text=text)
