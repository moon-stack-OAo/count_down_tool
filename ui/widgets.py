# -*- coding: utf-8 -*-
"""通用 UI 小部件。"""

import tkinter as tk

from ui.design.themed import register_themed, themed_frame, themed_label
from ui.design.tokens import (
    BTN_FONT_SIZE,
    CHIP_PAD_X,
    CHIP_PAD_Y,
    FONT_BODY,
    FONT_CAPTION,
    PILL_PAD_X,
    PILL_PAD_Y,
    RADIUS_CARD,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
)


class RoundedFrame(tk.Canvas):
    """圆角卡片容器"""

    def __init__(self, parent, bg_color="#1A2332", border_color="#2A3A4E",
                 corner_radius=RADIUS_CARD, border_width=1, **kwargs):
        super().__init__(parent, highlightthickness=0, bg=parent["bg"], **kwargs)
        self._bg_color = bg_color
        self._border_color = border_color
        self._radius = corner_radius
        self._border_width = border_width
        self.bind("<Configure>", self._draw)

    def configure_colors(self, bg_color=None, border_color=None, border_width=None):
        """运行时更新卡片配色并重绘。"""
        if bg_color is not None:
            self._bg_color = bg_color
        if border_color is not None:
            self._border_color = border_color
        if border_width is not None:
            self._border_width = border_width
        self._draw()

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

    def apply_theme_colors(
        self,
        *,
        bg=None,
        trough=None,
        thumb=None,
        thumb_hover=None,
    ) -> None:
        """就地换肤：更新底板/轨道/滑块色并重绘。"""
        if bg is not None:
            self._bg = bg
            try:
                self.configure(bg=bg)
            except tk.TclError:
                pass
        if trough is not None:
            self._trough = trough
        if thumb is not None:
            self._thumb = thumb
        if thumb_hover is not None:
            self._thumb_hover = thumb_hover
        self._redraw()


def init_circle_button(canvas, cx, cy, r, fill="#64748B", outline="", text="",
                       text_color="#F1F5F9", font_family="Segoe UI", font_size=FONT_BODY):
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


def make_settings_card(
    parent,
    c,
    *,
    pack: bool = True,
    fill: str = "x",
    expand: bool = False,
    padx_inner=None,
    pady_inner=None,
) -> tk.Frame:
    """设置中心风格卡片：card 底 + border 描边 + 内边距。

    设置 Tab 与 app_dialogs 弹窗内容区共用，保证观感一致。
    """
    colors = c if isinstance(c, dict) else {}
    inner_x = SPACE_MD if padx_inner is None else padx_inner
    inner_y = SPACE_SM if pady_inner is None else pady_inner
    card_f = tk.Frame(
        parent,
        bg=colors.get("card", "#1A2332"),
        highlightbackground=colors.get("border", "#2A3A4E"),
        highlightthickness=1,
        padx=inner_x,
        pady=inner_y,
    )
    register_themed(card_f, bg="card", highlightbackground="border")
    if pack:
        kwargs = {"fill": fill, "pady": (0, SPACE_MD)}
        if expand:
            kwargs["expand"] = True
        card_f.pack(**kwargs)
    return card_f


def section_title(parent, app, c, text, *, padx=SPACE_SM, pady=None):
    """分区小标题（text_muted + FONT_CAPTION）。"""
    if pady is None:
        pady = (0, SPACE_XS)
    lbl = themed_label(
        parent,
        app,
        text,
        fg_role="text_muted",
        bg_role="card",
        font_size=FONT_CAPTION,
        c=c,
    )
    lbl.pack(fill=tk.X, padx=padx, pady=pady)
    return lbl


def divider(parent, c, *, pady=SPACE_SM, side=None, app=None):
    """1px border 分隔线。"""
    if app is not None:
        line = themed_frame(parent, app, role="border", c=c, height=1)
    else:
        colors = c if isinstance(c, dict) else {}
        line = tk.Frame(parent, bg=colors.get("border", "#2A3A4E"), height=1)
        register_themed(line, bg="border")
    pack_kw = {"fill": tk.X, "pady": pady}
    if side is not None:
        pack_kw["side"] = side
    line.pack(**pack_kw)
    return line


def accent_bar(parent, c, *, side=tk.TOP, app=None):
    """顶栏 2px accent 条。"""
    if app is not None:
        bar = themed_frame(parent, app, role="accent", c=c, height=2)
    else:
        colors = c if isinstance(c, dict) else {}
        bar = tk.Frame(parent, bg=colors.get("accent", "#38BDF8"), height=2)
        register_themed(bar, bg="accent")
    bar.pack(fill=tk.X, side=side)
    return bar


def selectable_row(
    parent,
    app,
    c,
    text,
    *,
    selected=False,
    on_click=None,
    checkmark=True,
    font_size=FONT_BODY,
    padx=SPACE_SM,
    pady=CHIP_PAD_Y + 1,
    fg=None,
    wraplength=None,
    justify=None,
):
    """可选行：✓ 前缀、chip_hover、手型光标（主题/音效/启动模式等）。"""
    colors = c if isinstance(c, dict) else {}
    bg = colors.get("card", "#1A2332")
    text_fg = fg if fg is not None else colors.get("text", "#F1F5F9")
    if checkmark:
        mark = "✓  " if selected else "    "
        display = f"{mark}{text}"
    else:
        display = text
    kw = {
        "text": display,
        "font": app._font("label", font_size),
        "bg": bg,
        "fg": text_fg,
        "anchor": "w",
        "cursor": "hand2",
        "padx": padx,
        "pady": pady,
    }
    if wraplength is not None:
        kw["wraplength"] = wraplength
    if justify is not None:
        kw["justify"] = justify
    row = tk.Label(parent, **kw)
    row._row_text = text  # type: ignore[attr-defined]
    row._checkmark = checkmark  # type: ignore[attr-defined]
    register_themed(row, bg="card", fg="text")
    row._theme_hover_role = "chip_hover"  # type: ignore[attr-defined]
    row.pack(fill=tk.X)
    if on_click:
        row.bind("<Button-1>", lambda e: on_click())
    hover = colors.get("chip_hover", colors.get("border", bg))
    row.bind("<Enter>", lambda e, w=row, h=hover: w.config(bg=h))
    row.bind("<Leave>", lambda e, w=row, b=bg: w.config(bg=b))
    return row


def set_selectable_selected(row, selected, text=None):
    """刷新可选行勾选态；可选更新基础文案。"""
    if text is not None:
        row._row_text = text  # type: ignore[attr-defined]
    base = getattr(row, "_row_text", "")
    if getattr(row, "_checkmark", True):
        mark = "✓  " if selected else "    "
        row.config(text=f"{mark}{base}")
    else:
        row.config(text=base)


def make_chip(
    parent,
    text,
    *,
    app,
    c=None,
    padx=CHIP_PAD_X,
    pady=CHIP_PAD_Y,
):
    """轻量 chip（快捷预设等）；非主 CTA，与 make_pill / ttk Button 区分。

    几何：CHIP_PAD_* + FONT_CAPTION；色：chip / text_dim。
    """
    colors = c if isinstance(c, dict) else getattr(app, "COLORS", {}) or {}
    chip = tk.Label(
        parent,
        text=text,
        font=app._font("label", FONT_CAPTION),
        bg=colors.get("chip", colors.get("card", "#1A2332")),
        fg=colors.get("text_dim", colors.get("text", "#94A3B8")),
        padx=padx,
        pady=pady,
        cursor="hand2",
    )
    register_themed(chip, bg="chip", fg="text_dim")
    return chip


def make_pill(
    parent,
    text,
    *,
    app,
    c=None,
    primary=True,
    command=None,
    danger=False,
    padx=PILL_PAD_X,
    pady=PILL_PAD_Y,
    font_size=None,
):
    """对话框/设置胶囊按钮；primary 与主窗 Accent.TButton 同色同 pad。

    - primary：btn_primary / btn_on_primary，字号 BTN_FONT_SIZE（对齐 ttk）
    - secondary：chip / text（同 Secondary.TButton 语义）
    - danger：error / white
    - chip 请用 make_chip，勿用本函数冒充第三套
    """
    colors = c if isinstance(c, dict) else getattr(app, "COLORS", {}) or {}
    if danger:
        bg = colors["error"]
        fg = colors["white"]
        hover = colors.get("btn_hover_close", bg)
        bold = True
        size = FONT_CAPTION if font_size is None else font_size
    elif primary:
        bg = colors.get("btn_primary", colors["accent"])
        fg = colors.get("btn_on_primary", colors["bg"])
        hover = colors.get("btn_primary_hover", colors.get("accent_hover", bg))
        bold = True
        size = BTN_FONT_SIZE if font_size is None else font_size
    else:
        bg = colors.get("chip", colors["card"])
        fg = colors["text"]
        hover = colors.get("chip_hover", colors.get("border", bg))
        bold = False
        size = FONT_CAPTION if font_size is None else font_size

    font = app._font("label", size, bold=bold) if bold else app._font("label", size)
    btn = tk.Label(
        parent,
        text=text,
        font=font,
        bg=bg,
        fg=fg,
        padx=padx,
        pady=pady,
        cursor="hand2",
    )
    if danger:
        register_themed(btn, bg="error", fg="white")
        btn._theme_hover_role = "btn_hover_close"  # type: ignore[attr-defined]
    elif primary:
        register_themed(btn, bg="btn_primary", fg="btn_on_primary")
        btn._theme_hover_role = "btn_primary_hover"  # type: ignore[attr-defined]
    else:
        register_themed(btn, bg="chip", fg="text")
        btn._theme_hover_role = "chip_hover"  # type: ignore[attr-defined]
    if command:
        btn.bind("<Button-1>", lambda e: command())
    btn.bind("<Enter>", lambda e: btn.config(bg=hover))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn


# Themed 工厂 re-export（调用方可从 widgets 统一导入）
from ui.design.themed import (  # noqa: E402,F401
    color_of,
    resolve_colors,
    themed_button,
)
