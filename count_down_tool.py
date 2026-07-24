# -*- coding: utf-8 -*-
"""
倒计时工具 (Count Down Tool) - 多主题桌面倒计时
支持完整模式和 Mini 桌面小组件模式
依赖：pystray, pillow
安装：pip install pystray pillow
"""

import logging
import os
import platform
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from app import mode as _mode
from app import theme as _theme
from app import window_chrome as _chrome
from app.config_store import (
    default_mini_size as _cfg_default_mini_size,
    load_config as _cfg_load,
    mini_size_limits as _cfg_mini_size_limits,
    mini_text_fg as _cfg_mini_text_fg,
    resolved_mini_size as _cfg_resolved_mini_size,
    save_config as _cfg_save,
)
from app.countdown import CountdownController
from core.countdown_core import (
    APP_NAME,
    STATE_IDLE,
    format_target_label,
    next_second_delay_ms,
    resource_path,
    user_config_path,
)
from core.themes import DEFAULT_THEME_ID, resolve_theme
from services.tray import init_tray_icon, refresh_tray_menu, stop_tray
from services.windows_native import acquire_single_instance, bring_existing_to_front
from ui.full_window import build_full_ui, setup_styles
from ui.mini_window import (
    create_mini_window,
    destroy_mini_window,
    recreate_mini_window,
    sync_mini_state,
)
from ui.time_picker import show_time_picker

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("count_down_tool")

_ICON_PATH = resource_path(os.path.join("assets", "count_down_tool.ico"))


class CountdownApp:
    WINDOW_WIDTH = 500
    WINDOW_HEIGHT = 520
    MINI_WIDTH = 236
    MINI_HEIGHT = 48
    # macOS Retina / Tk 点阵下 Mini 易偏小，约为 Windows 的 1.9 倍
    MINI_WIDTH_MAC = 450
    MINI_HEIGHT_MAC = 90
    MINI_MIN_WIDTH = 180
    MINI_MIN_HEIGHT = 36
    MINI_MAX_WIDTH = 900
    MINI_MAX_HEIGHT = 240
    MINI_MIN_WIDTH_MAC = 280
    MINI_MIN_HEIGHT_MAC = 56
    MINI_MAX_WIDTH_MAC = 1400
    MINI_MAX_HEIGHT_MAC = 360
    TITLE_DRAG_EXCLUDE_RIGHT = 150
    PICKER_WIDTH = 420
    PICKER_HEIGHT = 440
    CORNER_RADIUS = 20
    MINI_MARGIN_RIGHT = 20
    MINI_MARGIN_BOTTOM = 60

    # 默认主题色（类级参考；运行时使用实例 self.COLORS）
    COLORS = resolve_theme(DEFAULT_THEME_ID)

    def __init__(self, master):
        self.master = master
        self.master.title(APP_NAME)
        self.master.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        self.master.resizable(False, False)
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
        # 进度条：start 时记录总时长；暂停时冻结当前进度
        self._duration_total_seconds = 0.0
        self._progress_value = 0.0
        self._time_spinboxes = []
        self._preset_chips = []
        self.progress_canvas = None

        # 报警相关
        self._alarm_count = 0
        self._alarm_timer_id = None
        self._bell_count = 0

        # 结束音效：muted / sound_id / sound_path / sound_history
        self._sound_muted = False
        self._sound_id = "soft"
        self._sound_path = ""
        self._sound_history = []

        self.FONTS = self._get_fonts(self.master)
        self._ctrl = CountdownController(self)

        # Mini 模式相关
        self._is_mini = False
        self.mini_window = None
        self.mini_countdown_label = None
        self.mini_time_label = None
        self.mini_sep_label = None
        self.mini_main_frame = None
        self.mini_content_frame = None
        self.mini_btn_frame = None
        self.mini_menu_btn = None
        self.mini_expand_btn = None
        self.mini_close_btn = None
        self._mini_layout_scale = None
        self._transparent_mode = False
        self._last_mode = "full"
        self._drag_data = {"x": 0, "y": 0}

        # 主题 / 自启
        self._theme_id = DEFAULT_THEME_ID
        self._theme_custom = None
        self._autostart = False
        # 自动更新
        self._check_update_on_start = True
        self._last_update_check = ""
        self._ignored_update_version = ""
        self.COLORS = resolve_theme(self._theme_id)

        # 倒计时状态（完整和 mini 共享）
        self.target_time = None
        self.countdown_text = "--:--:--"

        self._mini_pos = None  # 保存 Mini 窗口位置
        self._mini_size = None  # 保存 Mini 窗口尺寸 (w, h)
        self._mini_text = {}  # Mini 字色：主题色键，非 hex
        self._resize_data = None  # Mini 边缘缩放状态
        self._config_file = user_config_path()
        self._load_config()
        self.master.configure(bg=self.COLORS["bg"])

        self._setup_styles()
        self._setup_ui()
        self._on_time_changed()
        self.update_clock()
        self._init_tray_icon()
        self._set_window_rounded_corners()
        self._set_taskbar_visible()
        self._center_window_later()
        # 启动模式：last_mode=mini 进 Mini；无配置时非 Darwin 保持旧行为进 Mini
        if platform.system() != "Darwin":
            has_last = "last_mode" in getattr(self, "_loaded_keys", set())
            if (has_last and self._last_mode == "mini") or (not has_last):
                self._switch_to_mini()
        try:
            from services.updater import schedule_startup_check

            schedule_startup_check(self)
        except Exception:
            logger.debug("调度启动更新检查失败", exc_info=True)

    @staticmethod
    def _get_fonts(root=None):
        """按系统探测可用字体并回退，避免缺字时样式怪异。"""
        from core.fonts import resolve_fonts

        return resolve_fonts(root=root)

    def _font(self, key, size=None, bold=None):
        """基于 FONTS 派生字体，保证同一角色族名一致。"""
        base = self.FONTS[key]
        family = base[0]
        fsize = size if size is not None else base[1]
        weight = "bold" if bold is True else (base[2] if bold is None and len(base) > 2 else None)
        if weight:
            return (family, fsize, weight)
        return (family, fsize)

    # ------------------------------------------------------------------
    # 配置（委托 config_store）
    # ------------------------------------------------------------------

    def _load_config(self):
        _cfg_load(self)

    def default_mini_size(self):
        return _cfg_default_mini_size(self)

    def _mini_size_limits(self):
        return _cfg_mini_size_limits(self)

    def resolved_mini_size(self):
        return _cfg_resolved_mini_size(self)

    def _save_config(self):
        _cfg_save(self)

    def mini_text_fg(self, role: str) -> str:
        return _cfg_mini_text_fg(self, role)

    def _apply_theme(self, theme_id: str):
        _theme.apply_theme(self, theme_id)

    # ------------------------------------------------------------------
    # 倒计时（委托 CountdownController，保留 app.xxx 对外接口）
    # ------------------------------------------------------------------

    def _set_state(self, action: str) -> str:
        return self._ctrl.set_state(action)

    def _inputs_locked(self) -> bool:
        return self._ctrl.inputs_locked()

    def _apply_input_lock(self):
        self._ctrl.apply_input_lock()

    def _record_duration_total(self, target_time, now=None):
        self._ctrl.record_duration_total(target_time, now)

    def _update_progress_from_remaining(self, remaining_seconds: float):
        self._ctrl.update_progress_from_remaining(remaining_seconds)

    def _refresh_progress_bar(self):
        self._ctrl.refresh_progress_bar()

    def _draw_progress_bar(self, ratio: float):
        self._ctrl.draw_progress_bar(ratio)

    def _on_time_changed(self, *args):
        self._ctrl.on_time_changed(*args)

    def toggle_countdown(self):
        self._ctrl.toggle_countdown()

    def _apply_target_to_spinboxes(self, target):
        self._ctrl.apply_target_to_spinboxes(target)

    def _restart_countdown(self):
        self._ctrl.restart_countdown()

    def start_countdown(self):
        self._ctrl.start_countdown()

    def validate_inputs(self):
        return self._ctrl.validate_inputs()

    def get_target_time(self):
        return self._ctrl.get_target_time()

    def update_countdown(self, target_time):
        self._ctrl.update_countdown(target_time)

    def _on_countdown_finished(self):
        self._ctrl.on_countdown_finished()

    def _notify_finished(self):
        self._ctrl.notify_finished()

    def _ring_bell(self):
        self._ctrl.ring_bell()

    def _flash_visual(self):
        self._ctrl.flash_visual()

    def reset(self):
        self._ctrl.reset()

    def _set_preset_time(self, hours, minutes, seconds):
        self._ctrl.set_preset_time(hours, minutes, seconds)

    def _format_target_label(self, target, now=None):
        return format_target_label(target, now)

    def _set_icon(self):
        try:
            if os.path.exists(_ICON_PATH):
                self.master.iconbitmap(_ICON_PATH)
        except Exception:
            logger.warning("设置窗口图标失败", exc_info=True)

    # ------------------------------------------------------------------
    # 窗口 chrome（委托 window_chrome）
    # ------------------------------------------------------------------

    def _start_drag(self, event):
        _chrome.start_drag(self, event)

    def _on_drag(self, event):
        _chrome.on_drag(self, event)

    def _center_window(self):
        _chrome.center_window(self)

    def _center_window_later(self):
        _chrome.center_window_later(self)

    def _set_window_rounded_corners(self):
        _chrome.set_rounded_corners(self)

    def _set_taskbar_visible(self):
        _chrome.set_taskbar(self)

    def _bring_full_to_front(self):
        _chrome.bring_full_to_front(self)

    # ------------------------------------------------------------------
    # 系统托盘 / 模式（委托 mode）
    # ------------------------------------------------------------------

    def _init_tray_icon(self):
        init_tray_icon(self, _ICON_PATH)

    def _show_full_mode(self):
        _mode.show_full_mode(self)

    def _has_tray(self):
        return _mode.has_tray(self)

    def _hide_to_tray(self):
        _mode.hide_to_tray(self)

    def _quit_app(self):
        self._save_config()
        stop_tray(self)
        self._destroy_mini_window()
        self.master.destroy()

    def _show_time_picker(self):
        # 仅 running 禁止改到期时间；paused / idle / finished 可开
        if self._inputs_locked():
            return
        show_time_picker(self)

    def _toggle_transparent_mode(self, event=None):
        """切换透明模式（Windows 色键抠色；macOS systemTransparent）。"""
        self._transparent_mode = not self._transparent_mode
        self._save_config()
        if self._is_mini:
            self._recreate_mini_window()
        refresh_tray_menu(self)
        return "break"

    def _toggle_mini_mode(self):
        _mode.toggle_mini_mode(self)

    def _switch_to_mini(self):
        _mode.switch_to_mini(self)

    def _switch_to_full(self):
        _mode.switch_to_full(self)

    def _create_mini_window(self):
        create_mini_window(self)

    def _destroy_mini_window(self):
        destroy_mini_window(self)

    def _recreate_mini_window(self):
        recreate_mini_window(self)

    def _sync_mini_state(self):
        sync_mini_state(self)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_styles(self):
        setup_styles(self)

    def _setup_ui(self):
        build_full_ui(self)

    def update_clock(self):
        now = datetime.now()
        self.current_time_label.config(text=now.strftime("%H:%M:%S"))
        if self.mini_time_label:
            self.mini_time_label.config(text=now.strftime("%H:%M"))
        self.master.after(next_second_delay_ms(), self.update_clock)

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


def main():
    ok, _ = acquire_single_instance()
    if not ok:
        brought = bring_existing_to_front()
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
    # macOS 用菜单栏，不依赖 pystray（避免与 Tk 双循环崩溃）
    if platform.system() != "Darwin":
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
        print("程序仍可运行，但托盘功能可能不可用。\n")

    root = tk.Tk()
    CountdownApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
