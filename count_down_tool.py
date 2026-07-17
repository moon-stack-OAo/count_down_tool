# -*- coding: utf-8 -*-
"""
距离时间倒计时 - 现代化深色主题版
支持完整模式和 Mini 桌面小组件模式
依赖：pystray, pillow
安装：pip install pystray pillow
"""

import json
import os
import platform
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk, messagebox

__version__ = "1.0.0"

try:
    import pystray

    _HAS_PYSTRAY = True
except ImportError:
    _HAS_PYSTRAY = False

_ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "count_down_tool.ico")


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
    }

    def __init__(self, master):
        self.master = master
        self.master.title("倒计时工具")
        self.master.geometry("560x610")
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
        self._countdown_timer_id = None
        self.btn_start = None
        self.tray_icon = None
        self._first_hide = True

        # 报警相关
        self._alarm_count = 0
        self._alarm_timer_id = None

        self.FONTS = self._get_fonts()

        # Mini 模式相关
        self._is_mini = False
        self.mini_window = None
        self.mini_countdown_label = None
        self.mini_time_label = None
        self._transparent_mode = False
        self._drag_data = {"x": 0, "y": 0}

        # 倒计时状态（完整和 mini 共享）
        self.target_time = None
        self.countdown_text = "--:--:--"

        self._mini_pos = None  # 保存 Mini 窗口位置
        self._config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        self._load_config()

        self._setup_styles()
        self._setup_ui()
        self._on_time_changed()
        self.update_clock()
        self._init_tray_icon()
        self._center_window()
        self._set_window_rounded_corners()
        self._set_taskbar_visible()
        # macOS 不自动切换到 Mini 模式
        if platform.system() != "Darwin":
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

    def _load_config(self):
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self._mini_pos = config.get("mini_position")
        except Exception:
            self._mini_pos = None

    def _save_config(self):
        try:
            config = {}
            if self._mini_pos:
                config["mini_position"] = self._mini_pos
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass

    def _set_icon(self):
        try:
            if os.path.exists(_ICON_PATH):
                self.master.iconbitmap(_ICON_PATH)
        except Exception:
            pass

    def _start_drag(self, event):
        """开始拖动窗口"""
        if event.x > 440:  # 右侧120px为按钮区域，不触发拖动
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
            self._set_window_rounded_corners_fallback()

    def _set_window_rounded_corners_fallback(self):
        """回退方案：GDI 圆角"""
        if platform.system() != "Windows":
            return
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = int(self.master.frame(), 16)
            radius = 20
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
            pass

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
            pass

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
                pystray.MenuItem(lambda _: "暂停" if self.running else "开始倒计时", self._tray_toggle_countdown),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Mini 模式", self._tray_toggle_mini),
                pystray.MenuItem("透明模式", self._tray_toggle_transparent,
                                 checked=lambda _: self._transparent_mode),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self._tray_quit),
            )
            self.tray_icon = pystray.Icon("倒计时工具", image, "倒计时工具", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            print(f"托盘图标创建失败: {e}")
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
        self._transparent_mode = not self._transparent_mode
        if self._is_mini:
            self.master.after(0, self._recreate_mini_window)

    def _tray_quit(self, icon=None, item=None):
        self.master.after(0, self._quit_app)

    def _show_full_mode(self):
        """显示完整模式窗口"""
        if self._is_mini:
            self._switch_to_full()
        self.master.deiconify()
        self.master.lift()
        self.master.focus_force()

    def _hide_to_tray(self):
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
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
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
        self.master.update()
        self.master.withdraw()
        self._create_mini_window()

    def _switch_to_full(self):
        """切换到完整模式"""
        self._is_mini = False
        self._destroy_mini_window()
        self.master.deiconify()
        self.master.lift()

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
        win_w, win_h = 220, 48
        screen_w = mini.winfo_screenwidth()
        screen_h = mini.winfo_screenheight()

        if self._mini_pos:
            x, y = self._mini_pos
        else:
            x = (screen_w - win_w) // 2
            y = (screen_h - win_h) // 2
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
            bg=self.COLORS["title_bar"], fg="#FFFFFF",
        )
        self.mini_countdown_label.pack(side=tk.LEFT, expand=True)

        # 按钮容器
        btn_frame = tk.Frame(content_frame, bg=self.COLORS["title_bar"])
        btn_frame.pack(side=tk.RIGHT, padx=(4, 0))

        # 展开按钮
        expand_btn = tk.Label(
            btn_frame, text="↗", font=("Segoe UI", 10),
            bg=self.COLORS["title_bar"], fg=self.COLORS["accent_glow"], cursor="hand2",
        )
        expand_btn.pack(side=tk.LEFT, padx=(0, 4))
        expand_btn.bind("<Button-1>", lambda e: self._switch_to_full())

        # 关闭按钮
        close_btn = tk.Label(
            btn_frame, text="×", font=("Segoe UI", 10, "bold"),
            bg=self.COLORS["title_bar"], fg=self.COLORS["text_dim"], cursor="hand2",
        )
        close_btn.pack(side=tk.LEFT)
        close_btn.bind("<Button-1>", lambda e: self._quit_app())
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg=self.COLORS["btn_hover_close"]))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=self.COLORS["text_dim"]))

        # 拖拽功能（透明模式不需要拖拽）
        if platform.system() == "Windows":
            if not self._transparent_mode:
                for w in (mini, main_frame, content_frame,
                          self.mini_time_label, self.mini_countdown_label):
                    w.bind("<Button-1>", self._mini_start_drag)
        else:
            for widget in (mini, main_frame, content_frame,
                           self.mini_time_label, self.mini_countdown_label):
                widget.bind("<Button-1>", self._mini_start_drag)
                widget.bind("<B1-Motion>", self._mini_do_drag)

        self.mini_window = mini

        # 同步当前状态
        self._sync_mini_state()

    def _destroy_mini_window(self):
        if self.mini_window:
            try:
                # 保存位置
                geo = self.mini_window.geometry()
                # 解析 +x+y 格式
                parts = geo.split("+")
                if len(parts) == 3:
                    self._mini_pos = (int(parts[1]), int(parts[2]))
                    self._save_config()
            except Exception:
                pass
            try:
                self.mini_window.destroy()
            except Exception:
                pass
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
                pass
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
            self._save_config()

    def _sync_mini_state(self):
        """同步 mini 窗口的状态"""
        if self.mini_window and self.mini_countdown_label:
            self.mini_countdown_label.config(text=self.countdown_text)
            if self.running:
                self.mini_countdown_label.config(fg="#FFFFFF")
            elif self.countdown_text == "已到时间!":
                self.mini_countdown_label.config(fg=self.COLORS["success"])
            else:
                self.mini_countdown_label.config(fg=self.COLORS["text_dim"])

    def _show_time_picker(self):
        """弹出时间选择器 - 无边框毛玻璃风格"""

        picker = tk.Toplevel(self.master)
        picker.title("选择时间")
        picker.geometry("320x240")
        picker.resizable(False, False)
        picker.configure(bg=self.COLORS["bg"])
        picker.overrideredirect(True)  # 去掉原生边框
        picker.attributes("-topmost", True)

        # 屏幕居中
        picker.update_idletasks()
        sw = picker.winfo_screenwidth()
        sh = picker.winfo_screenheight()
        px = sw // 2 - 160
        py = sh // 2 - 120
        picker.geometry(f"+{px}+{py}")

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
                               font=("Segoe UI", 9))
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
            p_close, p_close_items, fill=self.COLORS["btn_hover_close"], text_color="#FFFFFF"))
        p_close.bind("<Leave>", lambda e: self._update_circle_button(
            p_close, p_close_items, fill=self.COLORS["btn_default"], text_color=self.COLORS["text_dim"]))
        p_close.bind("<Button-1>", lambda e: picker.destroy())

        # 底部紫色细线
        tk.Frame(picker, bg=self.COLORS["accent"], height=1).pack(fill=tk.X)

        # 标题
        tk.Label(picker, text="到期时间", font=("Segoe UI", 12, "bold"),
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

        for var, mx in [(h_var, 23), (m_var, 59), (s_var, 59)]:
            sb = ttk.Spinbox(input_frame, textvariable=var, from_=0, to=mx,
                             width=3, font=("Consolas", 18), wrap=True,
                             style="TSpinbox")
            sb.pack(side=tk.LEFT, padx=6)

            if var != s_var:
                tk.Label(input_frame, text=":", font=("Consolas", 18, "bold"),
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
                if not self.running:
                    self.toggle_countdown()
            except ValueError:
                pass

        # 确认 / 取消按钮
        btn_frame = tk.Frame(picker, bg=self.COLORS["bg"])
        btn_frame.pack(pady=14)

        ok_btn = tk.Label(btn_frame, text="确认", font=("Segoe UI", 11, "bold"),
                          bg=self.COLORS["accent"], fg="#FFFFFF", padx=24, pady=6,
                          cursor="hand2")
        ok_btn.pack(side=tk.LEFT, padx=6)
        ok_btn.bind("<Button-1>", lambda e: confirm())
        ok_btn.bind("<Enter>", lambda e: ok_btn.config(bg=self.COLORS["accent_hover"]))
        ok_btn.bind("<Leave>", lambda e: ok_btn.config(bg=self.COLORS["accent"]))

        cancel_btn = tk.Label(btn_frame, text="取消", font=("Segoe UI", 11),
                              bg=self.COLORS["card"], fg=self.COLORS["text_dim"],
                              padx=24, pady=6, cursor="hand2")
        cancel_btn.pack(side=tk.LEFT, padx=6)
        cancel_btn.bind("<Button-1>", lambda e: picker.destroy())
        cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(bg=self.COLORS["border"]))
        cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(bg=self.COLORS["card"]))

        picker.bind("<Return>", lambda e: confirm())
        picker.bind("<Escape>", lambda e: picker.destroy())

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
        title_label = tk.Label(title_bar, text="  ⏱ 倒计时工具",
                               bg=self.COLORS["title_bar"], fg=self.COLORS["text"],
                               font=("Segoe UI", 10, "bold"))
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
                                                            text_color="#FFFFFF"))
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
                                                          text_color="#FFFFFF"))
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
        ttk.Label(title_frame, text="倒计时工具", style="Title.TLabel").pack()

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

        for idx, (var, min_val, max_val) in enumerate(spinboxes):
            sb = ttk.Spinbox(
                spin_input_frame, textvariable=var, from_=min_val, to=max_val,
                width=3, font=("Consolas", 14), wrap=True,
                justify="center",
            )
            sb.grid(row=0, column=idx * 2, padx=4)
            if idx < 2:
                ttk.Label(spin_input_frame, text=":", font=("Consolas", 14, "bold"),
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
            btn = tk.Label(preset_inner, text=text, font=("Segoe UI", 9),
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
        now = datetime.now().strftime("%H:%M:%S")
        self.current_time_label.config(text=now)
        # 同步 mini 窗口时间
        if self.mini_time_label:
            self.mini_time_label.config(text=now)
        self.master.after(1000, self.update_clock)

    def _on_time_changed(self, *args):
        """当用户修改时间时，实时更新目标时间显示"""
        try:
            h = int(self.hour_var.get())
            m = int(self.minute_var.get())
            s = int(self.second_var.get())
            if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
                self.target_time_label.config(text="")
                return
            now = datetime.now()
            target = now.replace(hour=h, minute=m, second=s, microsecond=0)
            if target < now:
                target += timedelta(days=1)
            self.target_time = target
            self.target_time_label.config(text=target.strftime('%H:%M:%S'))
        except ValueError:
            pass

    def toggle_countdown(self):
        btn_text = self.btn_start.cget("text")
        if btn_text == "重新开始":
            self._restart_countdown()
            return
        self.running = not self.running
        if self.running:
            self.start_countdown()
            self.btn_start.config(text="暂停")
        else:
            if self._countdown_timer_id is not None:
                try:
                    self.master.after_cancel(self._countdown_timer_id)
                except Exception:
                    pass
                self._countdown_timer_id = None
            self.btn_start.config(text="继续")
        self._sync_mini_state()

    def _restart_countdown(self):
        if self.target_time:
            self.running = True
            self.btn_start.config(text="暂停")
            self.update_countdown(self.target_time)
        else:
            self.start_countdown()

    def start_countdown(self):
        if not self.validate_inputs():
            self.running = False
            return
        self.target_time = self.get_target_time()
        if not self.target_time:
            return
        self.update_countdown(self.target_time)

    def validate_inputs(self):
        try:
            for var, max_val in [(self.hour_var, 23),
                                 (self.minute_var, 59),
                                 (self.second_var, 59)]:
                val = int(var.get())
                if val < 0 or val > max_val:
                    self.show_error(f"输入值应在 00-{max_val:02} 之间")
                    return False
            return True
        except ValueError:
            self.show_error("请输入有效数字")
            return False

    def get_target_time(self):
        now = datetime.now()
        try:
            target = now.replace(
                hour=int(self.hour_var.get()),
                minute=int(self.minute_var.get()),
                second=int(self.second_var.get()),
                microsecond=0,
            )
            if target < now:
                target += timedelta(days=1)
            return target
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
                pass
            self._countdown_timer_id = None

        remaining = target_time - datetime.now()
        if remaining.total_seconds() <= 0:
            self.countdown_text = "已到时间!"
            self.countdown_label.config(text="已到时间!", style="Success.TLabel")
            self.running = False
            self.btn_start.config(text="重新开始")
            self._sync_mini_state()
            self._alarm_count = 0
            self._flash_visual()
            self._countdown_timer_id = None
            return

        total_seconds = int(remaining.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.countdown_text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.countdown_label.config(text=self.countdown_text, style="Countdown.TLabel")

        # 同步 mini 窗口
        self._sync_mini_state()

        self._countdown_timer_id = self.master.after(1000, lambda: self.update_countdown(target_time))

    def _flash_visual(self):
        if not self.countdown_label:
            return
        current_fg = self.COLORS["success"] if self._alarm_count % 2 == 0 else self.COLORS["error"]
        self.countdown_label.config(fg=current_fg)
        self._alarm_count += 1
        if self._alarm_count >= 6:
            self.countdown_label.config(style="Countdown.TLabel")
            self._alarm_count = 0
            self._alarm_timer_id = None
            return
        self._alarm_timer_id = self.master.after(500, self._flash_visual)

    def reset(self):
        self._alarm_count = 0
        if self._alarm_timer_id is not None:
            try:
                self.master.after_cancel(self._alarm_timer_id)
            except Exception:
                pass
            self._alarm_timer_id = None
        if self._countdown_timer_id is not None:
            try:
                self.master.after_cancel(self._countdown_timer_id)
            except Exception:
                pass
            self._countdown_timer_id = None
        self.running = False
        self.target_time = None
        self.hour_var.set("18")
        self.minute_var.set("00")
        self.second_var.set("00")
        self.countdown_text = "--:--:--"
        self.countdown_label.config(text="--:--:--", style="Countdown.TLabel")
        self.error_label.config(text="")
        self.btn_start.config(text="开始倒计时")
        self._sync_mini_state()

    def show_error(self, message):
        self.error_label.config(text=message)
        self.master.after(3000, lambda: self.error_label.config(text=""))

    def _set_preset_time(self, hours, minutes, seconds):
        now = datetime.now()
        duration = timedelta(hours=int(hours), minutes=int(minutes), seconds=int(seconds))
        target = now + duration

        if self.running:
            self.toggle_countdown()
        self.running = True
        self.btn_start.config(text="暂停")
        self.target_time = target
        self.update_countdown(target)
        self._sync_mini_state()


def main():
    missing = []
    try:
        import pystray
    except ImportError:
        missing.append("pystray")
    try:
        from PIL import Image
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
