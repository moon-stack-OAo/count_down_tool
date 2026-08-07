# -*- coding: utf-8 -*-
"""macOS 菜单栏（替代 pystray）。

pystray 在 Darwin 上会在后台线程跑 NSApplication.run，与 Tk 主循环争用 AppKit，
易在 Tcl AfterProc → PyEval_RestoreThread 时触发 TstateNULL 直接 abort。
因此 mac 统一用 Tk 菜单栏，全程主线程。

UI 仅经 app.ui_actions，本模块不 import ui。
"""

from __future__ import annotations

import logging
import platform
import tkinter as tk

from core.countdown_core import APP_NAME, __version__, button_text_for_state
from services.menu_labels import (
    TRAY_QUICK_START_MENU_LABEL,
    TRAY_QUICK_START_PRESETS,
    tray_mini_menu_label,
    tray_window_menu_label,
)

logger = logging.getLogger("count_down_tool")


def _ui(app):
    return getattr(app, "ui_actions", None)


def is_darwin() -> bool:
    return platform.system() == "Darwin"


def init_mac_menubar(app) -> bool:
    """安装菜单栏与 Dock 重开钩子。成功返回 True。"""
    if not is_darwin():
        return False
    root = app.master
    try:
        menubar = tk.Menu(root)

        # Apple 菜单（关于）
        apple = tk.Menu(menubar, name="apple", tearoff=0)
        menubar.add_cascade(menu=apple)

        def _about():
            ui = _ui(app)
            if ui is not None:
                ui.show_info(
                    app,
                    f"{APP_NAME}\n版本 {__version__}",
                    title=f"关于 {APP_NAME}",
                )

        apple.add_command(label=f"关于 {APP_NAME}", command=_about)

        # 设置：每次打开前重建，保证状态文案最新
        settings = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="设置", menu=settings)
        settings.configure(postcommand=lambda: _fill_settings(settings, app))
        _fill_settings(settings, app)

        root.config(menu=menubar)
        app._mac_menubar = menubar
        app._mac_settings_menu = settings
        app._status_menu_active = True
        app.tray_icon = None

        def _reopen(*_args):
            try:
                app._show_full_mode()
            except (tk.TclError, AttributeError, RuntimeError):
                logger.debug("mac ReopenApplication 失败", exc_info=True)

        try:
            root.createcommand("tk::mac::ReopenApplication", _reopen)
        except tk.TclError:
            pass

        logger.info("macOS 使用菜单栏（未启用 pystray）")
        return True
    except (tk.TclError, AttributeError, RuntimeError, ImportError):
        # mac 菜单栏边界：初始化失败则降级，不阻断启动
        logger.exception("macOS 菜单栏初始化失败")
        app._status_menu_active = False
        return False


def _fill_settings(menu: tk.Menu, app) -> None:
    try:
        menu.delete(0, tk.END)
    except tk.TclError:
        return

    menu.add_command(
        label="设置中心…",
        command=lambda: _show_settings(app),
    )
    menu.add_separator()

    menu.add_command(
        label=tray_window_menu_label(app._is_mini),
        command=app._show_full_mode,
    )
    pick_state = tk.DISABLED if app._inputs_locked() else tk.NORMAL
    menu.add_command(
        label="选择时间",
        command=app._show_time_picker,
        state=pick_state,
    )
    quick = tk.Menu(menu, tearoff=0)
    for label, hours, minutes, seconds in TRAY_QUICK_START_PRESETS:
        quick.add_command(
            label=label,
            command=lambda h=hours, m=minutes, s=seconds: _quick_start(
                app, h, m, s
            ),
        )
    menu.add_cascade(label=TRAY_QUICK_START_MENU_LABEL, menu=quick)
    menu.add_command(
        label=button_text_for_state(app._state),
        command=app.toggle_countdown,
    )
    menu.add_command(
        label="重置",
        command=lambda: _reset_countdown(app),
    )
    menu.add_separator()
    menu.add_command(
        label=tray_mini_menu_label(app._is_mini),
        command=app._toggle_mini_mode,
    )
    transparent_on = bool(getattr(app, "_transparent_mode", False))
    menu.add_command(
        label=("✓ 透明模式" if transparent_on else "透明模式"),
        command=app._toggle_transparent_mode,
    )
    size_state = tk.NORMAL if app._is_mini else tk.DISABLED
    menu.add_command(
        label="恢复默认大小",
        command=lambda: _reset_mini_size(app),
        state=size_state,
    )
    menu.add_command(
        label="字体颜色…",
        command=lambda: _show_text_picker(app),
    )
    menu.add_separator()
    menu.add_command(
        label="检查更新…",
        command=lambda: _open_update(app),
    )
    menu.add_separator()
    menu.add_command(label="退出", command=app._quit_app)


def _quick_start(app, hours: int, minutes: int, seconds: int) -> None:
    """菜单栏快捷开始（已在主线程）。"""
    app._set_preset_time(hours, minutes, seconds, force=True)


def _reset_countdown(app) -> None:
    """菜单栏重置倒计时。"""
    app.reset()


def _open_update(app) -> None:
    """菜单栏检查更新。"""
    from services.updater import open_update_from_ui

    open_update_from_ui(app)


def _show_settings(app) -> None:
    ui = _ui(app)
    if ui is not None:
        ui.show_settings(app)


def _reset_mini_size(app) -> None:
    ui = _ui(app)
    if app._is_mini and ui is not None:
        ui.reset_mini_size(app)


def _show_text_picker(app) -> None:
    ui = _ui(app)
    if ui is not None:
        ui.show_mini_text_picker(app)


def refresh_mac_menubar(app) -> None:
    """状态变化后重建设置菜单（若当前已挂载）。"""
    if not getattr(app, "_status_menu_active", False):
        return
    menu = getattr(app, "_mac_settings_menu", None)
    if menu is None:
        return
    try:
        if menu.winfo_exists():
            _fill_settings(menu, app)
    except tk.TclError:
        pass
