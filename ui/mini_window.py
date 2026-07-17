# -*- coding: utf-8 -*-
"""Mini 桌面小组件：创建 / 拖动 / 右键菜单。"""

import logging
import platform
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from countdown_core import STATE_FINISHED, STATE_RUNNING, parse_mini_geometry
from services.windows_native import start_native_window_drag

logger = logging.getLogger("count_down_tool")


def create_mini_window(app):
    """创建 Mini 窗口并挂到 app 上。"""
    if app.mini_window:
        return

    mini = tk.Toplevel(app.master)
    mini.title("")
    mini.overrideredirect(True)
    mini.attributes("-topmost", True)
    mini.configure(bg=app.COLORS["title_bar"])
    if platform.system() == "Windows":
        if app._transparent_mode:
            mini.attributes("-transparentcolor", app.COLORS["title_bar"])

    win_w, win_h = app.MINI_WIDTH, app.MINI_HEIGHT
    screen_w = mini.winfo_screenwidth()
    screen_h = mini.winfo_screenheight()

    if app._mini_pos:
        x, y = app._mini_pos
    else:
        x = screen_w - win_w - app.MINI_MARGIN_RIGHT
        y = screen_h - win_h - app.MINI_MARGIN_BOTTOM
    mini.geometry(f"{win_w}x{win_h}+{x}+{y}")

    if app._transparent_mode:
        mini.configure(highlightthickness=0)
    else:
        mini.configure(highlightthickness=1, highlightbackground=app.COLORS["accent"])

    main_frame = tk.Frame(mini, bg=app.COLORS["title_bar"])
    main_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

    content_frame = tk.Frame(main_frame, bg=app.COLORS["title_bar"])
    content_frame.pack(fill=tk.BOTH, expand=True)

    app.mini_time_label = tk.Label(
        content_frame, text=datetime.now().strftime("%H:%M"),
        font=app.FONTS["mini_time"],
        bg=app.COLORS["title_bar"], fg=app.COLORS["text_dim"],
    )
    app.mini_time_label.pack(side=tk.LEFT)

    tk.Label(
        content_frame, text="│",
        font=app.FONTS["mini_time"],
        bg=app.COLORS["title_bar"], fg=app.COLORS["border"],
    ).pack(side=tk.LEFT, padx=4)

    app.mini_countdown_label = tk.Label(
        content_frame, text=app.countdown_text,
        font=app.FONTS["mini_countdown"],
        bg=app.COLORS["title_bar"], fg=app.COLORS["white"],
    )
    app.mini_countdown_label.pack(side=tk.LEFT, expand=True)

    btn_frame = tk.Frame(content_frame, bg=app.COLORS["title_bar"])
    btn_frame.pack(side=tk.RIGHT, padx=(4, 0))

    expand_btn = tk.Label(
        btn_frame, text="↗", font=app._font("label", 10),
        bg=app.COLORS["title_bar"], fg=app.COLORS["accent_glow"], cursor="hand2",
    )
    expand_btn.pack(side=tk.LEFT, padx=(0, 4))
    expand_btn.bind("<Button-1>", lambda e: app._switch_to_full())

    close_btn = tk.Label(
        btn_frame, text="×", font=app._font("label", 10, bold=True),
        bg=app.COLORS["title_bar"], fg=app.COLORS["text_dim"], cursor="hand2",
    )
    close_btn.pack(side=tk.LEFT)
    close_btn.bind("<Button-1>", lambda e: mini_close(app))
    close_btn.bind("<Enter>", lambda e: close_btn.config(fg=app.COLORS["btn_hover_close"]))
    close_btn.bind("<Leave>", lambda e: close_btn.config(fg=app.COLORS["text_dim"]))

    drag_widgets = (mini, main_frame, content_frame,
                    app.mini_time_label, app.mini_countdown_label)
    if platform.system() == "Windows":
        for w in drag_widgets:
            w.bind("<Button-1>", lambda e: mini_start_drag(app, e))
            w.bind("<ButtonRelease-1>", lambda e: mini_end_drag(app, e))
    else:
        for widget in drag_widgets:
            widget.bind("<Button-1>", lambda e: mini_start_drag(app, e))
            widget.bind("<B1-Motion>", lambda e: mini_do_drag(app, e))
            widget.bind("<ButtonRelease-1>", lambda e: mini_end_drag(app, e))

    for w in drag_widgets:
        w.bind("<Button-3>", lambda e: show_mini_context_menu(app, e))
        if platform.system() == "Darwin":
            w.bind("<Control-Button-1>", lambda e: show_mini_context_menu(app, e))

    app.mini_window = mini
    sync_mini_state(app)


def show_mini_context_menu(app, event):
    """Mini 右键菜单。"""
    menu = tk.Menu(app.mini_window or app.master, tearoff=0,
                   bg=app.COLORS["card"], fg=app.COLORS["text"],
                   activebackground=app.COLORS["accent"],
                   activeforeground=app.COLORS["white"])
    menu.add_command(label="展开完整模式", command=app._switch_to_full)
    if platform.system() == "Windows":
        menu.add_command(
            label="关闭透明模式" if app._transparent_mode else "开启透明模式",
            command=app._toggle_transparent_mode,
        )
    menu.add_separator()
    if app._has_tray():
        menu.add_command(label="隐藏到托盘", command=lambda: mini_close(app))
    else:
        menu.add_command(label="关闭", command=lambda: mini_close(app))
    menu.add_command(label="退出", command=app._quit_app)
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def destroy_mini_window(app):
    """销毁 Mini 并保存位置。"""
    if app.mini_window:
        try:
            pos = parse_mini_geometry(app.mini_window.geometry())
            if pos is not None:
                app._mini_pos = pos
                app._save_config()
        except Exception:
            logger.warning("保存 Mini 窗口位置失败", exc_info=True)
        try:
            app.mini_window.destroy()
        except Exception:
            logger.warning("销毁 Mini 窗口失败", exc_info=True)
        app.mini_window = None
        app.mini_countdown_label = None
        app.mini_time_label = None


def recreate_mini_window(app):
    """重建 mini 窗口（切换透明模式时）。"""
    destroy_mini_window(app)
    create_mini_window(app)


def mini_start_drag(app, event):
    if platform.system() == "Windows":
        if app.mini_window:
            start_native_window_drag(app.mini_window)
    else:
        app._drag_data["x"] = event.x
        app._drag_data["y"] = event.y


def mini_do_drag(app, event):
    if platform.system() == "Windows":
        return
    if app.mini_window:
        x = app.mini_window.winfo_x() + event.x - app._drag_data["x"]
        y = app.mini_window.winfo_y() + event.y - app._drag_data["y"]
        app.mini_window.geometry(f"+{x}+{y}")
        app._mini_pos = (x, y)


def mini_end_drag(app, event=None):
    if not app.mini_window:
        return
    try:
        pos = parse_mini_geometry(app.mini_window.geometry())
        if pos is not None:
            app._mini_pos = pos
            app._save_config()
    except Exception:
        logger.warning("结束 Mini 拖动时保存位置失败", exc_info=True)


def mini_close(app):
    """Mini 关闭：有托盘则隐藏到托盘，否则回到完整模式。"""
    if app._has_tray():
        app._is_mini = False
        destroy_mini_window(app)
        app.master.withdraw()
        if app._first_hide:
            app._first_hide = False
            app.master.after(0, lambda: messagebox.showinfo(
                "提示",
                "程序已最小化到系统托盘。\n"
                "右键托盘图标可切换 Mini 模式或退出。",
                parent=app.master,
            ))
    else:
        app._switch_to_full()


def sync_mini_state(app):
    """同步 mini 窗口的状态显示。"""
    if app.mini_window and app.mini_countdown_label:
        app.mini_countdown_label.config(text=app.countdown_text)
        if app._state == STATE_RUNNING:
            app.mini_countdown_label.config(fg=app.COLORS["white"])
        elif app._state == STATE_FINISHED:
            app.mini_countdown_label.config(fg=app.COLORS["success"])
        else:
            app.mini_countdown_label.config(fg=app.COLORS["text_dim"])
