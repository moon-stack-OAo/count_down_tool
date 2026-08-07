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
import sys
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from app import mode as _mode
from app import theme as _theme
from app import window_chrome as _chrome
from app.config_store import (
    default_mini_size as _cfg_default_mini_size,
)
from app.config_store import (
    load_config as _cfg_load,
)
from app.config_store import (
    mini_size_limits as _cfg_mini_size_limits,
)
from app.config_store import (
    mini_text_fg as _cfg_mini_text_fg,
)
from app.config_store import (
    resolved_mini_size as _cfg_resolved_mini_size,
)
from app.config_store import (
    save_config as _cfg_save,
)
from app.countdown import CountdownController
from app.host_bindings import install_state_properties
from app.state import CountdownRuntime, PersistedState
from app.timers import cancel_all_timers, cancel_timer_attr
from core.app_logging import setup_app_logging
from core.countdown_core import (
    APP_NAME,
    format_target_label,
    next_second_delay_ms,
    resource_path,
    should_start_mini,
    should_update_mini_clock,
    user_config_path,
)
from core.themes import DEFAULT_THEME_ID, resolve_theme
from services.tray import init_tray_icon, refresh_tray_menu, stop_tray
from services.windows_native import (
    SHOW_POLL_INTERVAL_MS,
    acquire_single_instance,
    bring_existing_to_front,
    clear_stale_show_request,
    consume_show_request,
    frozen_executable_path,
    path_has_mark_of_the_web,
    request_show_existing,
    try_remove_mark_of_the_web,
)
from ui.full_window import build_full_ui, setup_styles
from ui.mini_window import (
    create_mini_window,
    destroy_mini_window,
    recreate_mini_window,
    sync_mini_state,
)
from ui.time_picker import show_time_picker

# 尽早初始化，保证 main 前 import 阶段之外的运行日志可落盘
setup_app_logging()
logger = logging.getLogger("count_down_tool")

_ICON_PATH = resource_path(os.path.join("assets", "count_down_tool.ico"))


@install_state_properties
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
    TITLE_DRAG_EXCLUDE_RIGHT = 190
    PICKER_WIDTH = 420
    PICKER_HEIGHT = 440
    CORNER_RADIUS = 20
    MINI_MARGIN_RIGHT = 20
    MINI_MARGIN_BOTTOM = 60

    # 默认主题色（类级参考；运行时使用实例 self.COLORS）
    COLORS = resolve_theme(DEFAULT_THEME_ID)

    def __init__(self, master):
        self.current_time_label = None
        self.master = master
        self.master.title(APP_NAME)
        self.master.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        self.master.resizable(False, False)
        # macOS 不支持 overrideredirect，会导致窗口无法显示
        if platform.system() != "Darwin":
            self.master.overrideredirect(True)

        # 结构化状态：app._xxx 由 install_state_properties 绑定（duck-type 兼容）
        self.state = PersistedState()
        self._runtime = CountdownRuntime()

        self._set_icon()

        # 窗口拖动相关变量
        self._drag_x = 0
        self._drag_y = 0

        self.running = False
        self.btn_start = None
        self.tray_icon = None
        self._first_hide = True
        self._time_spinboxes = []
        self._preset_chips = []
        self.progress_canvas = None

        self.FONTS = self._get_fonts(self.master)
        self._ctrl = CountdownController(self)

        # services → UI 端口：托盘/更新等禁止直接 import ui
        from app.ui_actions import bind_default_ui_actions

        bind_default_ui_actions(self)

        # Mini 模式相关（非持久化 UI 句柄）
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
        self._drag_data = {"x": 0, "y": 0}

        self._pending_update_result = None  # 有更新时缓存，供标题 NEW 角标
        self.COLORS = resolve_theme(self.state.theme_id)

        # 倒计时状态（完整和 mini 共享）
        self.target_time = None
        self.countdown_text = "--:--:--"

        self._resize_data = None  # Mini 边缘缩放状态
        self._mini_sync_cache = None  # Mini 倒计时/字色上次同步快照
        self._mini_clock_hm = None  # Mini 时钟上次 "%H:%M"
        self._config_file = user_config_path()
        self._load_config()
        self.master.configure(bg=self.COLORS["bg"])

        # after 定时器 id（退出时由 cancel_all_timers 统一清理；须在首个 after 调度前初始化）
        self._show_poll_timer_id = None
        self._clock_timer_id = None
        self._mini_geo_save_id = None
        self._startup_health_timer_id = None
        self._startup_update_timer_id = None

        self._setup_styles()
        self._setup_ui()
        self._on_time_changed()
        self.update_clock()
        tray_ok = self._init_tray_icon()
        self._set_window_rounded_corners()
        self._set_taskbar_visible()
        self._center_window_later()
        # 启动模式：startup_mode + last_mode（见 should_start_mini）
        has_last = "last_mode" in getattr(self, "_loaded_keys", set())
        if should_start_mini(
                getattr(self, "_startup_mode", "remember"),
                self._last_mode,
                has_last_mode=has_last,
        ):
            self._switch_to_mini()
        # 二次启动唤醒：轮询 show.request（跨平台文件标志）
        self._start_show_request_poll()
        # 启动诊断：MOTW 解锁提示、托盘失败可见提示（延后避免挡启动动画）
        try:
            self._startup_health_timer_id = self.master.after(
                600, lambda: self._startup_health_hints(tray_ok)
            )
        except tk.TclError:
            self._startup_health_timer_id = None
            logger.debug("调度启动健康提示失败", exc_info=True)
        try:
            from services.updater import schedule_startup_check

            schedule_startup_check(self)
        except (ImportError, AttributeError, RuntimeError, OSError):
            logger.debug("调度启动更新检查失败", exc_info=True)

    def _startup_health_hints(self, tray_ok: bool) -> None:
        """启动后提示：网络解锁标记、托盘不可用。"""
        self._startup_health_timer_id = None
        try:
            from ui.app_dialogs import show_info
        except ImportError:
            return

        # 1) Mark of the Web：从 zip/下载拖出的 exe 常见
        if getattr(sys, "frozen", False) and platform.system() == "Windows":
            try:
                exe = frozen_executable_path()
                if path_has_mark_of_the_web(exe):
                    unlocked = try_remove_mark_of_the_web(exe)
                    if unlocked:
                        show_info(
                            self,
                            "已自动解除此程序的「来自网络」锁定标记。\n\n"
                            "若托盘或设置仍异常，请完全退出后重新打开。\n"
                            "建议：将 zip 完整解压到固定文件夹再运行，"
                            "不要在压缩包窗口内直接拖出运行。",
                            title="安全提示",
                        )
                    else:
                        show_info(
                            self,
                            "检测到程序可能仍带有「来自网络」锁定标记"
                            "（从压缩包拖出或下载后常见）。\n\n"
                            "请右键本程序 → 属性 → 勾选「解除锁定」→ 确定，"
                            "然后完全退出再重新打开。\n\n"
                            "建议：将 zip 完整解压到固定文件夹再运行。",
                            title="安全提示",
                        )
            except (OSError, AttributeError, TypeError, ValueError, tk.TclError):
                logger.debug("MOTW 检测失败", exc_info=True)

        # 2) 托盘失败：明确提示（勿静默）
        if platform.system() != "Darwin" and not tray_ok:
            detail = getattr(self, "_tray_init_error", "") or "未知原因"
            try:
                show_info(
                    self,
                    "系统托盘图标未能创建，托盘菜单将不可用。\n\n"
                    f"详情：{detail}\n\n"
                    "仍可通过完整窗口标题栏 ⚙ 打开设置。\n"
                    "若 ⚙ 也无反应：结束全部倒计时进程后重试；"
                    "检查 exe 是否已「解除锁定」。",
                    title="托盘不可用",
                )
            except (tk.TclError, AttributeError, RuntimeError):
                logger.debug("托盘失败提示失败", exc_info=True)

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

    def _show_settings(self):
        """打开设置中心（经 ui_actions，A5 已装配）。"""
        from app.ui_actions import call_ui

        call_ui(self, "show_settings", self)

    # ------------------------------------------------------------------
    # 倒计时（委托 CountdownController，保留 app.xxx 对外接口）
    # ------------------------------------------------------------------

    def _set_state(self, action: str) -> str:
        return self._ctrl.set_state(action)

    def _inputs_locked(self) -> bool:
        return self._ctrl.inputs_locked()

    def _apply_input_lock(self):
        self._ctrl.apply_input_lock()

    def _apply_primary_button_style(self):
        self._ctrl.apply_primary_button_style()

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

    def _set_preset_time(self, hours, minutes, seconds, *, force: bool = False):
        self._ctrl.set_preset_time(hours, minutes, seconds, force=force)

    def _format_target_label(self, target, now=None):
        return format_target_label(target, now)

    def _set_icon(self):
        try:
            if os.path.exists(_ICON_PATH):
                self.master.iconbitmap(_ICON_PATH)
        except (OSError, tk.TclError):
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
        return bool(init_tray_icon(self, _ICON_PATH))

    def _show_full_mode(self):
        _mode.show_full_mode(self)

    def _handle_external_show(self):
        _mode.handle_external_show(self)

    def _start_show_request_poll(self):
        """定时检查次实例写入的 show 请求。"""
        self._poll_show_request()

    def _poll_show_request(self):
        try:
            if consume_show_request():
                self._handle_external_show()
        except (OSError, tk.TclError, AttributeError, RuntimeError):
            logger.debug("轮询 show 请求失败", exc_info=True)
        try:
            self._show_poll_timer_id = self.master.after(
                SHOW_POLL_INTERVAL_MS, self._poll_show_request
            )
        except tk.TclError:
            self._show_poll_timer_id = None

    def _has_tray(self):
        return _mode.has_tray(self)

    def _hide_to_tray(self):
        _mode.hide_to_tray(self)

    def _quit_app(self):
        self._save_config()
        # destroy 前统一取消全部 after，避免幽灵回调 / TclError
        self._cancel_all_timers()
        stop_tray(self)
        self._destroy_mini_window()
        self.master.destroy()

    def _cancel_all_timers(self):
        """取消应用上登记的全部 master.after 定时器。"""
        cancel_all_timers(self)

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
        try:
            now = datetime.now()
            # 主窗时钟仍每秒更新（含秒）
            self.current_time_label.config(text=now.strftime("%H:%M:%S"))
            # Mini 仅显示 %H:%M：分钟未变则跳过 configure
            if self.mini_time_label:
                hm = now.strftime("%H:%M")
                if should_update_mini_clock(self._mini_clock_hm, hm):
                    self.mini_time_label.config(text=hm)
                    self._mini_clock_hm = hm
        except tk.TclError:
            # 窗口已毁时勿再调度
            self._clock_timer_id = None
            return
        try:
            self._clock_timer_id = self.master.after(
                next_second_delay_ms(), self.update_clock
            )
        except tk.TclError:
            self._clock_timer_id = None

    def show_error(self, message):
        cancel_timer_attr(self, "_error_timer_id")
        try:
            self.error_label.config(text=message)
            self._error_timer_id = self.master.after(3000, self._clear_error)
        except tk.TclError:
            self._error_timer_id = None
            logger.debug("显示错误提示失败", exc_info=True)

    def _clear_error(self):
        self._error_timer_id = None
        try:
            self.error_label.config(text="")
        except tk.TclError:
            pass


def main():
    setup_app_logging()
    logger.info("应用启动")
    ok, _ = acquire_single_instance()
    if not ok:
        logger.info("检测到已有实例，发送 show 请求")
        # 先发 show 请求（主实例轮询恢复），再尝试直接置前
        request_show_existing()
        brought = bring_existing_to_front()
        if not brought:
            # 给主实例一点时间消费请求；仍失败则提示
            try:
                time.sleep(0.5)
            except OSError:
                pass
            brought = bring_existing_to_front()
        if not brought:
            try:
                root = tk.Tk()
                root.withdraw()
                messagebox.showinfo(APP_NAME, f"{APP_NAME} 已在运行中。")
                root.destroy()
            except (tk.TclError, RuntimeError, OSError):
                logger.warning("单实例提示失败", exc_info=True)
                print(f"{APP_NAME} 已在运行中。")
        return

    clear_stale_show_request()

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
        logger.warning("缺少可选依赖: %s", ", ".join(missing))
        print(f"警告: 缺少可选依赖: {', '.join(missing)}")
        print(f"pip install {' '.join(missing)}")
        print("程序仍可运行，但托盘功能可能不可用。\n")

    root = tk.Tk()
    try:
        CountdownApp(root)
        logger.info("进入主循环")
        root.mainloop()
    except Exception:
        logger.exception("主循环异常退出")
        raise
    finally:
        logger.info("应用退出")


if __name__ == "__main__":
    main()
