# -*- coding: utf-8 -*-
"""完整 / Mini / 托盘 显示模式切换。"""

from __future__ import annotations

from tkinter import messagebox

from services.tray import refresh_tray_menu


def has_tray(app) -> bool:
    """是否可隐藏到后台（托盘或 mac 菜单栏）。"""
    if getattr(app, "_status_menu_active", False):
        return True
    return bool(getattr(app, "tray_icon", None))


def show_full_mode(app) -> None:
    """显示完整模式窗口（托盘单击/菜单恢复）。"""
    if app._is_mini:
        switch_to_full(app)
        return
    app.master.deiconify()
    app._set_taskbar_visible()
    app._bring_full_to_front()
    app._center_window_later()


def hide_to_tray(app) -> None:
    if not has_tray(app):
        app._quit_app()
        return
    if app._first_hide:
        app._first_hide = False
        import platform

        if platform.system() == "Darwin":
            tip = (
                "程序已隐藏到后台。\n"
                "可通过菜单栏「设置」、Dock 图标或再次打开应用恢复窗口。"
            )
        else:
            tip = (
                "程序已最小化到系统托盘。\n"
                "右键托盘图标可切换 Mini 模式或退出。"
            )
        app.master.after(
            0,
            lambda: messagebox.showinfo("提示", tip, parent=app.master),
        )
    app.master.withdraw()


def toggle_mini_mode(app) -> None:
    if app._is_mini:
        switch_to_full(app)
    else:
        switch_to_mini(app)


def switch_to_mini(app) -> None:
    """切换到 Mini 模式。"""
    app._is_mini = True
    app._last_mode = "mini"
    app.master.update()
    app.master.withdraw()
    app._create_mini_window()
    app._save_config()
    refresh_tray_menu(app)


def switch_to_full(app) -> None:
    """切换到完整模式。"""
    app._is_mini = False
    app._last_mode = "full"
    app._destroy_mini_window()
    app.master.deiconify()
    # withdraw/deiconify 后需重新声明任务栏/Alt+Tab 可见
    app._set_taskbar_visible()
    app._bring_full_to_front()
    app._center_window_later()
    app._save_config()
    refresh_tray_menu(app)
