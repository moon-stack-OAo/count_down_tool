# -*- coding: utf-8 -*-
"""完整模式主界面布局。"""

import tkinter as tk
from tkinter import ttk

from countdown_core import APP_NAME
from ui.widgets import RoundedFrame, init_circle_button, update_circle_button


def setup_styles(app):
    """配置 ttk 样式。"""
    style = ttk.Style()
    style.theme_use("clam")
    c = app.COLORS

    style.configure(".", background=c["bg"], foreground=c["text"])

    style.configure("TLabel", background=c["bg"], foreground=c["text"],
                    font=app.FONTS["label"])
    style.configure("Title.TLabel", font=app.FONTS["title"],
                    foreground=c["white"], background=c["bg"])
    style.configure("Subtitle.TLabel", font=app.FONTS["label"],
                    foreground=c["text_muted"], background=c["bg"])
    style.configure("Time.TLabel", font=app.FONTS["time"],
                    foreground=c["accent_glow"], background=c["glass"])
    style.configure("Countdown.TLabel", font=app.FONTS["countdown"],
                    foreground=c["white"], background=c["glass"])
    style.configure("Success.TLabel", font=app.FONTS["countdown"],
                    foreground=c["success"], background=c["glass"])
    style.configure("Error.TLabel", font=app.FONTS["label"],
                    foreground=c["error"], background=c["bg"])
    style.configure("Dim.TLabel", foreground=c["text_dim"], background=c["glass"])
    style.configure("Flash.TLabel", font=app.FONTS["countdown"],
                    foreground=c["error"], background=c["glass"])

    style.configure("Accent.TButton",
                    font=app.FONTS["button"],
                    background=c["accent"],
                    foreground=c["bg"],
                    borderwidth=0,
                    focuscolor=c["accent_glow"],
                    padding=(24, 12))
    style.map("Accent.TButton",
              background=[("active", c["accent_hover"]),
                          ("pressed", c["accent_hover"]),
                          ("disabled", c["btn_default"])],
              foreground=[("disabled", c["text_muted"]),
                          ("!disabled", c["bg"])])

    style.configure("Secondary.TButton",
                    font=app.FONTS["label"],
                    background=c["card"],
                    foreground=c["text_dim"],
                    borderwidth=0,
                    padding=(18, 10))
    style.map("Secondary.TButton",
              background=[("active", c["chip_hover"]),
                          ("pressed", c["border"])],
              foreground=[("active", c["text"])])

    style.configure("TSpinbox",
                    fieldbackground=c["input_bg"],
                    background=c["input_bg"],
                    foreground=c["text"],
                    arrowcolor=c["accent_glow"],
                    bordercolor=c["border"],
                    lightcolor=c["border"],
                    darkcolor=c["border"],
                    insertcolor=c["accent"],
                    selectbackground=c["accent_soft"],
                    selectforeground=c["white"])
    style.map("TSpinbox",
              fieldbackground=[("focus", c["input_bg"])],
              bordercolor=[("focus", c["accent"])])


def build_full_ui(app):
    """构建完整模式主界面，控件引用挂到 app 上。可重复调用（主题重建）。"""
    c = app.COLORS
    font_family = app.FONTS["label"][0]

    # ===== 标题栏 =====
    title_bar = tk.Frame(app.master, bg=c["title_bar"], height=48)
    title_bar.pack(fill=tk.X)
    title_bar.pack_propagate(False)

    title_line = tk.Frame(title_bar, bg=c["accent"], height=2)
    title_line.pack(side=tk.BOTTOM, fill=tk.X)

    title_bar.bind("<Button-1>", app._start_drag)
    title_bar.bind("<B1-Motion>", app._on_drag)

    title_label = tk.Label(title_bar, text=f"  ⏱  {APP_NAME}",
                           bg=c["title_bar"], fg=c["text"],
                           font=app._font("label", 10, bold=True))
    title_label.pack(side=tk.LEFT, fill=tk.Y)
    title_label.bind("<Button-1>", app._start_drag)
    title_label.bind("<B1-Motion>", app._on_drag)

    btn_frame = tk.Frame(title_bar, bg=app.COLORS["title_bar"])
    btn_frame.pack(side=tk.RIGHT, padx=(0, 10))

    close_btn_size = 16
    close_btn = tk.Canvas(btn_frame, width=close_btn_size * 2, height=close_btn_size * 2,
                          bg=app.COLORS["title_bar"], highlightthickness=0, cursor="hand2")
    close_btn.pack(side=tk.RIGHT, padx=(6, 0))
    close_btn_items = init_circle_button(
        close_btn, close_btn_size, close_btn_size, close_btn_size - 1,
        fill=app.COLORS["btn_default"], text="×",
        text_color=app.COLORS["text_dim"], font_family=font_family, font_size=12,
    )
    close_btn.bind("<Enter>",
                   lambda e: update_circle_button(close_btn, close_btn_items,
                                                  fill=app.COLORS["btn_hover_close"],
                                                  text_color=app.COLORS["white"]))
    close_btn.bind("<Leave>",
                   lambda e: update_circle_button(close_btn, close_btn_items,
                                                  fill=app.COLORS["btn_default"],
                                                  text_color=app.COLORS["text_dim"]))
    close_btn.bind("<Button-1>", lambda e: app._hide_to_tray())

    min_btn_size = 16
    min_btn = tk.Canvas(btn_frame, width=min_btn_size * 2, height=min_btn_size * 2,
                        bg=app.COLORS["title_bar"], highlightthickness=0, cursor="hand2")
    min_btn.pack(side=tk.RIGHT, padx=(6, 0))
    min_btn_items = init_circle_button(
        min_btn, min_btn_size, min_btn_size, min_btn_size - 1,
        fill=app.COLORS["btn_default"], text="−",
        text_color=app.COLORS["text_dim"], font_family=font_family, font_size=12,
    )
    min_btn.bind("<Enter>",
                 lambda e: update_circle_button(min_btn, min_btn_items,
                                                fill=app.COLORS["btn_hover_min"],
                                                text_color=app.COLORS["white"]))
    min_btn.bind("<Leave>",
                 lambda e: update_circle_button(min_btn, min_btn_items,
                                                fill=app.COLORS["btn_default"],
                                                text_color=app.COLORS["text_dim"]))
    min_btn.bind("<Button-1>", lambda e: app._switch_to_mini())

    # ===== 主内容区域 =====
    main_frame = tk.Frame(app.master, bg=c["bg"])
    main_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(18, 24))

    title_frame = tk.Frame(main_frame, bg=c["bg"])
    title_frame.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(title_frame, text=APP_NAME, style="Title.TLabel").pack()
    ttk.Label(title_frame, text="专注当下 · 准时结束", style="Subtitle.TLabel").pack(
        pady=(2, 10)
    )

    clock_card = RoundedFrame(main_frame, bg_color=c["glass"],
                              border_color=c["card_border"],
                              corner_radius=14, height=148)
    clock_card.pack(fill=tk.X, pady=(0, 12))
    clock_inner = tk.Frame(clock_card, bg=c["glass"])
    clock_inner.place(relx=0.5, rely=0.5, anchor="center")

    ttk.Label(clock_inner, text="当前时间", style="Dim.TLabel",
              background=c["glass"]).pack(pady=(0, 2))
    app.current_time_label = ttk.Label(clock_inner, style="Time.TLabel",
                                       background=c["glass"])
    app.current_time_label.pack()

    app.target_time_label = ttk.Label(clock_inner, text="",
                                      font=app.FONTS["time"],
                                      foreground=c["text_dim"],
                                      background=c["glass"])
    app.target_time_label.pack(pady=(6, 0))

    input_sub = tk.Frame(clock_inner, bg=c["glass"])
    input_sub.pack(pady=(10, 0))

    ttk.Label(input_sub, text="到期时间", style="Dim.TLabel",
              background=c["glass"]).pack(pady=(0, 6))

    spin_input_frame = tk.Frame(input_sub, bg=c["glass"])
    spin_input_frame.pack()

    app.hour_var = tk.StringVar(value="18")
    app.minute_var = tk.StringVar(value="00")
    app.second_var = tk.StringVar(value="00")

    spinboxes = [
        (app.hour_var, 0, 23),
        (app.minute_var, 0, 59),
        (app.second_var, 0, 59),
    ]

    spin_font = app._font("time", 14)
    spin_colon_font = app._font("time", 14, bold=True)
    for idx, (var, min_val, max_val) in enumerate(spinboxes):
        sb = ttk.Spinbox(
            spin_input_frame, textvariable=var, from_=min_val, to=max_val,
            width=3, font=spin_font, wrap=True,
            justify="center",
        )
        sb.grid(row=0, column=idx * 2, padx=4)
        if idx < 2:
            ttk.Label(spin_input_frame, text=":", font=spin_colon_font,
                      background=c["glass"], foreground=c["text_muted"]
                      ).grid(row=0, column=idx * 2 + 1)

    app.hour_var.trace_add("write", app._on_time_changed)
    app.minute_var.trace_add("write", app._on_time_changed)
    app.second_var.trace_add("write", app._on_time_changed)

    countdown_card = RoundedFrame(main_frame, bg_color=c["glass"],
                                  border_color=c["accent"],
                                  corner_radius=14, border_width=2, height=120)
    countdown_card.pack(fill=tk.X, pady=(0, 12))
    countdown_inner = tk.Frame(countdown_card, bg=c["glass"])
    countdown_inner.place(relx=0.5, rely=0.5, anchor="center")

    ttk.Label(countdown_inner, text="剩余时间", style="Dim.TLabel",
              background=c["glass"]).pack()
    app.countdown_label = ttk.Label(countdown_inner, text="--:--:--",
                                    style="Countdown.TLabel",
                                    background=c["glass"])
    app.countdown_label.pack(pady=6)

    preset_card = RoundedFrame(main_frame, bg_color=c["glass"],
                               border_color=c["card_border"],
                               corner_radius=14)
    preset_card.pack(fill=tk.X, pady=(0, 12))
    preset_inner = tk.Frame(preset_card, bg=c["glass"])
    preset_inner.place(relx=0.5, rely=0.5, anchor="center")

    ttk.Label(preset_inner, text="快捷预设", style="Dim.TLabel",
              background=c["glass"]).pack(side=tk.LEFT, padx=(0, 12))

    preset_buttons = [
        ("5分钟", "00", "05", "00"),
        ("10分钟", "00", "10", "00"),
        ("15分钟", "00", "15", "00"),
        ("30分钟", "00", "30", "00"),
        ("1小时", "01", "00", "00"),
    ]
    for text, h, m, s in preset_buttons:
        btn = tk.Label(preset_inner, text=text, font=app._font("label", 9),
                       bg=c["chip"], fg=c["text"],
                       padx=11, pady=5, cursor="hand2")
        btn.pack(side=tk.LEFT, padx=(0, 8))
        btn.bind("<Enter>", lambda e, b=btn: b.config(
            bg=c["chip_hover"], fg=c["accent_glow"]))
        btn.bind("<Leave>", lambda e, b=btn: b.config(
            bg=c["chip"], fg=c["text"]))
        btn.bind("<Button-1>", lambda e, hh=h, mm=m, ss=s: app._set_preset_time(hh, mm, ss))

    app.error_label = ttk.Label(main_frame, style="Error.TLabel")
    app.error_label.pack(pady=(0, 10))

    action_frame = tk.Frame(main_frame, bg=c["bg"])
    action_frame.pack(fill=tk.X)

    app.btn_start = ttk.Button(action_frame, text="开始倒计时",
                               style="Accent.TButton", command=app.toggle_countdown)
    app.btn_start.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 10))

    ttk.Button(action_frame, text="重置", style="Secondary.TButton",
               command=app.reset).pack(side=tk.RIGHT)

    app.master.bind("<Escape>", lambda e: app._hide_to_tray())
    app.master.bind("<m>", lambda e: app._toggle_mini_mode())
    app.master.bind("<M>", lambda e: app._toggle_mini_mode())

    app.master.protocol("WM_DELETE_WINDOW", app._hide_to_tray)
