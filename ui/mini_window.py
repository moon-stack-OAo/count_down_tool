# -*- coding: utf-8 -*-
"""Mini 桌面小组件：创建 / 拖动 / 缩放 / 透明与几何持久化。

设置（透明、字色、默认大小等）走托盘/菜单栏，Mini 本身无右键菜单。
"""

import logging
import platform
import tkinter as tk
from datetime import datetime

from app.timers import cancel_timer_attr
from core.countdown_core import (
    STATE_FINISHED,
    STATE_RUNNING,
    mini_content_scale,
    normalize_mini_size,
    parse_mini_geometry,
    parse_mini_size,
    should_update_mini_countdown,
)
from services.windows_native import MINI_WINDOW_TITLE, set_tool_window, start_native_window_drag

logger = logging.getLogger("count_down_tool")

# Windows -transparentcolor 专用色键：勿用 title_bar/字色，避免浅色主题或字色命中被抠
# （纯白在部分环境也会误抠，故用极暗稀有色）
_MINI_TRANSPARENT_KEY = "#010203"

# 几何保存 debounce（ms）：拖动/缩放过程中合并写盘
_GEO_SAVE_DEBOUNCE_MS = 400

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


def _apply_mac_chrome(mini):
    """macOS：去掉标题栏/系统边框，仍由 WM 管理以便 -topmost 可用。

    必须在窗口首次映射（显示）前调用；映射后改 style 无效。
    不要在此调用 update/update_idletasks，否则会提前 map 导致 style 失效。
    """
    path = mini._w
    # 1) Carbon/Cocoa 兼容：plain + none ≈ 无标题栏无控件
    # 2) 新 Tk stylemask：不带 titled 即无标题栏；noShadow 去阴影边
    # 3) 最后才 overrideredirect（可能影响 topmost，仅作兜底）
    attempts = (
        lambda: mini.tk.call(
            "::tk::unsupported::MacWindowStyle", "style", path, "plain", "none",
        ),
        lambda: mini.tk.call(
            "::tk::unsupported::MacWindowStyle", "style", path, "help", "none",
        ),
        lambda: mini.tk.call(
            "::tk::unsupported::MacWindowStyle",
            "style", path, "floating", "noTitleBar",
        ),
        lambda: mini.attributes("-stylemask", "utility"),
        lambda: mini.attributes("-stylemask", ""),
        lambda: mini.overrideredirect(True),
    )
    for apply in attempts:
        try:
            apply()
            return True
        except tk.TclError:
            continue
    logger.debug("mac Mini chrome 全部失败", exc_info=True)
    return False


def _apply_mini_borderless(mini, system):
    """无边框 + 常驻置顶。"""
    try:
        if system == "Darwin":
            _apply_mac_chrome(mini)
        else:
            mini.overrideredirect(True)
    except tk.TclError:
        try:
            mini.overrideredirect(True)
        except tk.TclError:
            pass
    _ensure_mini_topmost(mini)


def _ensure_mini_topmost(mini):
    """强制 Mini 保持最前（mac 焦点丢失后 topmost 常被清掉）。"""
    if mini is None:
        return
    try:
        if not mini.winfo_exists():
            return
        mini.attributes("-topmost", True)
        mini.lift()
    except tk.TclError:
        pass


def create_mini_window(app):
    """创建 Mini 窗口并挂到 app 上。"""
    if app.mini_window:
        return

    mini = tk.Toplevel(app.master)
    # Mini 无边框小组件；设置可枚举标题供二次启动 bring_to_front（视觉仍无标题栏）
    mini.title(MINI_WINDOW_TITLE)
    system = platform.system()
    # mac：先隐藏，在首次 map 前设 MacWindowStyle，否则系统边框去不掉
    if system == "Darwin":
        try:
            mini.withdraw()
        except tk.TclError:
            pass
    _apply_mini_borderless(mini, system)
    # macOS 透明：-transparent + systemTransparent（底板透明、文字不透明、去阴影）
    # Windows 透明：-transparentcolor 专用稀有色键（勿用 title_bar，避免与字色/浅色主题冲突）
    if app._transparent_mode and system == "Darwin":
        bg = "systemTransparent"
    elif app._transparent_mode and system == "Windows":
        bg = _MINI_TRANSPARENT_KEY
    else:
        bg = app.COLORS["title_bar"]
    mini.configure(bg=bg)
    if app._transparent_mode:
        if system == "Windows":
            mini.attributes("-transparentcolor", _MINI_TRANSPARENT_KEY)
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
            if system == "Windows":
                # 显式清色键，避免个别环境下重建后仍抠色
                mini.attributes("-transparentcolor", "")
            elif system == "Darwin":
                mini.attributes("-transparent", False)
            mini.attributes("-alpha", 1.0)
        except tk.TclError:
            pass
    # 透明属性变更后 mac 上可能丢 topmost，再设一次
    _ensure_mini_topmost(mini)

    win_w, win_h = app.resolved_mini_size()
    min_w, min_h, max_w, max_h = app._mini_size_limits()
    screen_w = mini.winfo_screenwidth()
    screen_h = mini.winfo_screenheight()

    if app._mini_pos:
        x, y = int(app._mini_pos[0]), int(app._mini_pos[1])
    else:
        x = screen_w - win_w - app.MINI_MARGIN_RIGHT
        y = screen_h - win_h - app.MINI_MARGIN_BOTTOM
    # overrideredirect / 透明色键后，单次 geometry 常被忽略并落到 0,0
    _place_mini(mini, win_w, win_h, x, y)
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
        bg=bg, fg=app.mini_text_fg("clock"),
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
        bg=bg, fg=app.mini_text_fg("countdown_running"),
    )
    app.mini_countdown_label.pack(side=tk.LEFT, expand=True)

    btn_frame = tk.Frame(content_frame, bg=bg)
    btn_frame.pack(side=tk.RIGHT)

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
    app.mini_menu_btn = None
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

    # Mini 快捷键（需焦点在 Mini 上）；设置项请用托盘菜单
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

    # 布局后再强制尺寸/位置：overrideredirect 与透明属性后系统常重置到 0,0
    def _force_mini_place(event=None, w=win_w, h=win_h, px=x, py=y, win=mini):
        try:
            if not win.winfo_exists():
                return
            _place_mini(win, w, h, px, py)
        except tk.TclError:
            pass

    def _on_map(_event=None, win=mini):
        # style 只能在首次 map 前生效，此处只保 topmost；并再钉一次位置
        _ensure_mini_topmost(win)
        _force_mini_place()

    if system == "Darwin":
        mini.bind("<Map>", _on_map)
        try:
            mini.deiconify()
        except tk.TclError:
            pass
        mini.after_idle(_force_mini_place)
        mini.after(50, _force_mini_place)
        mini.after(200, _force_mini_place)
        mini.after_idle(lambda w=mini: _ensure_mini_topmost(w))
        mini.after(50, lambda w=mini: _ensure_mini_topmost(w))
        mini.after(200, lambda w=mini: _ensure_mini_topmost(w))
        # 周期性保活：切换其它 App 后仍保持浮层（id 登记到 app，销毁时统一 cancel）
        def _keep_topmost(win=mini, app_ref=app):
            try:
                if getattr(app_ref, "mini_window", None) is not win:
                    cancel_timer_attr(app_ref, "_mini_topmost_timer_id", widget=win)
                    return
                if not win.winfo_exists():
                    cancel_timer_attr(app_ref, "_mini_topmost_timer_id", widget=win)
                    return
                _ensure_mini_topmost(win)
                app_ref._mini_topmost_timer_id = win.after(1500, _keep_topmost)
            except tk.TclError:
                try:
                    app_ref._mini_topmost_timer_id = None
                except (AttributeError, TypeError):
                    pass

        try:
            app._mini_topmost_timer_id = mini.after(1500, _keep_topmost)
        except tk.TclError:
            app._mini_topmost_timer_id = None
    else:
        try:
            mini.lift()
            mini.focus_force()
        except tk.TclError:
            pass
        _ensure_mini_topmost(mini)
        # Windows：透明色键/无边框后位置常丢，idle 与短延迟再钉
        mini.after_idle(_force_mini_place)
        mini.after(50, _force_mini_place)
        mini.after(200, _force_mini_place)

    sync_mini_state(app)


def destroy_mini_window(app, capture_size=True):
    """销毁 Mini 并保存位置（默认也保存尺寸）。

    capture_size=False：仅保存位置，不覆盖 _mini_size（用于「恢复默认大小」）。
    """
    if app.mini_window:
        # 取消 debounce / mac topmost 保活，避免销毁后幽灵回调
        mini_win = app.mini_window
        cancel_timer_attr(app, "_mini_geo_save_id")
        cancel_timer_attr(app, "_mini_topmost_timer_id", widget=mini_win)
        try:
            if capture_size:
                _capture_mini_geometry(app)
            else:
                _remember_mini_pos(app)
            app._save_config()
        except (OSError, tk.TclError, AttributeError, TypeError, ValueError):
            logger.warning("保存 Mini 窗口几何失败", exc_info=True)
        try:
            mini_win.destroy()
        except tk.TclError:
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
        app._mini_press = None
        # 重建后需强制同步
        app._mini_sync_cache = None
        app._mini_clock_hm = None


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
    base_btn = 16 if system == "Darwin" else 10

    def _sz(base, floor=7):
        return max(floor, int(round(base * scale)))

    pad_x = _sz(base_pad_x, 2)
    pad_y = _sz(base_pad_y, 2)
    gap = _sz(base_gap, 2)
    time_sz = _sz(app.FONTS["mini_time"][1], 8)
    count_sz = _sz(app.FONTS["mini_countdown"][1], 10)
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
        if getattr(app, "mini_expand_btn", None):
            app.mini_expand_btn.config(font=app._font("label", btn_sz))
            app.mini_expand_btn.pack_configure(padx=(0, gap))
        if getattr(app, "mini_close_btn", None):
            app.mini_close_btn.config(font=app._font("label", btn_sz, bold=True))
    except tk.TclError:
        pass


def recreate_mini_window(app):
    """重建 mini 窗口（切换透明模式时）。"""
    # 先钉住当前位置，避免 destroy 时 geometry 读成 +0+0
    _remember_mini_pos(app)
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
    # 记录按下点，松手时用于区分「单击倒计时区」与拖动
    try:
        app._mini_press = {
            "x_root": int(getattr(event, "x_root", 0) or 0),
            "y_root": int(getattr(event, "y_root", 0) or 0),
            "widget": getattr(event, "widget", None),
        }
    except (TypeError, ValueError, AttributeError):
        app._mini_press = None
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
        _schedule_save_mini_geometry(app)


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


def _schedule_save_mini_geometry(app):
    """debounce 写入 Mini 几何到配置，避免拖动过程中频繁 _save_config。"""
    cancel_timer_attr(app, "_mini_geo_save_id")

    def _flush():
        app._mini_geo_save_id = None
        try:
            _capture_mini_geometry(app)
            app._save_config()
        except (OSError, tk.TclError, AttributeError, TypeError, ValueError):
            logger.warning("debounce 保存 Mini 几何失败", exc_info=True)

    try:
        master = app.master
        app._mini_geo_save_id = master.after(_GEO_SAVE_DEBOUNCE_MS, _flush)
    except tk.TclError:
        _flush()


def mini_on_release(app, event=None):
    """松手：捕获几何并 debounce 写盘；倒计时区单击则 toggle。"""
    if not app.mini_window:
        app._resize_data = None
        app._mini_press = None
        return
    was_resize = bool(app._resize_data)
    app._resize_data = None
    press = getattr(app, "_mini_press", None)
    app._mini_press = None
    # 倒计时区单击（移动 < 6px）：开始/暂停/继续
    if (
        not was_resize
        and press is not None
        and event is not None
        and getattr(app, "mini_countdown_label", None) is not None
    ):
        try:
            dx = abs(int(event.x_root) - int(press.get("x_root", 0)))
            dy = abs(int(event.y_root) - int(press.get("y_root", 0)))
            widget = press.get("widget")
            if dx <= 5 and dy <= 5 and widget is app.mini_countdown_label:
                if hasattr(app, "toggle_countdown"):
                    app.toggle_countdown()
                try:
                    from services.tray import refresh_tray_menu

                    refresh_tray_menu(app)
                except (ImportError, AttributeError, RuntimeError, tk.TclError):
                    pass
        except (TypeError, ValueError, AttributeError, tk.TclError):
            logger.debug("Mini 单击 toggle 失败", exc_info=True)
    try:
        _capture_mini_geometry(app)
        _schedule_save_mini_geometry(app)
        if was_resize:
            apply_mini_content_scale(app, force=True)
    except (OSError, tk.TclError, AttributeError, TypeError, ValueError):
        logger.warning("结束 Mini 操作时保存几何失败", exc_info=True)
    if was_resize:
        try:
            app.mini_window.configure(cursor="")
        except tk.TclError:
            pass


def _place_mini(win, w, h, x, y):
    """设置 Mini 尺寸与位置（geometry 字符串兼容负坐标）。"""
    try:
        win.geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")
    except tk.TclError:
        pass


def _remember_mini_pos(app):
    """用 winfo 优先记住位置；geometry 回退。忽略明显错误的 1x1@0,0 瞬态值。"""
    win = getattr(app, "mini_window", None)
    if not win:
        return
    try:
        if not win.winfo_exists():
            return
        try:
            win.update_idletasks()
        except tk.TclError:
            pass
        x, y = int(win.winfo_x()), int(win.winfo_y())
        ww, wh = int(win.winfo_width()), int(win.winfo_height())
        # 未映射/瞬态：winfo 常为 1x1 +0+0，勿覆盖已有位置
        if (x, y) == (0, 0) and ww <= 1 and wh <= 1 and app._mini_pos:
            return
        if ww > 1 and wh > 1:
            app._mini_pos = (x, y)
            return
        geo = win.geometry()
        pos = parse_mini_geometry(geo)
        if pos is not None and pos != (0, 0):
            app._mini_pos = pos
        elif pos is not None and not app._mini_pos:
            app._mini_pos = pos
    except tk.TclError:
        pass


def _capture_mini_geometry(app):
    """从当前 Mini 窗口读取位置与尺寸到 app 状态。"""
    if not app.mini_window:
        return
    _remember_mini_pos(app)
    try:
        geo = app.mini_window.geometry()
    except tk.TclError:
        return
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


def reset_mini_layout(app):
    """恢复默认 Mini 尺寸与位置；当前为 Mini 时立即生效。"""
    app._mini_size = None
    app._mini_pos = None
    if app.mini_window:
        destroy_mini_window(app, capture_size=False)
        # destroy 在 capture_size=False 时仍可能记住位置
        app._mini_pos = None
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
            import platform

            if platform.system() == "Darwin":
                tip = (
                    "程序已隐藏到后台。\n"
                    "可通过菜单栏「设置」、Dock 图标或再次打开应用恢复窗口。"
                )
            else:
                tip = (
                    "程序已最小化到系统托盘。\n"
                    "右键托盘图标可切换 Mini 模式或退出。"
                )

            def _tip():
                from ui.app_dialogs import show_info

                show_info(app, tip, title="提示")

            app.master.after(0, _tip)
    else:
        app._switch_to_full()


def _countdown_color_role(state: str) -> str:
    """状态 → Mini 倒计时字色角色。"""
    if state == STATE_RUNNING:
        return "countdown_running"
    if state == STATE_FINISHED:
        return "countdown_finished"
    return "countdown_paused"


def sync_mini_state(app):
    """同步 mini 窗口的状态显示（变更检测，避免每秒无意义 configure）。"""
    if not app.mini_window:
        return

    text = app.countdown_text
    state = app._state
    role = _countdown_color_role(state)
    try:
        countdown_fg = app.mini_text_fg(role)
        clock_fg = app.mini_text_fg("clock")
    except (AttributeError, TypeError, KeyError, tk.TclError):
        countdown_fg = None
        clock_fg = None

    # 缓存：(text, state, countdown_fg, clock_fg)；纯函数只比 (text, state)
    prev_full = getattr(app, "_mini_sync_cache", None)
    prev_ts = None
    if isinstance(prev_full, tuple) and len(prev_full) >= 2:
        prev_ts = (prev_full[0], prev_full[1])

    need_countdown = should_update_mini_countdown(prev_ts, text, state)
    # 同 state 下改字色（设置页）也需刷新
    if (
        not need_countdown
        and prev_full is not None
        and len(prev_full) >= 3
        and prev_full[2] != countdown_fg
    ):
        need_countdown = True
    need_clock_fg = (
        prev_full is None
        or len(prev_full) < 4
        or prev_full[3] != clock_fg
    )

    if need_countdown and app.mini_countdown_label:
        try:
            app.mini_countdown_label.config(text=text, fg=countdown_fg)
        except tk.TclError:
            pass

    if need_clock_fg and getattr(app, "mini_time_label", None):
        try:
            app.mini_time_label.config(fg=clock_fg)
        except tk.TclError:
            pass

    if need_countdown or need_clock_fg:
        app._mini_sync_cache = (text, state, countdown_fg, clock_fg)
