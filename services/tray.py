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
            pystray.MenuItem(
                "结束静音",
                lambda icon=None, item=None: tray_toggle_sound_mute(app),
                checked=lambda _: bool(getattr(app, "_sound_muted", False)),
            ),
            # 动态子菜单：每次 update_menu 重建历史/enabled
            pystray.MenuItem("结束音效", pystray.Menu(lambda: _iter_sound_menu_items(app))),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("开机自启",
                             lambda icon=None, item=None: tray_toggle_autostart(app),
                             checked=lambda _: app._autostart),
            pystray.MenuItem("主题", pystray.Menu(*theme_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "设置…",
                lambda icon=None, item=None: tray_show_settings(app),
            ),
            pystray.MenuItem(
                "检查更新…",
                lambda icon=None, item=None: tray_check_update(app),
            ),
            pystray.MenuItem(
                "启动时检查更新",
                lambda icon=None, item=None: tray_toggle_check_update_on_start(app),
                checked=lambda _: bool(getattr(app, "_check_update_on_start", True)),
            ),
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


def _iter_sound_menu_items(app):
    """结束音效子菜单项（generator）。每次 update_menu 重新生成历史列表。"""
    from services.sound import SOUND_ID_CUSTOM, SOUND_PRESETS, prune_sound_history

    for sid, name in SOUND_PRESETS:
        yield pystray.MenuItem(
            name,
            make_tray_sound_handler(app, sid),
            checked=make_tray_sound_checked(app, sid),
        )
    yield pystray.Menu.SEPARATOR
    yield pystray.MenuItem(
        "导入文件…",
        lambda icon=None, item=None: tray_pick_custom_sound(app),
    )

    history = prune_sound_history(getattr(app, "_sound_history", []))
    current_path = str(getattr(app, "_sound_path", "") or "")
    current_custom = getattr(app, "_sound_id", "") == SOUND_ID_CUSTOM
    if history:
        yield pystray.Menu.SEPARATOR
        for entry in history:
            path = entry.get("path") or ""
            label = entry.get("name") or os.path.basename(path) or "音效"
            if len(label) > 28:
                label = label[:25] + "…"
            yield pystray.MenuItem(
                label,
                make_tray_history_sound_handler(app, path),
                checked=make_tray_history_sound_checked(
                    app, path, current_custom, current_path
                ),
            )

    yield pystray.Menu.SEPARATOR
    # 播放中禁用试听，避免叠播；停止项仅播放中可点（update_menu 时求值）
    yield pystray.MenuItem(
        "试听",
        lambda icon=None, item=None: tray_preview_sound(app),
        enabled=lambda _: not _stop_preview_enabled(),
    )
    yield pystray.MenuItem(
        "停止试听",
        lambda icon=None, item=None: tray_stop_preview_sound(app),
        enabled=lambda _: _stop_preview_enabled(),
    )
    yield pystray.Menu.SEPARATOR
    yield pystray.MenuItem(
        "清空历史记录",
        lambda icon=None, item=None: tray_clear_sound_history(app),
    )
    yield pystray.MenuItem(
        "清理未使用音效…",
        lambda icon=None, item=None: tray_purge_orphan_sounds(app),
    )


def _stop_preview_enabled() -> bool:
    from services.sound import is_sound_playing

    return is_sound_playing()


def make_tray_sound_handler(app, sound_id):
    def _handler(icon=None, item=None):
        def _do():
            app._sound_id = sound_id
            app._save_config()
            refresh_tray_menu(app)

        app.master.after(0, _do)

    return _handler


def make_tray_sound_checked(app, sound_id):
    return lambda item=None: getattr(app, "_sound_id", "soft") == sound_id


def make_tray_history_sound_handler(app, path: str):
    def _handler(icon=None, item=None):
        def _do():
            from services.sound import SOUND_ID_CUSTOM, touch_sound_history

            if not path or not os.path.isfile(path):
                messagebox.showerror(
                    APP_NAME,
                    "该历史音效文件已不存在。",
                    parent=app.master,
                )
                app._sound_history = [
                    h
                    for h in getattr(app, "_sound_history", [])
                    if (h.get("path") if isinstance(h, dict) else h) != path
                ]
                app._save_config()
                refresh_tray_menu(app)
                return
            app._sound_id = SOUND_ID_CUSTOM
            app._sound_path = path
            app._sound_history = touch_sound_history(
                getattr(app, "_sound_history", []), path
            )
            app._save_config()
            refresh_tray_menu(app)

        app.master.after(0, _do)

    return _handler


def make_tray_history_sound_checked(app, path, current_custom, current_path):
    def _checked(item=None):
        if getattr(app, "_sound_id", "") != "custom":
            return False
        cur = str(getattr(app, "_sound_path", "") or "")
        try:
            return os.path.normcase(os.path.abspath(cur)) == os.path.normcase(
                os.path.abspath(path)
            )
        except OSError:
            return cur == path

    return _checked


def tray_toggle_sound_mute(app, icon=None, item=None):
    def _do():
        app._sound_muted = not bool(getattr(app, "_sound_muted", False))
        app._save_config()
        refresh_tray_menu(app)

    app.master.after(0, _do)


def tray_pick_custom_sound(app, icon=None, item=None):
    def _do():
        from tkinter import filedialog

        from services.sound import (
            AUDIO_FILETYPES,
            SOUND_ID_CUSTOM,
            import_custom_sound,
            is_audio_file,
            touch_sound_history,
        )

        path = filedialog.askopenfilename(
            parent=app.master,
            title="导入结束音效（将复制到本地库）",
            filetypes=AUDIO_FILETYPES,
        )
        if not path:
            return
        if not is_audio_file(path):
            messagebox.showerror(
                APP_NAME,
                "不支持的音频格式。\n请选择 wav / mp3 / aiff / m4a / ncm 等常见格式。",
                parent=app.master,
            )
            return
        result = import_custom_sound(path)
        if not result:
            messagebox.showerror(
                APP_NAME,
                "导入失败。\n请确认文件可读；若为 ncm 请确认可正常解密。",
                parent=app.master,
            )
            return
        stored, name = result
        app._sound_id = SOUND_ID_CUSTOM
        app._sound_path = stored
        app._sound_history = touch_sound_history(
            getattr(app, "_sound_history", []), stored, name
        )
        app._save_config()
        refresh_tray_menu(app)

    app.master.after(0, _do)


def tray_preview_sound(app, icon=None, item=None):
    """试听：必须在 pystray 回调内同步启动。

    pystray 会在菜单项回调返回后立刻 update_menu；若用 after(0) 推迟，
    菜单会按「未播放」把「停止试听」再次置灰，且听感上启动偏慢。
    """
    from services.sound import is_sound_playing, play_finish_sound_async, stop_playback

    # 已在播则先停再播，避免叠音；菜单 enabled 也会在 refresh 后禁用「试听」
    if is_sound_playing():
        stop_playback()

    # 试听忽略静音开关，便于确认所选音效
    play_finish_sound_async(
        app.master,
        muted=False,
        sound_id=str(getattr(app, "_sound_id", "soft") or "soft"),
        custom_path=str(getattr(app, "_sound_path", "") or ""),
    )
    # 同步刷新（与 pystray 线程一致）；pending 已置位 → 停止可点、试听禁用
    refresh_tray_menu(app)
    root = getattr(app, "master", None)
    if root is not None:
        try:
            root.after(400, lambda: refresh_tray_menu(app))
            # 播放结束后再刷，恢复「试听」可点
            root.after(1500, lambda: refresh_tray_menu(app))
        except Exception:
            pass


def tray_stop_preview_sound(app, icon=None, item=None):
    """停止试听：同步 stop，避免 after 推迟导致点了不停。"""
    from services.sound import stop_playback

    stop_playback()
    refresh_tray_menu(app)
    root = getattr(app, "master", None)
    if root is not None:
        try:
            # 与 sound 内延迟 rehalt 对齐，刷新菜单状态
            root.after(300, lambda: refresh_tray_menu(app))
        except Exception:
            pass


def tray_clear_sound_history(app, icon=None, item=None):
    """清空历史记录（保留当前 sound_path，不删磁盘文件）。"""

    def _do():
        app._sound_history = []
        app._save_config()
        refresh_tray_menu(app)

    app.master.after(0, _do)


def tray_purge_orphan_sounds(app, icon=None, item=None):
    """清理用户 sounds 库中未在历史且非当前路径的文件。"""

    def _do():
        from services.sound import purge_orphan_sounds, stop_playback

        ok = messagebox.askyesno(
            APP_NAME,
            "将删除本地音效库中未出现在历史列表、且不是当前所选的文件。\n"
            "历史记录本身不会被清空。\n\n确定清理？",
            parent=app.master,
        )
        if not ok:
            return
        stop_playback()
        n = purge_orphan_sounds(
            getattr(app, "_sound_history", []),
            str(getattr(app, "_sound_path", "") or ""),
        )
        messagebox.showinfo(
            APP_NAME,
            f"已清理 {n} 个未使用音效文件。" if n else "没有可清理的未使用音效。",
            parent=app.master,
        )
        refresh_tray_menu(app)

    app.master.after(0, _do)


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


def tray_show_settings(app, icon=None, item=None):
    """托盘打开设置中心（回主线程）。"""

    def _do():
        from ui.settings_window import show_settings

        show_settings(app)

    app.master.after(0, _do)


def tray_check_update(app, icon=None, item=None):
    from services.updater import tray_check_update as _check

    _check(app, icon, item)


def tray_toggle_check_update_on_start(app, icon=None, item=None):
    from services.updater import tray_toggle_check_update_on_start as _toggle

    _toggle(app, icon, item)


def load_tray_icon(icon_path):
    from PIL import Image
    if os.path.exists(icon_path):
        return Image.open(icon_path)
    return create_fallback_icon()


def create_fallback_icon():
    from PIL import Image, ImageDraw
    size = 64
    accent = (56, 189, 248)  # #38BDF8
    face = (15, 20, 25)  # #0F1419
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
