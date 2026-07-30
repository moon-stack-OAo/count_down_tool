# -*- coding: utf-8 -*-
"""到期时间选择器弹窗（主题化卡片样式）。"""

import logging
import platform
import tkinter as tk

from core.countdown_core import ACTION_RESUME, STATE_PAUSED, STATE_RUNNING
from ui.design.tokens import SPACE_LG, SPACE_MD, SPACE_SM
from ui.widgets import RoundedFrame, init_circle_button, make_pill, update_circle_button
from ui.window_chrome_dialog import center_dialog_later, use_borderless_chrome

logger = logging.getLogger("count_down_tool")


def _picker_parent(app):
    """优先挂到当前可见窗口，避免主窗 withdraw + overrideredirect 导致子窗无法交互。"""
    if getattr(app, "_is_mini", False):
        mini = getattr(app, "mini_window", None)
        if mini is not None:
            try:
                if mini.winfo_exists():
                    return mini
            except tk.TclError:
                pass
    return app.master


def _activate_picker(win, *, topmost: bool = True):
    """将窗口置前。topmost=False 时只 lift/聚焦，不常驻 -topmost（设置中心用）。"""
    try:
        win.lift()
        if topmost:
            win.attributes("-topmost", True)
        else:
            # 明确关掉，避免此前被设过 topmost 后残留
            try:
                win.attributes("-topmost", False)
            except tk.TclError:
                pass
        win.focus_force()
    except tk.TclError:
        pass
    if platform.system() == "Windows":
        try:
            import ctypes

            win.update_idletasks()
            frame = win.wm_frame()
            hwnd = int(frame, 16) if frame else int(win.winfo_id())
            user32 = ctypes.windll.user32
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        except (OSError, AttributeError, ValueError, TypeError, tk.TclError):
            logger.debug("时间选择器置前失败", exc_info=True)


def _read_hms(app):
    def one(name, default):
        try:
            v = getattr(app, name, None)
            if v is not None:
                return max(0, int(v.get()))
        except (TypeError, ValueError, tk.TclError):
            pass
        return default

    h = min(23, one("hour_var", 18))
    m = min(59, one("minute_var", 0))
    s = min(59, one("second_var", 0))
    return h, m, s


def _bind_hover_bg(widget, normal, hover):
    widget.bind("<Enter>", lambda e: widget.config(bg=hover))
    widget.bind("<Leave>", lambda e: widget.config(bg=normal))


def _fit_picker_window(picker, shell, min_w, min_h, *, borderless: bool = False):

    """按内容请求尺寸调整窗口，并居中到工作区。"""
    try:
        picker.update_idletasks()
        need_w = max(min_w, shell.winfo_reqwidth() + 48)
        need_h = max(min_h, shell.winfo_reqheight() + 40)
        if not borderless and platform.system() == "Windows":
            need_h += 32
            need_w += 16
        if borderless:
            from ui.window_chrome_dialog import CHROME_TITLE_HEIGHT

            need_h += CHROME_TITLE_HEIGHT
        center_dialog_later(picker, int(need_w), int(need_h))
    except tk.TclError:
        pass


def show_time_picker(app):
    """弹出时间选择器（可输入 + 圆形 ▲▼ 调时，主题卡片布局）。"""
    parent = _picker_parent(app)
    picker = tk.Toplevel(parent)
    picker.title("选择时间")
    min_w = max(getattr(app, "PICKER_WIDTH", 400), 400)
    min_h = max(getattr(app, "PICKER_HEIGHT", 420), 420)
    picker.geometry(f"{min_w}x{min_h}")
    picker.resizable(False, False)
    c = app.COLORS
    picker.configure(bg=c["bg"])
    try:
        picker.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        if parent is not app.master or parent.winfo_viewable():
            picker.transient(parent)
    except tk.TclError:
        pass

    h0, m0, s0 = _read_hms(app)
    h_var = tk.IntVar(value=h0)
    m_var = tk.IntVar(value=m0)
    s_var = tk.IntVar(value=s0)

    # 占位：chrome 需要先绑关闭；确认/取消在后面定义
    closed = {"done": False}

    def cancel():
        if closed["done"]:
            return
        closed["done"] = True
        try:
            picker.grab_release()
        except tk.TclError:
            pass
        try:
            picker.destroy()
        except tk.TclError:
            pass

    borderless = use_borderless_chrome(
        picker, app, title="选择时间", on_close=cancel
    )

    shell = tk.Frame(picker, bg=c["bg"])
    shell.pack(fill=tk.BOTH, expand=True, padx=SPACE_LG, pady=SPACE_MD)

    # 标题
    header = tk.Frame(shell, bg=c["bg"])
    header.pack(fill=tk.X, pady=(0, 10))
    tk.Label(
        header,
        text="选择到期时间",
        font=app._font("button", 13, bold=True),
        bg=c["bg"],
        fg=c["text"],
    ).pack(anchor="w")
    tk.Label(
        header,
        text="可直接输入或点上下按钮调整，确认后开始计时",
        font=app._font("label", 9),
        bg=c["bg"],
        fg=c["text_muted"],
    ).pack(anchor="w", pady=(4, 0))
    tk.Frame(header, bg=c["accent"], height=2).pack(fill=tk.X, pady=(10, 0))

    # 主卡片：Canvas 子控件用 place；高度须盖住步进+数字+单位
    card = RoundedFrame(
        shell,
        bg_color=c["glass"],
        border_color=c["accent"],
        corner_radius=16,
        border_width=2,
        height=240,
    )
    card.pack(fill=tk.X, pady=(0, 12))
    card_inner = tk.Frame(card, bg=c["glass"])
    card_inner.place(relx=0.5, rely=0.5, anchor="center")

    units_row = tk.Frame(card_inner, bg=c["glass"])
    units_row.pack(expand=True)

    mono = app._font("time", 24)
    mono_colon = app._font("time", 22, bold=True)
    label_font = app._font("label", 9)
    font_family = mono[0] if isinstance(mono, (tuple, list)) else "Segoe UI"

    def _step_btn(parent_fr, on_click, symbol):
        r = 13
        size = r * 2 + 4
        canvas = tk.Canvas(
            parent_fr,
            width=size,
            height=size,
            bg=c["glass"],
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        canvas.pack(pady=1)
        ids = init_circle_button(
            canvas,
            size // 2,
            size // 2,
            r,
            fill=c["chip"],
            text=symbol,
            text_color=c["accent_glow"],
            font_family=font_family,
            font_size=9,
        )

        def enter(_e=None):
            update_circle_button(
                canvas, ids, fill=c["chip_hover"], text_color=c["accent_glow"]
            )

        def leave(_e=None):
            update_circle_button(
                canvas, ids, fill=c["chip"], text_color=c["accent_glow"]
            )

        canvas.bind("<Enter>", enter)
        canvas.bind("<Leave>", leave)
        canvas.bind("<Button-1>", lambda e: on_click())
        return canvas

    def _unit(parent_fr, var, maximum, unit_label):
        col = tk.Frame(parent_fr, bg=c["glass"])
        col.pack(side=tk.LEFT, padx=10)
        text_var = tk.StringVar(value=f"{int(var.get()):02d}")
        editing = {"active": False}

        def _clamp_int(raw):
            try:
                n = int(str(raw).strip())
            except (TypeError, ValueError):
                return 0
            return max(0, min(maximum, n))

        def bump(delta):
            editing["active"] = False
            cur = _clamp_int(var.get())
            var.set((cur + delta) % (maximum + 1))
            text_var.set(f"{int(var.get()):02d}")
            _sync_preview()

        def commit_entry(_e=None):
            editing["active"] = False
            n = _clamp_int(text_var.get())
            var.set(n)
            text_var.set(f"{n:02d}")
            _sync_preview()

        def on_key(_e=None):
            editing["active"] = True
            raw = text_var.get().strip()
            if raw == "":
                return
            if not raw.isdigit():
                cleaned = "".join(ch for ch in raw if ch.isdigit())[:2]
                text_var.set(cleaned)
                raw = cleaned
            if len(raw) > 2:
                text_var.set(raw[:2])
                raw = raw[:2]
            if raw.isdigit():
                n = int(raw)
                if n > maximum:
                    n = maximum
                    text_var.set(str(n))
                var.set(n)
                _sync_preview()

        def validate_key(new_value):
            if new_value == "":
                return True
            if not new_value.isdigit():
                return False
            if len(new_value) > 2:
                return False
            return int(new_value) <= maximum or len(new_value) < 2

        _step_btn(col, lambda: bump(1), "▲")

        val_wrap = tk.Frame(col, bg=c["input_bg"], padx=8, pady=4)
        val_wrap.pack(pady=4)
        vcmd = (picker.register(validate_key), "%P")
        entry = tk.Entry(
            val_wrap,
            textvariable=text_var,
            font=mono,
            bg=c["input_bg"],
            fg=c["text"],
            insertbackground=c["text"],
            relief=tk.FLAT,
            justify=tk.CENTER,
            width=3,
            bd=0,
            highlightthickness=0,
            validate="key",
            validatecommand=vcmd,
        )
        entry.pack()

        def on_return(_e=None):
            commit_entry()
            confirm()
            return "break"

        entry.bind("<FocusOut>", commit_entry)
        entry.bind("<Return>", on_return)
        entry.bind("<KeyRelease>", on_key)
        entry.bind("<MouseWheel>", lambda e: bump(1 if e.delta > 0 else -1))
        # Linux 滚轮
        entry.bind("<Button-4>", lambda e: bump(1))
        entry.bind("<Button-5>", lambda e: bump(-1))

        def on_write(*_):
            if editing["active"]:
                return
            try:
                text_var.set(f"{int(var.get()):02d}")
                _sync_preview()
            except (tk.TclError, ValueError, TypeError):
                pass

        var.trace_add("write", on_write)
        _step_btn(col, lambda: bump(-1), "▼")

        tk.Label(
            col,
            text=unit_label,
            font=label_font,
            bg=c["glass"],
            fg=c["text_dim"],
        ).pack(pady=(2, 0))
        return col

    def _colon():
        tk.Label(
            units_row,
            text=":",
            font=mono_colon,
            bg=c["glass"],
            fg=c["accent_glow"],
        ).pack(side=tk.LEFT, pady=(0, 14))

    _unit(units_row, h_var, 23, "时")
    _colon()
    _unit(units_row, m_var, 59, "分")
    _colon()
    _unit(units_row, s_var, 59, "秒")

    # 预览条
    preview_bar = tk.Frame(shell, bg=c["card"], padx=14, pady=10)
    preview_bar.pack(fill=tk.X, pady=(0, 14))
    tk.Label(
        preview_bar,
        text="目标",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
    ).pack(side=tk.LEFT)
    preview_lbl = tk.Label(
        preview_bar,
        text=f"{h0:02d}:{m0:02d}:{s0:02d}",
        font=app._font("time", 14, bold=True),
        bg=c["card"],
        fg=c["accent_glow"],
    )
    preview_lbl.pack(side=tk.RIGHT)

    def _sync_preview():
        try:
            preview_lbl.config(
                text=f"{int(h_var.get()):02d}:{int(m_var.get()):02d}:{int(s_var.get()):02d}"
            )
        except (tk.TclError, ValueError, TypeError):
            pass

    def confirm():
        if closed["done"]:
            return
        try:
            # 失焦提交：确保 Entry 中未确认的输入生效
            try:
                picker.focus_set()
            except tk.TclError:
                pass
            hh = max(0, min(23, int(h_var.get())))
            mm = max(0, min(59, int(m_var.get())))
            ss = max(0, min(59, int(s_var.get())))
            h_var.set(hh)
            m_var.set(mm)
            s_var.set(ss)
            app.hour_var.set(f"{hh:02d}")
            app.minute_var.set(f"{mm:02d}")
            app.second_var.set(f"{ss:02d}")
            closed["done"] = True
            try:
                picker.grab_release()
            except tk.TclError:
                pass
            picker.destroy()
            if app._state == STATE_RUNNING:
                return
            if app._state == STATE_PAUSED:
                if not app.validate_inputs():
                    return
                target = app.get_target_time()
                if not target:
                    return
                app.target_time = target
                app._record_duration_total(target)
                app._set_state(ACTION_RESUME)
                app.update_countdown(target)
                app._sync_mini_state()
            else:
                app.toggle_countdown()
        except (ValueError, TypeError, tk.TclError):
            logger.debug("时间选择器输入无效", exc_info=True)

    btn_row = tk.Frame(shell, bg=c["bg"])
    btn_row.pack(pady=(0, 4))
    btn_inner = tk.Frame(btn_row, bg=c["bg"])
    btn_inner.pack()

    make_pill(
        btn_inner,
        "确认",
        app=app,
        c=c,
        primary=True,
        command=confirm,
        padx=32,
        pady=8,
        font_size=11,
    ).pack(side=tk.LEFT, padx=(0, SPACE_SM))
    make_pill(
        btn_inner,
        "取消",
        app=app,
        c=c,
        primary=False,
        command=cancel,
        padx=32,
        pady=8,
        font_size=11,
    ).pack(side=tk.LEFT)

    picker.bind("<Return>", lambda e: confirm())
    picker.bind("<Escape>", lambda e: cancel())
    picker.protocol("WM_DELETE_WINDOW", cancel)

    def _ready():
        _fit_picker_window(
            picker, shell, min_w, min_h, borderless=borderless
        )
        _activate_picker(picker)
        # 按需 grab：模态输入，关闭时已 grab_release
        try:
            if not closed["done"] and picker.winfo_exists():
                picker.grab_set()
        except tk.TclError:
            pass

    picker.after_idle(_ready)
    picker.after(50, _ready)
    picker.after(
        120,
        lambda: _fit_picker_window(
            picker, shell, min_w, min_h, borderless=borderless
        ),
    )
