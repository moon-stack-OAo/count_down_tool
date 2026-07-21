# -*- coding: utf-8 -*-
"""Mini 字色选择：带真实色块预览（托盘原生菜单无法着色）。"""

import tkinter as tk
from tkinter import ttk

from core.countdown_core import (
    APP_NAME,
    MINI_TEXT_COLOR_KEYS,
    MINI_TEXT_COLOR_LABELS,
    MINI_TEXT_ROLE_LABELS,
    MINI_TEXT_ROLES,
)
from ui.context_menus import current_mini_text_key, reset_mini_text_colors, set_mini_text_color


def show_mini_text_picker(app):
    """弹出 Mini 字色面板：每行角色 + 色块按钮。"""
    existing = getattr(app, "_mini_text_picker", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.lift()
                existing.focus_force()
                return
        except tk.TclError:
            pass
        app._mini_text_picker = None

    colors = app.COLORS
    win = tk.Toplevel(app.master)
    app._mini_text_picker = win
    win.title(f"{APP_NAME} · 字体颜色")
    win.configure(bg=colors["card"])
    win.attributes("-topmost", True)
    win.resizable(False, False)

    outer = tk.Frame(win, bg=colors["card"], padx=14, pady=12)
    outer.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        outer,
        text="Mini 字体颜色",
        font=app._font("label", 11, bold=True),
        bg=colors["card"],
        fg=colors["text"],
    ).pack(anchor=tk.W)

    tk.Label(
        outer,
        text="色块为当前主题实际颜色，点击即应用",
        font=app._font("label", 9),
        bg=colors["card"],
        fg=colors["text_muted"],
    ).pack(anchor=tk.W, pady=(2, 10))

    # 角色 → 当前选中指示 Label
    check_labels = {}

    def _refresh_checks():
        for role in MINI_TEXT_ROLES:
            cur = current_mini_text_key(app, role)
            for key, lbl in check_labels.get(role, {}).items():
                try:
                    lbl.config(text="✓" if key == cur else "")
                except tk.TclError:
                    pass

    def _pick(role, key):
        set_mini_text_color(app, role, key)
        _refresh_checks()
        from services.tray import refresh_tray_menu

        refresh_tray_menu(app)

    for role in MINI_TEXT_ROLES:
        row = tk.Frame(outer, bg=colors["card"])
        row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            row,
            text=MINI_TEXT_ROLE_LABELS.get(role, role),
            font=app._font("label", 9),
            bg=colors["card"],
            fg=colors["text_dim"],
            width=12,
            anchor=tk.W,
        ).pack(side=tk.LEFT)

        swatch_row = tk.Frame(row, bg=colors["card"])
        swatch_row.pack(side=tk.LEFT, fill=tk.X, expand=True)

        check_labels[role] = {}
        current = current_mini_text_key(app, role)
        for key in MINI_TEXT_COLOR_KEYS:
            hex_val = colors.get(key, "#888888")
            if not isinstance(hex_val, str) or not hex_val:
                hex_val = "#888888"
            cell = tk.Frame(swatch_row, bg=colors["card"])
            cell.pack(side=tk.LEFT, padx=2)

            # 色块：用主题色作背景，文字用对比色
            fg = _contrast_fg(hex_val)
            btn = tk.Label(
                cell,
                text="  ",
                width=3,
                font=app._font("label", 9),
                bg=hex_val,
                fg=fg,
                relief=tk.FLAT,
                bd=1,
                highlightthickness=1,
                highlightbackground=colors["border"],
                cursor="hand2",
            )
            btn.pack()
            btn.bind("<Button-1>", lambda e, r=role, k=key: _pick(r, k))
            # 悬停提示中文名
            tip = MINI_TEXT_COLOR_LABELS.get(key, key)
            btn.bind("<Enter>", lambda e, b=btn, t=tip, h=hex_val: b.config(
                text=t[:1] if len(t) else "·",
            ))
            btn.bind("<Leave>", lambda e, b=btn: b.config(text="  "))

            mark = tk.Label(
                cell,
                text="✓" if key == current else "",
                font=app._font("label", 8),
                bg=colors["card"],
                fg=colors["accent"],
                height=1,
            )
            mark.pack()
            check_labels[role][key] = mark

    # 图例：色键名称 + 小色块
    legend = tk.Frame(outer, bg=colors["card"])
    legend.pack(fill=tk.X, pady=(4, 8))
    tk.Label(
        legend,
        text="图例",
        font=app._font("label", 8),
        bg=colors["card"],
        fg=colors["text_muted"],
    ).pack(anchor=tk.W)
    legend_row = tk.Frame(legend, bg=colors["card"])
    legend_row.pack(fill=tk.X, pady=(4, 0))
    for key in MINI_TEXT_COLOR_KEYS:
        hex_val = colors.get(key, "#888888")
        if not isinstance(hex_val, str) or not hex_val:
            hex_val = "#888888"
        item = tk.Frame(legend_row, bg=colors["card"])
        item.pack(side=tk.LEFT, padx=(0, 8), pady=2)
        tk.Label(
            item,
            text="  ",
            width=2,
            bg=hex_val,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=colors["border"],
        ).pack(side=tk.LEFT)
        tk.Label(
            item,
            text=MINI_TEXT_COLOR_LABELS.get(key, key),
            font=app._font("label", 8),
            bg=colors["card"],
            fg=colors["text_dim"],
        ).pack(side=tk.LEFT, padx=(3, 0))

    footer = tk.Frame(outer, bg=colors["card"])
    footer.pack(fill=tk.X, pady=(4, 0))

    def _reset():
        reset_mini_text_colors(app)
        _refresh_checks()
        from services.tray import refresh_tray_menu

        refresh_tray_menu(app)

    def _close():
        try:
            win.destroy()
        except tk.TclError:
            pass
        app._mini_text_picker = None

    ttk.Button(footer, text="恢复默认", command=_reset).pack(side=tk.LEFT)
    ttk.Button(footer, text="关闭", command=_close).pack(side=tk.RIGHT)

    win.protocol("WM_DELETE_WINDOW", _close)

    # 相对主屏居中
    win.update_idletasks()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 3}")

    try:
        win.lift()
        win.focus_force()
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
    # 相对亮度
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#0F1419" if lum > 0.55 else "#FFFFFF"
