# -*- coding: utf-8 -*-
"""到期时间选择器弹窗。"""

import logging
import platform
import tkinter as tk
from tkinter import ttk

from countdown_core import STATE_RUNNING
from ui.widgets import RoundedFrame, init_circle_button, update_circle_button

logger = logging.getLogger("count_down_tool")


def show_time_picker(app):
    """弹出时间选择器（macOS 保留系统标题栏以便聚焦）。"""
    is_darwin = platform.system() == "Darwin"
    picker = tk.Toplevel(app.master)
    picker.title("选择时间")
    picker.geometry(f"{app.PICKER_WIDTH}x{app.PICKER_HEIGHT}")
    picker.resizable(False, False)
    picker.configure(bg=app.COLORS["bg"])
    # Darwin 下 overrideredirect 易导致无法聚焦，保留系统标题栏
    if not is_darwin:
        picker.overrideredirect(True)
    picker.attributes("-topmost", True)

    picker.update_idletasks()
    sw = picker.winfo_screenwidth()
    sh = picker.winfo_screenheight()
    px = sw // 2 - app.PICKER_WIDTH // 2
    py = sh // 2 - app.PICKER_HEIGHT // 2
    picker.geometry(f"+{px}+{py}")

    if not is_darwin:
        _picker_drag = {"x": 0, "y": 0}

        def _picker_start_drag(e):
            _picker_drag["x"] = e.x
            _picker_drag["y"] = e.y

        def _picker_do_drag(e):
            x = picker.winfo_x() + e.x - _picker_drag["x"]
            y = picker.winfo_y() + e.y - _picker_drag["y"]
            picker.geometry(f"+{x}+{y}")

        p_title_bar = tk.Frame(picker, bg=app.COLORS["title_bar"], height=36)
        p_title_bar.pack(fill=tk.X)
        p_title_bar.pack_propagate(False)
        p_title_bar.bind("<Button-1>", _picker_start_drag)
        p_title_bar.bind("<B1-Motion>", _picker_do_drag)

        title_label = tk.Label(p_title_bar, text="  ⏱ 选择时间",
                               bg=app.COLORS["title_bar"], fg=app.COLORS["text"],
                               font=app._font("label", 9))
        title_label.pack(side=tk.LEFT, fill=tk.Y)
        title_label.bind("<Button-1>", _picker_start_drag)
        title_label.bind("<B1-Motion>", _picker_do_drag)

        p_close = tk.Canvas(p_title_bar, width=24, height=24,
                            bg=app.COLORS["title_bar"], highlightthickness=0, cursor="hand2")
        p_close.pack(side=tk.RIGHT, padx=(0, 8))
        font_family = app.FONTS["label"][0]
        p_close_items = init_circle_button(
            p_close, 12, 12, 11,
            fill=app.COLORS["btn_default"], text="×",
            text_color=app.COLORS["text_dim"], font_family=font_family, font_size=10,
        )
        p_close.bind("<Enter>", lambda e: update_circle_button(
            p_close, p_close_items, fill=app.COLORS["btn_hover_close"],
            text_color=app.COLORS["white"]))
        p_close.bind("<Leave>", lambda e: update_circle_button(
            p_close, p_close_items, fill=app.COLORS["btn_default"],
            text_color=app.COLORS["text_dim"]))
        p_close.bind("<Button-1>", lambda e: picker.destroy())

        tk.Frame(picker, bg=app.COLORS["accent"], height=1).pack(fill=tk.X)

    tk.Label(picker, text="到期时间", font=app._font("button"),
             bg=app.COLORS["bg"], fg=app.COLORS["text"]).pack(pady=(12, 8))

    input_card = RoundedFrame(picker, bg_color=app.COLORS["glass"],
                              border_color=app.COLORS["card_border"],
                              corner_radius=12, height=56)
    input_card.pack(padx=24, fill=tk.X)
    input_frame = tk.Frame(input_card, bg=app.COLORS["glass"])
    input_frame.place(relx=0.5, rely=0.5, anchor="center")

    h_var = tk.StringVar(value="18")
    m_var = tk.StringVar(value="00")
    s_var = tk.StringVar(value="00")
    mono_font = app._font("time", 18)
    mono_bold = app._font("time", 18, bold=True)

    for var, mx in [(h_var, 23), (m_var, 59), (s_var, 59)]:
        sb = ttk.Spinbox(input_frame, textvariable=var, from_=0, to=mx,
                         width=3, font=mono_font, wrap=True,
                         style="TSpinbox")
        sb.pack(side=tk.LEFT, padx=6)

        if var != s_var:
            tk.Label(input_frame, text=":", font=mono_bold,
                     bg=app.COLORS["glass"], fg=app.COLORS["text_dim"]).pack(side=tk.LEFT)

    def confirm():
        try:
            h, m, s = int(h_var.get()), int(m_var.get()), int(s_var.get())
            if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
                return
            app.hour_var.set(f"{h:02d}")
            app.minute_var.set(f"{m:02d}")
            app.second_var.set(f"{s:02d}")
            picker.destroy()
            if app._state != STATE_RUNNING:
                app.toggle_countdown()
        except ValueError:
            logger.debug("时间选择器输入无效", exc_info=True)

    btn_frame = tk.Frame(picker, bg=app.COLORS["bg"])
    btn_frame.pack(pady=14)

    ok_btn = tk.Label(btn_frame, text="确认", font=app._font("label", 11, bold=True),
                      bg=app.COLORS["accent"], fg=app.COLORS["white"], padx=24, pady=6,
                      cursor="hand2")
    ok_btn.pack(side=tk.LEFT, padx=6)
    ok_btn.bind("<Button-1>", lambda e: confirm())
    ok_btn.bind("<Enter>", lambda e: ok_btn.config(bg=app.COLORS["accent_hover"]))
    ok_btn.bind("<Leave>", lambda e: ok_btn.config(bg=app.COLORS["accent"]))

    cancel_btn = tk.Label(btn_frame, text="取消", font=app._font("label", 11),
                          bg=app.COLORS["card"], fg=app.COLORS["text_dim"],
                          padx=24, pady=6, cursor="hand2")
    cancel_btn.pack(side=tk.LEFT, padx=6)
    cancel_btn.bind("<Button-1>", lambda e: picker.destroy())
    cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(bg=app.COLORS["border"]))
    cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(bg=app.COLORS["card"]))

    picker.bind("<Return>", lambda e: confirm())
    picker.bind("<Escape>", lambda e: picker.destroy())
    try:
        picker.focus_force()
    except Exception:
        logger.debug("时间选择器聚焦失败", exc_info=True)
