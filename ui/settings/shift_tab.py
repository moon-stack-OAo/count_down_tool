# -*- coding: utf-8 -*-
"""设置 · 班次顺延分区。"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import datetime

from core.countdown_core import (
    format_target_label,
    parse_shift_hms,
    target_from_shift,
    validate_shift,
)
from ui.design.themed import register_themed, themed_frame, themed_label
from ui.design.tokens import FONT_BODY, FONT_CAPTION, SPACE_SM, SPACE_XS
from ui.settings.layout import card, pill, section_title, selectable_row, set_selectable_selected

logger = logging.getLogger("count_down_tool")


def build_shift_section(app, parent, c, refreshers) -> None:
    """班次顺延：启用开关、开始/结束时刻、预览与保存。"""
    shift_card = card(parent, c)
    win = getattr(app, "_settings_window", None)

    section_title(shift_card, app, c, "班次顺延")

    themed_label(
        shift_card,
        app,
        "晚到 Δ 分钟 → 下班目标顺延 Δ；第一版不支持跨日班次。",
        fg_role="text_muted",
        bg_role="card",
        font_size=FONT_CAPTION,
        c=c,
        wraplength=420,
        justify=tk.LEFT,
        padx=SPACE_SM,
    ).pack(fill=tk.X, pady=(0, SPACE_SM))

    # 启用行占位：在 _toggle_enabled 定义后再创建
    enable_host = themed_frame(shift_card, app, role="card", c=c)
    enable_host.pack(fill=tk.X)

    # —— 开始 / 结束 ——
    form = themed_frame(shift_card, app, role="card", c=c)
    form.pack(fill=tk.X, padx=SPACE_SM, pady=(SPACE_XS, 0))

    start_var = tk.StringVar(
        value=str(getattr(app, "_shift_start", "09:00:00") or "09:00:00")
    )
    end_var = tk.StringVar(
        value=str(getattr(app, "_shift_end", "18:00:00") or "18:00:00")
    )

    def _row(label: str, var: tk.StringVar) -> tk.Entry:
        row = themed_frame(form, app, role="card", c=c)
        row.pack(fill=tk.X, pady=(0, SPACE_XS))
        themed_label(
            row,
            app,
            label,
            fg_role="text",
            bg_role="card",
            font_size=FONT_BODY,
            c=c,
            width=8,
        ).pack(side=tk.LEFT)
        entry = tk.Entry(
            row,
            textvariable=var,
            font=app._font("label", FONT_BODY),
            bg=c.get("input_bg", c["chip"]),
            fg=c["text"],
            insertbackground=c["text"],
            relief=tk.FLAT,
            width=12,
        )
        register_themed(entry, bg="input_bg", fg="text", insertbackground="text")
        entry.pack(side=tk.LEFT, padx=(SPACE_SM, 0), ipady=SPACE_XS)
        themed_label(
            row,
            app,
            "HH:MM:SS",
            fg_role="text_muted",
            bg_role="card",
            font_size=FONT_CAPTION,
            c=c,
        ).pack(side=tk.LEFT, padx=(SPACE_SM, 0))
        return entry

    start_entry = _row("开始", start_var)
    end_entry = _row("结束", end_var)

    preview_lbl = themed_label(
        shift_card,
        app,
        "",
        fg_role="text_dim",
        bg_role="card",
        font_size=FONT_CAPTION,
        c=c,
        justify=tk.LEFT,
        wraplength=420,
        padx=SPACE_SM,
    )
    preview_lbl.pack(fill=tk.X, pady=(SPACE_SM, SPACE_XS))

    btn_row = themed_frame(shift_card, app, role="card", c=c)
    btn_row.pack(fill=tk.X, padx=SPACE_SM, pady=(SPACE_XS, 0))

    def _toast(msg: str, *, kind: str = "ok") -> None:
        from ui.settings.shell import show_settings_toast

        if not show_settings_toast(app, msg, kind=kind):
            if kind == "error":
                from ui.app_dialogs import show_error

                show_error(app, msg, parent=win or app.master)
            else:
                from ui.app_dialogs import show_info

                show_info(app, msg, title="班次", parent=win or app.master)

    def _sync_main_shift_chip():
        """刷新主界面「今日班次」chip 启用/置灰样式（不整页重建）。"""
        try:
            from ui.full_window import sync_shift_chip

            sync_shift_chip(app)
        except (ImportError, AttributeError, tk.TclError, RuntimeError):
            logger.debug("同步班次 chip 失败", exc_info=True)

    def _toggle_enabled():
        app._shift_enabled = not bool(getattr(app, "_shift_enabled", False))
        app._save_config()
        _refresh()
        _sync_main_shift_chip()
        try:
            from services.tray import refresh_tray_menu

            refresh_tray_menu(app)
        except (ImportError, AttributeError, RuntimeError, tk.TclError):
            pass

    def _update_preview(*_args):
        palette = getattr(app, "COLORS", None) or c
        start = start_var.get().strip()
        end = end_var.get().strip()
        ok, err = validate_shift(start, end)
        if not ok:
            try:
                preview_lbl.config(
                    text=err or "班次配置无效",
                    fg=palette["error"],
                )
            except tk.TclError:
                pass
            return
        start_hms, _ = parse_shift_hms(start)
        end_hms, _ = parse_shift_hms(end)
        if start_hms is None or end_hms is None:
            return
        sh, sm, ss = start_hms
        eh, em, es = end_hms
        now = datetime.now()
        target, duration, delta, terr = target_from_shift(
            sh, sm, ss, eh, em, es, now
        )
        span = ""
        if duration is not None:
            total = int(duration.total_seconds())
            hh, rem = divmod(total, 3600)
            mm, sec = divmod(rem, 60)
            span = f"{hh:02d}:{mm:02d}:{sec:02d}"
        if terr or target is None:
            try:
                preview_lbl.config(
                    text=f"时长 {span} · {terr or '无法预览'}",
                    fg=palette.get("warning", palette["text_dim"]),
                )
            except tk.TclError:
                pass
            return
        label = format_target_label(target, now)
        delta_m = int(delta.total_seconds() // 60) if delta is not None else 0
        try:
            preview_lbl.config(
                text=f"时长 {span} · 若现在开始 → 目标 {label}"
                + (f"（已晚 {delta_m} 分）" if delta_m > 0 else ""),
                fg=palette.get("text_dim", palette["text"]),
            )
        except tk.TclError:
            pass

    def _save():
        start = start_var.get().strip()
        end = end_var.get().strip()
        ok, err = validate_shift(start, end)
        if not ok:
            _toast(err or "班次配置无效", kind="error")
            _update_preview()
            return
        start_hms, _ = parse_shift_hms(start)
        end_hms, _ = parse_shift_hms(end)
        if start_hms is None or end_hms is None:
            _toast("班次时刻无效", kind="error")
            return
        sh, sm, ss = start_hms
        eh, em, es = end_hms
        app._shift_start = f"{sh:02d}:{sm:02d}:{ss:02d}"
        app._shift_end = f"{eh:02d}:{em:02d}:{es:02d}"
        start_var.set(app._shift_start)
        end_var.set(app._shift_end)
        app._save_config()
        _refresh()
        _update_preview()
        _sync_main_shift_chip()
        try:
            from services.tray import refresh_tray_menu

            refresh_tray_menu(app)
        except (ImportError, AttributeError, RuntimeError, tk.TclError):
            pass
        _toast("班次配置已保存")

    enable_lbl = selectable_row(
        enable_host,
        app,
        c,
        "启用班次顺延",
        selected=False,
        on_click=_toggle_enabled,
        pady=SPACE_SM,
    )

    for var in (start_var, end_var):
        try:
            var.trace_add("write", _update_preview)
        except (tk.TclError, AttributeError):
            pass

    pill(
        btn_row,
        "保存班次",
        app=app,
        c=c,
        primary=True,
        command=_save,
    ).pack(side=tk.LEFT)

    def _refresh():
        enabled = bool(getattr(app, "_shift_enabled", False))
        try:
            set_selectable_selected(enable_lbl, enabled, text="启用班次顺延")
        except tk.TclError:
            pass
        # 外部刷新时同步输入框（主题重建后）
        try:
            cur_s = str(getattr(app, "_shift_start", "09:00:00") or "09:00:00")
            cur_e = str(getattr(app, "_shift_end", "18:00:00") or "18:00:00")
            if start_var.get() != cur_s:
                start_var.set(cur_s)
            if end_var.get() != cur_e:
                end_var.set(cur_e)
        except tk.TclError:
            pass
        _update_preview()

    refreshers.append(_refresh)
    _refresh()
    # 避免未使用警告（Entry 保留引用防 GC）
    _ = (start_entry, end_entry)
