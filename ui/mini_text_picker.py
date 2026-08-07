# -*- coding: utf-8 -*-
"""Mini 字色选择：主题弹窗 + 真实色块预览（托盘原生菜单无法着色）。"""

from __future__ import annotations

import logging
import platform
import tkinter as tk

from core.countdown_core import (
    APP_NAME,
    MINI_TEXT_COLOR_KEYS,
    MINI_TEXT_COLOR_LABELS,
    MINI_TEXT_ROLE_LABELS,
    MINI_TEXT_ROLES,
    STATE_FINISHED,
    STATE_RUNNING,
)
from ui.context_menus import (
    current_mini_text_key,
    reset_mini_text_colors,
    set_mini_text_color,
)
from ui.design.tokens import SPACE_MD, SPACE_SM, SPACE_XS
from ui.widgets import make_pill, make_settings_card
from ui.window_chrome_dialog import center_dialog

logger = logging.getLogger("count_down_tool")

_SW = 26  # 色块边长（像素）


def _picker_parent(app):
    """挂到当前可见窗，避免主窗 withdraw 后子窗不映射。"""
    sw = getattr(app, "_settings_window", None)
    if sw is not None:
        try:
            if sw.winfo_exists():
                return sw
        except tk.TclError:
            pass
    if getattr(app, "_is_mini", False):
        mini = getattr(app, "mini_window", None)
        if mini is not None:
            try:
                if mini.winfo_exists():
                    return mini
            except tk.TclError:
                pass
    return app.master


def _activate(win: tk.Misc) -> None:
    """置前并聚焦（保留 topmost，避免被设置中心盖住）。"""
    try:
        win.deiconify()
        win.lift()
        win.attributes("-topmost", True)
        win.focus_force()
    except tk.TclError:
        pass
    if platform.system() == "Windows":
        try:
            from services.windows_native import force_window_to_front

            force_window_to_front(win)
        except (ImportError, OSError, AttributeError, tk.TclError):
            try:
                import ctypes

                win.update_idletasks()
                frame = win.wm_frame()
                hwnd = int(frame, 16) if frame else int(win.winfo_id())
                user32 = ctypes.windll.user32
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
            except (OSError, AttributeError, ValueError, TypeError, tk.TclError):
                logger.debug("字色弹窗置前失败", exc_info=True)


def _active_countdown_role(app) -> str:
    """当前倒计时状态对应的字色角色。"""
    state = getattr(app, "_state", None)
    if state == STATE_RUNNING:
        return "countdown_running"
    if state == STATE_FINISHED:
        return "countdown_finished"
    return "countdown_paused"


def _fit_and_place(win: tk.Misc) -> None:
    """按内容自然尺寸定位，避免固定 geometry 裁切。"""
    try:
        win.update_idletasks()
    except tk.TclError:
        return
    # 内容需求尺寸 + 边距；Windows 标题栏/边框额外留白
    try:
        req_w = int(win.winfo_reqwidth())
        req_h = int(win.winfo_reqheight())
    except tk.TclError:
        return
    chrome_h = 40 if platform.system() == "Windows" else 8
    chrome_w = 16 if platform.system() == "Windows" else 8
    w = max(420, req_w + chrome_w)
    h = max(200, req_h + chrome_h)
    # 不超过工作区 90%，超出时宁可可滚动感（仍完整显示优先）
    try:
        from services.windows_native import get_work_area

        work = get_work_area(win)
        if work:
            _ox, _oy, aw, ah = work
            w = min(w, max(360, int(aw * 0.95)))
            h = min(h, max(240, int(ah * 0.9)))
    except (ImportError, OSError, AttributeError, TypeError, ValueError, tk.TclError):
        try:
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            w = min(w, max(360, int(sw * 0.95)))
            h = min(h, max(240, int(sh * 0.9)))
        except tk.TclError:
            pass
    center_dialog(win, int(w), int(h))
    # 布局稳定后再按真实 req 放大一次（避免首次低估）
    def _resize_again():
        try:
            if not win.winfo_exists():
                return
            win.update_idletasks()
            rw = max(int(win.winfo_reqwidth()) + chrome_w, w)
            rh = max(int(win.winfo_reqheight()) + chrome_h, h)
            # 若内容更大，抬高窗口高度，避免底部按钮被裁
            if rw > win.winfo_width() or rh > win.winfo_height():
                center_dialog(win, int(rw), int(rh))
        except tk.TclError:
            pass

    try:
        win.after_idle(_resize_again)
        win.after(80, _resize_again)
    except tk.TclError:
        pass


def show_mini_text_picker(app):
    """弹出 Mini 字色面板：每行角色 + 色块按钮。"""
    existing = getattr(app, "_mini_text_picker", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                _activate(existing)
                return
        except tk.TclError:
            pass
        app._mini_text_picker = None

    c = app.COLORS
    parent = _picker_parent(app)

    win = tk.Toplevel(parent)
    app._mini_text_picker = win
    title = "Mini 字体颜色"
    win.title(f"{APP_NAME} · {title}")
    win.configure(bg=c["bg"])
    # 允许垂直微调，避免极端 DPI 下裁切
    win.resizable(False, True)
    try:
        win.attributes("-topmost", True)
    except tk.TclError:
        pass

    def _close(_e=None):
        try:
            win.destroy()
        except tk.TclError:
            pass
        app._mini_text_picker = None
        return "break"

    win.protocol("WM_DELETE_WINDOW", _close)
    try:
        win.bind("<Escape>", _close)
    except tk.TclError:
        pass

    shell = tk.Frame(win, bg=c["bg"], padx=SPACE_MD, pady=SPACE_MD)
    shell.pack(fill=tk.BOTH, expand=True)

    # 简短说明（单行，省高度）
    intro = make_settings_card(shell, c, pack=True, fill="x", pady_inner=SPACE_SM)
    tk.Label(
        intro,
        text="点击色块即应用；带 ✓ 为当前选中。仅当前状态角色会立刻反映在 Mini 上。",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c.get("text_muted", c["text_dim"]),
        wraplength=480,
        justify=tk.LEFT,
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM)

    swatch_canvases: dict = {}
    current_name_labels: dict = {}
    role_active_marks: dict = {}

    def _hex_for(key: str) -> str:
        val = c.get(key, "#888888")
        if not isinstance(val, str) or not val:
            return "#888888"
        return val

    def _paint_swatch(
        cv: tk.Canvas, key: str, selected: bool, hover: bool = False
    ) -> None:
        hex_val = _hex_for(key)
        try:
            cv.delete("all")
        except tk.TclError:
            return
        accent = c.get("accent", "#38BDF8")
        accent_glow = c.get("accent_glow", accent)
        border = c.get("border", "#2A3A4E")
        s = _SW
        if selected:
            cv.create_rectangle(0, 0, s - 1, s - 1, outline=accent, width=3, fill="")
            cv.create_rectangle(
                3, 3, s - 4, s - 4, outline=c.get("bg", "#0F1419"), width=1, fill=hex_val
            )
            mark = _contrast_fg(hex_val)
            cv.create_text(
                s // 2,
                s // 2,
                text="✓",
                fill=mark,
                font=app._font("label", 10, bold=True),
            )
        elif hover:
            cv.create_rectangle(
                1, 1, s - 2, s - 2, outline=accent_glow, width=2, fill=hex_val
            )
        else:
            cv.create_rectangle(
                2, 2, s - 3, s - 3, outline=border, width=1, fill=hex_val
            )
        cv.configure(bg=c["card"], highlightthickness=0)

    def _set_current_name(role: str, key: str) -> None:
        lbl = current_name_labels.get(role)
        if lbl is None:
            return
        name = MINI_TEXT_COLOR_LABELS.get(key, key)
        try:
            lbl.config(text=name, fg=_hex_for(key))
        except tk.TclError:
            pass

    def _refresh_active_marks():
        active = _active_countdown_role(app)
        for role, lbl in role_active_marks.items():
            # clock 始终生效；倒计时角色仅当前状态生效
            show = (role == "clock") or (role == active)
            try:
                lbl.config(
                    text="生效中" if show else "",
                    fg=c.get("accent", "#38BDF8") if show else c.get("text_muted"),
                )
            except tk.TclError:
                pass

    def _refresh_selection():
        for role in MINI_TEXT_ROLES:
            cur = current_mini_text_key(app, role)
            _set_current_name(role, cur)
            for key, cv in swatch_canvases.get(role, {}).items():
                _paint_swatch(cv, key, key == cur, hover=False)
        _refresh_active_marks()

    def _pick(role, key):
        set_mini_text_color(app, role, key)
        _refresh_selection()
        from services.tray import refresh_tray_menu

        refresh_tray_menu(app)

    roles_card = make_settings_card(shell, c, pack=True, fill="x")
    tk.Label(
        roles_card,
        text="按角色设置",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c.get("text_muted", c["text_dim"]),
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))
    tk.Frame(roles_card, bg=c.get("border", "#2A3A4E"), height=1).pack(
        fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_SM)
    )

    for idx, role in enumerate(MINI_TEXT_ROLES):
        row = tk.Frame(roles_card, bg=c["card"])
        row.pack(fill=tk.X, padx=SPACE_SM, pady=(0 if idx == 0 else SPACE_SM, 0))

        name_col = tk.Frame(row, bg=c["card"])
        name_col.pack(side=tk.LEFT, padx=(0, SPACE_SM))
        head = tk.Frame(name_col, bg=c["card"])
        head.pack(anchor=tk.W)
        tk.Label(
            head,
            text=MINI_TEXT_ROLE_LABELS.get(role, role),
            font=app._font("label", 9),
            bg=c["card"],
            fg=c["text_dim"],
            anchor=tk.W,
        ).pack(side=tk.LEFT)
        mark = tk.Label(
            head,
            text="",
            font=app._font("label", 8, bold=True),
            bg=c["card"],
            fg=c.get("accent", "#38BDF8"),
            padx=4,
        )
        mark.pack(side=tk.LEFT)
        role_active_marks[role] = mark

        cur0 = current_mini_text_key(app, role)
        cur_lbl = tk.Label(
            name_col,
            text=MINI_TEXT_COLOR_LABELS.get(cur0, cur0),
            font=app._font("label", 8, bold=True),
            bg=c["card"],
            fg=_hex_for(cur0),
            anchor=tk.W,
        )
        cur_lbl.pack(anchor=tk.W)
        current_name_labels[role] = cur_lbl

        swatch_row = tk.Frame(row, bg=c["card"])
        swatch_row.pack(side=tk.LEFT, fill=tk.X, expand=True)

        swatch_canvases[role] = {}
        for key in MINI_TEXT_COLOR_KEYS:
            cell = tk.Frame(swatch_row, bg=c["card"])
            cell.pack(side=tk.LEFT, padx=2)
            cv = tk.Canvas(
                cell,
                width=_SW,
                height=_SW,
                bg=c["card"],
                highlightthickness=0,
                bd=0,
                cursor="hand2",
            )
            cv.pack()
            _paint_swatch(cv, key, key == cur0)

            tip = MINI_TEXT_COLOR_LABELS.get(key, key)

            def _on_enter(e, canvas=cv, k=key, r=role, t=tip):
                try:
                    cur = current_mini_text_key(app, r)
                    if k != cur:
                        _paint_swatch(canvas, k, False, hover=True)
                except tk.TclError:
                    pass

            def _on_leave(e, canvas=cv, k=key, r=role):
                try:
                    cur = current_mini_text_key(app, r)
                    _paint_swatch(canvas, k, k == cur, hover=False)
                except tk.TclError:
                    pass

            def _on_click(e, r=role, k=key):
                _pick(r, k)

            cv.bind("<Button-1>", _on_click)
            cv.bind("<Enter>", _on_enter)
            cv.bind("<Leave>", _on_leave)
            # 悬停提示（原生 tooltip 简陋：用 title 属性不可用，绑 leave 已够）
            swatch_canvases[role][key] = cv

    # 紧凑图例：单行小色点 + 名
    legend_card = make_settings_card(shell, c, pack=True, fill="x", pady_inner=SPACE_SM)
    legend_row = tk.Frame(legend_card, bg=c["card"])
    legend_row.pack(fill=tk.X, padx=SPACE_SM)
    for key in MINI_TEXT_COLOR_KEYS:
        hex_val = _hex_for(key)
        item = tk.Frame(legend_row, bg=c["card"])
        item.pack(side=tk.LEFT, padx=(0, SPACE_SM))
        tk.Label(
            item,
            text="  ",
            width=1,
            bg=hex_val,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=1,
            highlightbackground=c.get("border", "#2A3A4E"),
        ).pack(side=tk.LEFT, ipadx=1, ipady=1)
        tk.Label(
            item,
            text=MINI_TEXT_COLOR_LABELS.get(key, key),
            font=app._font("label", 8),
            bg=c["card"],
            fg=c["text_dim"],
        ).pack(side=tk.LEFT, padx=(2, 0))

    def _reset():
        reset_mini_text_colors(app)
        _refresh_selection()
        from services.tray import refresh_tray_menu

        refresh_tray_menu(app)

    btn_row = tk.Frame(shell, bg=c["bg"])
    btn_row.pack(fill=tk.X, pady=(SPACE_SM, 0))
    make_pill(
        btn_row, "恢复默认", app=app, c=c, primary=False, command=_reset
    ).pack(side=tk.LEFT)
    make_pill(btn_row, "完成", app=app, c=c, primary=True, command=_close).pack(
        side=tk.RIGHT
    )

    _refresh_active_marks()
    _fit_and_place(win)
    _activate(win)
    try:
        win.after(30, lambda: _activate(win))
        win.after(120, lambda: _activate(win))
    except tk.TclError:
        pass


def _contrast_fg(hex_color: str) -> str:
    """根据背景亮度选黑/白字。"""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "#FFFFFF"
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return "#FFFFFF"
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#0F1419" if lum > 0.55 else "#FFFFFF"
