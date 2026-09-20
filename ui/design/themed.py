# -*- coding: utf-8 -*-
"""Themed 控件工厂：绑定 app.COLORS，并预留 _theme_roles 供后续就地换肤。"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Mapping, MutableMapping, Optional

from ui.design.tokens import FONT_BODY

# Frame 背景 role → COLORS 键（含作分隔线/强调条背景的语义色）
_FRAME_ROLES = frozenset(
    {
        "card",
        "bg",
        "glass",
        "title_bar",
        "chip",
        "chip_active",
        "input_bg",
        "border",
        "border_subtle",
        "accent",
        "error",
        "toast_bg",
        "tab_active",
    }
)

# Label 前景 role → COLORS 键（含常用语义色）
_LABEL_FG_ROLES = frozenset(
    {
        "text",
        "text_dim",
        "text_muted",
        "text_secondary",
        "chip_text",
        "accent",
        "accent_glow",
        "success",
        "error",
        "warning",
        "white",
    }
)


def resolve_colors(app, c: Optional[Mapping[str, str]] = None) -> Mapping[str, str]:
    """优先显式 c，否则 app.COLORS。"""
    if isinstance(c, Mapping) and c:
        return c
    return getattr(app, "COLORS", {}) or {}


def color_of(
    colors: Mapping[str, str],
    key: str,
    *fallbacks: str,
    default: str = "#1A2332",
) -> str:
    """按键取色，支持备用键。"""
    if key in colors and colors[key]:
        return str(colors[key])
    for fb in fallbacks:
        if fb in colors and colors[fb]:
            return str(colors[fb])
    return default


def register_themed(widget: tk.Misc, **roles: str) -> tk.Misc:
    """在控件上登记主题角色，供后续 B1 就地换色遍历。

    约定：
    - 关键字为配置属性名（bg / fg / highlightbackground / trough / thumb …）
    - 值为 COLORS 键名（如 card、text、accent）
    - 存储于 widget._theme_roles: dict[str, str]
    """
    existing = getattr(widget, "_theme_roles", None)
    if isinstance(existing, MutableMapping):
        existing.update(roles)
    else:
        widget._theme_roles = dict(roles)  # type: ignore[attr-defined]
    return widget


def _is_ttk_widget(widget: tk.Misc) -> bool:
    mod = getattr(type(widget), "__module__", "") or ""
    return mod.startswith("tkinter.ttk")


def _resolve_role_color(colors: Mapping[str, str], key: str) -> Optional[str]:
    """按角色键取色；常见别名带回退。"""
    if not key:
        return None
    if key == "text_muted":
        return color_of(colors, "text_muted", "text_dim", "text", default="")
    if key == "text_dim":
        return color_of(colors, "text_dim", "text", default="")
    if key == "card_border":
        return color_of(colors, "card_border", "border", default="")
    if key == "btn_on_primary":
        return color_of(colors, "btn_on_primary", "bg", default="")
    if key == "btn_primary":
        return color_of(colors, "btn_primary", "accent", default="")
    val = color_of(colors, key, default="")
    return val or None


def _rebind_hover_bg(widget: tk.Misc, colors: Mapping[str, str], roles: Mapping[str, str]) -> None:
    """若控件登记了 hover 角色，按新色重绑 Enter/Leave（pill / selectable_row）。"""
    hover_key = getattr(widget, "_theme_hover_role", None)
    if not hover_key:
        return
    base_key = roles.get("bg")
    if not base_key:
        return
    base = _resolve_role_color(colors, base_key)
    hover = _resolve_role_color(colors, str(hover_key))
    if not base or not hover:
        return
    try:
        widget.unbind("<Enter>")
        widget.unbind("<Leave>")
        widget.bind("<Enter>", lambda e, w=widget, h=hover: w.config(bg=h))
        widget.bind("<Leave>", lambda e, w=widget, b=base: w.config(bg=b))
    except tk.TclError:
        pass


def _recolor_rounded_frame(widget: tk.Misc, colors: Mapping[str, str], roles: Mapping[str, str]) -> bool:
    """RoundedFrame：configure_colors + Canvas 底板跟主背景。"""
    configure_colors = getattr(widget, "configure_colors", None)
    if not callable(configure_colors):
        return False
    bg_key = roles.get("bg")
    border_key = roles.get("border") or roles.get("border_color") or roles.get("highlightbackground")
    kw: dict[str, Any] = {}
    if bg_key:
        c = _resolve_role_color(colors, bg_key)
        if c:
            kw["bg_color"] = c
    if border_key:
        c = _resolve_role_color(colors, border_key)
        if c:
            kw["border_color"] = c
    try:
        # Canvas 透出区域跟窗口底色，避免圆角外沿旧色
        canvas_bg = _resolve_role_color(colors, "bg")
        if canvas_bg:
            widget.configure(bg=canvas_bg)
        if kw:
            configure_colors(**kw)
        return True
    except tk.TclError:
        return False


def _recolor_circle_canvas(widget: tk.Misc, colors: Mapping[str, str]) -> bool:
    """标题栏圆形钮：更新底板 / 圆 / 字，并重绑悬停色。"""
    items = getattr(widget, "_circle_items", None)
    if not items:
        return False
    try:
        from ui.widgets import update_circle_button
    except ImportError:
        return False
    title_bg = _resolve_role_color(colors, "title_bar") or color_of(colors, "bg")
    fill_default = _resolve_role_color(colors, "btn_default") or "#334155"
    text_default = _resolve_role_color(colors, "text_dim") or "#8B9CB3"
    hover_key = getattr(widget, "_hover_role", None) or "accent"
    hover = _resolve_role_color(colors, str(hover_key)) or fill_default
    white = _resolve_role_color(colors, "white") or "#FFFFFF"
    enabled = bool(getattr(widget, "_circle_enabled", True))
    try:
        widget.configure(bg=title_bg)
        update_circle_button(widget, items, fill=fill_default, text_color=text_default)
        if enabled:
            widget.unbind("<Enter>")
            widget.unbind("<Leave>")
            widget.bind(
                "<Enter>",
                lambda e, c=widget, it=items, h=hover, w=white: update_circle_button(
                    c, it, fill=h, text_color=w
                ),
            )
            widget.bind(
                "<Leave>",
                lambda e, c=widget, it=items, f=fill_default, t=text_default: update_circle_button(
                    c, it, fill=f, text_color=t
                ),
            )
        return True
    except tk.TclError:
        return False


def recolor_one(widget: tk.Misc, colors: Mapping[str, str]) -> bool:
    """按 `_theme_roles` 就地换色单个控件；成功返回 True。"""
    if not colors:
        return False
    roles = getattr(widget, "_theme_roles", None)
    if not isinstance(roles, Mapping) or not roles:
        # 圆形钮可能只挂了 _circle_items
        if getattr(widget, "_circle_items", None):
            return _recolor_circle_canvas(widget, colors)
        return False

    if getattr(widget, "_circle_items", None):
        ok = _recolor_circle_canvas(widget, colors)
        # 仍继续写 roles（如 bg=title_bar）
    else:
        ok = False

    if callable(getattr(widget, "configure_colors", None)):
        if _recolor_rounded_frame(widget, colors, roles):
            return True

    # ThinScrollbar：trough/thumb 为自定义属性，走 apply_theme_colors
    apply_sb = getattr(widget, "apply_theme_colors", None)
    if callable(apply_sb) and any(
        k in roles for k in ("trough", "thumb", "thumb_hover")
    ):
        sb_kw: dict[str, str] = {}
        for attr in ("bg", "trough", "thumb", "thumb_hover"):
            key = roles.get(attr)
            if not key:
                continue
            resolved = _resolve_role_color(colors, str(key))
            if resolved:
                sb_kw[attr] = resolved
        if sb_kw:
            try:
                apply_sb(**sb_kw)
                ok = True
            except (tk.TclError, TypeError, AttributeError):
                pass
            if ok:
                return True

    is_ttk = _is_ttk_widget(widget)
    cfg: dict[str, str] = {}
    for attr, color_key in roles.items():
        if attr in ("border", "border_color", "trough", "thumb", "thumb_hover"):
            # RoundedFrame / ThinScrollbar 专用，已处理或跳过
            continue
        resolved = _resolve_role_color(colors, str(color_key))
        if not resolved:
            continue
        if is_ttk:
            if attr == "bg":
                cfg["background"] = resolved
            elif attr == "fg":
                cfg["foreground"] = resolved
            else:
                cfg[attr] = resolved
        else:
            cfg[attr] = resolved
    if cfg:
        try:
            widget.configure(**cfg)
            ok = True
        except tk.TclError:
            pass
    if ok:
        _rebind_hover_bg(widget, colors, roles)
    return ok


def recolor_widget_tree(root: tk.Misc, colors: Mapping[str, str]) -> int:
    """深度优先遍历：有 `_theme_roles`（或圆形钮元数据）则换色；返回成功数。"""
    if root is None or not colors:
        return 0
    count = 0

    def _walk(w: tk.Misc) -> None:
        nonlocal count
        try:
            children = list(w.winfo_children())
        except tk.TclError:
            return
        for child in children:
            _walk(child)
        if recolor_one(w, colors):
            count += 1

    _walk(root)
    return count


def recolor_app(app, colors: Optional[Mapping[str, str]] = None) -> int:
    """就地换主窗已登记控件、进度条 Canvas 等；返回换色控件数。

    ttk Style 应由调用方先 `_setup_styles()`；本函数不 destroy 子树。
    不触碰 Mini 透明色键（Mini 由调用方决定重建）。
    """
    c = resolve_colors(app, colors)
    if not c:
        return 0
    master = getattr(app, "master", None)
    if master is None:
        return 0

    n = recolor_widget_tree(master, c)

    # 进度条：底板 + track/fill（fill 色随状态，委托既有刷新）
    progress = getattr(app, "progress_canvas", None)
    if progress is not None:
        try:
            card_bg = _resolve_role_color(c, "card") or color_of(c, "card", "bg")
            progress.configure(bg=card_bg)
            n += 1
        except tk.TclError:
            pass
        refresh = getattr(app, "_refresh_progress_bar", None)
        if callable(refresh):
            try:
                refresh()
            except (tk.TclError, AttributeError, TypeError, ValueError):
                pass

    # 显式 RoundedFrame 兜底（树遍历应已覆盖；缺登记时仍更新）
    for attr, bg_key, border_key in (
        ("_settings_card", "card", "card_border"),
        ("_countdown_card", "card", "card_border"),
    ):
        card = getattr(app, attr, None)
        if card is None or not callable(getattr(card, "configure_colors", None)):
            continue
        roles = getattr(card, "_theme_roles", None)
        if isinstance(roles, Mapping) and roles:
            continue
        try:
            card.configure(bg=_resolve_role_color(c, "bg") or color_of(c, "bg"))
            card.configure_colors(
                bg_color=_resolve_role_color(c, bg_key),
                border_color=_resolve_role_color(c, border_key),
            )
            n += 1
        except (tk.TclError, TypeError, AttributeError):
            pass

    return n


def themed_frame(
    parent,
    app,
    *,
    role: str = "card",
    c: Optional[Mapping[str, str]] = None,
    **kwargs: Any,
) -> tk.Frame:
    """主题化 Frame；role 对应 COLORS 背景键（card/bg/glass/title_bar 等）。"""
    colors = resolve_colors(app, c)
    role_key = role if role in _FRAME_ROLES else "card"
    bg = color_of(colors, role_key, "card", "bg", default="#1A2332")
    fr = tk.Frame(parent, bg=bg, **kwargs)
    register_themed(fr, bg=role_key)
    return fr


def themed_label(
    parent,
    app,
    text: str = "",
    *,
    fg_role: Optional[str] = None,
    role: Optional[str] = None,
    bg_role: Optional[str] = None,
    font_size: int = FONT_BODY,
    bold: bool = False,
    c: Optional[Mapping[str, str]] = None,
    **kwargs: Any,
) -> tk.Label:
    """主题化 Label。

    - fg_role：前景色键（text / text_dim / text_muted / accent …）
    - role：fg_role 的兼容别名（既有调用可继续用 role=）
    - bg_role：背景色键；None 时默认 card
    """
    colors = resolve_colors(app, c)
    raw_fg = fg_role if fg_role is not None else (role if role is not None else "text")
    fg_key = raw_fg if raw_fg in _LABEL_FG_ROLES else "text"
    bg_key = bg_role if bg_role in _FRAME_ROLES else "card"
    if fg_key == "text_muted":
        fg = color_of(colors, "text_muted", "text_dim", "text", default="#64748B")
    elif fg_key == "text_dim":
        fg = color_of(colors, "text_dim", "text", default="#8B9CB3")
    else:
        fg = color_of(colors, fg_key, "text", default="#F1F5F9")
    bg = color_of(colors, bg_key, "card", "bg", default="#1A2332")
    font = (
        app._font("label", font_size, bold=True)
        if bold
        else app._font("label", font_size)
    )
    kw = dict(kwargs)
    kw.setdefault("anchor", "w")
    lbl = tk.Label(parent, text=text, font=font, bg=bg, fg=fg, **kw)
    register_themed(lbl, bg=bg_key, fg=fg_key)
    return lbl


def themed_button(
    parent,
    app,
    text: str,
    *,
    primary: bool = True,
    danger: bool = False,
    command=None,
    c: Optional[Mapping[str, str]] = None,
    **kwargs: Any,
) -> tk.Label:
    """对话框/设置确认取消入口；薄封装 make_pill（勿再长第三套）。

    主窗主操作请用 ttk Accent/Primary*/Secondary；快捷预设用 make_chip。
    """
    from ui.widgets import make_pill

    return make_pill(
        parent,
        text,
        app=app,
        c=c,
        primary=primary,
        danger=danger,
        command=command,
        **kwargs,
    )


__all__ = (
    "resolve_colors",
    "color_of",
    "register_themed",
    "recolor_one",
    "recolor_widget_tree",
    "recolor_app",
    "themed_frame",
    "themed_label",
    "themed_button",
)
