# -*- coding: utf-8 -*-
"""完整窗右键菜单 + Mini 字色工具（供托盘复用）。"""

import platform
import tkinter as tk
from tkinter import messagebox

from core.countdown_core import (
    APP_NAME,
    MINI_TEXT_COLOR_KEYS,
    MINI_TEXT_DEFAULTS,
    button_text_for_state,
    normalize_mini_text,
)
from core.themes import list_themes
from services.autostart import is_autostart_enabled, set_autostart


def tray_window_menu_label(is_mini: bool) -> str:
    """托盘「显示/展开」文案。"""
    return "展开主窗口" if is_mini else "显示主窗口"


def tray_mini_menu_label(is_mini: bool) -> str:
    """托盘 Mini 切换文案。"""
    return "退出 Mini 模式" if is_mini else "Mini 模式"


def _styled_menu(app, parent):
    return tk.Menu(
        parent,
        tearoff=0,
        bg=app.COLORS["card"],
        fg=app.COLORS["text"],
        activebackground=app.COLORS["accent"],
        activeforeground=app.COLORS["white"],
    )


def _popup_xy(event):
    """从事件解析屏幕坐标。"""
    x = getattr(event, "x_root", None)
    y = getattr(event, "y_root", None)
    if x is None or y is None:
        widget = getattr(event, "widget", None)
        if widget is not None:
            x = widget.winfo_rootx() + max(0, getattr(event, "x", 0))
            y = widget.winfo_rooty() + max(0, getattr(event, "y", 0))
        else:
            return None, None
    return int(x), int(y)


def _popup(menu, event):
    """弹出菜单。兼容右键与按钮点击（macOS 按钮事件坐标也可能有效）。"""
    try:
        x, y = _popup_xy(event)
        if x is None:
            return
        menu.tk_popup(x, y)
    except tk.TclError:
        pass
    finally:
        try:
            menu.grab_release()
        except tk.TclError:
            pass


def _menu_alive(menu):
    try:
        return bool(menu) and menu.winfo_exists()
    except tk.TclError:
        return False


def add_countdown_toggle_item(menu, app):
    """开始 / 暂停 / 继续 / 重新开始（按当前 app._state 生成文案）。"""
    menu.add_command(
        label=button_text_for_state(app._state),
        command=app.toggle_countdown,
    )


def add_exit_item(menu, app):
    menu.add_command(label="退出", command=app._quit_app)


def _toggle_autostart_ui(app):
    """主线程切换开机自启（与托盘逻辑一致）。"""
    target = not is_autostart_enabled()
    ok = set_autostart(target)
    if not ok:
        messagebox.showerror(
            APP_NAME,
            "设置开机自启失败。\n请检查是否有权限写入启动文件夹。",
            parent=app.master,
        )
        app._autostart = is_autostart_enabled()
        return
    app._autostart = target
    app._save_config()


def add_autostart_item(menu, app):
    """开机自启（Windows 有效；其它平台项仍可点，set_autostart 内部会处理）。"""
    label = "✓ 开机自启" if app._autostart else "开机自启"
    menu.add_command(label=label, command=lambda: _toggle_autostart_ui(app))


def add_theme_cascade(menu, app):
    """主题级联子菜单。"""
    theme_menu = _styled_menu(app, menu)
    for tid, name in list_themes():
        mark = "✓ " if app._theme_id == tid else ""
        theme_menu.add_command(
            label=f"{mark}{name}",
            command=lambda t=tid: app._apply_theme(t),
        )
    menu.add_cascade(label="主题", menu=theme_menu)


def current_mini_text_key(app, role):
    """当前角色生效的色键（含默认）。"""
    cfg = normalize_mini_text(getattr(app, "_mini_text", None))
    return cfg.get(role, MINI_TEXT_DEFAULTS.get(role, "white"))


def set_mini_text_color(app, role, color_key):
    """写入 Mini 字色并刷新显示（托盘/配置共用）。"""
    cfg = dict(normalize_mini_text(getattr(app, "_mini_text", None)))
    if color_key not in MINI_TEXT_COLOR_KEYS:
        return
    default_key = MINI_TEXT_DEFAULTS.get(role)
    if color_key == default_key:
        cfg.pop(role, None)
    else:
        cfg[role] = color_key
    app._mini_text = cfg
    app._save_config()
    from ui.mini_window import sync_mini_state

    sync_mini_state(app)


def reset_mini_text_colors(app):
    """恢复 Mini 字色为默认。"""
    app._mini_text = {}
    app._save_config()
    from ui.mini_window import sync_mini_state

    sync_mini_state(app)


def _fill_full_menu(menu, app):
    """按最新状态填充完整窗右键菜单。"""
    try:
        menu.delete(0, tk.END)
    except tk.TclError:
        return
    menu.add_command(label="切换到 Mini 模式", command=app._switch_to_mini)
    add_countdown_toggle_item(menu, app)
    menu.add_separator()
    def _open_settings():
        from ui.settings_window import show_settings

        show_settings(app)

    menu.add_command(label="设置…", command=_open_settings)
    if app._has_tray():
        menu.add_command(label="隐藏到托盘", command=app._hide_to_tray)
    else:
        if platform.system() == "Windows":
            add_autostart_item(menu, app)
        add_theme_cascade(menu, app)
    menu.add_separator()
    add_exit_item(menu, app)


def _ensure_ctx_menu(app, attr, parent, filler):
    """复用 Menu，用 postcommand 在每次显示前按最新状态重建条目。"""
    menu = getattr(app, attr, None)
    if not _menu_alive(menu):
        menu = _styled_menu(app, parent)
        setattr(app, attr, menu)

    def _post():
        filler(menu, app)

    try:
        menu.configure(postcommand=_post)
    except tk.TclError:
        pass
    filler(menu, app)
    return menu


def popup_full_menu(app, event):
    """完整窗右键菜单：每次显示前按最新状态重建。"""
    menu = _ensure_ctx_menu(app, "_full_ctx_menu", app.master, _fill_full_menu)
    _popup(menu, event)


def bind_full_context_menu(app, *widgets):
    """为完整窗区域绑定右键（Button-3；macOS 另绑 Control-Button-1）。"""
    for w in widgets:
        if w is None:
            continue
        w.bind("<Button-3>", lambda e, a=app: popup_full_menu(a, e))
        if platform.system() == "Darwin":
            w.bind("<Control-Button-1>", lambda e, a=app: popup_full_menu(a, e))


def bind_full_context_menu_tree(app, root_widget):
    """递归绑定 root 及其子控件（用于主内容区）。"""
    if root_widget is None:
        return

    def _walk(w):
        bind_full_context_menu(app, w)
        try:
            children = w.winfo_children()
        except tk.TclError:
            return
        for child in children:
            _walk(child)

    _walk(root_widget)
