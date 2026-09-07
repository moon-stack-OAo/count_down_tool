# -*- coding: utf-8 -*-
"""设置 · 自定义主题色编辑（预览 / 保存 / 重置）。"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import colorchooser
from typing import Any, Dict, Tuple

from core.themes import (
    is_valid_hex_color,
    resolve_theme,
    sanitize_theme_custom,
)
from ui.design.themed import register_themed, themed_frame, themed_label
from ui.design.tokens import FONT_BODY, FONT_CAPTION, SPACE_SM, SPACE_XS
from ui.settings.layout import card, pill, section_title

logger = logging.getLogger("count_down_tool")

# 常用语义色（不暴露全部 30+；不含 Mini 透明相关键）
EDITABLE_THEME_COLOR_KEYS: Tuple[Tuple[str, str], ...] = (
    ("bg", "背景"),
    ("card", "卡片"),
    ("accent", "强调色"),
    ("text", "主文字"),
    ("text_dim", "次要文字"),
    ("success", "成功"),
    ("warning", "警告"),
    ("error", "错误"),
    ("chip", "标签底"),
    ("border", "边框"),
    ("btn_primary", "主按钮"),
)

_SWATCH = 22


def theme_custom_dict(app) -> Dict[str, str]:
    """返回已消毒的自定义色副本；无则空 dict。"""
    cleaned = sanitize_theme_custom(getattr(app, "_theme_custom", None))
    return dict(cleaned) if cleaned else {}


def preset_color_for(app, key: str) -> str:
    """当前预设主题下某键的默认色（不含 custom 覆盖）。"""
    tid = getattr(app, "_theme_id", None)
    base = resolve_theme(tid, None)
    return str(base.get(key, "#888888"))


def effective_color_for(app, key: str) -> str:
    """当前生效色（预设 + custom）。"""
    colors = getattr(app, "COLORS", None)
    if isinstance(colors, dict) and key in colors and colors[key]:
        return str(colors[key])
    return str(
        resolve_theme(
            getattr(app, "_theme_id", None),
            getattr(app, "_theme_custom", None),
        ).get(key, "#888888")
    )


def set_custom_color(app, key: str, value: str, *, preview: bool = True) -> bool:
    """覆盖单键自定义色；非法色返回 False。"""
    if not isinstance(key, str) or not key:
        return False
    # 仅允许覆盖预设里已有的键
    base_keys = resolve_theme(getattr(app, "_theme_id", None), None)
    if key not in base_keys:
        return False
    if not is_valid_hex_color(value):
        return False
    custom = theme_custom_dict(app)
    custom[key] = value.strip()
    app._theme_custom = sanitize_theme_custom(custom)
    if preview:
        from app.theme import refresh_theme_colors

        refresh_theme_colors(app, save=False)
    return True


def clear_custom_color(app, key: str, *, preview: bool = True) -> bool:
    """清除单键覆盖；键本就不存在也返回 True。

    清空后写 ``{}``（非 None），以便 ``_save_config`` 能把磁盘上的
    theme_custom 一并清掉。
    """
    custom = theme_custom_dict(app)
    if key in custom:
        del custom[key]
    cleaned = sanitize_theme_custom(custom)
    app._theme_custom = cleaned if cleaned is not None else {}
    if preview:
        from app.theme import refresh_theme_colors

        refresh_theme_colors(app, save=False)
    return True


def clear_all_custom_colors(app, *, preview: bool = True, save: bool = False) -> None:
    """清空全部自定义色。"""
    app._theme_custom = {}
    if preview:
        from app.theme import refresh_theme_colors

        refresh_theme_colors(app, save=save)
    elif save:
        try:
            app._save_config()
        except (OSError, TypeError, ValueError, AttributeError):
            logger.debug("清空自定义色后保存失败", exc_info=True)


def save_theme_custom(app) -> None:
    """将当前内存中的 theme_custom 持久化。"""
    from app.theme import refresh_theme_colors

    # None → {}，确保落盘能清空旧覆盖
    if getattr(app, "_theme_custom", None) is None:
        app._theme_custom = {}
    refresh_theme_colors(app, save=True)


def build_theme_custom_section(app, parent, c, refreshers) -> None:
    """外观 Tab：自定义颜色分区。"""
    custom_card = card(parent, c)
    section_title(custom_card, app, c, "自定义颜色")

    themed_label(
        custom_card,
        app,
        "点击色块选择颜色；可先预览再保存。切换预设主题后，自定义色仍作为覆盖生效。",
        fg_role="text_muted",
        bg_role="card",
        font_size=FONT_CAPTION,
        c=c,
        wraplength=420,
        justify=tk.LEFT,
        padx=SPACE_SM,
    ).pack(fill=tk.X, pady=(0, SPACE_SM))

    rows_host = themed_frame(custom_card, app, role="card", c=c)
    rows_host.pack(fill=tk.X, padx=SPACE_SM)

    swatches: Dict[str, tk.Frame] = {}
    hex_lbls: Dict[str, tk.Label] = {}
    reset_btns: Dict[str, Any] = {}

    def _toast(msg: str, *, kind: str = "ok") -> None:
        from ui.settings.shell import show_settings_toast

        show_settings_toast(app, msg, kind=kind)

    def _refresh_rows() -> None:
        custom = theme_custom_dict(app)
        for key, _label in EDITABLE_THEME_COLOR_KEYS:
            color = effective_color_for(app, key)
            sw = swatches.get(key)
            if sw is not None:
                try:
                    sw.config(bg=color)
                    # 色块角色跟当前键，便于设置窗 recolor 时大致跟色
                    register_themed(sw, bg=key if key in ("bg", "card", "accent", "chip", "border", "error") else "chip")
                except tk.TclError:
                    pass
            hl = hex_lbls.get(key)
            if hl is not None:
                try:
                    mark = " · 已改" if key in custom else ""
                    hl.config(text=f"{color}{mark}")
                except tk.TclError:
                    pass
            rb = reset_btns.get(key)
            if rb is not None:
                try:
                    if key in custom:
                        rb.pack(side=tk.RIGHT, padx=(SPACE_XS, 0))
                    else:
                        rb.pack_forget()
                except tk.TclError:
                    pass

    def _pick(key: str, label: str) -> None:
        initial = effective_color_for(app, key)
        parent_win = getattr(app, "_settings_window", None) or app.master
        try:
            _rgb, hex_val = colorchooser.askcolor(
                color=initial,
                title=f"选择「{label}」颜色",
                parent=parent_win,
            )
        except tk.TclError:
            logger.debug("颜色选择器失败", exc_info=True)
            return
        if not hex_val:
            return
        if not set_custom_color(app, key, str(hex_val), preview=True):
            _toast("无效颜色", kind="error")
            return
        _refresh_rows()
        _toast(f"已预览「{label}」，请点保存以持久化")

    def _reset_one(key: str, label: str) -> None:
        clear_custom_color(app, key, preview=True)
        _refresh_rows()
        _toast(f"已恢复「{label}」为预设色")

    def _save() -> None:
        save_theme_custom(app)
        _refresh_rows()
        _toast("自定义颜色已保存")

    def _reset_all() -> None:
        clear_all_custom_colors(app, preview=True, save=True)
        _refresh_rows()
        _toast("已重置全部自定义色")

    # 仅展示当前主题色表里存在的键
    known = set(resolve_theme(getattr(app, "_theme_id", None), None).keys())
    for key, label in EDITABLE_THEME_COLOR_KEYS:
        if key not in known:
            continue
        row = themed_frame(rows_host, app, role="card", c=c)
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

        swatch = tk.Frame(
            row,
            width=_SWATCH,
            height=_SWATCH,
            bg=effective_color_for(app, key),
            highlightthickness=1,
            highlightbackground=c.get("border", "#2A3A4E"),
            cursor="hand2",
        )
        swatch.pack(side=tk.LEFT, padx=(SPACE_SM, SPACE_XS))
        swatch.pack_propagate(False)
        register_themed(swatch, bg=key if key in ("bg", "card", "accent", "chip", "border", "error") else "chip")
        swatch.bind("<Button-1>", lambda e, k=key, lb=label: _pick(k, lb))
        swatches[key] = swatch

        hex_lbl = themed_label(
            row,
            app,
            effective_color_for(app, key),
            fg_role="text_dim",
            bg_role="card",
            font_size=FONT_CAPTION,
            c=c,
            cursor="hand2",
        )
        hex_lbl.pack(side=tk.LEFT, padx=(0, SPACE_SM))
        hex_lbl.bind("<Button-1>", lambda e, k=key, lb=label: _pick(k, lb))
        hex_lbls[key] = hex_lbl

        reset_lbl = themed_label(
            row,
            app,
            "重置",
            fg_role="accent",
            bg_role="card",
            font_size=FONT_CAPTION,
            c=c,
            cursor="hand2",
        )
        reset_lbl.bind("<Button-1>", lambda e, k=key, lb=label: _reset_one(k, lb))
        reset_btns[key] = reset_lbl

    btn_row = themed_frame(custom_card, app, role="card", c=c)
    btn_row.pack(fill=tk.X, padx=SPACE_SM, pady=(SPACE_SM, 0))

    pill(btn_row, "保存", app=app, c=c, primary=True, command=_save).pack(
        side=tk.LEFT
    )
    pill(
        btn_row,
        "重置全部自定义",
        app=app,
        c=c,
        primary=False,
        command=_reset_all,
    ).pack(side=tk.LEFT, padx=(SPACE_SM, 0))

    refreshers.append(_refresh_rows)
    _refresh_rows()


__all__ = (
    "EDITABLE_THEME_COLOR_KEYS",
    "theme_custom_dict",
    "preset_color_for",
    "effective_color_for",
    "set_custom_color",
    "clear_custom_color",
    "clear_all_custom_colors",
    "save_theme_custom",
    "build_theme_custom_section",
)
