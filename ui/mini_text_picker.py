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

# 与 app_dialogs 接近的内容宽
_PICKER_WIDTH = 460


def _picker_parent(app):
    """挂到当前可见窗，避免主窗 withdraw 后子窗不映射。"""
    # 设置中心打开时优先（从外观 Tab 点入）
    sw = getattr(app, "_settings_window", None)
    if sw is not None:
        try:
            if sw.winfo_exists():
                return sw
        except tk.TclError:
            pass
    # Mini 模式主窗常 withdraw，挂 Mini
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
    win.resizable(False, False)
    # 系统原生标题栏（不用无边框自绘）
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

    # 说明卡片
    intro = make_settings_card(shell, c, pack=True, fill="x")
    tk.Label(
        intro,
        text="字色",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c.get("text_muted", c["text_dim"]),
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))
    tk.Frame(intro, bg=c.get("accent", "#38BDF8"), height=2).pack(
        fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_SM)
    )
    tk.Label(
        intro,
        text="色块取自当前主题。点击即应用，可按角色分别设置。",
        font=app._font("label", 10),
        bg=c["card"],
        fg=c["text"],
        wraplength=_PICKER_WIDTH - 64,
        justify=tk.LEFT,
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))

    # 角色 → 色键 → canvas 色块；角色 → 当前色名 Label
    swatch_canvases: dict = {}
    current_name_labels: dict = {}
    _SW = 28  # 色块边长（像素）

    def _hex_for(key: str) -> str:
        val = c.get(key, "#888888")
        if not isinstance(val, str) or not val:
            return "#888888"
        return val

    def _paint_swatch(cv: tk.Canvas, key: str, selected: bool, hover: bool = False) -> None:
        """绘制色块：选中=粗 accent 环 + 对比色 ✓；悬停=细 accent 环。"""
        hex_val = _hex_for(key)
        try:
            cv.delete("all")
        except tk.TclError:
            return
        accent = c.get("accent", "#38BDF8")
        accent_glow = c.get("accent_glow", accent)
        border = c.get("border", "#2A3A4E")
        s = _SW
        # 外环
        if selected:
            ring = accent
            cv.create_rectangle(0, 0, s - 1, s - 1, outline=ring, width=3, fill="")
            cv.create_rectangle(
                3, 3, s - 4, s - 4, outline=c.get("bg", "#0F1419"), width=1, fill=hex_val
            )
        elif hover:
            cv.create_rectangle(
                1, 1, s - 2, s - 2, outline=accent_glow, width=2, fill=hex_val
            )
        else:
            cv.create_rectangle(
                2, 2, s - 3, s - 3, outline=border, width=1, fill=hex_val
            )
        # 选中勾
        if selected:
            mark = _contrast_fg(hex_val)
            cv.create_text(
                s // 2,
                s // 2,
                text="✓",
                fill=mark,
                font=app._font("label", 11, bold=True),
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

    def _refresh_selection():
        for role in MINI_TEXT_ROLES:
            cur = current_mini_text_key(app, role)
            _set_current_name(role, cur)
            for key, cv in swatch_canvases.get(role, {}).items():
                _paint_swatch(cv, key, key == cur, hover=False)

    def _pick(role, key):
        set_mini_text_color(app, role, key)
        _refresh_selection()
        from services.tray import refresh_tray_menu

        refresh_tray_menu(app)

    # 角色色板卡片
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

        # 左：角色名 + 当前色名
        name_col = tk.Frame(row, bg=c["card"])
        name_col.pack(side=tk.LEFT, padx=(0, SPACE_SM))
        tk.Label(
            name_col,
            text=MINI_TEXT_ROLE_LABELS.get(role, role),
            font=app._font("label", 9),
            bg=c["card"],
            fg=c["text_dim"],
            width=12,
            anchor=tk.W,
        ).pack(anchor=tk.W)
        cur0 = current_mini_text_key(app, role)
        cur_lbl = tk.Label(
            name_col,
            text=MINI_TEXT_COLOR_LABELS.get(cur0, cur0),
            font=app._font("label", 8, bold=True),
            bg=c["card"],
            fg=_hex_for(cur0),
            width=12,
            anchor=tk.W,
        )
        cur_lbl.pack(anchor=tk.W)
        current_name_labels[role] = cur_lbl

        swatch_row = tk.Frame(row, bg=c["card"])
        swatch_row.pack(side=tk.LEFT, fill=tk.X, expand=True)

        swatch_canvases[role] = {}
        current = cur0
        for key in MINI_TEXT_COLOR_KEYS:
            cell = tk.Frame(swatch_row, bg=c["card"])
            cell.pack(side=tk.LEFT, padx=3)
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
            selected = key == current
            _paint_swatch(cv, key, selected)

            def _on_enter(e, canvas=cv, k=key, r=role):
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
            swatch_canvases[role][key] = cv

    # 图例卡片
    legend_card = make_settings_card(shell, c, pack=True, fill="x")
    tk.Label(
        legend_card,
        text="图例",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c.get("text_muted", c["text_dim"]),
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))
    tk.Frame(legend_card, bg=c.get("border", "#2A3A4E"), height=1).pack(
        fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_SM)
    )

    legend_wrap = tk.Frame(legend_card, bg=c["card"])
    legend_wrap.pack(fill=tk.X, padx=SPACE_SM)

    keys = list(MINI_TEXT_COLOR_KEYS)
    mid = (len(keys) + 1) // 2
    for chunk in (keys[:mid], keys[mid:]):
        legend_row = tk.Frame(legend_wrap, bg=c["card"])
        legend_row.pack(fill=tk.X, pady=(0, SPACE_XS))
        for key in chunk:
            hex_val = _hex_for(key)
            item = tk.Frame(legend_row, bg=c["card"])
            item.pack(side=tk.LEFT, padx=(0, SPACE_MD), pady=1)
            chip = tk.Label(
                item,
                text="  ",
                width=1,
                bg=hex_val,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=1,
                highlightbackground=c.get("border", "#2A3A4E"),
            )
            chip.pack(side=tk.LEFT, ipadx=2, ipady=2)
            tk.Label(
                item,
                text=MINI_TEXT_COLOR_LABELS.get(key, key),
                font=app._font("label", 8),
                bg=c["card"],
                fg=c["text_dim"],
            ).pack(side=tk.LEFT, padx=(SPACE_XS, 0))

    def _reset():
        reset_mini_text_colors(app)
        _refresh_selection()
        from services.tray import refresh_tray_menu

        refresh_tray_menu(app)

    btn_row = tk.Frame(shell, bg=c["bg"])
    btn_row.pack(fill=tk.X, pady=(0, 0))
    make_pill(
        btn_row, "恢复默认", app=app, c=c, primary=False, command=_reset
    ).pack(side=tk.LEFT)
    make_pill(btn_row, "完成", app=app, c=c, primary=True, command=_close).pack(
        side=tk.RIGHT
    )

    win.update_idletasks()
    w = max(360, min(_PICKER_WIDTH, win.winfo_reqwidth() + 24))
    h = max(280, win.winfo_reqheight() + 12)
    center_dialog(win, int(w), int(h))
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
