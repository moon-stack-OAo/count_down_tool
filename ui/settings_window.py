# -*- coding: utf-8 -*-
"""设置中心：Toplevel 单例，分区管理外观 / 声音 / 系统 / 关于。"""

from __future__ import annotations

import logging
import os
import platform
import tkinter as tk
import webbrowser
from tkinter import filedialog

from core.countdown_core import APP_NAME, __version__
from core.themes import list_themes
from core.update import GITHUB_RELEASES_PAGE
from services.autostart import is_autostart_enabled, set_autostart
from ui.app_dialogs import ask_yes_no, show_error, show_info, temporary_withdraw
from ui.design.tokens import (
    SETTINGS_HEIGHT,
    SETTINGS_WIDTH,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
)
from ui.time_picker import _picker_parent
from ui.widgets import ThinScrollbar, make_pill
from ui.window_chrome_dialog import ensure_dialog_visible

logger = logging.getLogger("count_down_tool")


def close_settings(app) -> None:
    """关闭设置窗（主题切换前调用，避免颜色过期的悬浮窗）。"""
    win = getattr(app, "_settings_window", None)
    if win is None:
        return
    try:
        if win.winfo_exists():
            win.destroy()
    except tk.TclError:
        pass
    app._settings_window = None


def show_settings(app, initial_tab: str | None = None) -> None:
    """打开设置中心（单例：已存在则置前）。失败时向用户提示。

    initial_tab: 可选 Tab 键 appearance / sound / system / about；
    主题重建后重开时用于恢复原分区。
    """
    try:
        _show_settings_impl(app, initial_tab=initial_tab)
    except Exception as exc:
        # 设置窗边界：任意构建失败都需提示用户，保留宽捕获
        logger.exception("打开设置中心失败")
        app._settings_window = None
        try:
            show_error(
                app,
                "无法打开设置中心。\n\n"
                f"详情：{exc}\n\n"
                "建议：结束所有倒计时进程后重试；"
                "若 exe 从压缩包拖出，请右键「解除锁定」或重新完整解压后再运行。",
            )
        except (tk.TclError, AttributeError, RuntimeError):
            logger.debug("设置失败提示也失败", exc_info=True)


_SETTINGS_TAB_KEYS = frozenset({"appearance", "sound", "system", "about"})


def _normalize_settings_tab(tab: str | None) -> str:
    """非法或空 Tab 回退到外观。"""
    if tab and tab in _SETTINGS_TAB_KEYS:
        return tab
    return "appearance"


def get_settings_open_tab(app) -> str | None:
    """若设置窗打开则返回当前 Tab 键，否则 None。"""
    win = getattr(app, "_settings_window", None)
    if win is None:
        return None
    try:
        if not win.winfo_exists():
            return None
    except tk.TclError:
        return None
    tab = getattr(win, "_settings_tab", None)
    return _normalize_settings_tab(tab) if tab else "appearance"


def _show_settings_impl(app, initial_tab: str | None = None) -> None:
    """打开设置中心（单例：已存在则强制可见）。"""
    start_tab = _normalize_settings_tab(initial_tab)
    existing = getattr(app, "_settings_window", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                show_tab = getattr(existing, "_settings_show_tab", None)
                if initial_tab is not None and callable(show_tab):
                    try:
                        show_tab(start_tab)
                    except (tk.TclError, TypeError, ValueError):
                        pass
                ensure_dialog_visible(
                    existing, SETTINGS_WIDTH, SETTINGS_HEIGHT
                )
                return
        except tk.TclError:
            pass
        app._settings_window = None

    parent = _picker_parent(app)
    c = app.COLORS
    win = tk.Toplevel(parent)
    app._settings_window = win
    win.title(f"{APP_NAME} · 设置")
    win.configure(bg=c["bg"])
    win.geometry(f"{SETTINGS_WIDTH}x{SETTINGS_HEIGHT}")
    win.resizable(False, False)
    try:
        if parent is not app.master or parent.winfo_viewable():
            win.transient(parent)
    except tk.TclError:
        pass

    # 关闭时清单例并停试听
    def _on_close():
        try:
            from services.sound import stop_playback

            stop_playback()
        except (ImportError, OSError, AttributeError, RuntimeError):
            pass
        try:
            win.destroy()
        except tk.TclError:
            pass
        if getattr(app, "_settings_window", None) is win:
            app._settings_window = None

    win.protocol("WM_DELETE_WINDOW", _on_close)
    # 使用系统原生边框/标题栏（避免无边框窗在部分机器上不可见或难置前）
    try:
        win.bind("<Escape>", lambda e: (_on_close(), "break")[1])
    except tk.TclError:
        pass

    # ===== 顶栏 Tab + 单页可滚动内容 =====
    shell = tk.Frame(win, bg=c["bg"])
    shell.pack(fill=tk.BOTH, expand=True)

    tab_bar = tk.Frame(shell, bg=c.get("title_bar", c["bg"]))
    tab_bar.pack(fill=tk.X, side=tk.TOP)
    tk.Frame(shell, bg=c["accent"], height=2).pack(fill=tk.X, side=tk.TOP)

    page_host = tk.Frame(shell, bg=c["bg"])
    page_host.pack(fill=tk.BOTH, expand=True)

    tabs_spec = (
        ("appearance", "外观"),
        ("sound", "声音"),
        ("system", "系统"),
        ("about", "关于"),
    )
    pages: dict = {}
    tab_btns: dict = {}
    state = {"tab": start_tab}
    win._settings_tab = start_tab  # type: ignore[attr-defined]

    def _style_tab(key: str, active: bool):
        btn = tab_btns.get(key)
        if btn is None:
            return
        try:
            if active:
                btn.config(
                    bg=c["bg"],
                    fg=c.get("accent_glow", c["accent"]),
                    font=app._font("label", 10, bold=True),
                )
            else:
                btn.config(
                    bg=c.get("title_bar", c["bg"]),
                    fg=c["text_dim"],
                    font=app._font("label", 10),
                )
        except tk.TclError:
            pass

    def _show_tab(key: str):
        if key not in pages:
            return
        state["tab"] = key
        win._settings_tab = key  # type: ignore[attr-defined]
        for k, frame in pages.items():
            try:
                if k == key:
                    frame.pack(fill=tk.BOTH, expand=True)
                else:
                    frame.pack_forget()
            except tk.TclError:
                pass
            _style_tab(k, k == key)
        # 切页后滚回顶部，并按当前内容高度同步是否可滚
        try:
            pages[key]._settings_canvas.yview_moveto(0)  # type: ignore[attr-defined]
        except (tk.TclError, AttributeError):
            pass
        try:
            sync = getattr(pages[key], "_settings_sync_scroll", None)
            if sync:
                pages[key].after_idle(sync)
        except (tk.TclError, AttributeError, TypeError):
            pass

    win._settings_show_tab = _show_tab  # type: ignore[attr-defined]

    for key, label in tabs_spec:
        btn = tk.Label(
            tab_bar,
            text=label,
            font=app._font("label", 10),
            bg=c.get("title_bar", c["bg"]),
            fg=c["text_dim"],
            padx=16,
            pady=10,
            cursor="hand2",
        )
        btn.pack(side=tk.LEFT)
        btn.bind("<Button-1>", lambda e, k=key: _show_tab(k))
        tab_btns[key] = btn

        page = _make_scroll_page(page_host, app, c)
        pages[key] = page

    # 状态刷新回调集合（主题/音效切换后局部更新勾选）
    refreshers = []

    def _refresh_all():
        for fn in list(refreshers):
            try:
                fn()
            except (tk.TclError, AttributeError, TypeError, ValueError, RuntimeError):
                logger.debug("设置窗刷新失败", exc_info=True)

    _build_appearance_section(app, pages["appearance"]._settings_content, c, refreshers)
    _build_sound_section(app, pages["sound"]._settings_content, c, refreshers, win)
    _build_system_section(app, pages["system"]._settings_content, c, refreshers)
    _build_about_section(app, pages["about"]._settings_content, c)

    _show_tab(start_tab)
    win.update_idletasks()
    for page in pages.values():
        _bind_wheel_tree(page, page._settings_canvas)
        sync = getattr(page, "_settings_sync_scroll", None)
        if sync:
            try:
                page.after_idle(sync)
            except tk.TclError:
                pass
    # 强制可见：多次居中 + 短暂 topmost，避免「点了没反应」
    ensure_dialog_visible(win, SETTINGS_WIDTH, SETTINGS_HEIGHT)
    # 暴露刷新，供内部局部更新勾选
    win._settings_refresh = _refresh_all  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 分区构建
# ---------------------------------------------------------------------------


def _make_scroll_page(host: tk.Frame, app, c) -> tk.Frame:
    """单 Tab 页：Canvas + 细滚动条 + content 内边距。

    内容未超出视口时：scrollregion 锁在可视高度，禁止空滚；滚动条由 ThinScrollbar 自动收起。
    """
    page = tk.Frame(host, bg=c["bg"])
    canvas = tk.Canvas(page, bg=c["bg"], highlightthickness=0, bd=0)
    scrollbar = ThinScrollbar(
        page,
        command=canvas.yview,
        bg=c["bg"],
        trough=c.get("input_bg", c["card"]),
        thumb=c.get("border", c["text_muted"]),
        thumb_hover=c.get("text_muted", c["text_dim"]),
        width=6,
        pad=3,
    )
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    body = tk.Frame(canvas, bg=c["bg"])
    body_id = canvas.create_window((0, 0), window=body, anchor="nw")
    scroll_state = {"needed": False}

    def _content_height() -> int:
        try:
            body.update_idletasks()
            return max(int(body.winfo_reqheight()), 1)
        except tk.TclError:
            return 1

    def _sync_scroll(_e=None):
        """按内容与视口高度更新 scrollregion；不足一屏时不可滚。"""
        try:
            ch = max(int(canvas.winfo_height()), 1)
            bh = _content_height()
            needed = bh > ch + 1
            scroll_state["needed"] = needed
            if needed:
                canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), bh))
            else:
                # 锁在视口高度，yview 无法再偏移
                canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), ch))
                canvas.yview_moveto(0)
            # 触发滚动条 set，收起/展开宽度
            try:
                first, last = canvas.yview()
                scrollbar.set(first, last)
            except tk.TclError:
                pass
        except tk.TclError:
            pass

    def _on_canvas_configure(e):
        try:
            canvas.itemconfigure(body_id, width=e.width)
        except tk.TclError:
            pass
        _sync_scroll()

    body.bind("<Configure>", _sync_scroll)
    canvas.bind("<Configure>", _on_canvas_configure)

    def _wheel(e):
        if not scroll_state["needed"]:
            return
        try:
            if platform.system() == "Darwin":
                canvas.yview_scroll(int(-1 * e.delta), "units")
            else:
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        except tk.TclError:
            pass

    def _wheel_up(_e=None):
        if scroll_state["needed"]:
            try:
                canvas.yview_scroll(-1, "units")
            except tk.TclError:
                pass

    def _wheel_down(_e=None):
        if scroll_state["needed"]:
            try:
                canvas.yview_scroll(1, "units")
            except tk.TclError:
                pass

    canvas.bind("<MouseWheel>", _wheel)
    canvas.bind("<Button-4>", _wheel_up)
    canvas.bind("<Button-5>", _wheel_down)

    content = tk.Frame(body, bg=c["bg"])
    content.pack(fill=tk.BOTH, expand=True, padx=SPACE_MD, pady=(SPACE_MD, SPACE_SM))

    page._settings_canvas = canvas  # type: ignore[attr-defined]
    page._settings_content = content  # type: ignore[attr-defined]
    page._settings_wheel = _wheel  # type: ignore[attr-defined]
    page._settings_scroll_state = scroll_state  # type: ignore[attr-defined]
    page._settings_sync_scroll = _sync_scroll  # type: ignore[attr-defined]
    page._settings_wheel_up = _wheel_up  # type: ignore[attr-defined]
    page._settings_wheel_down = _wheel_down  # type: ignore[attr-defined]
    return page


def _bind_wheel_tree(root: tk.Misc, canvas: tk.Canvas) -> None:
    """把滚轮事件绑到子树；仅内容溢出时滚动。"""
    page = None
    try:
        # canvas 的 master 即 page
        page = canvas.master
    except AttributeError:
        page = None
    scroll_state = getattr(page, "_settings_scroll_state", None) if page else None
    wheel = getattr(page, "_settings_wheel", None) if page else None
    wheel_up = getattr(page, "_settings_wheel_up", None) if page else None
    wheel_down = getattr(page, "_settings_wheel_down", None) if page else None

    def _wheel(e):
        if scroll_state is not None and not scroll_state.get("needed"):
            return
        if wheel:
            wheel(e)
            return
        try:
            if platform.system() == "Darwin":
                canvas.yview_scroll(int(-1 * e.delta), "units")
            else:
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        except tk.TclError:
            pass

    def _up(e):
        if scroll_state is not None and not scroll_state.get("needed"):
            return
        if wheel_up:
            wheel_up(e)
        else:
            try:
                canvas.yview_scroll(-1, "units")
            except tk.TclError:
                pass

    def _down(e):
        if scroll_state is not None and not scroll_state.get("needed"):
            return
        if wheel_down:
            wheel_down(e)
        else:
            try:
                canvas.yview_scroll(1, "units")
            except tk.TclError:
                pass

    def _bind(w):
        w.bind("<MouseWheel>", _wheel)
        w.bind("<Button-4>", _up)
        w.bind("<Button-5>", _down)
        for child in w.winfo_children():
            _bind(child)

    try:
        _bind(root)
    except tk.TclError:
        pass


def _card(parent, c) -> tk.Frame:
    card = tk.Frame(
        parent,
        bg=c["card"],
        highlightbackground=c["border"],
        highlightthickness=1,
        padx=SPACE_MD,
        pady=SPACE_SM,
    )
    card.pack(fill=tk.X, pady=(0, SPACE_MD))
    return card


def _build_appearance_section(app, parent, c, refreshers) -> None:
    from core.countdown_core import (
        STARTUP_MODE_FULL,
        STARTUP_MODE_MINI,
        STARTUP_MODE_REMEMBER,
        normalize_startup_mode,
    )

    # —— 主题 ——
    card = _card(parent, c)
    tk.Label(
        card,
        text="主题",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))

    rows = {}

    def _apply(tid: str):
        app._apply_theme(tid)
        # apply_theme 会关窗并以新主题重开；若窗仍在则刷新勾选
        for fn in refreshers:
            try:
                fn()
            except (tk.TclError, AttributeError, TypeError, ValueError, RuntimeError):
                pass

    def _refresh_theme():
        cur = getattr(app, "_theme_id", "")
        for tid, lbl in rows.items():
            try:
                mark = "✓  " if tid == cur else "    "
                name = lbl._theme_name  # type: ignore[attr-defined]
                lbl.config(text=f"{mark}{name}")
            except tk.TclError:
                pass

    for tid, name in list_themes():
        row = tk.Label(
            card,
            text="",
            font=app._font("label", 10),
            bg=c["card"],
            fg=c["text"],
            anchor="w",
            cursor="hand2",
            padx=SPACE_SM,
            pady=6,
        )
        row._theme_name = name  # type: ignore[attr-defined]
        row.pack(fill=tk.X)
        row.bind("<Button-1>", lambda e, t=tid: _apply(t))
        row.bind(
            "<Enter>",
            lambda e, w=row: w.config(bg=c.get("chip_hover", c["border"])),
        )
        row.bind("<Leave>", lambda e, w=row: w.config(bg=c["card"]))
        rows[tid] = row

    refreshers.append(_refresh_theme)
    _refresh_theme()

    # —— 默认启动模式 ——
    start_card = _card(parent, c)
    tk.Label(
        start_card,
        text="默认启动模式",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))

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
                mark = "✓  " if mid == cur else "    "
                name = lbl._startup_name  # type: ignore[attr-defined]
                lbl.config(text=f"{mark}{name}")
            except tk.TclError:
                pass

    for mid, name in startup_opts:
        row = tk.Label(
            start_card,
            text="",
            font=app._font("label", 10),
            bg=c["card"],
            fg=c["text"],
            anchor="w",
            cursor="hand2",
            padx=SPACE_SM,
            pady=6,
        )
        row._startup_name = name  # type: ignore[attr-defined]
        row.pack(fill=tk.X)
        row.bind("<Button-1>", lambda e, m=mid: _set_startup(m))
        row.bind(
            "<Enter>",
            lambda e, w=row: w.config(bg=c.get("chip_hover", c["border"])),
        )
        row.bind("<Leave>", lambda e, w=row: w.config(bg=c["card"]))
        startup_rows[mid] = row

    refreshers.append(_refresh_startup)
    _refresh_startup()

    # —— Mini 字色 ——
    mini_card = _card(parent, c)
    tk.Label(
        mini_card,
        text="Mini 外观",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))

    def _open_mini_text():
        from ui.mini_text_picker import show_mini_text_picker

        show_mini_text_picker(app)

    text_row = tk.Label(
        mini_card,
        text="Mini 字体颜色…",
        font=app._font("label", 10),
        bg=c["card"],
        fg=c["text"],
        anchor="w",
        cursor="hand2",
        padx=SPACE_SM,
        pady=SPACE_SM,
    )
    text_row.pack(fill=tk.X)
    text_row.bind("<Button-1>", lambda e: _open_mini_text())
    text_row.bind(
        "<Enter>",
        lambda e, w=text_row: w.config(bg=c.get("chip_hover", c["border"])),
    )
    text_row.bind("<Leave>", lambda e, w=text_row: w.config(bg=c["card"]))


def _build_sound_section(app, parent, c, refreshers, win) -> None:
    from services.sound import (
        AUDIO_FILETYPES,
        SOUND_ID_CUSTOM,
        SOUND_PRESETS,
        import_custom_sound,
        is_audio_file,
        is_sound_playing,
        normalize_sound_history,
        path_is_file_quick,
        play_finish_sound_async,
        prune_sound_history,
        purge_orphan_sounds,
        stop_playback,
        touch_sound_history,
    )

    card = _card(parent, c)

    sound_rows = {}
    history_frame = tk.Frame(card, bg=c["card"])

    def _tray_refresh():
        try:
            from services.tray import refresh_tray_menu

            refresh_tray_menu(app)
        except (ImportError, AttributeError, RuntimeError, tk.TclError):
            pass

    def _toggle_mute():
        app._sound_muted = not bool(getattr(app, "_sound_muted", False))
        app._save_config()
        _refresh()
        _tray_refresh()

    def _set_sound(sid: str):
        app._sound_id = sid
        app._save_config()
        _refresh()
        _tray_refresh()

    def _select_history(path: str):
        if not path or not path_is_file_quick(path):
            show_error(app, "该历史音效文件已不存在。", parent=win)
            app._sound_history = [
                h
                for h in getattr(app, "_sound_history", [])
                if (h.get("path") if isinstance(h, dict) else h) != path
            ]
            app._save_config()
            _refresh()
            return
        app._sound_id = SOUND_ID_CUSTOM
        app._sound_path = path
        app._sound_history = touch_sound_history(
            getattr(app, "_sound_history", []), path
        )
        app._save_config()
        _refresh()
        _tray_refresh()

    def _import_sound():
        # 选择文件期间先隐藏设置窗，避免挡住系统对话框；
        # parent 用 None，避免系统对话框挂在被隐藏的 Toplevel 上
        with temporary_withdraw(win):
            path = filedialog.askopenfilename(
                parent=None,
                title="导入结束音效（将复制到本地库）",
                filetypes=AUDIO_FILETYPES,
            )
        if not path:
            return
        if not is_audio_file(path):
            show_error(
                app,
                "不支持的音频格式。\n请选择 wav / mp3 / aiff / m4a / ncm 等常见格式。",
                parent=win,
            )
            return
        result = import_custom_sound(path)
        if not result:
            show_error(
                app,
                "导入失败。\n请确认文件可读；若为 ncm 请确认可正常解密。",
                parent=win,
            )
            return
        stored, name = result
        app._sound_id = SOUND_ID_CUSTOM
        app._sound_path = stored
        app._sound_history = touch_sound_history(
            getattr(app, "_sound_history", []), stored, name
        )
        app._save_config()
        _refresh()
        _tray_refresh()
        show_info(
            app,
            f"已导入并设为结束音效：\n{name}",
            title="导入成功",
            parent=win,
        )

    def _preview_root():
        # 系统铃依赖 root.bell/after；主窗 Mini withdraw 时可能无声，优先设置窗
        try:
            if win.winfo_exists():
                return win
        except tk.TclError:
            pass
        return app.master

    def _preview():
        # 勿先 stop 再 async：交给 async 内部 halt，避免 gen/竞态掐断刚起的播放
        play_finish_sound_async(
            _preview_root(),
            muted=False,
            sound_id=str(getattr(app, "_sound_id", "soft") or "soft"),
            custom_path=str(getattr(app, "_sound_path", "") or ""),
        )
        _schedule_preview_refresh()

    def _stop_preview():
        stop_playback()
        _schedule_preview_refresh()

    def _clear_history_and_orphans():
        """清空历史列表，并删除库中未引用文件（保留当前结束音效）。"""
        ok = ask_yes_no(
            app,
            "将清空历史记录，并删除本地音效库中未使用的文件。\n"
            "当前正在使用的结束音效会保留。\n\n确定？",
            title="清空历史与未使用",
            yes_text="清空",
            no_text="取消",
            danger=True,
            parent=win,
        )
        if not ok:
            return
        stop_playback()
        app._sound_history = []
        n = purge_orphan_sounds(
            [],
            str(getattr(app, "_sound_path", "") or ""),
        )
        app._save_config()
        _refresh()
        _tray_refresh()
        if n:
            msg = f"历史已清空，并删除了 {n} 个未使用音效文件。\n当前结束音效保持不变。"
        else:
            msg = "历史已清空。\n当前结束音效保持不变。"
        show_info(app, msg, title="已清空", parent=win)

    def _schedule_preview_refresh():
        _refresh()
        try:
            win.after(400, _refresh)
            win.after(1500, _refresh)
            win.after(3500, _refresh)
        except tk.TclError:
            pass

    # 静音开关
    mute_lbl = tk.Label(
        card,
        text="",
        font=app._font("label", 10),
        bg=c["card"],
        fg=c["text"],
        anchor="w",
        cursor="hand2",
        padx=SPACE_SM,
        pady=SPACE_SM,
    )
    mute_lbl.pack(fill=tk.X)
    mute_lbl.bind("<Button-1>", lambda e: _toggle_mute())

    tk.Frame(card, bg=c["border"], height=1).pack(fill=tk.X, pady=SPACE_SM)

    tk.Label(
        card,
        text="结束音效",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))

    for sid, name in SOUND_PRESETS:
        row = tk.Label(
            card,
            text="",
            font=app._font("label", 10),
            bg=c["card"],
            fg=c["text"],
            anchor="w",
            cursor="hand2",
            padx=SPACE_SM,
            pady=6,
        )
        row._sound_name = name  # type: ignore[attr-defined]
        row.pack(fill=tk.X)
        row.bind("<Button-1>", lambda e, s=sid: _set_sound(s))
        row.bind(
            "<Enter>",
            lambda e, w=row: w.config(bg=c.get("chip_hover", c["border"])),
        )
        row.bind("<Leave>", lambda e, w=row: w.config(bg=c["card"]))
        sound_rows[sid] = row

    # 自定义当前项提示
    custom_lbl = tk.Label(
        card,
        text="",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_dim"],
        anchor="w",
        padx=SPACE_SM,
        pady=4,
        wraplength=SETTINGS_WIDTH - 96,
        justify=tk.LEFT,
    )
    custom_lbl.pack(fill=tk.X)

    history_frame.pack(fill=tk.X, pady=(SPACE_XS, 0))

    btn_row = tk.Frame(card, bg=c["card"])
    btn_row.pack(fill=tk.X, pady=(SPACE_SM, 0))

    _pill(btn_row, "导入文件…", app=app, c=c, primary=False, command=_import_sound).pack(
        side=tk.LEFT, padx=(0, SPACE_SM)
    )
    preview_btn = _pill(btn_row, "试听", app=app, c=c, primary=True, command=_preview)
    preview_btn.pack(side=tk.LEFT, padx=(0, SPACE_SM))
    stop_btn = _pill(btn_row, "停止试听", app=app, c=c, primary=False, command=_stop_preview)
    stop_btn.pack(side=tk.LEFT)

    util_row = tk.Frame(card, bg=c["card"])
    util_row.pack(fill=tk.X, pady=(SPACE_SM, 0))
    _pill(
        util_row,
        "清空历史与未使用…",
        app=app,
        c=c,
        primary=False,
        command=_clear_history_and_orphans,
    ).pack(side=tk.LEFT)

    def _rebuild_history():
        for child in list(history_frame.winfo_children()):
            try:
                child.destroy()
            except tk.TclError:
                pass
        prev = normalize_sound_history(getattr(app, "_sound_history", []))
        history = prune_sound_history(prev)
        # 展示清理与配置同步：失效路径从内存与 config 去掉
        if history != prev:
            app._sound_history = history
            try:
                app._save_config()
            except (OSError, TypeError, ValueError, AttributeError):
                pass
        if not history:
            return
        tk.Label(
            history_frame,
            text="最近导入",
            font=app._font("label", 9),
            bg=c["card"],
            fg=c["text_muted"],
            anchor="w",
        ).pack(fill=tk.X, padx=SPACE_SM, pady=(SPACE_SM, SPACE_XS))
        cur = str(getattr(app, "_sound_id", "soft") or "soft")
        cur_path = str(getattr(app, "_sound_path", "") or "")
        for entry in history[:8]:
            path = entry.get("path") or ""
            label = entry.get("name") or os.path.basename(path) or "音效"
            if len(label) > 32:
                label = label[:29] + "…"
            mark = ""
            if cur == SOUND_ID_CUSTOM and path:
                try:
                    if os.path.normcase(os.path.abspath(cur_path)) == os.path.normcase(
                            os.path.abspath(path)
                    ):
                        mark = "✓  "
                    else:
                        mark = "    "
                except OSError:
                    mark = "✓  " if cur_path == path else "    "
            else:
                mark = "    "
            row = tk.Label(
                history_frame,
                text=f"{mark}{label}",
                font=app._font("label", 9),
                bg=c["card"],
                fg=c["text"],
                anchor="w",
                cursor="hand2",
                padx=SPACE_SM,
                pady=4,
            )
            row.pack(fill=tk.X)
            row.bind("<Button-1>", lambda e, p=path: _select_history(p))
            row.bind(
                "<Enter>",
                lambda e, w=row: w.config(bg=c.get("chip_hover", c["border"])),
            )
            row.bind("<Leave>", lambda e, w=row: w.config(bg=c["card"]))
        # 历史行是新建控件，须重绑滚轮才能在列表上滚动
        page = getattr(history_frame, "master", None)
        canvas = None
        try:
            # card → content → body → page；向上找带 _settings_canvas 的祖先
            w = history_frame
            for _ in range(8):
                if w is None:
                    break
                canvas = getattr(w, "_settings_canvas", None)
                if canvas is not None:
                    page = w
                    break
                w = getattr(w, "master", None)
        except AttributeError:
            canvas = None
        if page is not None and canvas is not None:
            _bind_wheel_tree(history_frame, canvas)

    def _refresh():
        muted = bool(getattr(app, "_sound_muted", False))
        try:
            mute_lbl.config(text=("✓  结束静音" if muted else "    结束静音"))
        except tk.TclError:
            pass
        cur = str(getattr(app, "_sound_id", "soft") or "soft")
        for sid, lbl in sound_rows.items():
            try:
                mark = "✓  " if sid == cur else "    "
                lbl.config(text=f"{mark}{lbl._sound_name}")  # type: ignore[attr-defined]
            except tk.TclError:
                pass
        path = str(getattr(app, "_sound_path", "") or "")
        if cur == SOUND_ID_CUSTOM and path:
            base = os.path.basename(path) or path
            if len(base) > 36:
                base = base[:33] + "…"
            tip = f"当前自定义：{base}"
        else:
            tip = "可导入本地音频作为结束提示音"
        try:
            custom_lbl.config(text=tip)
        except tk.TclError:
            pass
        _rebuild_history()
        playing = is_sound_playing()
        try:
            preview_btn.config(fg=c["text_muted"] if playing else c["bg"])
            stop_btn.config(fg=c["text"] if playing else c["text_muted"])
        except tk.TclError:
            pass

    refreshers.append(_refresh)
    _refresh()


def _open_path_in_file_manager(path: str) -> None:
    """用系统文件管理器打开目录或选中文件。"""
    import subprocess

    target = os.path.abspath(path)
    system = platform.system()
    if system == "Windows":
        if os.path.isfile(target):
            subprocess.run(
                ["explorer", "/select,", target],
                check=False,
            )
        else:
            os.startfile(target)  # type: ignore[attr-defined]
    elif system == "Darwin":
        if os.path.isfile(target):
            subprocess.run(["open", "-R", target], check=False)
        else:
            subprocess.run(["open", target], check=False)
    else:
        folder = target if os.path.isdir(target) else os.path.dirname(target)
        subprocess.run(["xdg-open", folder or target], check=False)


def _build_system_section(app, parent, c, refreshers) -> None:
    card = _card(parent, c)
    win = getattr(app, "_settings_window", None)

    is_win = platform.system() == "Windows"

    auto_lbl = None
    if is_win:
        auto_lbl = tk.Label(
            card,
            text="",
            font=app._font("label", 10),
            bg=c["card"],
            fg=c["text"],
            anchor="w",
            cursor="hand2",
            padx=SPACE_SM,
            pady=SPACE_SM,
        )
        auto_lbl.pack(fill=tk.X)

    upd_lbl = tk.Label(
        card,
        text="",
        font=app._font("label", 10),
        bg=c["card"],
        fg=c["text"],
        anchor="w",
        cursor="hand2",
        padx=SPACE_SM,
        pady=SPACE_SM,
    )
    upd_lbl.pack(fill=tk.X)

    tk.Label(
        card,
        text="手动检查请到「关于」页",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
        padx=SPACE_SM,
    ).pack(fill=tk.X, pady=(0, SPACE_XS))

    def _toggle_autostart():
        target = not is_autostart_enabled()
        ok = set_autostart(target)
        if not ok:
            show_error(
                app,
                "设置开机自启失败。\n请检查是否有权限写入启动文件夹。",
                parent=getattr(app, "_settings_window", None) or app.master,
            )
            app._autostart = is_autostart_enabled()
            _refresh()
            return
        app._autostart = target
        app._save_config()
        _refresh()
        try:
            from services.tray import refresh_tray_menu

            refresh_tray_menu(app)
        except (ImportError, AttributeError, RuntimeError, tk.TclError):
            pass

    def _toggle_check_update():
        app._check_update_on_start = not bool(
            getattr(app, "_check_update_on_start", True)
        )
        app._save_config()
        _refresh()
        try:
            from services.tray import refresh_tray_menu

            refresh_tray_menu(app)
        except (ImportError, AttributeError, RuntimeError, tk.TclError):
            pass

    if auto_lbl is not None:
        auto_lbl.bind("<Button-1>", lambda e: _toggle_autostart())
    upd_lbl.bind("<Button-1>", lambda e: _toggle_check_update())
    hover_widgets = [upd_lbl] + ([auto_lbl] if auto_lbl is not None else [])
    for w in hover_widgets:
        w.bind(
            "<Enter>",
            lambda e, x=w: x.config(bg=c.get("chip_hover", c["border"])),
        )
        w.bind("<Leave>", lambda e, x=w: x.config(bg=c["card"]))

    # —— 配置目录 / Mini 重置 ——
    tk.Frame(card, bg=c["border"], height=1).pack(fill=tk.X, pady=SPACE_SM)

    util_row = tk.Frame(card, bg=c["card"])
    util_row.pack(fill=tk.X, pady=(SPACE_XS, 0))

    def _open_config_dir():
        from core.countdown_core import user_config_dir

        try:
            path = user_config_dir(create=True)
            _open_path_in_file_manager(path)
        except (OSError, AttributeError, TypeError, ValueError, RuntimeError) as exc:
            logger.debug("打开配置目录失败", exc_info=True)
            show_error(
                app,
                f"无法打开配置目录。\n\n详情：{exc}",
                parent=win or app.master,
            )

    def _reset_mini_layout():
        from ui.mini_window import reset_mini_layout

        try:
            reset_mini_layout(app)
            show_info(
                app,
                "已恢复 Mini 默认位置与大小。",
                title="已重置",
                parent=win or app.master,
            )
        except (tk.TclError, AttributeError, OSError, RuntimeError) as exc:
            logger.debug("重置 Mini 布局失败", exc_info=True)
            show_error(
                app,
                f"重置失败。\n\n详情：{exc}",
                parent=win or app.master,
            )

    _pill(
        util_row,
        "打开配置目录",
        app=app,
        c=c,
        primary=False,
        command=_open_config_dir,
    ).pack(side=tk.LEFT, padx=(0, SPACE_SM))
    _pill(
        util_row,
        "重置 Mini 位置/大小",
        app=app,
        c=c,
        primary=False,
        command=_reset_mini_layout,
    ).pack(side=tk.LEFT)

    # —— 忽略的更新版本 ——
    tk.Frame(card, bg=c["border"], height=1).pack(fill=tk.X, pady=SPACE_SM)

    ign_lbl = tk.Label(
        card,
        text="",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
        padx=SPACE_SM,
    )
    ign_lbl.pack(fill=tk.X, pady=(0, SPACE_XS))

    ign_btn_row = tk.Frame(card, bg=c["card"])
    ign_btn_row.pack(fill=tk.X)

    def _clear_ignored():
        app._ignored_update_version = ""
        app._save_config()
        try:
            from services.updater import set_pending_update

            # 清除忽略后角标仍依赖下次检查；仅清 pending 无效缓存
            pending = getattr(app, "_pending_update_result", None)
            if pending is not None:
                set_pending_update(app, pending)
            else:
                set_pending_update(app, None)
        except (ImportError, AttributeError, RuntimeError, TypeError):
            pass
        _refresh()
        show_info(
            app,
            "已清除忽略的更新版本。\n下次检查更新时将重新提示。",
            title="已清除",
            parent=win or app.master,
        )

    clear_ign_btn = _pill(
        ign_btn_row,
        "清除忽略版本",
        app=app,
        c=c,
        primary=False,
        command=_clear_ignored,
    )
    clear_ign_btn.pack(side=tk.LEFT)

    def _refresh():
        auto = bool(getattr(app, "_autostart", False))
        check = bool(getattr(app, "_check_update_on_start", True))
        try:
            if auto_lbl is not None:
                auto_lbl.config(text=("✓  开机自启" if auto else "    开机自启"))
            upd_lbl.config(
                text=("✓  启动时检查更新" if check else "    启动时检查更新")
            )
        except tk.TclError:
            pass
        ign = str(getattr(app, "_ignored_update_version", "") or "").strip()
        try:
            if ign:
                ign_lbl.config(text=f"已忽略更新版本：v{ign}")
                if not clear_ign_btn.winfo_ismapped():
                    clear_ign_btn.pack(side=tk.LEFT)
            else:
                ign_lbl.config(text="未忽略任何版本")
                if clear_ign_btn.winfo_ismapped():
                    clear_ign_btn.pack_forget()
        except tk.TclError:
            pass

    refreshers.append(_refresh)
    _refresh()


def _build_about_section(app, parent, c) -> None:
    card = _card(parent, c)

    tk.Label(
        card,
        text=APP_NAME,
        font=app._font("label", 11, bold=True),
        bg=c["card"],
        fg=c["text"],
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM)
    tk.Label(
        card,
        text=f"版本 {__version__}",
        font=app._font("label", 10),
        bg=c["card"],
        fg=c["text_dim"],
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(SPACE_XS, SPACE_XS))

    last_check_lbl = tk.Label(
        card,
        text="",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
    )
    last_check_lbl.pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_MD))

    def _refresh_last_check() -> None:
        raw = str(getattr(app, "_last_update_check", "") or "").strip()
        if raw:
            # 配置存 ISO 日期；只展示日期部分
            day = raw[:10] if len(raw) >= 10 else raw
            text = f"上次检查：{day}"
        else:
            text = "尚未检查"
        try:
            last_check_lbl.config(text=text)
        except tk.TclError:
            pass

    _refresh_last_check()

    btn_row = tk.Frame(card, bg=c["card"])
    btn_row.pack(fill=tk.X)

    status_lbl = tk.Label(
        card,
        text="",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
        justify=tk.LEFT,
        wraplength=SETTINGS_WIDTH - 96,
    )
    status_lbl.pack(fill=tk.X, padx=SPACE_SM, pady=(SPACE_MD, 0))

    action_row = tk.Frame(card, bg=c["card"])

    # 发现更新时再 pack

    def _set_status(message: str, kind: str = "info") -> None:
        colors = {
            "busy": c.get("text_muted", c["text_dim"]),
            "ok": c.get("success", c["text"]),
            "error": c.get("error", c["text"]),
            "update": c.get("accent_glow", c.get("accent", c["text"])),
            "info": c.get("text_dim", c["text"]),
        }
        try:
            status_lbl.configure(
                text=message or "",
                fg=colors.get(kind, c.get("text_dim", c["text"])),
            )
        except tk.TclError:
            return
        # 检查结束后刷新「上次检查」（busy 阶段尚未写入）
        if kind != "busy":
            _refresh_last_check()
        # 有更新时露出「查看更新」
        try:
            if kind == "update":
                if not action_row.winfo_ismapped():
                    action_row.pack(fill=tk.X, padx=SPACE_SM, pady=(SPACE_SM, 0))
            else:
                if action_row.winfo_ismapped():
                    action_row.pack_forget()
        except tk.TclError:
            pass

    def _check():
        from services.updater import run_update_check

        run_update_check(app, manual=True, status_cb=_set_status)

    def _open_releases():
        try:
            webbrowser.open(GITHUB_RELEASES_PAGE)
        except (OSError, webbrowser.Error, AttributeError, TypeError, ValueError):
            logger.debug("打开发布页失败", exc_info=True)

    def _open_update():
        from services.updater import open_update_from_ui

        open_update_from_ui(app)

    _pill(btn_row, "检查更新…", app=app, c=c, primary=True, command=_check).pack(
        side=tk.LEFT, padx=(0, SPACE_SM)
    )
    _pill(btn_row, "GitHub 发布页", app=app, c=c, primary=False, command=_open_releases).pack(
        side=tk.LEFT
    )
    _pill(
        action_row,
        "查看更新…",
        app=app,
        c=c,
        primary=True,
        command=_open_update,
    ).pack(side=tk.LEFT)

    # 若此前已发现更新，进入关于页时直接展示
    pending = getattr(app, "_pending_update_result", None)
    if pending is not None and getattr(pending, "has_update", False):
        ver = (getattr(pending, "latest_version", None) or "").strip()
        _set_status(f"发现新版本 v{ver}" if ver else "发现新版本", "update")

    # —— 日志 / 版本信息 ——
    tk.Frame(card, bg=c["border"], height=1).pack(fill=tk.X, pady=SPACE_MD)

    util_row = tk.Frame(card, bg=c["card"])
    util_row.pack(fill=tk.X)

    parent_win = getattr(app, "_settings_window", None)

    def _open_log():
        from core.countdown_core import user_log_path

        try:
            log_path = user_log_path()
            # 确保目录存在；文件可能尚未创建
            parent_dir = os.path.dirname(log_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            if os.path.isfile(log_path):
                _open_path_in_file_manager(log_path)
            else:
                _open_path_in_file_manager(parent_dir or log_path)
        except (OSError, AttributeError, TypeError, ValueError, RuntimeError) as exc:
            logger.debug("打开运行日志失败", exc_info=True)
            show_error(
                app,
                f"无法打开运行日志。\n\n详情：{exc}",
                parent=parent_win or app.master,
            )

    def _copy_version():
        from core.countdown_core import APP_NAME_EN

        bits = platform.machine() or ""
        sys_name = platform.system() or ""
        rel = platform.release() or ""
        py = platform.python_version()
        lines = [
            f"{APP_NAME} ({APP_NAME_EN})",
            f"版本 {__version__}",
            f"平台 {sys_name} {rel} {bits}".strip(),
            f"Python {py}",
        ]
        text = "\n".join(lines)
        try:
            root = parent_win if parent_win is not None else app.master
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update_idletasks()
            show_info(
                app,
                "版本信息已复制到剪贴板。",
                title="已复制",
                parent=parent_win or app.master,
            )
        except (tk.TclError, AttributeError, TypeError, RuntimeError) as exc:
            logger.debug("复制版本信息失败", exc_info=True)
            show_error(
                app,
                f"复制失败。\n\n详情：{exc}",
                parent=parent_win or app.master,
            )

    _pill(
        util_row,
        "打开日志",
        app=app,
        c=c,
        primary=False,
        command=_open_log,
    ).pack(side=tk.LEFT, padx=(0, SPACE_SM))
    _pill(
        util_row,
        "复制版本信息",
        app=app,
        c=c,
        primary=False,
        command=_copy_version,
    ).pack(side=tk.LEFT)


# ---------------------------------------------------------------------------
# 控件与布局工具
# ---------------------------------------------------------------------------


def _pill(parent, text, *, app, c, primary=True, command=None):
    """兼容旧调用：委托统一 make_pill。"""
    return make_pill(parent, text, app=app, c=c, primary=primary, command=command)
