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
    # Mini 统一无边框小组件外观。macOS 系统右键在无边框上不稳定，靠 ⋯ 按钮 +
    # Control-点击 / Button-2/3 作为菜单入口（见 bind_mini_context_menu）。
    mini.title("")
    mini.overrideredirect(True)
    mini.attributes("-topmost", True)
    system = platform.system()
    # macOS 透明：-transparent + systemTransparent（底板透明、文字不透明）
    # Windows 透明：-transparentcolor 色键抠底
    if app._transparent_mode and system == "Darwin":
        bg = "systemTransparent"
    else:
        bg = app.COLORS["title_bar"]
    mini.configure(bg=bg)
    if app._transparent_mode:
        if system == "Windows":
            mini.attributes("-transparentcolor", app.COLORS["title_bar"])
        elif system == "Darwin":
            try:
                mini.attributes("-transparent", True)
            except tk.TclError:
                # 旧 Tk 无 -transparent 时回退半透明
                try:
                    mini.attributes("-alpha", 0.3)
                except tk.TclError:
                    logger.debug("设置 Mini 透明失败", exc_info=True)
                bg = app.COLORS["title_bar"]
                mini.configure(bg=bg)
    else:
        try:
            if system == "Darwin":
                mini.attributes("-transparent", False)
            mini.attributes("-alpha", 1.0)
        except tk.TclError:
            pass

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

    main_frame = tk.Frame(mini, bg=bg)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

    content_frame = tk.Frame(main_frame, bg=bg)
    content_frame.pack(fill=tk.BOTH, expand=True)

    app.mini_time_label = tk.Label(
        content_frame, text=datetime.now().strftime("%H:%M"),
        font=app.FONTS["mini_time"],
        bg=bg, fg=app.COLORS["text_dim"],
    )
    app.mini_time_label.pack(side=tk.LEFT)

    tk.Label(
        content_frame, text="│",
        font=app.FONTS["mini_time"],
        bg=bg, fg=app.COLORS["border"],
    ).pack(side=tk.LEFT, padx=4)

    app.mini_countdown_label = tk.Label(
        content_frame, text=app.countdown_text,
        font=app.FONTS["mini_countdown"],
        bg=bg, fg=app.COLORS["white"],
    )
    app.mini_countdown_label.pack(side=tk.LEFT, expand=True)

    btn_frame = tk.Frame(content_frame, bg=bg)
    btn_frame.pack(side=tk.RIGHT, padx=(4, 0))

    # 菜单按钮：macOS 触控板右键不稳定时的可靠入口
    menu_btn = tk.Label(
        btn_frame, text="⋯", font=app._font("label", 12, bold=True),
        bg=bg, fg=app.COLORS["text_dim"], cursor="hand2",
    )
    menu_btn.pack(side=tk.LEFT, padx=(0, 4))
    menu_btn.bind("<Button-1>", lambda e: show_mini_context_menu(app, e))
    menu_btn.bind("<Enter>", lambda e: menu_btn.config(fg=app.COLORS["accent"]))
    menu_btn.bind("<Leave>", lambda e: menu_btn.config(fg=app.COLORS["text_dim"]))

    expand_btn = tk.Label(
        btn_frame, text="↗", font=app._font("label", 10),
        bg=bg, fg=app.COLORS["accent_glow"], cursor="hand2",
    )
    expand_btn.pack(side=tk.LEFT, padx=(0, 4))
    expand_btn.bind("<Button-1>", lambda e: app._switch_to_full())

    close_btn = tk.Label(
        btn_frame, text="×", font=app._font("label", 10, bold=True),
        bg=bg, fg=app.COLORS["text_dim"], cursor="hand2",
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

    bind_mini_context_menu(app, *drag_widgets, menu_btn, expand_btn, close_btn)

    app.mini_window = mini
    # 确保 macOS 上 Toplevel 获得焦点，右键/菜单可弹出
    try:
        mini.lift()
        mini.focus_force()
    except tk.TclError:
        pass

    # Mini 快捷键（与完整窗一致；需焦点在 Mini 上）
    mini.bind("<Escape>", lambda e: mini_close(app))
    mini.bind("<m>", lambda e: app._switch_to_full())
    mini.bind("<M>", lambda e: app._switch_to_full())
    mini.bind("<t>", app._toggle_transparent_mode)
    mini.bind("<T>", app._toggle_transparent_mode)
    for w in drag_widgets:
        w.bind("<t>", app._toggle_transparent_mode)
        w.bind("<T>", app._toggle_transparent_mode)
        w.bind("<m>", lambda e: app._switch_to_full())
        w.bind("<M>", lambda e: app._switch_to_full())

    sync_mini_state(app)


def bind_mini_context_menu(app, *widgets):
    """绑定 Mini 右键/副键菜单。

    macOS：触控板副键常为 Button-2；Control+点击为 Control-Button-1。
    无边框窗体上右键常失效，故同时提供 ⋯ 按钮。
    """
    sequences = ("<Button-2>", "<Button-3>", "<Control-Button-1>")
    for w in widgets:
        if w is None:
            continue
        for seq in sequences:
            w.bind(seq, lambda e, a=app: show_mini_context_menu(a, e))


def show_mini_context_menu(app, event):
    """Mini 右键菜单（委托共享构建，重建后绑定仍有效）。"""
    from ui.context_menus import popup_mini_menu

    try:
        if app.mini_window:
            app.mini_window.lift()
            app.mini_window.focus_force()
    except tk.TclError:
        pass
    popup_mini_menu(app, event)


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
        app._last_mode = "full"
        destroy_mini_window(app)
        app.master.withdraw()
        app._save_config()
        from services.tray import refresh_tray_menu

        refresh_tray_menu(app)
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
