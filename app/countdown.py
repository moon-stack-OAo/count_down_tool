# -*- coding: utf-8 -*-
"""倒计时控制器：状态机、tick、进度、结束提醒。"""

from __future__ import annotations

import logging
from datetime import datetime
from tkinter import messagebox, ttk

from core.countdown_core import (
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
    next_second_delay_ms,
    next_state,
    progress_ratio,
    target_from_duration,
    target_from_hms,
    validate_hms,
)
from services.tray import refresh_tray_menu

logger = logging.getLogger("count_down_tool")


class CountdownController:
    """持有 app 引用；状态字段仍挂在 app 上，保证外部 app.xxx 行为不变。"""

    def __init__(self, app):
        self.app = app

    def set_state(self, action: str) -> str:
        """按动作推进状态机，并同步按钮文案与 running 标志。"""
        app = self.app
        app._state = next_state(action, app._state)
        app.running = app._state == STATE_RUNNING
        if app.btn_start:
            app.btn_start.config(text=button_text_for_state(app._state))
        self.apply_input_lock()
        refresh_tray_menu(app)
        return app._state

    def inputs_locked(self) -> bool:
        """仅 running 时锁定到期时间与快捷预设；暂停后可改时间。"""
        return self.app._state == STATE_RUNNING

    def apply_input_lock(self):
        """按状态启用/禁用 Spinbox 与预设 chip。"""
        app = self.app
        locked = self.inputs_locked()
        spin_state = "disabled" if locked else "normal"
        for sb in getattr(app, "_time_spinboxes", None) or []:
            try:
                sb.config(state=spin_state)
            except Exception:
                logger.debug("设置 Spinbox 状态失败", exc_info=True)

        chips = getattr(app, "_preset_chips", None) or []
        c = app.COLORS
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
                            lambda e, h=hh, m=mm, s=ss: self.set_preset_time(h, m, s),
                        )
                except Exception:
                    logger.debug("预设 chip 启用失败", exc_info=True)

    def record_duration_total(self, target_time, now=None):
        """成功开始/重启时记录总时长（秒）。"""
        app = self.app
        if now is None:
            now = datetime.now()
        if app._preset_duration is not None:
            total = app._preset_duration.total_seconds()
        elif target_time is not None:
            total = (target_time - now).total_seconds()
        else:
            total = 0.0
        app._duration_total_seconds = max(0.0, float(total))
        app._progress_value = 0.0

    def update_progress_from_remaining(self, remaining_seconds: float):
        """根据剩余秒数刷新进度（running 时调用）。"""
        app = self.app
        app._progress_value = progress_ratio(
            remaining_seconds, app._duration_total_seconds
        )
        self.draw_progress_bar(app._progress_value)

    def refresh_progress_bar(self):
        """按状态绘制进度：idle=0，finished=1，paused/running 用缓存值。"""
        app = self.app
        if app._state == STATE_IDLE:
            app._progress_value = 0.0
        elif app._state == STATE_FINISHED:
            app._progress_value = 1.0
        self.draw_progress_bar(app._progress_value)

    def draw_progress_bar(self, ratio: float):
        """在 Canvas 上绘制细进度条。"""
        app = self.app
        canvas = getattr(app, "progress_canvas", None)
        fill_id = getattr(app, "_progress_fill_id", None)
        if not canvas or fill_id is None:
            return
        try:
            w = float(getattr(app, "_progress_bar_w", 280) or 280)
            h = float(getattr(app, "_progress_bar_h", 4) or 4)
            r = max(0.0, min(1.0, float(ratio)))
            fill_w = w * r
            canvas.coords(fill_id, 0, 0, fill_w, h)
            c = app.COLORS
            canvas.itemconfig(fill_id, fill=c["accent"])
            track_id = getattr(app, "_progress_track_id", None)
            if track_id is not None:
                canvas.itemconfig(
                    track_id, fill=c.get("border", c.get("card_border", c["chip"]))
                )
                canvas.coords(track_id, 0, 0, w, h)
        except Exception:
            logger.debug("绘制进度条失败", exc_info=True)

    def on_time_changed(self, *args):
        """当用户修改时间时，实时更新目标时间显示。"""
        app = self.app
        if not app._applying_preset:
            app._preset_duration = None
        try:
            h = int(app.hour_var.get())
            m = int(app.minute_var.get())
            s = int(app.second_var.get())
            ok, _ = validate_hms(h, m, s)
            if not ok:
                app.target_time_label.config(text="")
                return
            now = datetime.now()
            target = target_from_hms(h, m, s, now)
            app.target_time = target
            app.target_time_label.config(text=format_target_label(target, now))
        except ValueError:
            pass

    def toggle_countdown(self):
        app = self.app
        if app._state == STATE_FINISHED:
            self.restart_countdown()
            return
        if app._state == STATE_RUNNING:
            if app._countdown_timer_id is not None:
                try:
                    app.master.after_cancel(app._countdown_timer_id)
                except Exception:
                    logger.debug("暂停时取消倒计时定时器失败", exc_info=True)
                app._countdown_timer_id = None
            self.set_state(ACTION_PAUSE)
        elif app._state == STATE_PAUSED:
            self.set_state(ACTION_RESUME)
            if app.target_time:
                self.update_countdown(app.target_time)
            else:
                self.start_countdown()
        else:
            self.start_countdown()
        app._sync_mini_state()

    def apply_target_to_spinboxes(self, target):
        app = self.app
        app._applying_preset = True
        try:
            app.hour_var.set(f"{target.hour:02d}")
            app.minute_var.set(f"{target.minute:02d}")
            app.second_var.set(f"{target.second:02d}")
        finally:
            app._applying_preset = False

    def restart_countdown(self):
        app = self.app
        if app._preset_duration is not None:
            now = datetime.now()
            target = now + app._preset_duration
            self.apply_target_to_spinboxes(target)
            app.target_time = target
            app.target_time_label.config(text=format_target_label(target, now))
            self.record_duration_total(target, now)
            self.set_state(ACTION_RESTART)
            self.update_countdown(target)
            app._sync_mini_state()
            return
        if not self.validate_inputs():
            return
        target = self.get_target_time()
        if not target:
            return
        app.target_time = target
        self.record_duration_total(target)
        self.set_state(ACTION_RESTART)
        self.update_countdown(app.target_time)
        app._sync_mini_state()

    def start_countdown(self):
        app = self.app
        if not self.validate_inputs():
            self.set_state(ACTION_START_FAIL)
            return
        app.target_time = self.get_target_time()
        if not app.target_time:
            self.set_state(ACTION_START_FAIL)
            return
        if app._state in (STATE_IDLE, STATE_FINISHED):
            self.record_duration_total(app.target_time)
        if app._state == STATE_IDLE:
            self.set_state(ACTION_START)
        elif app._state == STATE_PAUSED:
            self.set_state(ACTION_RESUME)
        elif app._state == STATE_FINISHED:
            self.set_state(ACTION_RESTART)
        self.update_countdown(app.target_time)

    def validate_inputs(self):
        app = self.app
        ok, err = validate_hms(
            app.hour_var.get(),
            app.minute_var.get(),
            app.second_var.get(),
        )
        if not ok:
            app.show_error(err or "请输入有效数字")
            return False
        return True

    def get_target_time(self):
        app = self.app
        try:
            return target_from_hms(
                int(app.hour_var.get()),
                int(app.minute_var.get()),
                int(app.second_var.get()),
            )
        except ValueError as e:
            app.show_error(str(e))
            return None

    def update_countdown(self, target_time):
        app = self.app
        if not app.running:
            return

        if app._countdown_timer_id is not None:
            try:
                app.master.after_cancel(app._countdown_timer_id)
            except Exception:
                logger.debug("取消倒计时定时器失败", exc_info=True)
            app._countdown_timer_id = None

        remaining = target_time - datetime.now()
        rem_sec = remaining.total_seconds()
        if rem_sec <= 0:
            app.countdown_text = "已到时间!"
            app.countdown_label.config(text="已到时间!", style="Success.TLabel")
            app._progress_value = 1.0
            self.draw_progress_bar(1.0)
            self.set_state(ACTION_FINISH)
            app._sync_mini_state()
            self.on_countdown_finished()
            app._countdown_timer_id = None
            return

        total_seconds = int(rem_sec)
        app.countdown_text = format_remaining(total_seconds)
        app.countdown_label.config(text=app.countdown_text, style="Countdown.TLabel")
        self.update_progress_from_remaining(rem_sec)
        app._sync_mini_state()

        app._countdown_timer_id = app.master.after(
            next_second_delay_ms(), lambda: self.update_countdown(target_time)
        )

    def on_countdown_finished(self):
        """结束提醒：闪烁 + 通知 + 提示音。失败只 log。"""
        app = self.app
        app._alarm_count = 0
        app._bell_count = 0
        try:
            self.flash_visual()
        except Exception:
            logger.warning("视觉闪烁失败", exc_info=True)
        try:
            self.notify_finished()
        except Exception:
            logger.warning("结束通知失败", exc_info=True)
        try:
            self.ring_bell()
        except Exception:
            logger.warning("提示音失败", exc_info=True)

    def notify_finished(self):
        app = self.app
        title = APP_NAME
        message = "倒计时已结束"
        if app.tray_icon is not None:
            try:
                app.tray_icon.notify(message, title)
                return
            except Exception:
                logger.debug("托盘 notify 失败", exc_info=True)
        try:
            app.master.after(
                0, lambda: messagebox.showinfo(title, message, parent=app.master)
            )
        except Exception:
            logger.debug("messagebox 通知失败", exc_info=True)

    def ring_bell(self):
        """响铃 2~3 次，间隔约 400ms。"""
        app = self.app
        try:
            app.master.bell()
        except Exception:
            logger.debug("bell 失败", exc_info=True)
        app._bell_count += 1
        if app._bell_count < 3:
            app.master.after(400, self.ring_bell)

    def flash_visual(self):
        app = self.app
        if not app.countdown_label:
            return
        style = ttk.Style()
        fg = (
            app.COLORS["success"]
            if app._alarm_count % 2 == 0
            else app.COLORS["error"]
        )
        style.configure(
            "Flash.TLabel",
            font=app.FONTS["countdown"],
            foreground=fg,
            background=app.COLORS["glass"],
        )
        app.countdown_label.config(style="Flash.TLabel")
        app._alarm_count += 1
        if app._alarm_count >= 6:
            app.countdown_label.config(style="Countdown.TLabel")
            app._alarm_count = 0
            app._alarm_timer_id = None
            return
        app._alarm_timer_id = app.master.after(500, self.flash_visual)

    def reset(self):
        app = self.app
        app._alarm_count = 0
        app._bell_count = 0
        app._preset_duration = None
        app._duration_total_seconds = 0.0
        app._progress_value = 0.0
        if app._alarm_timer_id is not None:
            try:
                app.master.after_cancel(app._alarm_timer_id)
            except Exception:
                logger.debug("取消报警定时器失败", exc_info=True)
            app._alarm_timer_id = None
        if app._countdown_timer_id is not None:
            try:
                app.master.after_cancel(app._countdown_timer_id)
            except Exception:
                logger.debug("重置时取消倒计时定时器失败", exc_info=True)
            app._countdown_timer_id = None
        self.set_state(ACTION_RESET)
        app.target_time = None
        app.hour_var.set("18")
        app.minute_var.set("00")
        app.second_var.set("00")
        app.countdown_text = "--:--:--"
        app.countdown_label.config(text="--:--:--", style="Countdown.TLabel")
        app.error_label.config(text="")
        self.draw_progress_bar(0.0)
        app._sync_mini_state()

    def set_preset_time(self, hours, minutes, seconds):
        app = self.app
        if self.inputs_locked():
            return
        now = datetime.now()
        target, duration = target_from_duration(hours, minutes, seconds, now)
        app._preset_duration = duration

        self.apply_target_to_spinboxes(target)
        app.target_time = target
        app.target_time_label.config(text=format_target_label(target, now))

        if app._countdown_timer_id is not None:
            try:
                app.master.after_cancel(app._countdown_timer_id)
            except Exception:
                logger.debug("预设时取消倒计时定时器失败", exc_info=True)
            app._countdown_timer_id = None

        self.record_duration_total(target, now)
        app._state = STATE_RUNNING
        app.running = True
        if app.btn_start:
            app.btn_start.config(text=button_text_for_state(STATE_RUNNING))
        self.apply_input_lock()
        refresh_tray_menu(app)
        self.update_countdown(target)
        app._sync_mini_state()
