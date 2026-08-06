# -*- coding: utf-8 -*-
"""完整模式主界面布局。"""

import tkinter as tk
from tkinter import ttk

from core.countdown_core import APP_NAME, __version__
from ui.chrome_titlebar import MAIN_TITLE_HEIGHT, add_circle_button, build_title_bar
from ui.context_menus import bind_full_context_menu, bind_full_context_menu_tree
from ui.widgets import RoundedFrame


def refresh_update_badge(app) -> None:
    """按 app._pending_update_result 显示/隐藏标题栏 NEW 角标。"""
    badge = getattr(app, "_title_update_badge", None)
    if badge is None:
        return
    try:
        if not badge.winfo_exists():
            return
    except tk.TclError:
        return
    pending = getattr(app, "_pending_update_result", None)
    show = bool(pending is not None and getattr(pending, "has_update", False))
    try:
        if show:
            if not badge.winfo_ismapped():
                badge.pack(side=tk.LEFT, padx=(6, 0))
        else:
            if badge.winfo_ismapped():
                badge.pack_forget()
    except tk.TclError:
        pass


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
    style.configure("Caption.TLabel", font=app._font("label", 9),
                    foreground=c["text_muted"], background=c["glass"])
    style.configure("Meta.TLabel", font=app._font("label", 9),
                    foreground=c["text_dim"], background=c["glass"])
    style.configure("MetaMuted.TLabel", font=app._font("label", 8),
                    foreground=c["text_muted"], background=c["glass"])
    # 结束闪烁：预注册奇偶色，flash_visual 只切换 style
    style.configure("FlashEven.TLabel", font=app.FONTS["countdown"],
                    foreground=c["success"], background=c["glass"])
    style.configure("FlashOdd.TLabel", font=app.FONTS["countdown"],
                    foreground=c["error"], background=c["glass"])
    # 兼容旧 style 名（等同奇数帧 error 色）
    style.configure("Flash.TLabel", font=app.FONTS["countdown"],
                    foreground=c["error"], background=c["glass"])

    _btn_fg = c.get("btn_on_primary", c["bg"])
    # 空闲 / 开始
    style.configure("Accent.TButton",
                    font=app.FONTS["button"],
                    background=c.get("btn_primary", c["accent"]),
                    foreground=_btn_fg,
                    borderwidth=0,
                    focuscolor=c["accent_glow"],
                    padding=(24, 12))
    style.map("Accent.TButton",
              background=[("active", c.get("btn_primary_hover", c["accent_hover"])),
                          ("pressed", c.get("btn_primary_hover", c["accent_hover"])),
                          ("disabled", c["btn_default"])],
              foreground=[("disabled", c["text_muted"]),
                          ("!disabled", _btn_fg)])
    # 运行中 / 暂停
    style.configure("PrimaryRunning.TButton",
                    font=app.FONTS["button"],
                    background=c.get("btn_running", c["warning"]),
                    foreground=_btn_fg,
                    borderwidth=0,
                    focuscolor=c.get("btn_running_hover", c["warning"]),
                    padding=(24, 12))
    style.map("PrimaryRunning.TButton",
              background=[("active", c.get("btn_running_hover", c["warning"])),
                          ("pressed", c.get("btn_running_hover", c["warning"])),
                          ("disabled", c["btn_default"])],
              foreground=[("disabled", c["text_muted"]),
                          ("!disabled", _btn_fg)])
    # 完成
    style.configure("PrimaryFinished.TButton",
                    font=app.FONTS["button"],
                    background=c.get("btn_finished", c["success"]),
                    foreground=_btn_fg,
                    borderwidth=0,
                    focuscolor=c.get("btn_finished_hover", c["success"]),
                    padding=(24, 12))
    style.map("PrimaryFinished.TButton",
              background=[("active", c.get("btn_finished_hover", c["success"])),
                          ("pressed", c.get("btn_finished_hover", c["success"])),
                          ("disabled", c["btn_default"])],
              foreground=[("disabled", c["text_muted"]),
                          ("!disabled", _btn_fg)])

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
              fieldbackground=[("readonly", c["input_bg"]),
                               ("disabled", c.get("card", c["input_bg"])),
                               ("focus", c["input_bg"])],
              foreground=[("disabled", c["text_muted"])],
              bordercolor=[("focus", c["accent"]),
                           ("disabled", c["border"])])


def build_full_ui(app):
    """构建完整模式主界面，控件引用挂到 app 上。可重复调用（主题重建）。"""
    c = app.COLORS

    # ===== 标题栏（公共自绘组件）=====
    chrome = build_title_bar(
        app.master,
        app,
        title=f"⏱  {APP_NAME}",
        height=MAIN_TITLE_HEIGHT,
        on_drag_start=app._start_drag,
        on_drag_motion=app._on_drag,
    )
    title_bar = chrome.frame
    title_label = chrome.title_label

    def _on_update_from_title(_e=None):
        from services.updater import open_update_from_ui

        open_update_from_ui(app)

    # 弱样式版本号：点击等同检查更新
    version_label = tk.Label(
        title_bar,
        text=f"v{__version__}",
        bg=c["title_bar"],
        fg=c.get("text_muted", c.get("text_dim", c["text"])),
        font=app._font("label", 8),
        cursor="hand2",
    )
    version_label.pack(side=tk.LEFT, padx=(6, 0))
    version_label.bind("<Button-1>", _on_update_from_title)
    app._title_version_label = version_label

    # 标题旁 NEW：有可用更新时显示，点击打开更新流程
    update_badge = tk.Label(
        title_bar,
        text=" NEW ",
        bg=c.get("error", "#FB7185"),
        fg=c.get("white", "#FFFFFF"),
        font=app._font("label", 8, bold=True),
        cursor="hand2",
        padx=4,
        pady=1,
    )
    app._title_update_badge = update_badge
    update_badge.bind("<Button-1>", _on_update_from_title)
    refresh_update_badge(app)

    def _open_settings(_e=None):
        if hasattr(app, "_show_settings"):
            app._show_settings()
        else:
            from ui.settings_window import show_settings

            show_settings(app)

    # pack side=RIGHT：先 close → min → settings，视觉从左到右 ⚙ − ×
    add_circle_button(
        chrome.btn_frame,
        app,
        text="×",
        command=lambda _e=None: app._hide_to_tray(),
        hover_fill=c["btn_hover_close"],
        font_size=12,
        name="close",
        chrome=chrome,
    )
    add_circle_button(
        chrome.btn_frame,
        app,
        text="−",
        command=lambda _e=None: app._switch_to_mini(),
        hover_fill=c["btn_hover_min"],
        font_size=12,
        name="mini",
        chrome=chrome,
    )
    add_circle_button(
        chrome.btn_frame,
        app,
        text="⚙",
        command=_open_settings,
        hover_fill=c["accent"],
        font_size=10,
        name="settings",
        chrome=chrome,
    )

    # ===== 主内容区域 =====
    main_frame = tk.Frame(app.master, bg=c["bg"])
    main_frame.pack(fill=tk.BOTH, expand=True, padx=22, pady=(14, 16))

    # ----- 倒计时主视觉卡（置顶）-----
    _display_border = c.get("card_border", c["border"])
    countdown_card = RoundedFrame(
        main_frame,
        bg_color=c["glass"],
        border_color=_display_border,
        corner_radius=14,
        border_width=1,
        height=172,
    )
    countdown_card.pack(fill=tk.X, pady=(0, 12))
    countdown_inner = tk.Frame(countdown_card, bg=c["glass"])
    countdown_inner.place(relx=0.5, rely=0.5, anchor="center")

    ttk.Label(
        countdown_inner,
        text="剩余时间",
        style="Caption.TLabel",
        background=c["glass"],
    ).pack(pady=(0, 2))

    app.countdown_label = ttk.Label(
        countdown_inner,
        text="--:--:--",
        style="Countdown.TLabel",
        background=c["glass"],
    )
    app.countdown_label.pack(pady=(0, 4))

    # 进度条（细条；主题重建后需重新挂到 app）
    _progress_w, _progress_h = 280, 4
    app.progress_canvas = tk.Canvas(
        countdown_inner,
        width=_progress_w,
        height=_progress_h,
        bg=c["glass"],
        highlightthickness=0,
        bd=0,
    )
    app.progress_canvas.pack(pady=(4, 8))
    app._progress_bar_w = _progress_w
    app._progress_bar_h = _progress_h
    app._progress_track_id = app.progress_canvas.create_rectangle(
        0, 0, _progress_w, _progress_h,
        fill=c.get("border", c["card_border"]), outline="",
    )
    app._progress_fill_id = app.progress_canvas.create_rectangle(
        0, 0, 0, _progress_h,
        fill=c["accent"], outline="",
    )

    app.target_time_label = ttk.Label(
        countdown_inner,
        text="",
        style="Meta.TLabel",
        background=c["glass"],
    )
    app.target_time_label.pack()

    app.current_time_label = ttk.Label(
        countdown_inner,
        text="",
        style="MetaMuted.TLabel",
        background=c["glass"],
    )
    app.current_time_label.pack(pady=(4, 0))

    # ----- 设置卡：到期时间 + 快捷预设 -----
    settings_card = RoundedFrame(
        main_frame,
        bg_color=c["card"],
        border_color=c["card_border"],
        corner_radius=14,
        border_width=1,
        height=132,
    )
    settings_card.pack(fill=tk.X, pady=(0, 10))
    app._settings_card = settings_card
    settings_inner = tk.Frame(settings_card, bg=c["card"])
    settings_inner.place(relx=0.5, rely=0.5, anchor="center")
    app._settings_inner = settings_inner

    time_row = tk.Frame(settings_inner, bg=c["card"])
    time_row.pack()

    ttk.Label(
        time_row,
        text="到期时间（今日）",
        style="Caption.TLabel",
        background=c["card"],
    ).pack(side=tk.LEFT, padx=(0, 12))

    spin_input_frame = tk.Frame(time_row, bg=c["card"])
    spin_input_frame.pack(side=tk.LEFT)

    app.hour_var = tk.StringVar(value="18")
    app.minute_var = tk.StringVar(value="00")
    app.second_var = tk.StringVar(value="00")

    spinboxes = [
        (app.hour_var, 0, 23),
        (app.minute_var, 0, 59),
        (app.second_var, 0, 59),
    ]

    def _spin_wheel(event, spin: ttk.Spinbox):
        """滚轮增减；运行锁定时忽略。"""
        if getattr(app, "_inputs_locked", lambda: False)():
            return "break"
        try:
            if event.delta > 0 or getattr(event, "num", None) == 4:
                spin.invoke("buttonup")
            else:
                spin.invoke("buttondown")
        except tk.TclError:
            pass
        return "break"

    app._time_spinboxes = []
    spin_font = app._font("time", 14)
    spin_colon_font = app._font("time", 14, bold=True)
    for idx, (var, min_val, max_val) in enumerate(spinboxes):
        sb = ttk.Spinbox(
            spin_input_frame,
            textvariable=var,
            from_=min_val,
            to=max_val,
            width=3,
            font=spin_font,
            wrap=True,
            justify="center",
        )
        sb.grid(row=0, column=idx * 2, padx=3)
        sb.bind("<MouseWheel>", lambda e, s=sb: _spin_wheel(e, s))
        sb.bind("<Button-4>", lambda e, s=sb: _spin_wheel(e, s))
        sb.bind("<Button-5>", lambda e, s=sb: _spin_wheel(e, s))
        app._time_spinboxes.append(sb)
        if idx < 2:
            ttk.Label(
                spin_input_frame,
                text=":",
                font=spin_colon_font,
                background=c["card"],
                foreground=c["text_muted"],
            ).grid(row=0, column=idx * 2 + 1)

    app.hour_var.trace_add("write", app._on_time_changed)
    app.minute_var.trace_add("write", app._on_time_changed)
    app.second_var.trace_add("write", app._on_time_changed)

    preset_row = tk.Frame(settings_inner, bg=c["card"])
    preset_row.pack(pady=(12, 0))

    ttk.Label(
        preset_row,
        text="快捷时长",
        style="Caption.TLabel",
        background=c["card"],
    ).pack(side=tk.LEFT, padx=(0, 10))

    preset_buttons = [
        ("+5分", "00", "05", "00"),
        ("+10分", "00", "10", "00"),
        ("+15分", "00", "15", "00"),
        ("+30分", "00", "30", "00"),
        ("+1时", "01", "00", "00"),
    ]
    app._preset_chips = []
    for text, h, m, s in preset_buttons:
        btn = tk.Label(
            preset_row,
            text=text,
            font=app._font("label", 9),
            bg=c["chip"],
            fg=c["text_dim"],
            padx=10,
            pady=5,
            cursor="hand2",
        )
        btn.pack(side=tk.LEFT, padx=(0, 6))
        btn._preset_hms = (h, m, s)  # type: ignore[attr-defined]
        app._preset_chips.append(btn)

    # 按当前状态应用输入锁定、主按钮色、进度条
    if hasattr(app, "_apply_input_lock"):
        app._apply_input_lock()
    if hasattr(app, "_apply_primary_button_style"):
        app._apply_primary_button_style()
    if hasattr(app, "_refresh_progress_bar"):
        app._refresh_progress_bar()

    app.error_label = ttk.Label(main_frame, style="Error.TLabel")
    app.error_label.pack(pady=(0, 8))

    action_frame = tk.Frame(main_frame, bg=c["bg"])
    action_frame.pack(fill=tk.X)

    app.btn_start = ttk.Button(
        action_frame,
        text="开始倒计时",
        style="Accent.TButton",
        command=app.toggle_countdown,
    )
    app.btn_start.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 10))

    ttk.Button(
        action_frame,
        text="重置",
        style="Secondary.TButton",
        command=app.reset,
    ).pack(side=tk.RIGHT)

    # 主题重建会重复 build：先 unbind 再绑，避免快捷键叠加
    for seq in ("<Escape>", "<m>", "<M>", "<t>", "<T>"):
        try:
            app.master.unbind(seq)
        except tk.TclError:
            pass
    app.master.bind("<Escape>", lambda e: app._hide_to_tray())
    app.master.bind("<m>", lambda e: app._toggle_mini_mode())
    app.master.bind("<M>", lambda e: app._toggle_mini_mode())
    app.master.bind("<t>", app._toggle_transparent_mode)
    app.master.bind("<T>", app._toggle_transparent_mode)

    app.master.protocol("WM_DELETE_WINDOW", app._hide_to_tray)

    # 右键菜单：标题区 + 主内容树（不绑关闭/最小化按钮，避免误触）
    # Button-3 与标题拖动（Button-1）互不干扰
    bind_full_context_menu(app, title_bar, title_label, version_label, update_badge)
    bind_full_context_menu_tree(app, main_frame)
