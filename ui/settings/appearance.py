# -*- coding: utf-8 -*-
"""设置 · 外观分区。"""

from __future__ import annotations

import tkinter as tk

from core.themes import list_themes
from ui.design.tokens import SPACE_SM
from ui.settings.layout import card, section_title, selectable_row, set_selectable_selected


def build_appearance_section(app, parent, c, refreshers) -> None:
    from core.countdown_core import (
        STARTUP_MODE_FULL,
        STARTUP_MODE_MINI,
        STARTUP_MODE_REMEMBER,
        normalize_startup_mode,
    )

    # —— 主题 ——
    theme_card = card(parent, c)
    section_title(theme_card, app, c, "主题")

    rows = {}

    def _apply(tid: str):
        app._apply_theme(tid)
        # apply_theme 优先就地换色并触发 _settings_refresh；此处兜底刷新勾选
        for fn in refreshers:
            try:
                fn()
            except (tk.TclError, AttributeError, TypeError, ValueError, RuntimeError):
                pass

    def _refresh_theme():
        cur = getattr(app, "_theme_id", "")
        for tid, lbl in rows.items():
            try:
                name = lbl._theme_name  # type: ignore[attr-defined]
                set_selectable_selected(lbl, tid == cur, text=name)
            except tk.TclError:
                pass

    for tid, name in list_themes():
        row = selectable_row(
            theme_card,
            app,
            c,
            name,
            selected=False,
            on_click=lambda t=tid: _apply(t),
        )
        row._theme_name = name  # type: ignore[attr-defined]
        rows[tid] = row

    refreshers.append(_refresh_theme)
    _refresh_theme()

    # —— 自定义颜色 ——
    from ui.settings.theme_custom_editor import build_theme_custom_section

    build_theme_custom_section(app, parent, c, refreshers)

    # —— 默认启动模式 ——
    start_card = card(parent, c)
    section_title(start_card, app, c, "默认启动模式")

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
                name = lbl._startup_name  # type: ignore[attr-defined]
                set_selectable_selected(lbl, mid == cur, text=name)
            except tk.TclError:
                pass

    for mid, name in startup_opts:
        row = selectable_row(
            start_card,
            app,
            c,
            name,
            selected=False,
            on_click=lambda m=mid: _set_startup(m),
        )
        row._startup_name = name  # type: ignore[attr-defined]
        startup_rows[mid] = row

    refreshers.append(_refresh_startup)
    _refresh_startup()

    # —— Mini 字色 ——
    mini_card = card(parent, c)
    section_title(mini_card, app, c, "Mini 外观")

    def _open_mini_text():
        from ui.mini_text_picker import show_mini_text_picker

        show_mini_text_picker(app)

    selectable_row(
        mini_card,
        app,
        c,
        "Mini 字体颜色…",
        selected=False,
        on_click=_open_mini_text,
        checkmark=False,
        pady=SPACE_SM,
    )
