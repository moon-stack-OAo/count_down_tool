# -*- coding: utf-8 -*-
"""设置 · 外观分区。"""

from __future__ import annotations

import tkinter as tk

from core.themes import list_themes
from ui.design.tokens import SPACE_SM, SPACE_XS
from ui.settings.layout import card


def build_appearance_section(app, parent, c, refreshers) -> None:
    from core.countdown_core import (
        STARTUP_MODE_FULL,
        STARTUP_MODE_MINI,
        STARTUP_MODE_REMEMBER,
        normalize_startup_mode,
    )

    # —— 主题 ——
    theme_card = card(parent, c)
    tk.Label(
        theme_card,
        text="主题",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))

    rows = {}

    def _apply(tid: str):
        app._apply_theme(tid)
        # apply_theme 会关窗并以新主题重开；若窗仍在则刷新勾选
        for fn in refreshers:
            try:
                fn()
            except (tk.TclError, AttributeError, TypeError, ValueError, RuntimeError):
                pass

    def _refresh_theme():
        cur = getattr(app, "_theme_id", "")
        for tid, lbl in rows.items():
            try:
                mark = "✓  " if tid == cur else "    "
                name = lbl._theme_name  # type: ignore[attr-defined]
                lbl.config(text=f"{mark}{name}")
            except tk.TclError:
                pass

    for tid, name in list_themes():
        row = tk.Label(
            theme_card,
            text="",
            font=app._font("label", 10),
            bg=c["card"],
            fg=c["text"],
            anchor="w",
            cursor="hand2",
            padx=SPACE_SM,
            pady=6,
        )
        row._theme_name = name  # type: ignore[attr-defined]
        row.pack(fill=tk.X)
        row.bind("<Button-1>", lambda e, t=tid: _apply(t))
        row.bind(
            "<Enter>",
            lambda e, w=row: w.config(bg=c.get("chip_hover", c["border"])),
        )
        row.bind("<Leave>", lambda e, w=row: w.config(bg=c["card"]))
        rows[tid] = row

    refreshers.append(_refresh_theme)
    _refresh_theme()

    # —— 默认启动模式 ——
    start_card = card(parent, c)
    tk.Label(
        start_card,
        text="默认启动模式",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))

    startup_opts = (
        (STARTUP_MODE_REMEMBER, "记住上次"),
        (STARTUP_MODE_FULL, "总是完整模式"),
        (STARTUP_MODE_MINI, "总是 Mini"),
    )
    startup_rows = {}

    def _set_startup(mode: str):
        app._startup_mode = normalize_startup_mode(mode)
        app._save_config()
        _refresh_startup()

    def _refresh_startup():
        cur = normalize_startup_mode(getattr(app, "_startup_mode", STARTUP_MODE_REMEMBER))
        for mid, lbl in startup_rows.items():
            try:
                mark = "✓  " if mid == cur else "    "
                name = lbl._startup_name  # type: ignore[attr-defined]
                lbl.config(text=f"{mark}{name}")
            except tk.TclError:
                pass

    for mid, name in startup_opts:
        row = tk.Label(
            start_card,
            text="",
            font=app._font("label", 10),
            bg=c["card"],
            fg=c["text"],
            anchor="w",
            cursor="hand2",
            padx=SPACE_SM,
            pady=6,
        )
        row._startup_name = name  # type: ignore[attr-defined]
        row.pack(fill=tk.X)
        row.bind("<Button-1>", lambda e, m=mid: _set_startup(m))
        row.bind(
            "<Enter>",
            lambda e, w=row: w.config(bg=c.get("chip_hover", c["border"])),
        )
        row.bind("<Leave>", lambda e, w=row: w.config(bg=c["card"]))
        startup_rows[mid] = row

    refreshers.append(_refresh_startup)
    _refresh_startup()

    # —— Mini 字色 ——
    mini_card = card(parent, c)
    tk.Label(
        mini_card,
        text="Mini 外观",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))

    def _open_mini_text():
        from ui.mini_text_picker import show_mini_text_picker

        show_mini_text_picker(app)

    text_row = tk.Label(
        mini_card,
        text="Mini 字体颜色…",
        font=app._font("label", 10),
        bg=c["card"],
        fg=c["text"],
        anchor="w",
        cursor="hand2",
        padx=SPACE_SM,
        pady=SPACE_SM,
    )
    text_row.pack(fill=tk.X)
    text_row.bind("<Button-1>", lambda e: _open_mini_text())
    text_row.bind(
        "<Enter>",
        lambda e, w=text_row: w.config(bg=c.get("chip_hover", c["border"])),
    )
    text_row.bind("<Leave>", lambda e, w=text_row: w.config(bg=c["card"]))
