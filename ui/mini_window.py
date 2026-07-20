# -*- coding: utf-8 -*-
"""Mini 桌面小组件：创建 / 拖动 / 缩放 / 右键菜单。"""

import logging
import platform
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from countdown_core import (
    STATE_FINISHED,
    STATE_RUNNING,
    mini_content_scale,
    normalize_mini_size,
    parse_mini_geometry,
    parse_mini_size,
)
from services.windows_native import set_tool_window, start_native_window_drag

logger = logging.getLogger("count_down_tool")

# 边缘热区宽度（像素）
_RESIZE_BORDER = 6

# 边缘 → 光标
_RESIZE_CURSORS = {
    "n": "sb_v_double_arrow",
    "s": "sb_v_double_arrow",
    "e": "sb_h_double_arrow",
    "w": "sb_h_double_arrow",
    "ne": "size_ne_sw",
    "sw": "size_ne_sw",
    "nw": "size_nw_se",
    "se": "size_nw_se",
}


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

    win_w, win_h = app.resolved_mini_size()
    min_w, min_h, max_w, max_h = app._mini_size_limits()
    screen_w = mini.winfo_screenwidth()
    screen_h = mini.winfo_screenheight()

    if app._mini_pos:
        x, y = app._mini_pos
    else:
        x = screen_w - win_w - app.MINI_MARGIN_RIGHT
        y = screen_h - win_h - app.MINI_MARGIN_BOTTOM
    mini.geometry(f"{win_w}x{win_h}+{x}+{y}")
    try:
        mini.minsize(min_w, min_h)
        mini.maxsize(max_w, max_h)
    except tk.TclError:
        pass

    if app._transparent_mode:
        mini.configure(highlightthickness=0)
    else:
        mini.configure(highlightthickness=1, highlightbackground=app.COLORS["accent"])

    main_frame = tk.Frame(mini, bg=bg)
    main_frame.pack(fill=tk.BOTH, expand=True)

    content_frame = tk.Frame(main_frame, bg=bg)
    content_frame.pack(fill=tk.BOTH, expand=True)

    app.mini_time_label = tk.Label(
        content_frame, text=datetime.now().strftime("%H:%M"),
        font=app.FONTS["mini_time"],
        bg=bg, fg=app.COLORS["text_dim"],
    )
    app.mini_time_label.pack(side=tk.LEFT)

    app.mini_sep_label = tk.Label(
        content_frame, text="│",
        font=app.FONTS["mini_time"],
        bg=bg, fg=app.COLORS["border"],
    )
    app.mini_sep_label.pack(side=tk.LEFT)

    app.mini_countdown_label = tk.Label(
        content_frame, text=app.countdown_text,
        font=app.FONTS["mini_countdown"],
        bg=bg, fg=app.COLORS["white"],
    )
    app.mini_countdown_label.pack(side=tk.LEFT, expand=True)

    btn_frame = tk.Frame(content_frame, bg=bg)
    btn_frame.pack(side=tk.RIGHT)

    # 菜单按钮：macOS 触控板右键不稳定时的可靠入口
    menu_btn = tk.Label(
        btn_frame, text="⋯", font=app._font("label", 12, bold=True),
        bg=bg, fg=app.COLORS["text_dim"], cursor="hand2",
    )
    menu_btn.pack(side=tk.LEFT)
    menu_btn.bind("<Button-1>", lambda e: show_mini_context_menu(app, e))
    menu_btn.bind("<Enter>", lambda e: menu_btn.config(fg=app.COLORS["accent"]))
    menu_btn.bind("<Leave>", lambda e: menu_btn.config(fg=app.COLORS["text_dim"]))

    expand_btn = tk.Label(
        btn_frame, text="↗", font=app._font("label", 10),
        bg=bg, fg=app.COLORS["accent_glow"], cursor="hand2",
    )
    expand_btn.pack(side=tk.LEFT)
    expand_btn.bind("<Button-1>", lambda e: app._switch_to_full())

    close_btn = tk.Label(
        btn_frame, text="×", font=app._font("label", 10, bold=True),
        bg=bg, fg=app.COLORS["text_dim"], cursor="hand2",
    )
    close_btn.pack(side=tk.LEFT)
    close_btn.bind("<Button-1>", lambda e: mini_close(app))
    close_btn.bind("<Enter>", lambda e: close_btn.config(fg=app.COLORS["btn_hover_close"]))
    close_btn.bind("<Leave>", lambda e: close_btn.config(fg=app.COLORS["text_dim"]))

    app.mini_main_frame = main_frame
    app.mini_content_frame = content_frame
    app.mini_btn_frame = btn_frame
    app.mini_menu_btn = menu_btn
    app.mini_expand_btn = expand_btn
    app.mini_close_btn = close_btn
    app._mini_layout_scale = None
    app.mini_window = mini
    # 桌面小组件：不进任务栏 / Alt+Tab
    set_tool_window(mini)
    apply_mini_content_scale(app, win_w, win_h, force=True)

    drag_widgets = (
        mini, main_frame, content_frame,
        app.mini_time_label, app.mini_sep_label, app.mini_countdown_label,
    )
    for widget in drag_widgets:
        widget.bind("<Button-1>", lambda e: mini_on_press(app, e))
        widget.bind("<B1-Motion>", lambda e: mini_on_motion(app, e))
        widget.bind("<ButtonRelease-1>", lambda e: mini_on_release(app, e))
        widget.bind("<Motion>", lambda e: mini_on_hover(app, e))
        widget.bind("<Leave>", lambda e: mini_on_leave(app, e))

    bind_mini_context_menu(app, *drag_widgets, menu_btn, expand_btn, close_btn)

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

    # macOS：布局后再强制不低于用户/默认尺寸，避免被压成极小窗
    def _force_mini_size(event=None, w=win_w, h=win_h, win=mini):
        try:
            if not win.winfo_exists():
                return
            if win.winfo_width() < w - 2 or win.winfo_height() < h - 2:
                geo = win.geometry()
                parts = geo.split("+")
                pos = f"+{parts[1]}+{parts[2]}" if len(parts) == 3 else ""
                win.geometry(f"{w}x{h}{pos}")
        except tk.TclError:
            pass

    if system == "Darwin":
        mini.after_idle(_force_mini_size)
        mini.after(50, _force_mini_size)

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


def destroy_mini_window(app, capture_size=True):
    """销毁 Mini 并保存位置（默认也保存尺寸）。

    capture_size=False：仅保存位置，不覆盖 _mini_size（用于「恢复默认大小」）。
    """
    if app.mini_window:
        try:
            if capture_size:
                _capture_mini_geometry(app)
            else:
                geo = app.mini_window.geometry()
                pos = parse_mini_geometry(geo)
                if pos is not None:
                    app._mini_pos = pos
            app._save_config()
        except Exception:
            logger.warning("保存 Mini 窗口几何失败", exc_info=True)
        try:
            app.mini_window.destroy()
        except Exception:
            logger.warning("销毁 Mini 窗口失败", exc_info=True)
        app.mini_window = None
        app.mini_countdown_label = None
        app.mini_time_label = None
        app.mini_sep_label = None
        app.mini_main_frame = None
        app.mini_content_frame = None
        app.mini_btn_frame = None
        app.mini_menu_btn = None
        app.mini_expand_btn = None
        app.mini_close_btn = None
        app._mini_layout_scale = None
        app._resize_data = None


def apply_mini_content_scale(app, width=None, height=None, force=False):
    """按相对默认尺寸的比例缩放 Mini 字号与内边距。"""
    if not getattr(app, "mini_window", None):
        return
    try:
        if width is None or height is None:
            width = app.mini_window.winfo_width()
            height = app.mini_window.winfo_height()
        width, height = int(width), int(height)
        if width <= 1 or height <= 1:
            return
    except (tk.TclError, TypeError, ValueError):
        return

    base_w, base_h = app.default_mini_size()
    scale = mini_content_scale(width, height, base_w, base_h)
    prev = getattr(app, "_mini_layout_scale", None)
    if not force and prev is not None and abs(prev - scale) < 0.02:
        return
    app._mini_layout_scale = scale

    system = platform.system()
    base_pad_x, base_pad_y = (8, 5) if system == "Darwin" else (6, 4)
    base_gap = 5 if system == "Darwin" else 4
    base_menu = 18 if system == "Darwin" else 12
    base_btn = 16 if system == "Darwin" else 10

    def _sz(base, floor=7):
        return max(floor, int(round(base * scale)))

    pad_x = _sz(base_pad_x, 2)
    pad_y = _sz(base_pad_y, 2)
    gap = _sz(base_gap, 2)
    time_sz = _sz(app.FONTS["mini_time"][1], 8)
    count_sz = _sz(app.FONTS["mini_countdown"][1], 10)
    menu_sz = _sz(base_menu, 8)
    btn_sz = _sz(base_btn, 8)

    try:
        if getattr(app, "mini_main_frame", None):
            app.mini_main_frame.pack_configure(padx=pad_x, pady=pad_y)
        if getattr(app, "mini_time_label", None):
            app.mini_time_label.config(font=app._font("mini_time", time_sz, bold=True))
        if getattr(app, "mini_sep_label", None):
            app.mini_sep_label.config(font=app._font("mini_time", time_sz, bold=True))
            app.mini_sep_label.pack_configure(padx=gap)
        if getattr(app, "mini_countdown_label", None):
            app.mini_countdown_label.config(
                font=app._font("mini_countdown", count_sz, bold=True)
            )
        if getattr(app, "mini_btn_frame", None):
            app.mini_btn_frame.pack_configure(padx=(gap, 0))
        if getattr(app, "mini_menu_btn", None):
            app.mini_menu_btn.config(font=app._font("label", menu_sz, bold=True))
            app.mini_menu_btn.pack_configure(padx=(0, gap))
        if getattr(app, "mini_expand_btn", None):
            app.mini_expand_btn.config(font=app._font("label", btn_sz))
            app.mini_expand_btn.pack_configure(padx=(0, gap))
        if getattr(app, "mini_close_btn", None):
            app.mini_close_btn.config(font=app._font("label", btn_sz, bold=True))
    except tk.TclError:
        pass


def recreate_mini_window(app):
    """重建 mini 窗口（切换透明模式时）。"""
    destroy_mini_window(app)
    create_mini_window(app)


def _event_xy_in_window(app, event):
    """将事件坐标转为相对 Mini 窗口左上角。"""
    win = app.mini_window
    if not win:
        return 0, 0
    try:
        return event.x_root - win.winfo_rootx(), event.y_root - win.winfo_rooty()
    except tk.TclError:
        return event.x, event.y


def _hit_resize_edge(app, x, y):
    """根据相对窗口坐标判断缩放边缘；中心返回 None。"""
    win = app.mini_window
    if not win:
        return None
    try:
        w = max(win.winfo_width(), 1)
        h = max(win.winfo_height(), 1)
    except tk.TclError:
        return None
    b = _RESIZE_BORDER
    on_w = x <= b
    on_e = x >= w - b
    on_n = y <= b
    on_s = y >= h - b
    if on_n and on_w:
        return "nw"
    if on_n and on_e:
        return "ne"
    if on_s and on_w:
        return "sw"
    if on_s and on_e:
        return "se"
    if on_n:
        return "n"
    if on_s:
        return "s"
    if on_w:
        return "w"
    if on_e:
        return "e"
    return None


def mini_on_hover(app, event):
    """边缘悬停时切换缩放光标。"""
    if not app.mini_window or app._resize_data:
        return
    x, y = _event_xy_in_window(app, event)
    edge = _hit_resize_edge(app, x, y)
    cursor = _RESIZE_CURSORS.get(edge, "")
    try:
        app.mini_window.configure(cursor=cursor)
    except tk.TclError:
        pass


def mini_on_leave(app, event):
    if app._resize_data:
        return
    try:
        if app.mini_window:
            app.mini_window.configure(cursor="")
    except tk.TclError:
        pass


def mini_on_press(app, event):
    """按下：边缘开始缩放，否则拖动窗口。"""
    if not app.mini_window:
        return
    x, y = _event_xy_in_window(app, event)
    edge = _hit_resize_edge(app, x, y)
    if edge:
        try:
            win = app.mini_window
            app._resize_data = {
                "edge": edge,
                "start_x": event.x_root,
                "start_y": event.y_root,
                "orig_x": win.winfo_x(),
                "orig_y": win.winfo_y(),
                "orig_w": win.winfo_width(),
                "orig_h": win.winfo_height(),
            }
        except tk.TclError:
            app._resize_data = None
        return

    app._resize_data = None
    if platform.system() == "Windows":
        start_native_window_drag(app.mini_window)
    else:
        app._drag_data["x"] = event.x
        app._drag_data["y"] = event.y


def mini_on_motion(app, event):
    """拖动或缩放。"""
    if app._resize_data:
        _do_resize(app, event)
        return
    if platform.system() == "Windows":
        return
    if app.mini_window:
        x = app.mini_window.winfo_x() + event.x - app._drag_data["x"]
        y = app.mini_window.winfo_y() + event.y - app._drag_data["y"]
        app.mini_window.geometry(f"+{x}+{y}")
        app._mini_pos = (x, y)


def _do_resize(app, event):
    data = app._resize_data
    win = app.mini_window
    if not data or not win:
        return
    min_w, min_h, max_w, max_h = app._mini_size_limits()
    dx = event.x_root - data["start_x"]
    dy = event.y_root - data["start_y"]
    edge = data["edge"]
    x, y = data["orig_x"], data["orig_y"]
    w, h = data["orig_w"], data["orig_h"]

    if "e" in edge:
        w = data["orig_w"] + dx
    if "s" in edge:
        h = data["orig_h"] + dy
    if "w" in edge:
        w = data["orig_w"] - dx
        x = data["orig_x"] + dx
    if "n" in edge:
        h = data["orig_h"] - dy
        y = data["orig_y"] + dy

    w = max(min_w, min(max_w, w))
    h = max(min_h, min(max_h, h))
    # 钳制后修正左/上边位置，避免窗口跳动
    if "w" in edge:
        x = data["orig_x"] + data["orig_w"] - w
    if "n" in edge:
        y = data["orig_y"] + data["orig_h"] - h

    try:
        win.geometry(f"{w}x{h}+{x}+{y}")
        apply_mini_content_scale(app, w, h)
    except tk.TclError:
        pass


def mini_on_release(app, event=None):
    """松手：保存位置与尺寸。"""
    if not app.mini_window:
        app._resize_data = None
        return
    was_resize = bool(app._resize_data)
    app._resize_data = None
    try:
        _capture_mini_geometry(app)
        app._save_config()
        if was_resize:
            apply_mini_content_scale(app, force=True)
    except Exception:
        logger.warning("结束 Mini 操作时保存几何失败", exc_info=True)
    if was_resize:
        try:
            app.mini_window.configure(cursor="")
        except tk.TclError:
            pass


def _capture_mini_geometry(app):
    """从当前 Mini 窗口读取位置与尺寸到 app 状态。"""
    if not app.mini_window:
        return
    geo = app.mini_window.geometry()
    pos = parse_mini_geometry(geo)
    if pos is not None:
        app._mini_pos = pos
    size = parse_mini_size(geo)
    if size is not None:
        min_w, min_h, max_w, max_h = app._mini_size_limits()
        normalized = normalize_mini_size(size, min_w, min_h, max_w, max_h)
        if normalized:
            app._mini_size = normalized


def reset_mini_size(app):
    """恢复平台默认 Mini 尺寸并重建窗口。"""
    app._mini_size = None
    if app.mini_window:
        # 销毁时勿把当前放大尺寸写回 _mini_size
        destroy_mini_window(app, capture_size=False)
        create_mini_window(app)
    app._save_config()


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
