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
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
)
from ui.time_picker import _activate_picker, _picker_parent
from ui.widgets import ThinScrollbar, make_pill
from ui.window_chrome_dialog import center_dialog_later, use_borderless_chrome

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


def show_settings(app) -> None:
    """打开设置中心（单例：已存在则置前）。"""
    existing = getattr(app, "_settings_window", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                _activate_picker(existing, topmost=False)
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
        except Exception:
            pass
        try:
            win.destroy()
        except tk.TclError:
            pass
        if getattr(app, "_settings_window", None) is win:
            app._settings_window = None

    win.protocol("WM_DELETE_WINDOW", _on_close)
    # Windows：无边框 + 自绘标题栏；macOS 等保留原生边框
    use_borderless_chrome(win, app, title="⚙  设置", on_close=_on_close)

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
    state = {"tab": "appearance"}

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
        except Exception:
            pass
        try:
            sync = getattr(pages[key], "_settings_sync_scroll", None)
            if sync:
                pages[key].after_idle(sync)
        except Exception:
            pass

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
            except Exception:
                logger.debug("设置窗刷新失败", exc_info=True)

    _build_appearance_section(app, pages["appearance"]._settings_content, c, refreshers)
    _build_sound_section(app, pages["sound"]._settings_content, c, refreshers, win)
    _build_system_section(app, pages["system"]._settings_content, c, refreshers)
    _build_about_section(app, pages["about"]._settings_content, c)

    _show_tab("appearance")
    win.update_idletasks()
    for page in pages.values():
        _bind_wheel_tree(page, page._settings_canvas)
        sync = getattr(page, "_settings_sync_scroll", None)
        if sync:
            try:
                page.after_idle(sync)
            except tk.TclError:
                pass
    # overrideredirect 后系统常落到 0,0，延后多次居中
    center_dialog_later(win, SETTINGS_WIDTH, SETTINGS_HEIGHT)
    _activate_picker(win, topmost=False)
    # 暴露刷新，供内部切换主题后重绘勾选（主题会 close 窗，一般用不到）
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
    except Exception:
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
    card = _card(parent, c)
    rows = {}

    def _apply(tid: str):
        app._apply_theme(tid)
        # apply_theme 会 close_settings；若未关闭则刷新勾选
        for fn in refreshers:
            try:
                fn()
            except Exception:
                pass

    def _refresh():
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

    refreshers.append(_refresh)
    _refresh()


def _build_sound_section(app, parent, c, refreshers, win) -> None:
    from services.sound import (
        AUDIO_FILETYPES,
        SOUND_ID_CUSTOM,
        SOUND_PRESETS,
        import_custom_sound,
        is_audio_file,
        is_sound_playing,
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
        except Exception:
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
        if not path or not os.path.isfile(path):
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
        # Windows 无边框设置窗会盖住系统文件框：选择期间先隐藏设置
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
        history = prune_sound_history(getattr(app, "_sound_history", []))
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
        except Exception:
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


def _build_system_section(app, parent, c, refreshers) -> None:
    card = _card(parent, c)

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
        except Exception:
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
        except Exception:
            pass

    auto_lbl.bind("<Button-1>", lambda e: _toggle_autostart())
    upd_lbl.bind("<Button-1>", lambda e: _toggle_check_update())
    for w in (auto_lbl, upd_lbl):
        w.bind(
            "<Enter>",
            lambda e, x=w: x.config(bg=c.get("chip_hover", c["border"])),
        )
        w.bind("<Leave>", lambda e, x=w: x.config(bg=c["card"]))

    def _refresh():
        auto = bool(getattr(app, "_autostart", False))
        check = bool(getattr(app, "_check_update_on_start", True))
        try:
            auto_lbl.config(text=("✓  开机自启" if auto else "    开机自启"))
            upd_lbl.config(
                text=("✓  启动时检查更新" if check else "    启动时检查更新")
            )
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
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(SPACE_XS, SPACE_MD))

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
        except Exception:
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


# ---------------------------------------------------------------------------
# 控件与布局工具
# ---------------------------------------------------------------------------


def _pill(parent, text, *, app, c, primary=True, command=None):
    """兼容旧调用：委托统一 make_pill。"""
    return make_pill(parent, text, app=app, c=c, primary=primary, command=command)
