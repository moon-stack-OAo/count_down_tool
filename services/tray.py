# -*- coding: utf-8 -*-
"""系统托盘：菜单构建、图标线程、回调经 master.after 回主线程。"""

import logging
import os
import threading
from tkinter import messagebox

from autostart import is_autostart_enabled, set_autostart
from countdown_core import APP_NAME, button_text_for_state
from themes import list_themes

logger = logging.getLogger("count_down_tool")

try:
    import pystray

    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False
    pystray = None


def init_tray_icon(app, icon_path):
    """创建托盘图标并启动后台线程。失败时 app.tray_icon 置 None。"""
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
            pystray.MenuItem("显示主窗口", lambda icon=None, item=None: tray_show_window(app),
                             default=True),
            pystray.MenuItem("选择时间", lambda icon=None, item=None: tray_show_time_picker(app)),
            pystray.MenuItem(lambda _: button_text_for_state(app._state),
                             lambda icon=None, item=None: tray_toggle_countdown(app)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Mini 模式", lambda icon=None, item=None: tray_toggle_mini(app)),
            pystray.MenuItem("透明模式",
                             lambda icon=None, item=None: tray_toggle_transparent(app),
                             checked=lambda _: app._transparent_mode),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("开机自启",
                             lambda icon=None, item=None: tray_toggle_autostart(app),
                             checked=lambda _: app._autostart),
            pystray.MenuItem("主题", pystray.Menu(*theme_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", lambda icon=None, item=None: tray_quit(app)),
        )
        app.tray_icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
        threading.Thread(target=app.tray_icon.run, daemon=True).start()
    except Exception:
        logger.exception("托盘图标创建失败")
        app.tray_icon = None


def make_tray_theme_handler(app, theme_id):
    def _handler(icon=None, item=None):
        app.master.after(0, lambda: app._apply_theme(theme_id))

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
    app.master.after(0, app.toggle_countdown)


def tray_toggle_mini(app, icon=None, item=None):
    app.master.after(0, app._toggle_mini_mode)


def tray_toggle_transparent(app, icon=None, item=None):
    def _do():
        app._toggle_transparent_mode()

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
