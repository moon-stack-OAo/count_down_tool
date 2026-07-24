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


class ThinScrollbar(tk.Canvas):
    """主题化细滚动条（替代原生 Scrollbar）。

    用法：
        sb = ThinScrollbar(parent, command=canvas.yview, bg=..., trough=..., thumb=...)
        canvas.configure(yscrollcommand=sb.set)
    """

    def __init__(
        self,
        parent,
        *,
        command=None,
        bg="#0F172A",
        trough="#1E293B",
        thumb="#475569",
        thumb_hover="#64748B",
        width=6,
        pad=2,
        **kwargs,
    ):
        super().__init__(
            parent,
            width=width + pad * 2,
            highlightthickness=0,
            bd=0,
            bg=bg,
            **kwargs,
        )
        self._command = command
        self._bg = bg
        self._trough = trough
        self._thumb = thumb
        self._thumb_hover = thumb_hover
        self._bar_w = width
        self._pad = pad
        self._first = 0.0
        self._last = 1.0
        self._thumb_id = None
        self._drag_offset = None  # 按下时相对滑块顶边的偏移
        self._hover = False

        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set(self, first, last):
        """供 canvas.yscrollcommand 调用；first/last 为 0~1 比例。"""
        try:
            self._first = float(first)
            self._last = float(last)
        except (TypeError, ValueError):
            self._first, self._last = 0.0, 1.0
        # 内容未溢出时收起宽度
        try:
            if self._first <= 0.0 and self._last >= 1.0:
                self.configure(width=0)
            else:
                self.configure(width=self._bar_w + self._pad * 2)
        except tk.TclError:
            pass
        self._redraw()

    def _thumb_color(self):
        return (
            self._thumb_hover
            if self._hover or self._drag_offset is not None
            else self._thumb
        )

    def _metrics(self):
        h = max(1, self.winfo_height())
        span = max(0.0, min(1.0, self._last - self._first))
        if span >= 1.0 - 1e-9:
            return h, 0, h
        thumb_h = max(24, int(h * span))
        max_top = max(0, h - thumb_h)
        top = int(self._first * max_top) if max_top else 0
        return h, top, thumb_h

    def _redraw(self):
        try:
            self.delete("all")
        except tk.TclError:
            return
        h = self.winfo_height()
        w = self.winfo_width()
        if h < 2 or w < 1:
            return
        if self._first <= 0.0 and self._last >= 1.0:
            return
        x0 = self._pad
        x1 = x0 + self._bar_w
        self.create_rectangle(x0, 0, x1, h, fill=self._trough, outline="", tags="trough")
        _, top, thumb_h = self._metrics()
        self._thumb_id = self.create_rectangle(
            x0,
            top,
            x1,
            top + thumb_h,
            fill=self._thumb_color(),
            outline="",
            tags="thumb",
        )

    def _frac_from_top(self, top: float) -> float:
        h, _, thumb_h = self._metrics()
        max_top = max(1, h - thumb_h)
        top = max(0.0, min(float(max_top), float(top)))
        return top / max_top

    def _move_to(self, frac):
        frac = max(0.0, min(1.0, float(frac)))
        if self._command:
            try:
                self._command("moveto", frac)
            except tk.TclError:
                pass

    def _on_enter(self, _e=None):
        self._hover = True
        self._redraw()

    def _on_leave(self, _e=None):
        if self._drag_offset is not None:
            return
        self._hover = False
        self._redraw()

    def _on_press(self, event):
        _, top, thumb_h = self._metrics()
        if top <= event.y <= top + thumb_h:
            self._drag_offset = event.y - top
        else:
            # 点击轨道：跳转使滑块中心对准点击点
            self._drag_offset = thumb_h / 2.0
            self._move_to(self._frac_from_top(event.y - self._drag_offset))
        self._redraw()

    def _on_drag(self, event):
        if self._drag_offset is None:
            return
        self._move_to(self._frac_from_top(event.y - self._drag_offset))

    def _on_release(self, _e=None):
        self._drag_offset = None
        self._redraw()


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
