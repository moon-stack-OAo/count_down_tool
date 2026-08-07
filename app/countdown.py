# -*- coding: utf-8 -*-
"""倒计时控制器：状态机、tick、进度、结束提醒。"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import datetime

from app.timers import cancel_timer_attr
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
    inputs_locked_for_state,
    next_second_delay_ms,
    next_state,
    progress_ratio,
    remaining_seconds,
    target_from_duration,
    target_from_hms,
    validate_hms,
)
from services.tray import refresh_tray_menu

logger = logging.getLogger("count_down_tool")

# 类型注解用 Protocol；运行时仍为 CountdownApp
try:
    from app.protocols import CountdownHost
except ImportError:  # pragma: no cover
    CountdownHost = object  # type: ignore[misc, assignment]


class CountdownController:
    """持有 app 引用；状态字段仍挂在 app 上，保证外部 app.xxx 行为不变。"""

    def __init__(self, app: CountdownHost):
        self.app = app

    def set_state(self, action: str) -> str:
        """按动作推进状态机，并同步按钮文案与 running 标志。"""
        app = self.app
        app._state = next_state(action, app._state)
        app.running = app._state == STATE_RUNNING
        if app.btn_start:
            app.btn_start.config(text=button_text_for_state(app._state))
        self.apply_primary_button_style()
        self.apply_input_lock()
        refresh_tray_menu(app)
        return app._state

    def inputs_locked(self) -> bool:
        """仅 running 时锁定到期时间与快捷预设；paused 可改时间后按新目标继续。"""
        return inputs_locked_for_state(self.app._state)

    def clear_paused_remaining(self):
        """清空暂停冻结的剩余秒数。"""
        self.app._paused_remaining = None

    def apply_primary_button_style(self):
        """主按钮按状态切换样式：空闲 accent / 运行·暂停 warning / 完成 success。"""
        app = self.app
        btn = getattr(app, "btn_start", None)
        if not btn:
            return
        state = app._state
        if state in (STATE_RUNNING, STATE_PAUSED):
            style_name = "PrimaryRunning.TButton"
        elif state == STATE_FINISHED:
            style_name = "PrimaryFinished.TButton"
        else:
            style_name = "Accent.TButton"
        try:
            btn.config(style=style_name, text=button_text_for_state(state))
        except tk.TclError:
            logger.debug("主按钮样式切换失败", exc_info=True)

    def apply_input_lock(self):
        """按状态启用/禁用 Spinbox 与预设 chip；锁定时设置卡弱化。"""
        app = self.app
        locked = self.inputs_locked()
        spin_state = "disabled" if locked else "normal"
        for sb in getattr(app, "_time_spinboxes", None) or []:
            try:
                sb.config(state=spin_state)
            except tk.TclError:
                logger.debug("设置 Spinbox 状态失败", exc_info=True)

        chips = getattr(app, "_preset_chips", None) or []
        c = app.COLORS
        for btn in chips:
            try:
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")
                btn.unbind("<Button-1>")
            except tk.TclError:
                logger.debug("预设 chip 解绑事件失败", exc_info=True)
            if locked:
                try:
                    btn.config(
                        bg=c.get("btn_default", c["chip"]),
                        fg=c["text_muted"],
                        cursor="arrow",
                    )
                except tk.TclError:
                    logger.debug("预设 chip 禁用样式失败", exc_info=True)
            else:
                hms = getattr(btn, "_preset_hms", None)
                try:
                    btn.config(bg=c["chip"], fg=c.get("text_dim", c["text"]), cursor="hand2")
                    btn.bind(
                        "<Enter>",
                        lambda e, b=btn: b.config(
                            bg=c["chip_hover"], fg=c["accent_glow"]
                        ),
                    )
                    btn.bind(
                        "<Leave>",
                        lambda e, b=btn: b.config(
                            bg=c["chip"], fg=c.get("text_dim", c["text"])
                        ),
                    )
                    if hms is not None:
                        hh, mm, ss = hms
                        btn.bind(
                            "<Button-1>",
                            lambda e, h=hh, m=mm, s=ss: self.set_preset_time(h, m, s),
                        )
                except tk.TclError:
                    logger.debug("预设 chip 启用失败", exc_info=True)

        # 设置卡锁定时整体弱化（不改布局，只调色）
        card = getattr(app, "_settings_card", None)
        if card is not None:
            try:
                border = c.get("border", c.get("card_border", c["chip"]))
                if locked:
                    card.configure_colors(
                        bg_color=c.get("card", c["glass"]),
                        border_color=border,
                    )
                else:
                    card.configure_colors(
                        bg_color=c.get("card", c["glass"]),
                        border_color=c.get("card_border", border),
                    )
            except (tk.TclError, AttributeError, KeyError, TypeError):
                logger.debug("设置卡锁定样式失败", exc_info=True)

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
        """在 Canvas 上绘制细进度条；完成态用 success 色。"""
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
            fill_color = (
                c.get("success", c["accent"])
                if app._state == STATE_FINISHED
                else c["accent"]
            )
            canvas.itemconfig(fill_id, fill=fill_color)
            track_id = getattr(app, "_progress_track_id", None)
            if track_id is not None:
                canvas.itemconfig(
                    track_id, fill=c.get("border", c.get("card_border", c["chip"]))
                )
                canvas.coords(track_id, 0, 0, w, h)
        except (tk.TclError, TypeError, ValueError, KeyError, AttributeError):
            logger.debug("绘制进度条失败", exc_info=True)

    def remember_last_hms(self, *, save: bool = True) -> None:
        """把当前 spinbox 时分秒记入持久化字段（可选写盘）。"""
        app = self.app
        try:
            h = int(str(app.hour_var.get()).strip())
            m = int(str(app.minute_var.get()).strip())
            s = int(str(app.second_var.get()).strip())
        except (ValueError, TypeError, AttributeError, tk.TclError):
            return
        ok, _ = validate_hms(h, m, s)
        if not ok:
            return
        app._last_hour = f"{h:02d}"
        app._last_minute = f"{m:02d}"
        app._last_second = f"{s:02d}"
        if save and hasattr(app, "_save_config"):
            try:
                app._save_config()
            except (OSError, TypeError, ValueError, AttributeError):
                logger.debug("保存 last_hms 失败", exc_info=True)

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
            # 暂停中改时间：丢弃冻结剩余，继续时按新 target 走
            if app._state == STATE_PAUSED:
                self.clear_paused_remaining()
            app.target_time_label.config(text=format_target_label(target, now))
            # 用户改时间时记住默认到期时刻（不频繁写盘：仅内存）
            if not app._applying_preset:
                self.remember_last_hms(save=False)
        except (ValueError, TypeError, tk.TclError):
            # 输入中间态（空/非数字）时静默
            pass

    def toggle_countdown(self):
        app = self.app
        if app._state == STATE_FINISHED:
            self.restart_countdown()
            return
        if app._state == STATE_RUNNING:
            self.pause_countdown()
        elif app._state == STATE_PAUSED:
            self.resume_countdown()
        else:
            self.start_countdown()
        app._sync_mini_state()

    def pause_countdown(self):
        """暂停：取消 tick，UI 冻结为暂停瞬间的剩余；目标时刻保持不变。"""
        app = self.app
        cancel_timer_attr(app, "_countdown_timer_id")
        now = datetime.now()
        if app.target_time is not None:
            rem = remaining_seconds(app.target_time, now)
        else:
            rem = 0.0
        # 仅用于暂停态展示；继续时按原 target 相对 now 重算
        app._paused_remaining = rem
        app.countdown_text = format_remaining(int(rem))
        if app.countdown_label:
            app.countdown_label.config(
                text=app.countdown_text, style="Countdown.TLabel"
            )
        self.update_progress_from_remaining(rem)
        self.set_state(ACTION_PAUSE)

    def resume_countdown(self):
        """继续：保留原 target_time，按 now 重算剩余；已过目标则直接结束。"""
        app = self.app
        app._paused_remaining = None
        now = datetime.now()
        if app.target_time is not None:
            if app.target_time_label:
                app.target_time_label.config(
                    text=format_target_label(app.target_time, now)
                )
            self.set_state(ACTION_RESUME)
            # update_countdown 内部用 target − now；≤0 会走结束逻辑
            self.update_countdown(app.target_time)
        else:
            self.start_countdown()

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
        self.clear_paused_remaining()
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
        if app._state == STATE_PAUSED and app._paused_remaining is not None:
            self.resume_countdown()
            return
        if not self.validate_inputs():
            self.set_state(ACTION_START_FAIL)
            return
        self.clear_paused_remaining()
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
        self.remember_last_hms(save=True)
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

        cancel_timer_attr(app, "_countdown_timer_id")

        rem_sec = remaining_seconds(target_time, datetime.now())
        if rem_sec <= 0:
            self.clear_paused_remaining()
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
        try:
            self.flash_visual()
        except (tk.TclError, AttributeError, KeyError, TypeError):
            logger.warning("视觉闪烁失败", exc_info=True)
        try:
            self.notify_finished()
        except Exception:
            # 托盘/系统通知边界：异常类型平台相关
            logger.warning("结束通知失败", exc_info=True)
        try:
            self.ring_bell()
        except Exception:
            # 音效后端（winsound/afplay 等）边界
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
                # 托盘原生 API 边界
                logger.debug("托盘 notify 失败", exc_info=True)
        try:
            def _tip():
                from ui.app_dialogs import show_info

                show_info(app, message, title=title)

            app.master.after(0, _tip)
        except (tk.TclError, RuntimeError, AttributeError):
            logger.debug("结束通知弹窗失败", exc_info=True)

    def ring_bell(self):
        """结束提示音：文件类完整播 1 次；系统铃循环 3 次；静音跳过。"""
        app = self.app
        from services.sound import play_finish_sound_async

        play_finish_sound_async(
            app.master,
            muted=bool(getattr(app, "_sound_muted", False)),
            sound_id=str(getattr(app, "_sound_id", "soft") or "soft"),
            custom_path=str(getattr(app, "_sound_path", "") or ""),
        )

    def flash_visual(self):
        app = self.app
        if not app.countdown_label:
            return
        # 样式在 setup_styles 预注册；此处只切换，避免每次 ttk.Style + configure
        flash_style = (
            "FlashEven.TLabel"
            if app._alarm_count % 2 == 0
            else "FlashOdd.TLabel"
        )
        app.countdown_label.config(style=flash_style)
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
        app._preset_duration = None
        self.clear_paused_remaining()
        app._duration_total_seconds = 0.0
        app._progress_value = 0.0
        cancel_timer_attr(app, "_alarm_timer_id")
        cancel_timer_attr(app, "_countdown_timer_id")
        self.set_state(ACTION_RESET)
        app.target_time = None
        # 恢复上次到期时分秒（无记录则 18:00:00）
        h = str(getattr(app, "_last_hour", "18") or "18")
        m = str(getattr(app, "_last_minute", "00") or "00")
        s = str(getattr(app, "_last_second", "00") or "00")
        try:
            app.hour_var.set(h)
            app.minute_var.set(m)
            app.second_var.set(s)
        except (tk.TclError, AttributeError):
            pass
        app.countdown_text = "--:--:--"
        try:
            app.countdown_label.config(text="--:--:--", style="Countdown.TLabel")
            app.error_label.config(text="")
        except (tk.TclError, AttributeError):
            pass
        self.draw_progress_bar(0.0)
        app._sync_mini_state()

    def set_preset_time(self, hours, minutes, seconds, *, force: bool = False):
        """快捷预设：写入目标后走状态机开始（与正常 START/RESTART 一致）。

        force=True 时允许 running 下强制重启（托盘「快捷开始」）；主界面 chip 仍受锁。
        """
        app = self.app
        if self.inputs_locked() and not force:
            return
        now = datetime.now()
        target, duration = target_from_duration(hours, minutes, seconds, now)
        app._preset_duration = duration
        self.clear_paused_remaining()

        self.apply_target_to_spinboxes(target)
        app.target_time = target
        if app.target_time_label:
            app.target_time_label.config(text=format_target_label(target, now))

        cancel_timer_attr(app, "_countdown_timer_id")

        self.record_duration_total(target, now)
        # 禁止直接写 _state；idle→START，finished→RESTART；
        # paused→RESUME；running+force 时 START 非法转换保持 running
        if app._state == STATE_FINISHED:
            self.set_state(ACTION_RESTART)
        elif app._state == STATE_PAUSED:
            self.set_state(ACTION_RESUME)
        else:
            # idle→running；running+force 保持 running
            self.set_state(ACTION_START)
        self.remember_last_hms(save=True)
        self.update_countdown(target)
        app._sync_mini_state()
