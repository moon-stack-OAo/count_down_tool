# -*- coding: utf-8 -*-
"""
倒计时工具 (Count Down Tool) - 现代化深色主题版
支持完整模式和 Mini 桌面小组件模式
依赖：pystray, pillow
安装：pip install pystray pillow
"""

import atexit
import logging
import os
import platform
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

from countdown_core import (
    ACTION_FINISH,
    ACTION_PAUSE,
    ACTION_RESET,
    ACTION_RESTART,
    ACTION_RESUME,
    ACTION_START,
    ACTION_START_FAIL,
    APP_NAME,
    APP_NAME_EN,
    STATE_FINISHED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RUNNING,
    button_text_for_state,
    format_remaining,
    format_target_label,
    load_config_dict,
    merge_config,
    merge_mini_position,
    next_second_delay_ms,
    next_state,
    parse_mini_geometry,
    resource_path,
    save_config_dict,
    target_from_duration,
    target_from_hms,
    try_acquire_weak_lock,
    user_config_dir,
    user_config_path,
    validate_hms,
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("count_down_tool")

try:
    import pystray

    _HAS_PYSTRAY = True
except ImportError:
    _HAS_PYSTRAY = False

# 单实例锁句柄（进程级）
_instance_lock = None


def _bring_existing_to_front():
    """已有实例时尝试置前（Windows）；失败静默。"""
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value or ""
            if APP_NAME in title or APP_NAME_EN in title:
                found.append(hwnd)
            return True

        user32.EnumWindows(_enum, 0)
        if not found:
            return False
        hwnd = found[0]
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        logger.debug("置前已有实例失败", exc_info=True)
        return False


def _acquire_single_instance():
    """
    单实例保护。成功返回 (True, handle)；已有实例返回 (False, None)；
    锁机制异常时返回 (True, None) 并继续启动。
    """
    global _instance_lock
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            kernel32.CreateMutexW.argtypes = [
                wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR
            ]
            kernel32.CreateMutexW.restype = wintypes.HANDLE
            kernel32.GetLastError.restype = wintypes.DWORD

            mutex = kernel32.CreateMutexW(None, False, "Local\\CountDownTool_SingleInstance")
            if not mutex:
                logger.warning("CreateMutexW 失败，跳过单实例检查")
                return True, None
            ERROR_ALREADY_EXISTS = 183
            if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
                kernel32.CloseHandle(mutex)
                return False, None
            _instance_lock = mutex
            atexit.register(lambda: kernel32.CloseHandle(mutex) if mutex else None)
            return True, mutex

        lock_path = os.path.join(user_config_dir(), "count_down_tool.lock")
        lock_fp = None
        use_fcntl = False
        try:
            import fcntl  # noqa: F401
            use_fcntl = True
        except ImportError:
            use_fcntl = False

        if use_fcntl:
            lock_fp = open(lock_path, "a+", encoding="utf-8")
            try:
                import fcntl
                fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # 写入 PID 便于排查
                try:
                    lock_fp.seek(0)
                    lock_fp.truncate()
                    lock_fp.write(str(os.getpid()))
                    lock_fp.flush()
                except Exception:
                    pass
            except (BlockingIOError, OSError):
                lock_fp.close()
                return False, None

            def _release_fcntl():
                try:
                    try:
                        import fcntl
                        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
                    except Exception:
                        pass
                    lock_fp.close()
                    try:
                        os.remove(lock_path)
                    except OSError:
                        pass
                except Exception:
                    logger.debug("释放锁文件失败", exc_info=True)

            _instance_lock = lock_fp
            atexit.register(_release_fcntl)
            return True, lock_fp

        # 弱锁：PID 检测，避免异常退出残留锁
        if not try_acquire_weak_lock(lock_path):
            return False, None

        def _release_weak():
            try:
                os.remove(lock_path)
            except OSError:
                pass

        _instance_lock = lock_path
        atexit.register(_release_weak)
        return True, lock_path
    except Exception:
        logger.exception("单实例锁异常，继续启动")
        return True, None


_ICON_PATH = resource_path("count_down_tool.ico")


class RoundedFrame(tk.Canvas):
    """毛玻璃风格卡片容器"""

    def __init__(self, parent, bg_color="#1A1F35", border_color="#2A3050",
                 corner_radius=16, **kwargs):
        super().__init__(parent, highlightthickness=0, bg=parent["bg"], **kwargs)
        self._bg_color = bg_color
        self._border_color = border_color
        self._radius = corner_radius
        self.bind("<Configure>", self._draw)

    def _draw(self, event=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w > 1 and h > 1:
            self._draw_rounded_rect(0, 0, w, h, self._radius,
                                    self._bg_color, self._border_color)

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


class CountdownApp:
    WINDOW_WIDTH = 560
    WINDOW_HEIGHT = 610
    MINI_WIDTH = 220
    MINI_HEIGHT = 48
    TITLE_DRAG_EXCLUDE_RIGHT = 440
    PICKER_WIDTH = 320
    PICKER_HEIGHT = 240
    CORNER_RADIUS = 20
    MINI_MARGIN_RIGHT = 20
    MINI_MARGIN_BOTTOM = 60

    COLORS = {
        "bg": "#0B0E1A",
        "card": "#1A1F35",
        "card_border": "#2A3050",
        "glass": "#1C2240",
        "accent": "#8B5CF6",
        "accent_hover": "#7C3AED",
        "accent_glow": "#A78BFA",
        "success": "#34D399",
        "error": "#F87171",
        "text": "#F1F5F9",
        "text_dim": "#94A3B8",
        "input_bg": "#151929",
        "border": "#2D3555",
        "title_bar": "#0D1220",
        "btn_default": "#334155",
        "btn_hover_min": "#F59E0B",
        "btn_hover_close": "#EF4444",
        "white": "#FFFFFF",
    }

    def __init__(self, master):
        self.master = master
        self.master.title(APP_NAME)
        self.master.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        self.master.resizable(False, False)
        self.master.configure(bg=self.COLORS["bg"])
        # macOS 不支持 overrideredirect，会导致窗口无法显示
        if platform.system() != "Darwin":
            self.master.overrideredirect(True)

        self._set_icon()

        # 窗口拖动相关变量
        self._drag_x = 0
        self._drag_y = 0

        self.running = False
        self._state = STATE_IDLE
        self._countdown_timer_id = None
        self.btn_start = None
        self.tray_icon = None
        self._first_hide = True
        self._error_timer_id = None
        self._preset_duration = None
        self._applying_preset = False

        # 报警相关
        self._alarm_count = 0
        self._alarm_timer_id = None
        self._bell_count = 0

        self.FONTS = self._get_fonts()

        # Mini 模式相关
        self._is_mini = False
        self.mini_window = None
        self.mini_countdown_label = None
        self.mini_time_label = None
        self._transparent_mode = False
        self._last_mode = "full"
        self._drag_data = {"x": 0, "y": 0}

        # 倒计时状态（完整和 mini 共享）
        self.target_time = None
        self.countdown_text = "--:--:--"

        self._mini_pos = None  # 保存 Mini 窗口位置
        self._config_file = user_config_path()
        self._load_config()

        self._setup_styles()
        self._setup_ui()
        self._on_time_changed()
        self.update_clock()
        self._init_tray_icon()
        self._center_window()
        self._set_window_rounded_corners()
        self._set_taskbar_visible()
        # 启动模式：last_mode=mini 进 Mini；无配置时非 Darwin 保持旧行为进 Mini
        if platform.system() != "Darwin":
            has_last = "last_mode" in getattr(self, "_loaded_keys", set())
            if (has_last and self._last_mode == "mini") or (not has_last):
                self._switch_to_mini()

    @staticmethod
    def _get_fonts():
        system = platform.system()
        if system == "Windows":
            return {
                "title": ("Segoe UI", 20, "bold"),
                "time": ("Consolas", 32, "bold"),
                "countdown": ("Consolas", 42, "bold"),
                "label": ("Segoe UI", 11),
                "button": ("Segoe UI", 12, "bold"),
                "mini_time": ("Consolas", 10, "bold"),
                "mini_countdown": ("Consolas", 16, "bold"),
            }
        elif system == "Darwin":
            return {
                "title": ("Helvetica Neue", 20, "bold"),
                "time": ("Menlo", 32, "bold"),
                "countdown": ("Menlo", 42, "bold"),
                "label": ("Helvetica Neue", 11),
                "button": ("Helvetica Neue", 12, "bold"),
                "mini_time": ("Menlo", 10, "bold"),
                "mini_countdown": ("Menlo", 16, "bold"),
            }
        else:
            return {
                "title": ("Ubuntu", 20, "bold"),
                "time": ("Monospace", 32, "bold"),
                "countdown": ("Monospace", 42, "bold"),
                "label": ("Ubuntu", 11),
                "button": ("Ubuntu", 12, "bold"),
                "mini_time": ("Monospace", 10, "bold"),
                "mini_countdown": ("Monospace", 16, "bold"),
            }

    def _font(self, key, size=None, bold=None):
        """基于 FONTS 派生字体，保证跨平台一致"""
        base = self.FONTS[key]
        family = base[0]
        fsize = size if size is not None else base[1]
        weight = "bold" if bold is True else (base[2] if bold is None and len(base) > 2 else None)
        if weight:
            return (family, fsize, weight)
        return (family, fsize)

    def _load_config(self):
        self._loaded_keys = set()
        try:
            config = load_config_dict(self._config_file)
            self._loaded_keys = set(config.keys())
            self._mini_pos = config.get("mini_position")
            if "transparent_mode" in config:
                self._transparent_mode = bool(config.get("transparent_mode"))
            lm = config.get("last_mode")
            if lm in ("full", "mini"):
                self._last_mode = lm
        except Exception:
            logger.exception("读取配置失败")
            self._mini_pos = None

    def _save_config(self):
        try:
            config = load_config_dict(self._config_file)
            config = merge_mini_position(config, self._mini_pos)
            mode = "mini" if self._is_mini else "full"
            config = merge_config(
                config,
                transparent_mode=bool(self._transparent_mode),
                last_mode=mode,
            )
            save_config_dict(self._config_file, config)
        except Exception:
            logger.exception("保存配置失败")

    def _set_state(self, action: str) -> str:
        """按动作推进状态机，并同步按钮文案与 running 标志。"""
        self._state = next_state(action, self._state)
        self.running = self._state == STATE_RUNNING
        if self.btn_start:
            self.btn_start.config(text=button_text_for_state(self._state))
        return self._state

    def _set_icon(self):
        try:
            if os.path.exists(_ICON_PATH):
                self.master.iconbitmap(_ICON_PATH)
        except Exception:
            logger.warning("设置窗口图标失败", exc_info=True)

    def _start_drag(self, event):
        """开始拖动窗口"""
        if event.x > self.TITLE_DRAG_EXCLUDE_RIGHT:
            return
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        """拖动窗口"""
        x = self.master.winfo_x() + (event.x - self._drag_x)
        y = self.master.winfo_y() + (event.y - self._drag_y)
        self.master.geometry(f"+{x}+{y}")

    def _center_window(self):
        """窗口居中显示"""
        self.master.update_idletasks()
        width = self.master.winfo_width()
        height = self.master.winfo_height()
        screen_w = self.master.winfo_screenwidth()
        screen_h = self.master.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.master.geometry(f"{width}x{height}+{x}+{y}")

    def _set_window_rounded_corners(self):
        """设置窗口圆角（使用 DWM 系统级圆角）"""
        if platform.system() != "Windows":
            return
        try:
            import ctypes
            from ctypes import c_int, byref

            hwnd = int(self.master.frame(), 16)
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2

            dwm = ctypes.windll.dwmapi
            preference = c_int(DWMWCP_ROUND)
            result = dwm.DwmSetWindowAttribute(
                hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                byref(preference), ctypes.sizeof(preference),
            )
            if result != 0:
                self._set_window_rounded_corners_fallback()
        except Exception:
            logger.warning("DWM 圆角设置失败，尝试回退方案", exc_info=True)
            self._set_window_rounded_corners_fallback()

    def _set_window_rounded_corners_fallback(self):
        """回退方案：GDI 圆角"""
        if platform.system() != "Windows":
            return
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = int(self.master.frame(), 16)
            radius = self.CORNER_RADIUS
            width = self.master.winfo_width()
            height = self.master.winfo_height()

            create_round_rect_rgn = ctypes.windll.gdi32.CreateRoundRectRgn
            create_round_rect_rgn.argtypes = [
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int
            ]
            create_round_rect_rgn.restype = wintypes.HRGN

            rgn = create_round_rect_rgn(0, 0, width, height, radius * 2, radius * 2)

            set_window_rgn = ctypes.windll.user32.SetWindowRgn
            set_window_rgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
            set_window_rgn.restype = ctypes.c_int
            set_window_rgn(hwnd, rgn, True)
        except Exception:
            logger.warning("GDI 圆角设置失败", exc_info=True)

    def _set_taskbar_visible(self):
        """设置窗口在任务栏和 Alt+Tab 中可见"""
        # macOS 不需要此设置
        if platform.system() != "Windows":
            return
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = int(self.master.frame(), 16)
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080

            get_window_long = ctypes.windll.user32.GetWindowLongW
            set_window_long = ctypes.windll.user32.SetWindowLongW
            get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
            get_window_long.restype = ctypes.c_long
            set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
            set_window_long.restype = ctypes.c_long

            style = get_window_long(hwnd, GWL_EXSTYLE)
            style = style & ~WS_EX_TOOLWINDOW
            style = style | WS_EX_APPWINDOW
            set_window_long(hwnd, GWL_EXSTYLE, style)
        except Exception:
            logger.warning("任务栏可见性设置失败", exc_info=True)

    def _init_circle_button(self, canvas, cx, cy, r, fill="#64748B", outline="", text="", text_color="#F1F5F9",
                            font_size=10):
        oval_id = canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline=outline, width=0)
        text_id = None
        if text:
            text_id = canvas.create_text(cx, cy, text=text, fill=text_color, font=(self.FONTS["label"][0], font_size))
        return (oval_id, text_id)

    def _update_circle_button(self, canvas, item_ids, fill=None, text=None, text_color=None):
        oval_id, text_id = item_ids
        if fill is not None:
            canvas.itemconfig(oval_id, fill=fill)
        if text_id is not None:
            if text_color is not None:
                canvas.itemconfig(text_id, fill=text_color)
            if text is not None:
                canvas.itemconfig(text_id, text=text)

    # ------------------------------------------------------------------
    # 系统托盘
    # ------------------------------------------------------------------

    def _init_tray_icon(self):
        if not _HAS_PYSTRAY:
            return
        try:
            image = self._load_tray_icon()
            menu = pystray.Menu(
                pystray.MenuItem("显示主窗口", self._tray_show_window, default=True),
                pystray.MenuItem("选择时间", self._tray_show_time_picker),
                pystray.MenuItem(lambda _: button_text_for_state(self._state), self._tray_toggle_countdown),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Mini 模式", self._tray_toggle_mini),
                pystray.MenuItem("透明模式", self._tray_toggle_transparent,
                                 checked=lambda _: self._transparent_mode),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self._tray_quit),
            )
            self.tray_icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception:
            logger.exception("托盘图标创建失败")
            self.tray_icon = None

    def _load_tray_icon(self):
        from PIL import Image
        if os.path.exists(_ICON_PATH):
            return Image.open(_ICON_PATH)
        return self._create_fallback_icon()

    @staticmethod
    def _create_fallback_icon():
        from PIL import Image, ImageDraw
        size = 64
        purple = (124, 58, 237)
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([4, 4, size - 4, size - 4], fill=purple)
        draw.ellipse([10, 10, size - 10, size - 10], fill="white")
        center = size // 2
        draw.line([(center, center), (center, 18)], fill=purple, width=3)
        draw.line([(center, center), (size - 18, center)], fill=purple, width=3)
        draw.ellipse([center - 3, center - 3, center + 3, center + 3], fill=purple)
        return image

    def _tray_show_window(self, icon=None, item=None):
        self.master.after(0, self._show_full_mode)

    def _tray_show_time_picker(self, icon=None, item=None):
        self.master.after(0, self._show_time_picker)

    def _tray_toggle_countdown(self, icon=None, item=None):
        self.master.after(0, self.toggle_countdown)

    def _tray_toggle_mini(self, icon=None, item=None):
        self.master.after(0, self._toggle_mini_mode)

    def _tray_toggle_transparent(self, icon=None, item=None):
        def _do():
            self._toggle_transparent_mode()

        self.master.after(0, _do)

    def _toggle_transparent_mode(self):
        self._transparent_mode = not self._transparent_mode
        self._save_config()
        if self._is_mini:
            self._recreate_mini_window()

    def _tray_quit(self, icon=None, item=None):
        self.master.after(0, self._quit_app)

    def _show_full_mode(self):
        """显示完整模式窗口"""
        if self._is_mini:
            self._switch_to_full()
        self.master.deiconify()
        self.master.lift()
        self.master.focus_force()

    def _has_tray(self):
        return bool(_HAS_PYSTRAY and self.tray_icon)

    def _hide_to_tray(self):
        if not self._has_tray():
            self._quit_app()
            return
        if self._first_hide:
            self._first_hide = False
            self.master.after(0, lambda: messagebox.showinfo(
                "提示",
                "程序已最小化到系统托盘。\n"
                "右键托盘图标可切换 Mini 模式或退出。",
                parent=self.master,
            ))
        self.master.withdraw()

    def _quit_app(self):
        self._save_config()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                logger.warning("停止托盘图标失败", exc_info=True)
        self._destroy_mini_window()
        self.master.destroy()

    # ------------------------------------------------------------------
    # Mini 模式
    # ------------------------------------------------------------------

    def _toggle_mini_mode(self):
        if self._is_mini:
            self._switch_to_full()
        else:
            self._switch_to_mini()

    def _switch_to_mini(self):
        """切换到 Mini 模式"""
        self._is_mini = True
        self._last_mode = "mini"
        self.master.update()
        self.master.withdraw()
        self._create_mini_window()
        self._save_config()

    def _switch_to_full(self):
        """切换到完整模式"""
        self._is_mini = False
        self._last_mode = "full"
        self._destroy_mini_window()
        self.master.deiconify()
        self.master.lift()
        self._save_config()

    def _create_mini_window(self):
        """创建 Mini 桌面小组件 - 毛玻璃风格"""
        if self.mini_window:
            return

        mini = tk.Toplevel(self.master)
        mini.title("")
        mini.overrideredirect(True)  # 无边框
        mini.attributes("-topmost", True)  # 置顶
        mini.configure(bg=self.COLORS["title_bar"])
        if platform.system() == "Windows":
            if self._transparent_mode:
                mini.attributes("-transparentcolor", self.COLORS["title_bar"])
            # 否则不设透明度，完全不透明，WM_NCHITTEST 原生拖拽

        # 设置窗口大小和位置（屏幕右下角）
        win_w, win_h = self.MINI_WIDTH, self.MINI_HEIGHT
        screen_w = mini.winfo_screenwidth()
        screen_h = mini.winfo_screenheight()

        if self._mini_pos:
            x, y = self._mini_pos
        else:
            x = screen_w - win_w - self.MINI_MARGIN_RIGHT
            y = screen_h - win_h - self.MINI_MARGIN_BOTTOM
        mini.geometry(f"{win_w}x{win_h}+{x}+{y}")

        # 毛玻璃边框（透明模式下去除边框）
        if self._transparent_mode:
            mini.configure(highlightthickness=0)
        else:
            mini.configure(highlightthickness=2, highlightbackground=self.COLORS["accent"])

        # 主容器
        main_frame = tk.Frame(mini, bg=self.COLORS["title_bar"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # 单行布局：时间 + 倒计时 + 按钮
        content_frame = tk.Frame(main_frame, bg=self.COLORS["title_bar"])
        content_frame.pack(fill=tk.BOTH, expand=True)

        # 当前时间
        self.mini_time_label = tk.Label(
            content_frame, text=datetime.now().strftime("%H:%M"),
            font=self.FONTS["mini_time"],
            bg=self.COLORS["title_bar"], fg=self.COLORS["text_dim"],
        )
        self.mini_time_label.pack(side=tk.LEFT)

        # 分隔符
        tk.Label(
            content_frame, text="│",
            font=self.FONTS["mini_time"],
            bg=self.COLORS["title_bar"], fg=self.COLORS["border"],
        ).pack(side=tk.LEFT, padx=4)

        # 倒计时显示
        self.mini_countdown_label = tk.Label(
            content_frame, text=self.countdown_text,
            font=self.FONTS["mini_countdown"],
            bg=self.COLORS["title_bar"], fg=self.COLORS["white"],
        )
        self.mini_countdown_label.pack(side=tk.LEFT, expand=True)

        # 按钮容器
        btn_frame = tk.Frame(content_frame, bg=self.COLORS["title_bar"])
        btn_frame.pack(side=tk.RIGHT, padx=(4, 0))

        # 展开按钮
        expand_btn = tk.Label(
            btn_frame, text="↗", font=self._font("label", 10),
            bg=self.COLORS["title_bar"], fg=self.COLORS["accent_glow"], cursor="hand2",
        )
        expand_btn.pack(side=tk.LEFT, padx=(0, 4))
        expand_btn.bind("<Button-1>", lambda e: self._switch_to_full())

        # 关闭按钮
        close_btn = tk.Label(
            btn_frame, text="×", font=self._font("label", 10, bold=True),
            bg=self.COLORS["title_bar"], fg=self.COLORS["text_dim"], cursor="hand2",
        )
        close_btn.pack(side=tk.LEFT)
        close_btn.bind("<Button-1>", lambda e: self._mini_close())
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg=self.COLORS["btn_hover_close"]))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=self.COLORS["text_dim"]))

        # 拖拽（含透明模式）
        drag_widgets = (mini, main_frame, content_frame,
                        self.mini_time_label, self.mini_countdown_label)
        if platform.system() == "Windows":
            for w in drag_widgets:
                w.bind("<Button-1>", self._mini_start_drag)
                w.bind("<ButtonRelease-1>", self._mini_end_drag)
        else:
            for widget in drag_widgets:
                widget.bind("<Button-1>", self._mini_start_drag)
                widget.bind("<B1-Motion>", self._mini_do_drag)
                widget.bind("<ButtonRelease-1>", self._mini_end_drag)

        # 右键菜单
        for w in drag_widgets:
            w.bind("<Button-3>", self._show_mini_context_menu)
            if platform.system() == "Darwin":
                w.bind("<Control-Button-1>", self._show_mini_context_menu)

        self.mini_window = mini

        # 同步当前状态
        self._sync_mini_state()

    def _show_mini_context_menu(self, event):
        """Mini 右键菜单。"""
        menu = tk.Menu(self.mini_window or self.master, tearoff=0,
                       bg=self.COLORS["card"], fg=self.COLORS["text"],
                       activebackground=self.COLORS["accent"],
                       activeforeground=self.COLORS["white"])
        menu.add_command(label="展开完整模式", command=self._switch_to_full)
        if platform.system() == "Windows":
            menu.add_command(
                label="关闭透明模式" if self._transparent_mode else "开启透明模式",
                command=self._toggle_transparent_mode,
            )
        menu.add_separator()
        if self._has_tray():
            menu.add_command(label="隐藏到托盘", command=self._mini_close)
        else:
            menu.add_command(label="关闭", command=self._mini_close)
        menu.add_command(label="退出", command=self._quit_app)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _destroy_mini_window(self):
        if self.mini_window:
            try:
                pos = parse_mini_geometry(self.mini_window.geometry())
                if pos is not None:
                    self._mini_pos = pos
                    self._save_config()
            except Exception:
                logger.warning("保存 Mini 窗口位置失败", exc_info=True)
            try:
                self.mini_window.destroy()
            except Exception:
                logger.warning("销毁 Mini 窗口失败", exc_info=True)
            self.mini_window = None
            self.mini_countdown_label = None
            self.mini_time_label = None

    def _recreate_mini_window(self):
        """重建 mini 窗口（切换透明模式时）"""
        self._destroy_mini_window()
        self._create_mini_window()

    def _mini_start_drag(self, event):
        if platform.system() == "Windows":
            try:
                import ctypes
                hwnd = int(self.mini_window.frame(), 16)
                ctypes.windll.user32.ReleaseCapture()
                ctypes.windll.user32.PostMessageW(hwnd, 0xA1, 2, 0)
            except Exception:
                logger.debug("Mini 原生拖动失败", exc_info=True)
        else:
            self._drag_data["x"] = event.x
            self._drag_data["y"] = event.y

    def _mini_do_drag(self, event):
        if platform.system() == "Windows":
            return
        if self.mini_window:
            x = self.mini_window.winfo_x() + event.x - self._drag_data["x"]
            y = self.mini_window.winfo_y() + event.y - self._drag_data["y"]
            self.mini_window.geometry(f"+{x}+{y}")
            self._mini_pos = (x, y)

    def _mini_end_drag(self, event=None):
        if not self.mini_window:
            return
        try:
            pos = parse_mini_geometry(self.mini_window.geometry())
            if pos is not None:
                self._mini_pos = pos
                self._save_config()
        except Exception:
            logger.warning("结束 Mini 拖动时保存位置失败", exc_info=True)

    def _mini_close(self):
        """Mini 关闭：有托盘则隐藏到托盘，否则回到完整模式"""
        if self._has_tray():
            self._is_mini = False
            self._destroy_mini_window()
            self.master.withdraw()
            if self._first_hide:
                self._first_hide = False
                self.master.after(0, lambda: messagebox.showinfo(
                    "提示",
                    "程序已最小化到系统托盘。\n"
                    "右键托盘图标可切换 Mini 模式或退出。",
                    parent=self.master,
                ))
        else:
            self._switch_to_full()

    def _sync_mini_state(self):
        """同步 mini 窗口的状态"""
        if self.mini_window and self.mini_countdown_label:
            self.mini_countdown_label.config(text=self.countdown_text)
            if self._state == STATE_RUNNING:
                self.mini_countdown_label.config(fg=self.COLORS["white"])
            elif self._state == STATE_FINISHED:
                self.mini_countdown_label.config(fg=self.COLORS["success"])
            else:
                self.mini_countdown_label.config(fg=self.COLORS["text_dim"])

    def _show_time_picker(self):
        """弹出时间选择器 - 毛玻璃风格（macOS 保留系统标题栏以便聚焦）"""

        is_darwin = platform.system() == "Darwin"
        picker = tk.Toplevel(self.master)
        picker.title("选择时间")
        picker.geometry(f"{self.PICKER_WIDTH}x{self.PICKER_HEIGHT}")
        picker.resizable(False, False)
        picker.configure(bg=self.COLORS["bg"])
        # Darwin 下 overrideredirect 易导致无法聚焦，保留系统标题栏
        if not is_darwin:
            picker.overrideredirect(True)
        picker.attributes("-topmost", True)

        # 屏幕居中
        picker.update_idletasks()
        sw = picker.winfo_screenwidth()
        sh = picker.winfo_screenheight()
        px = sw // 2 - self.PICKER_WIDTH // 2
        py = sh // 2 - self.PICKER_HEIGHT // 2
        picker.geometry(f"+{px}+{py}")

        if not is_darwin:
            # 拖动变量
            _picker_drag = {"x": 0, "y": 0}

            def _picker_start_drag(e):
                _picker_drag["x"] = e.x
                _picker_drag["y"] = e.y

            def _picker_do_drag(e):
                x = picker.winfo_x() + e.x - _picker_drag["x"]
                y = picker.winfo_y() + e.y - _picker_drag["y"]
                picker.geometry(f"+{x}+{y}")

            # 自定义标题栏
            p_title_bar = tk.Frame(picker, bg=self.COLORS["title_bar"], height=36)
            p_title_bar.pack(fill=tk.X)
            p_title_bar.pack_propagate(False)
            p_title_bar.bind("<Button-1>", _picker_start_drag)
            p_title_bar.bind("<B1-Motion>", _picker_do_drag)

            title_label = tk.Label(p_title_bar, text="  ⏱ 选择时间",
                                   bg=self.COLORS["title_bar"], fg=self.COLORS["text"],
                                   font=self._font("label", 9))
            title_label.pack(side=tk.LEFT, fill=tk.Y)
            title_label.bind("<Button-1>", _picker_start_drag)
            title_label.bind("<B1-Motion>", _picker_do_drag)

            # 关闭按钮
            p_close = tk.Canvas(p_title_bar, width=24, height=24,
                                bg=self.COLORS["title_bar"], highlightthickness=0, cursor="hand2")
            p_close.pack(side=tk.RIGHT, padx=(0, 8))
            p_close_items = self._init_circle_button(p_close, 12, 12, 11,
                                                     fill=self.COLORS["btn_default"], text="×",
                                                     text_color=self.COLORS["text_dim"], font_size=10)
            p_close.bind("<Enter>", lambda e: self._update_circle_button(
                p_close, p_close_items, fill=self.COLORS["btn_hover_close"],
                text_color=self.COLORS["white"]))
            p_close.bind("<Leave>", lambda e: self._update_circle_button(
                p_close, p_close_items, fill=self.COLORS["btn_default"],
                text_color=self.COLORS["text_dim"]))
            p_close.bind("<Button-1>", lambda e: picker.destroy())

            # 底部紫色细线
            tk.Frame(picker, bg=self.COLORS["accent"], height=1).pack(fill=tk.X)

        # 标题
        tk.Label(picker, text="到期时间", font=self._font("button"),
                 bg=self.COLORS["bg"], fg=self.COLORS["text"]).pack(pady=(12, 8))

        # 时间输入框容器
        input_card = RoundedFrame(picker, bg_color=self.COLORS["glass"],
                                  border_color=self.COLORS["card_border"],
                                  corner_radius=12, height=56)
        input_card.pack(padx=24, fill=tk.X)
        input_frame = tk.Frame(input_card, bg=self.COLORS["glass"])
        input_frame.place(relx=0.5, rely=0.5, anchor="center")

        h_var = tk.StringVar(value="18")
        m_var = tk.StringVar(value="00")
        s_var = tk.StringVar(value="00")
        mono_font = self._font("time", 18)
        mono_bold = self._font("time", 18, bold=True)

        for var, mx in [(h_var, 23), (m_var, 59), (s_var, 59)]:
            sb = ttk.Spinbox(input_frame, textvariable=var, from_=0, to=mx,
                             width=3, font=mono_font, wrap=True,
                             style="TSpinbox")
            sb.pack(side=tk.LEFT, padx=6)

            if var != s_var:
                tk.Label(input_frame, text=":", font=mono_bold,
                         bg=self.COLORS["glass"], fg=self.COLORS["text_dim"]).pack(side=tk.LEFT)

        def confirm():
            try:
                h, m, s = int(h_var.get()), int(m_var.get()), int(s_var.get())
                if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
                    return
                self.hour_var.set(f"{h:02d}")
                self.minute_var.set(f"{m:02d}")
                self.second_var.set(f"{s:02d}")
                picker.destroy()
                if self._state != STATE_RUNNING:
                    self.toggle_countdown()
            except ValueError:
                logger.debug("时间选择器输入无效", exc_info=True)

        # 确认 / 取消按钮
        btn_frame = tk.Frame(picker, bg=self.COLORS["bg"])
        btn_frame.pack(pady=14)

        ok_btn = tk.Label(btn_frame, text="确认", font=self._font("label", 11, bold=True),
                          bg=self.COLORS["accent"], fg=self.COLORS["white"], padx=24, pady=6,
                          cursor="hand2")
        ok_btn.pack(side=tk.LEFT, padx=6)
        ok_btn.bind("<Button-1>", lambda e: confirm())
        ok_btn.bind("<Enter>", lambda e: ok_btn.config(bg=self.COLORS["accent_hover"]))
        ok_btn.bind("<Leave>", lambda e: ok_btn.config(bg=self.COLORS["accent"]))

        cancel_btn = tk.Label(btn_frame, text="取消", font=self._font("label", 11),
                              bg=self.COLORS["card"], fg=self.COLORS["text_dim"],
                              padx=24, pady=6, cursor="hand2")
        cancel_btn.pack(side=tk.LEFT, padx=6)
        cancel_btn.bind("<Button-1>", lambda e: picker.destroy())
        cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(bg=self.COLORS["border"]))
        cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(bg=self.COLORS["card"]))

        picker.bind("<Return>", lambda e: confirm())
        picker.bind("<Escape>", lambda e: picker.destroy())
        try:
            picker.focus_force()
        except Exception:
            logger.debug("时间选择器聚焦失败", exc_info=True)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_styles(self):
        """配置毛玻璃风格 ttk 样式"""
        style = ttk.Style()
        style.theme_use("clam")

        # 全局背景
        style.configure(".", background=self.COLORS["bg"], foreground=self.COLORS["text"])

        # Label 样式
        style.configure("TLabel", background=self.COLORS["bg"], foreground=self.COLORS["text"],
                        font=self.FONTS["label"])
        style.configure("Title.TLabel", font=self.FONTS["title"], foreground="#FFFFFF")
        style.configure("Time.TLabel", font=self.FONTS["time"], foreground=self.COLORS["accent_glow"])
        style.configure("Countdown.TLabel", font=self.FONTS["countdown"], foreground="#FFFFFF")
        style.configure("Success.TLabel", font=self.FONTS["countdown"], foreground=self.COLORS["success"])
        style.configure("Error.TLabel", font=self.FONTS["label"], foreground=self.COLORS["error"])
        style.configure("Dim.TLabel", foreground=self.COLORS["text_dim"], background=self.COLORS["card"])

        # Button 样式 - 胶囊形
        style.configure("Accent.TButton",
                        font=self.FONTS["button"],
                        background=self.COLORS["accent"],
                        foreground="#FFFFFF",
                        padding=(24, 12))
        style.map("Accent.TButton",
                  background=[("active", self.COLORS["accent_hover"]),
                              ("disabled", self.COLORS["btn_default"])])

        style.configure("Secondary.TButton",
                        font=self.FONTS["label"],
                        background=self.COLORS["card"],
                        foreground=self.COLORS["text_dim"],
                        padding=(18, 10))
        style.map("Secondary.TButton",
                  background=[("active", self.COLORS["border"])])

        # Spinbox 样式
        style.configure("TSpinbox",
                        fieldbackground=self.COLORS["input_bg"],
                        foreground=self.COLORS["text"],
                        arrowcolor=self.COLORS["text_dim"],
                        bordercolor=self.COLORS["border"],
                        lightcolor=self.COLORS["border"],
                        darkcolor=self.COLORS["border"])

    def _setup_ui(self):
        # ===== 毛玻璃标题栏 =====
        title_bar = tk.Frame(self.master, bg=self.COLORS["title_bar"], height=48)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)

        # 底部微光边线
        title_line = tk.Frame(title_bar, bg=self.COLORS["accent"], height=1)
        title_line.pack(side=tk.BOTTOM, fill=tk.X)

        # 标题栏拖动事件
        title_bar.bind("<Button-1>", self._start_drag)
        title_bar.bind("<B1-Motion>", self._on_drag)

        # 标题文字
        title_label = tk.Label(title_bar, text=f"  ⏱ {APP_NAME}",
                               bg=self.COLORS["title_bar"], fg=self.COLORS["text"],
                               font=self._font("label", 10, bold=True))
        title_label.pack(side=tk.LEFT, fill=tk.Y)
        title_label.bind("<Button-1>", self._start_drag)
        title_label.bind("<B1-Motion>", self._on_drag)

        # 按钮容器
        btn_frame = tk.Frame(title_bar, bg=self.COLORS["title_bar"])
        btn_frame.pack(side=tk.RIGHT, padx=(0, 10))

        # 关闭按钮
        close_btn_size = 16
        close_btn = tk.Canvas(btn_frame, width=close_btn_size * 2, height=close_btn_size * 2,
                              bg=self.COLORS["title_bar"], highlightthickness=0, cursor="hand2")
        close_btn.pack(side=tk.RIGHT, padx=(6, 0))
        close_btn_items = self._init_circle_button(close_btn, close_btn_size, close_btn_size, close_btn_size - 1,
                                                   fill=self.COLORS["btn_default"], text="×",
                                                   text_color=self.COLORS["text_dim"], font_size=12)
        close_btn.bind("<Enter>",
                       lambda e: self._update_circle_button(close_btn, close_btn_items,
                                                            fill=self.COLORS["btn_hover_close"],
                                                            text_color=self.COLORS["white"]))
        close_btn.bind("<Leave>",
                       lambda e: self._update_circle_button(close_btn, close_btn_items,
                                                            fill=self.COLORS["btn_default"],
                                                            text_color=self.COLORS["text_dim"]))
        close_btn.bind("<Button-1>", lambda e: self._hide_to_tray())

        # 最小化按钮
        min_btn_size = 16
        min_btn = tk.Canvas(btn_frame, width=min_btn_size * 2, height=min_btn_size * 2,
                            bg=self.COLORS["title_bar"], highlightthickness=0, cursor="hand2")
        min_btn.pack(side=tk.RIGHT, padx=(6, 0))
        min_btn_items = self._init_circle_button(min_btn, min_btn_size, min_btn_size, min_btn_size - 1,
                                                 fill=self.COLORS["btn_default"], text="−",
                                                 text_color=self.COLORS["text_dim"], font_size=12)
        min_btn.bind("<Enter>",
                     lambda e: self._update_circle_button(min_btn, min_btn_items,
                                                          fill=self.COLORS["btn_hover_min"],
                                                          text_color=self.COLORS["white"]))
        min_btn.bind("<Leave>",
                     lambda e: self._update_circle_button(min_btn, min_btn_items,
                                                          fill=self.COLORS["btn_default"],
                                                          text_color=self.COLORS["text_dim"]))
        min_btn.bind("<Button-1>", lambda e: self._switch_to_mini())

        # ===== 主内容区域 =====
        main_frame = tk.Frame(self.master, bg=self.COLORS["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(16, 24))

        # 标题
        title_frame = tk.Frame(main_frame, bg=self.COLORS["bg"])
        title_frame.pack(fill=tk.X, pady=(0, 14))
        ttk.Label(title_frame, text=APP_NAME, style="Title.TLabel").pack()

        # 当前时间卡片 - 带发光边框
        clock_card = RoundedFrame(main_frame, bg_color=self.COLORS["glass"],
                                  border_color=self.COLORS["card_border"],
                                  corner_radius=16, height=140)
        clock_card.pack(fill=tk.X, pady=(0, 14))
        clock_inner = tk.Frame(clock_card, bg=self.COLORS["glass"])
        clock_inner.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(clock_inner, text="当前时间", style="Dim.TLabel",
                  background=self.COLORS["glass"]).pack(pady=(0, 2))
        self.current_time_label = ttk.Label(clock_inner, style="Time.TLabel",
                                            background=self.COLORS["glass"])
        self.current_time_label.pack()

        # 目标时间显示
        self.target_time_label = ttk.Label(clock_inner, text="",
                                           font=self.FONTS["time"],
                                           foreground=self.COLORS["accent_glow"],
                                           background=self.COLORS["glass"])
        self.target_time_label.pack(pady=(8, 0))

        # 到期时间输入区域
        input_sub = tk.Frame(clock_inner, bg=self.COLORS["glass"])
        input_sub.pack(pady=(10, 0))

        ttk.Label(input_sub, text="到期时间", style="Dim.TLabel",
                  background=self.COLORS["glass"]).pack(pady=(0, 6))

        spin_input_frame = tk.Frame(input_sub, bg=self.COLORS["glass"])
        spin_input_frame.pack()

        self.hour_var = tk.StringVar(value="18")
        self.minute_var = tk.StringVar(value="00")
        self.second_var = tk.StringVar(value="00")

        spinboxes = [
            (self.hour_var, 0, 23),
            (self.minute_var, 0, 59),
            (self.second_var, 0, 59),
        ]

        spin_font = self._font("time", 14)
        spin_colon_font = self._font("time", 14, bold=True)
        for idx, (var, min_val, max_val) in enumerate(spinboxes):
            sb = ttk.Spinbox(
                spin_input_frame, textvariable=var, from_=min_val, to=max_val,
                width=3, font=spin_font, wrap=True,
                justify="center",
            )
            sb.grid(row=0, column=idx * 2, padx=4)
            if idx < 2:
                ttk.Label(spin_input_frame, text=":", font=spin_colon_font,
                          background=self.COLORS["glass"], foreground=self.COLORS["text_dim"]
                          ).grid(row=0, column=idx * 2 + 1)

        # 绑定变量变化事件，实时更新目标时间
        self.hour_var.trace_add("write", self._on_time_changed)
        self.minute_var.trace_add("write", self._on_time_changed)
        self.second_var.trace_add("write", self._on_time_changed)

        # 倒计时显示卡片 - 紫色边框
        countdown_card = RoundedFrame(main_frame, bg_color=self.COLORS["glass"],
                                      border_color=self.COLORS["accent"],
                                      corner_radius=16, height=130)
        countdown_card.pack(fill=tk.X, pady=(0, 14))
        countdown_inner = tk.Frame(countdown_card, bg=self.COLORS["glass"])
        countdown_inner.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(countdown_inner, text="剩余时间", style="Dim.TLabel",
                  background=self.COLORS["glass"]).pack()
        self.countdown_label = ttk.Label(countdown_inner, text="--:--:--",
                                         style="Countdown.TLabel",
                                         background=self.COLORS["glass"])
        self.countdown_label.pack(pady=8)

        # 快捷预设卡片
        preset_card = RoundedFrame(main_frame, bg_color=self.COLORS["glass"],
                                   border_color=self.COLORS["card_border"],
                                   corner_radius=16)
        preset_card.pack(fill=tk.X, pady=(0, 14))
        preset_inner = tk.Frame(preset_card, bg=self.COLORS["glass"])
        preset_inner.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(preset_inner, text="快捷预设", style="Dim.TLabel",
                  background=self.COLORS["glass"]).pack(side=tk.LEFT, padx=(0, 12))

        preset_buttons = [
            ("5分钟", "00", "05", "00"),
            ("10分钟", "00", "10", "00"),
            ("15分钟", "00", "15", "00"),
            ("30分钟", "00", "30", "00"),
            ("1小时", "01", "00", "00"),
        ]
        for text, h, m, s in preset_buttons:
            btn = tk.Label(preset_inner, text=text, font=self._font("label", 9),
                           bg=self.COLORS["input_bg"], fg=self.COLORS["text"],
                           padx=10, pady=4, cursor="hand2")
            btn.pack(side=tk.LEFT, padx=(0, 8))
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=self.COLORS["border"]))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=self.COLORS["input_bg"]))
            btn.bind("<Button-1>", lambda e, hh=h, mm=m, ss=s: self._set_preset_time(hh, mm, ss))

        # 错误提示
        self.error_label = ttk.Label(main_frame, style="Error.TLabel")
        self.error_label.pack(pady=(0, 10))

        # 控制按钮 - 胶囊形
        btn_frame = tk.Frame(main_frame, bg=self.COLORS["bg"])
        btn_frame.pack(fill=tk.X)

        self.btn_start = ttk.Button(btn_frame, text="开始倒计时",
                                    style="Accent.TButton", command=self.toggle_countdown)
        self.btn_start.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 10))

        ttk.Button(btn_frame, text="重置", style="Secondary.TButton",
                   command=self.reset).pack(side=tk.RIGHT)

        # 快捷键
        self.master.bind("<Escape>", lambda e: self._hide_to_tray())
        self.master.bind("<m>", lambda e: self._toggle_mini_mode())
        self.master.bind("<M>", lambda e: self._toggle_mini_mode())

        self.master.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

    # ------------------------------------------------------------------
    # 倒计时逻辑
    # ------------------------------------------------------------------

    def update_clock(self):
        now = datetime.now()
        self.current_time_label.config(text=now.strftime("%H:%M:%S"))
        if self.mini_time_label:
            self.mini_time_label.config(text=now.strftime("%H:%M"))
        self.master.after(next_second_delay_ms(), self.update_clock)

    def _format_target_label(self, target, now=None):
        return format_target_label(target, now)

    def _on_time_changed(self, *args):
        """当用户修改时间时，实时更新目标时间显示"""
        if not self._applying_preset:
            self._preset_duration = None
        try:
            h = int(self.hour_var.get())
            m = int(self.minute_var.get())
            s = int(self.second_var.get())
            ok, _ = validate_hms(h, m, s)
            if not ok:
                self.target_time_label.config(text="")
                return
            now = datetime.now()
            target = target_from_hms(h, m, s, now)
            self.target_time = target
            self.target_time_label.config(text=self._format_target_label(target, now))
        except ValueError:
            pass

    def toggle_countdown(self):
        if self._state == STATE_FINISHED:
            self._restart_countdown()
            return
        if self._state == STATE_RUNNING:
            if self._countdown_timer_id is not None:
                try:
                    self.master.after_cancel(self._countdown_timer_id)
                except Exception:
                    logger.debug("暂停时取消倒计时定时器失败", exc_info=True)
                self._countdown_timer_id = None
            self._set_state(ACTION_PAUSE)
        elif self._state == STATE_PAUSED:
            self._set_state(ACTION_RESUME)
            if self.target_time:
                self.update_countdown(self.target_time)
            else:
                self.start_countdown()
        else:
            # idle → start
            self.start_countdown()
        self._sync_mini_state()

    def _apply_target_to_spinboxes(self, target):
        self._applying_preset = True
        try:
            self.hour_var.set(f"{target.hour:02d}")
            self.minute_var.set(f"{target.minute:02d}")
            self.second_var.set(f"{target.second:02d}")
        finally:
            self._applying_preset = False

    def _restart_countdown(self):
        if self._preset_duration is not None:
            now = datetime.now()
            target = now + self._preset_duration
            self._apply_target_to_spinboxes(target)
            self.target_time = target
            self.target_time_label.config(text=self._format_target_label(target, now))
            self._set_state(ACTION_RESTART)
            self.update_countdown(target)
            self._sync_mini_state()
            return
        # 校验失败保持 finished，不提前转 running
        if not self.validate_inputs():
            return
        target = self.get_target_time()
        if not target:
            return
        self.target_time = target
        self._set_state(ACTION_RESTART)
        self.update_countdown(self.target_time)
        self._sync_mini_state()

    def start_countdown(self):
        if not self.validate_inputs():
            self._set_state(ACTION_START_FAIL)
            return
        self.target_time = self.get_target_time()
        if not self.target_time:
            self._set_state(ACTION_START_FAIL)
            return
        if self._state == STATE_IDLE:
            self._set_state(ACTION_START)
        elif self._state == STATE_PAUSED:
            self._set_state(ACTION_RESUME)
        elif self._state == STATE_FINISHED:
            self._set_state(ACTION_RESTART)
        self.update_countdown(self.target_time)

    def validate_inputs(self):
        ok, err = validate_hms(
            self.hour_var.get(),
            self.minute_var.get(),
            self.second_var.get(),
        )
        if not ok:
            self.show_error(err or "请输入有效数字")
            return False
        return True

    def get_target_time(self):
        try:
            return target_from_hms(
                int(self.hour_var.get()),
                int(self.minute_var.get()),
                int(self.second_var.get()),
            )
        except ValueError as e:
            self.show_error(str(e))
            return None

    def update_countdown(self, target_time):
        if not self.running:
            return

        # 取消旧的定时器，防止竞态条件
        if self._countdown_timer_id is not None:
            try:
                self.master.after_cancel(self._countdown_timer_id)
            except Exception:
                logger.debug("取消倒计时定时器失败", exc_info=True)
            self._countdown_timer_id = None

        remaining = target_time - datetime.now()
        if remaining.total_seconds() <= 0:
            self.countdown_text = "已到时间!"
            self.countdown_label.config(text="已到时间!", style="Success.TLabel")
            self._set_state(ACTION_FINISH)
            self._sync_mini_state()
            self._on_countdown_finished()
            self._countdown_timer_id = None
            return

        total_seconds = int(remaining.total_seconds())
        self.countdown_text = format_remaining(total_seconds)
        self.countdown_label.config(text=self.countdown_text, style="Countdown.TLabel")

        # 同步 mini 窗口
        self._sync_mini_state()

        self._countdown_timer_id = self.master.after(
            next_second_delay_ms(), lambda: self.update_countdown(target_time)
        )

    def _on_countdown_finished(self):
        """结束提醒：闪烁 + 通知 + 提示音。失败只 log。"""
        self._alarm_count = 0
        self._bell_count = 0
        try:
            self._flash_visual()
        except Exception:
            logger.warning("视觉闪烁失败", exc_info=True)
        try:
            self._notify_finished()
        except Exception:
            logger.warning("结束通知失败", exc_info=True)
        try:
            self._ring_bell()
        except Exception:
            logger.warning("提示音失败", exc_info=True)

    def _notify_finished(self):
        title = APP_NAME
        message = "倒计时已结束"
        if self.tray_icon is not None:
            try:
                self.tray_icon.notify(message, title)
                return
            except Exception:
                logger.debug("托盘 notify 失败", exc_info=True)
        # 无托盘：非阻塞提示
        try:
            self.master.after(0, lambda: messagebox.showinfo(title, message, parent=self.master))
        except Exception:
            logger.debug("messagebox 通知失败", exc_info=True)

    def _ring_bell(self):
        """响铃 2~3 次，间隔约 400ms。"""
        try:
            self.master.bell()
        except Exception:
            logger.debug("bell 失败", exc_info=True)
        self._bell_count += 1
        if self._bell_count < 3:
            self.master.after(400, self._ring_bell)

    def _flash_visual(self):
        if not self.countdown_label:
            return
        style = ttk.Style()
        fg = self.COLORS["success"] if self._alarm_count % 2 == 0 else self.COLORS["error"]
        style.configure("Flash.TLabel", font=self.FONTS["countdown"],
                        foreground=fg, background=self.COLORS["glass"])
        self.countdown_label.config(style="Flash.TLabel")
        self._alarm_count += 1
        if self._alarm_count >= 6:
            self.countdown_label.config(style="Countdown.TLabel")
            self._alarm_count = 0
            self._alarm_timer_id = None
            return
        self._alarm_timer_id = self.master.after(500, self._flash_visual)

    def reset(self):
        self._alarm_count = 0
        self._bell_count = 0
        self._preset_duration = None
        if self._alarm_timer_id is not None:
            try:
                self.master.after_cancel(self._alarm_timer_id)
            except Exception:
                logger.debug("取消报警定时器失败", exc_info=True)
            self._alarm_timer_id = None
        if self._countdown_timer_id is not None:
            try:
                self.master.after_cancel(self._countdown_timer_id)
            except Exception:
                logger.debug("重置时取消倒计时定时器失败", exc_info=True)
            self._countdown_timer_id = None
        self._set_state(ACTION_RESET)
        self.target_time = None
        self.hour_var.set("18")
        self.minute_var.set("00")
        self.second_var.set("00")
        self.countdown_text = "--:--:--"
        self.countdown_label.config(text="--:--:--", style="Countdown.TLabel")
        self.error_label.config(text="")
        self._sync_mini_state()

    def show_error(self, message):
        if self._error_timer_id is not None:
            try:
                self.master.after_cancel(self._error_timer_id)
            except Exception:
                logger.debug("取消错误提示定时器失败", exc_info=True)
            self._error_timer_id = None
        self.error_label.config(text=message)
        self._error_timer_id = self.master.after(3000, self._clear_error)

    def _clear_error(self):
        self.error_label.config(text="")
        self._error_timer_id = None

    def _set_preset_time(self, hours, minutes, seconds):
        now = datetime.now()
        target, duration = target_from_duration(hours, minutes, seconds, now)
        self._preset_duration = duration

        self._apply_target_to_spinboxes(target)
        self.target_time = target
        self.target_time_label.config(text=self._format_target_label(target, now))

        if self._countdown_timer_id is not None:
            try:
                self.master.after_cancel(self._countdown_timer_id)
            except Exception:
                logger.debug("预设时取消倒计时定时器失败", exc_info=True)
            self._countdown_timer_id = None

        # 预设直接进入 running（任意状态可切）
        self._state = STATE_RUNNING
        self.running = True
        if self.btn_start:
            self.btn_start.config(text=button_text_for_state(STATE_RUNNING))
        self.update_countdown(target)
        self._sync_mini_state()


def main():
    ok, _ = _acquire_single_instance()
    if not ok:
        brought = _bring_existing_to_front()
        if not brought:
            try:
                root = tk.Tk()
                root.withdraw()
                messagebox.showinfo(APP_NAME, f"{APP_NAME} 已在运行中。")
                root.destroy()
            except Exception:
                logger.warning("单实例提示失败", exc_info=True)
                print(f"{APP_NAME} 已在运行中。")
        return

    missing = []
    try:
        import pystray  # noqa: F401
    except ImportError:
        missing.append("pystray")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("pillow")

    if missing:
        print(f"警告: 缺少可选依赖: {', '.join(missing)}")
        print(f"pip install {' '.join(missing)}")
        print("程序仍可运行，但托盘功能不可用。\n")

    root = tk.Tk()
    CountdownApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
