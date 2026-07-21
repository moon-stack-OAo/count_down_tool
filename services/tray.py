# -*- coding: utf-8 -*-
"""系统托盘：Windows 用 pystray；macOS 用 Tk 菜单栏（见 mac_menu）。

回调经 master.after 回主线程。Darwin 禁止后台 NSApplication.run，避免与 Tk 冲突崩溃。
"""

import logging
import os
import platform
import threading
from tkinter import messagebox

from core.countdown_core import APP_NAME, button_text_for_state
from core.themes import list_themes
from services.autostart import is_autostart_enabled, set_autostart
from ui.context_menus import tray_mini_menu_label, tray_window_menu_label

logger = logging.getLogger("count_down_tool")

try:
    import pystray

    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False
    pystray = None


def init_tray_icon(app, icon_path):
    """创建状态菜单入口。macOS 走菜单栏；其它平台走 pystray 后台线程。"""
    app.tray_icon = None
    app._status_menu_active = False

    if platform.system() == "Darwin":
        from services.mac_menu import init_mac_menubar

        init_mac_menubar(app)
        return

    if not HAS_PYSTRAY:
        return
    try:
        image = load_tray_icon(icon_path)
        theme_items = []
        for tid, name in list_themes():
            theme_items.append(
                pystray.MenuItem(
                    name,
                    make_tray_theme_handler(app, tid),
                    checked=make_tray_theme_checked(app, tid),
                )
            )
        menu = pystray.Menu(
            # 文案随 Mini/完整模式动态变化
            pystray.MenuItem(
                lambda _: tray_window_menu_label(app._is_mini),
                lambda icon=None, item=None: tray_show_window(app),
                default=True,
            ),
            pystray.MenuItem(
                "选择时间",
                lambda icon=None, item=None: tray_show_time_picker(app),
                enabled=lambda _: not app._inputs_locked(),
            ),
            pystray.MenuItem(lambda _: button_text_for_state(app._state),
                             lambda icon=None, item=None: tray_toggle_countdown(app)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda _: tray_mini_menu_label(app._is_mini),
                lambda icon=None, item=None: tray_toggle_mini(app),
            ),
            pystray.MenuItem("透明模式",
                             lambda icon=None, item=None: tray_toggle_transparent(app),
                             checked=lambda _: app._transparent_mode),
            pystray.MenuItem(
                "恢复默认大小",
                lambda icon=None, item=None: tray_reset_mini_size(app),
                enabled=lambda _: bool(app._is_mini),
            ),
            # 系统托盘无法上色，改为打开带真实色块的面板
            pystray.MenuItem(
                "字体颜色…",
                lambda icon=None, item=None: tray_show_mini_text_picker(app),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("开机自启",
                             lambda icon=None, item=None: tray_toggle_autostart(app),
                             checked=lambda _: app._autostart),
            pystray.MenuItem("主题", pystray.Menu(*theme_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", lambda icon=None, item=None: tray_quit(app)),
        )
        app.tray_icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
        app._status_menu_active = True
        threading.Thread(target=app.tray_icon.run, daemon=True).start()
    except Exception:
        logger.exception("托盘图标创建失败")
        app.tray_icon = None
        app._status_menu_active = False


def refresh_tray_menu(app):
    """同步动态菜单文案/勾选状态。

    Windows 上 pystray 会缓存原生菜单；callable 文案变更后必须调用 update_menu。
    macOS 菜单栏用 postcommand / 主动 _fill 刷新。
    """
    if platform.system() == "Darwin":
        try:
            from services.mac_menu import refresh_mac_menubar

            refresh_mac_menubar(app)
        except Exception:
            logger.debug("刷新 mac 菜单栏失败", exc_info=True)
        return

    icon = getattr(app, "tray_icon", None)
    if not icon:
        return
    try:
        # 重新赋值 menu 再 update，避免部分平台只刷新勾选不刷新文案
        menu = getattr(icon, "menu", None)
        if menu is not None:
            icon.menu = menu
        icon.update_menu()
    except Exception:
        logger.debug("刷新托盘菜单失败", exc_info=True)


def make_tray_theme_handler(app, theme_id):
    def _handler(icon=None, item=None):
        def _do():
            app._apply_theme(theme_id)
            refresh_tray_menu(app)

        app.master.after(0, _do)

    return _handler


def make_tray_theme_checked(app, theme_id):
    return lambda item=None: app._theme_id == theme_id


def tray_toggle_autostart(app, icon=None, item=None):
    def _do():
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
        refresh_tray_menu(app)

    app.master.after(0, _do)


def load_tray_icon(icon_path):
    from PIL import Image
    if os.path.exists(icon_path):
        return Image.open(icon_path)
    return create_fallback_icon()


def create_fallback_icon():
    from PIL import Image, ImageDraw
    size = 64
    accent = (56, 189, 248)  # #38BDF8
    face = (15, 20, 25)      # #0F1419
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse([4, 4, size - 4, size - 4], fill=accent)
    draw.ellipse([10, 10, size - 10, size - 10], fill=face)
    center = size // 2
    draw.line([(center, center), (center, 18)], fill=accent, width=3)
    draw.line([(center, center), (size - 18, center)], fill=accent, width=3)
    draw.ellipse([center - 3, center - 3, center + 3, center + 3], fill=accent)
    return image


def tray_show_window(app, icon=None, item=None):
    app.master.after(0, app._show_full_mode)


def tray_show_time_picker(app, icon=None, item=None):
    app.master.after(0, app._show_time_picker)


def tray_toggle_countdown(app, icon=None, item=None):
    def _do():
        app.toggle_countdown()
        # 状态变更后强制重建托盘原生菜单（Windows 缓存）
        refresh_tray_menu(app)

    app.master.after(0, _do)


def tray_toggle_mini(app, icon=None, item=None):
    app.master.after(0, app._toggle_mini_mode)


def tray_toggle_transparent(app, icon=None, item=None):
    def _do():
        app._toggle_transparent_mode()
        refresh_tray_menu(app)

    app.master.after(0, _do)


def tray_reset_mini_size(app, icon=None, item=None):
    def _do():
        from ui.mini_window import reset_mini_size

        if app._is_mini:
            reset_mini_size(app)
        refresh_tray_menu(app)

    app.master.after(0, _do)


def tray_show_mini_text_picker(app, icon=None, item=None):
    def _do():
        from ui.mini_text_picker import show_mini_text_picker

        show_mini_text_picker(app)

    app.master.after(0, _do)


def tray_quit(app, icon=None, item=None):
    app.master.after(0, app._quit_app)


def stop_tray(app):
    """退出时停止托盘图标。"""
    if app.tray_icon:
        try:
            app.tray_icon.stop()
        except Exception:
            logger.warning("停止托盘图标失败", exc_info=True)
