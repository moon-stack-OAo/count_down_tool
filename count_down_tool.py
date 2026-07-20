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
from tkinter import ttk, messagebox

from autostart import is_autostart_enabled
from countdown_core import (
    ACTION_FINISH,
    ACTION_PAUSE,
    ACTION_RESET,
    ACTION_RESTART,
    ACTION_RESUME,
    ACTION_START,
    ACTION_START_FAIL,
    APP_NAME,
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
    progress_ratio,
    resource_path,
    save_config_dict,
    target_from_duration,
    target_from_hms,
    user_config_path,
    validate_hms,
)
from services.tray import HAS_PYSTRAY, init_tray_icon, refresh_tray_menu, stop_tray
from services.windows_native import (
    acquire_single_instance,
    bring_existing_to_front,
    set_taskbar_visible,
    set_window_rounded_corners,
)
from themes import DEFAULT_THEME_ID, resolve_theme
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

_ICON_PATH = resource_path("count_down_tool.ico")


class CountdownApp:
    WINDOW_WIDTH = 500
    WINDOW_HEIGHT = 520
    MINI_WIDTH = 236
    MINI_HEIGHT = 48
    # macOS Retina / Tk 点阵下 Mini 易偏小，约为 Windows 的 2.5 倍
    MINI_WIDTH_MAC = 590
    MINI_HEIGHT_MAC = 120
    TITLE_DRAG_EXCLUDE_RIGHT = 190
    PICKER_WIDTH = 320
    PICKER_HEIGHT = 240
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

        self.FONTS = self._get_fonts()

        # Mini 模式相关
        self._is_mini = False
        self.mini_window = None
        self.mini_countdown_label = None
        self.mini_time_label = None
        self._transparent_mode = False
        self._last_mode = "full"
        self._drag_data = {"x": 0, "y": 0}

        # 主题 / 自启
        self._theme_id = DEFAULT_THEME_ID
        self._theme_custom = None
        self._autostart = False
        self.COLORS = resolve_theme(self._theme_id)

        # 倒计时状态（完整和 mini 共享）
        self.target_time = None
        self.countdown_text = "--:--:--"

        self._mini_pos = None  # 保存 Mini 窗口位置
        self._config_file = user_config_path()
        self._load_config()
        self.master.configure(bg=self.COLORS["bg"])

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
                "mini_time": ("Menlo", 25, "bold"),
                "mini_countdown": ("Menlo", 40, "bold"),
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
            # 主题
            tid = config.get("theme_id")
            if isinstance(tid, str) and tid:
                self._theme_id = tid
            custom = config.get("theme_custom")
            self._theme_custom = custom if isinstance(custom, dict) else None
            self.COLORS = resolve_theme(self._theme_id, self._theme_custom)
            # 开机自启：以系统真实状态为准，并回写配置保持一致
            real_autostart = is_autostart_enabled()
            self._autostart = real_autostart
            if config.get("autostart") is not None and bool(config.get("autostart")) != real_autostart:
                try:
                    cfg = merge_config(config, autostart=real_autostart)
                    save_config_dict(self._config_file, cfg)
                except Exception:
                    logger.debug("回写 autostart 配置失败", exc_info=True)
        except Exception:
            logger.exception("读取配置失败")
            self._mini_pos = None
            self.COLORS = resolve_theme(self._theme_id, self._theme_custom)

    def _save_config(self):
        try:
            config = load_config_dict(self._config_file)
            config = merge_mini_position(config, self._mini_pos)
            mode = "mini" if self._is_mini else "full"
            config = merge_config(
                config,
                transparent_mode=bool(self._transparent_mode),
                last_mode=mode,
                theme_id=self._theme_id,
                autostart=bool(self._autostart),
            )
            if self._theme_custom is not None:
                config = merge_config(config, theme_custom=self._theme_custom)
            save_config_dict(self._config_file, config)
        except Exception:
            logger.exception("保存配置失败")

    def _apply_theme(self, theme_id: str):
        """切换预设主题并重建主界面（保留业务状态）。"""
        if theme_id == self._theme_id and self.COLORS:
            # 同 id 仍允许强制刷新（例如 custom 变更）；此处无 custom UI，直接跳过
            pass
        # 保存 UI 输入与倒计时显示
        saved_h = saved_m = saved_s = None
        try:
            if getattr(self, "hour_var", None) is not None:
                saved_h = self.hour_var.get()
                saved_m = self.minute_var.get()
                saved_s = self.second_var.get()
        except Exception:
            pass
        saved_countdown = self.countdown_text
        saved_target = self.target_time
        was_mini = self._is_mini

        self._theme_id = theme_id
        self.COLORS = resolve_theme(self._theme_id, self._theme_custom)
        self.master.configure(bg=self.COLORS["bg"])
        self._setup_styles()

        # Mini 先正规销毁（保存位置），再清空主界面
        if was_mini:
            self._destroy_mini_window()
        for child in list(self.master.winfo_children()):
            try:
                child.destroy()
            except Exception:
                logger.debug("销毁子控件失败", exc_info=True)
        self.btn_start = None
        self.current_time_label = None
        self.target_time_label = None
        self.countdown_label = None
        self.error_label = None
        self.progress_canvas = None
        self._time_spinboxes = []
        self._preset_chips = []

        self._setup_ui()

        # 恢复输入与显示
        self._applying_preset = True
        try:
            if saved_h is not None:
                self.hour_var.set(saved_h)
                self.minute_var.set(saved_m)
                self.second_var.set(saved_s)
        finally:
            self._applying_preset = False

        self.target_time = saved_target
        self.countdown_text = saved_countdown
        if self.btn_start:
            self.btn_start.config(text=button_text_for_state(self._state))
        if self.countdown_label:
            if self._state == STATE_FINISHED and saved_countdown:
                self.countdown_label.config(text=saved_countdown, style="Success.TLabel")
            else:
                self.countdown_label.config(
                    text=saved_countdown or "--:--:--",
                    style="Countdown.TLabel",
                )
        try:
            self._on_time_changed()
        except Exception:
            logger.debug("主题切换后刷新目标时间失败", exc_info=True)

        # 主题重建后按状态恢复锁定与进度
        self._apply_input_lock()
        self._refresh_progress_bar()

        # Mini 开着则按新颜色重建
        if was_mini:
            self._is_mini = True
            self._create_mini_window()

        self._save_config()
        refresh_tray_menu(self)

    def _set_state(self, action: str) -> str:
        """按动作推进状态机，并同步按钮文案与 running 标志。"""
        self._state = next_state(action, self._state)
        self.running = self._state == STATE_RUNNING
        if self.btn_start:
            self.btn_start.config(text=button_text_for_state(self._state))
        self._apply_input_lock()
        refresh_tray_menu(self)
        return self._state

    def _inputs_locked(self) -> bool:
        """running / paused 时锁定到期时间与快捷预设。"""
        return self._state in (STATE_RUNNING, STATE_PAUSED)

    def _apply_input_lock(self):
        """按状态启用/禁用 Spinbox 与预设 chip。"""
        locked = self._inputs_locked()
        spin_state = "disabled" if locked else "normal"
        for sb in getattr(self, "_time_spinboxes", None) or []:
            try:
                sb.config(state=spin_state)
            except Exception:
                logger.debug("设置 Spinbox 状态失败", exc_info=True)

        chips = getattr(self, "_preset_chips", None) or []
        c = self.COLORS
        for btn in chips:
            try:
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")
                btn.unbind("<Button-1>")
            except Exception:
                pass
            if locked:
                try:
                    btn.config(
                        bg=c.get("btn_default", c["chip"]),
                        fg=c["text_muted"],
                        cursor="arrow",
                    )
                except Exception:
                    logger.debug("预设 chip 禁用样式失败", exc_info=True)
            else:
                hms = getattr(btn, "_preset_hms", None)
                try:
                    btn.config(bg=c["chip"], fg=c["text"], cursor="hand2")
                    btn.bind(
                        "<Enter>",
                        lambda e, b=btn: b.config(
                            bg=c["chip_hover"], fg=c["accent_glow"]
                        ),
                    )
                    btn.bind(
                        "<Leave>",
                        lambda e, b=btn: b.config(bg=c["chip"], fg=c["text"]),
                    )
                    if hms is not None:
                        hh, mm, ss = hms
                        btn.bind(
                            "<Button-1>",
                            lambda e, h=hh, m=mm, s=ss: self._set_preset_time(h, m, s),
                        )
                except Exception:
                    logger.debug("预设 chip 启用失败", exc_info=True)

    def _record_duration_total(self, target_time, now=None):
        """成功开始/重启时记录总时长（秒）。"""
        if now is None:
            now = datetime.now()
        if self._preset_duration is not None:
            total = self._preset_duration.total_seconds()
        elif target_time is not None:
            total = (target_time - now).total_seconds()
        else:
            total = 0.0
        self._duration_total_seconds = max(0.0, float(total))
        self._progress_value = 0.0

    def _update_progress_from_remaining(self, remaining_seconds: float):
        """根据剩余秒数刷新进度（running 时调用）。"""
        self._progress_value = progress_ratio(
            remaining_seconds, self._duration_total_seconds
        )
        self._draw_progress_bar(self._progress_value)

    def _refresh_progress_bar(self):
        """按状态绘制进度：idle=0，finished=1，paused/running 用缓存值。"""
        if self._state == STATE_IDLE:
            self._progress_value = 0.0
        elif self._state == STATE_FINISHED:
            self._progress_value = 1.0
        # paused / running：保持 _progress_value（暂停冻结）
        self._draw_progress_bar(self._progress_value)

    def _draw_progress_bar(self, ratio: float):
        """在 Canvas 上绘制细进度条。"""
        canvas = getattr(self, "progress_canvas", None)
        fill_id = getattr(self, "_progress_fill_id", None)
        if not canvas or fill_id is None:
            return
        try:
            w = float(getattr(self, "_progress_bar_w", 280) or 280)
            h = float(getattr(self, "_progress_bar_h", 4) or 4)
            r = max(0.0, min(1.0, float(ratio)))
            fill_w = w * r
            canvas.coords(fill_id, 0, 0, fill_w, h)
            c = self.COLORS
            canvas.itemconfig(fill_id, fill=c["accent"])
            track_id = getattr(self, "_progress_track_id", None)
            if track_id is not None:
                canvas.itemconfig(
                    track_id, fill=c.get("border", c.get("card_border", c["chip"]))
                )
                canvas.coords(track_id, 0, 0, w, h)
        except Exception:
            logger.debug("绘制进度条失败", exc_info=True)

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
        set_window_rounded_corners(self.master, self.CORNER_RADIUS)

    def _set_taskbar_visible(self):
        set_taskbar_visible(self.master)

    # ------------------------------------------------------------------
    # 系统托盘
    # ------------------------------------------------------------------

    def _init_tray_icon(self):
        init_tray_icon(self, _ICON_PATH)

    def _show_full_mode(self):
        """显示完整模式窗口"""
        if self._is_mini:
            self._switch_to_full()
        self.master.deiconify()
        self.master.lift()
        self.master.focus_force()

    def _has_tray(self):
        return bool(HAS_PYSTRAY and self.tray_icon)

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
        stop_tray(self)
        self._destroy_mini_window()
        self.master.destroy()

    def _show_time_picker(self):
        show_time_picker(self)

    def _toggle_transparent_mode(self, event=None):
        """切换透明模式（Windows 色键抠色；macOS systemTransparent）。"""
        self._transparent_mode = not self._transparent_mode
        self._save_config()
        if self._is_mini:
            self._recreate_mini_window()
        refresh_tray_menu(self)
        return "break"

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
        refresh_tray_menu(self)

    def _switch_to_full(self):
        """切换到完整模式"""
        self._is_mini = False
        self._last_mode = "full"
        self._destroy_mini_window()
        self.master.deiconify()
        self.master.lift()
        self._save_config()
        refresh_tray_menu(self)

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
            self._record_duration_total(target, now)
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
        self._record_duration_total(target)
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
        # 仅 idle / finished 重新记总时长；resume 保持原总时长与进度
        if self._state in (STATE_IDLE, STATE_FINISHED):
            self._record_duration_total(self.target_time)
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
        rem_sec = remaining.total_seconds()
        if rem_sec <= 0:
            self.countdown_text = "已到时间!"
            self.countdown_label.config(text="已到时间!", style="Success.TLabel")
            self._progress_value = 1.0
            self._draw_progress_bar(1.0)
            self._set_state(ACTION_FINISH)
            self._sync_mini_state()
            self._on_countdown_finished()
            self._countdown_timer_id = None
            return

        total_seconds = int(rem_sec)
        self.countdown_text = format_remaining(total_seconds)
        self.countdown_label.config(text=self.countdown_text, style="Countdown.TLabel")
        self._update_progress_from_remaining(rem_sec)

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
        self._duration_total_seconds = 0.0
        self._progress_value = 0.0
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
        self._draw_progress_bar(0.0)
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
        # running / paused 时锁定，忽略点击
        if self._inputs_locked():
            return
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

        # 预设直接进入 running（idle / finished 可切）
        self._record_duration_total(target, now)
        self._state = STATE_RUNNING
        self.running = True
        if self.btn_start:
            self.btn_start.config(text=button_text_for_state(STATE_RUNNING))
        self._apply_input_lock()
        self.update_countdown(target)
        self._sync_mini_state()


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
