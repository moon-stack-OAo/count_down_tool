# -*- coding: utf-8 -*-
"""设置中心：Toplevel 单例，分区管理外观 / 声音 / 系统 / 关于。"""

from __future__ import annotations

import logging
import os
import platform
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox

from core.countdown_core import APP_NAME, __version__
from core.themes import list_themes
from core.update import GITHUB_RELEASES_PAGE
from services.autostart import is_autostart_enabled, set_autostart
from ui.design.tokens import (
    SETTINGS_HEIGHT,
    SETTINGS_WIDTH,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
)
from ui.time_picker import _activate_picker, _picker_parent

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
                _activate_picker(existing)
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
        win.attributes("-topmost", True)
    except tk.TclError:
        pass
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

    # ===== 可滚动内容 =====
    outer = tk.Frame(win, bg=c["bg"])
    outer.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(outer, bg=c["bg"], highlightthickness=0, bd=0)
    scrollbar = tk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    body = tk.Frame(canvas, bg=c["bg"])
    body_id = canvas.create_window((0, 0), window=body, anchor="nw")

    def _on_body_configure(_e=None):
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except tk.TclError:
            pass

    def _on_canvas_configure(e):
        try:
            canvas.itemconfigure(body_id, width=e.width)
        except tk.TclError:
            pass

    body.bind("<Configure>", _on_body_configure)
    canvas.bind("<Configure>", _on_canvas_configure)

    def _wheel(e):
        try:
            if platform.system() == "Darwin":
                canvas.yview_scroll(int(-1 * e.delta), "units")
            else:
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        except tk.TclError:
            pass

    def _bind_wheel(w):
        w.bind("<MouseWheel>", _wheel)
        w.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        w.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        for child in w.winfo_children():
            _bind_wheel(child)

    pad = SPACE_LG
    content = tk.Frame(body, bg=c["bg"])
    content.pack(fill=tk.BOTH, expand=True, padx=pad, pady=pad)

    # 标题
    tk.Label(
        content,
        text="设置中心",
        font=app._font("button", 14, bold=True),
        bg=c["bg"],
        fg=c["text"],
    ).pack(anchor="w")
    tk.Label(
        content,
        text="外观 · 声音 · 系统 · 关于",
        font=app._font("label", 9),
        bg=c["bg"],
        fg=c["text_muted"],
    ).pack(anchor="w", pady=(SPACE_XS, SPACE_MD))
    tk.Frame(content, bg=c["accent"], height=2).pack(fill=tk.X, pady=(0, SPACE_LG))

    # 状态刷新回调集合（主题/音效切换后局部更新勾选）
    refreshers = []

    def _refresh_all():
        for fn in list(refreshers):
            try:
                fn()
            except Exception:
                logger.debug("设置窗刷新失败", exc_info=True)

    _build_appearance_section(app, content, c, refreshers)
    _build_sound_section(app, content, c, refreshers, win)
    _build_system_section(app, content, c, refreshers)
    _build_about_section(app, content, c)

    # 底部关闭
    footer = tk.Frame(content, bg=c["bg"])
    footer.pack(fill=tk.X, pady=(SPACE_LG, 0))
    _pill(
        footer,
        "关闭",
        app=app,
        c=c,
        primary=False,
        command=_on_close,
    ).pack(side=tk.RIGHT)

    win.update_idletasks()
    _bind_wheel(body)
    _center_window(win, SETTINGS_WIDTH, SETTINGS_HEIGHT)
    _activate_picker(win)
    # 暴露刷新，供内部切换主题后重绘勾选（主题会 close 窗，一般用不到）
    win._settings_refresh = _refresh_all  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 分区构建
# ---------------------------------------------------------------------------


def _section_header(parent, title: str, app, c) -> tk.Frame:
    box = tk.Frame(parent, bg=c["bg"])
    box.pack(fill=tk.X, pady=(0, SPACE_SM))
    tk.Label(
        box,
        text=title,
        font=app._font("label", 11, bold=True),
        bg=c["bg"],
        fg=c["accent_glow"],
    ).pack(anchor="w")
    return box


def _card(parent, c) -> tk.Frame:
    card = tk.Frame(
        parent,
        bg=c["card"],
        highlightbackground=c["border"],
        highlightthickness=1,
        padx=SPACE_MD,
        pady=SPACE_MD,
    )
    card.pack(fill=tk.X, pady=(0, SPACE_LG))
    return card


def _build_appearance_section(app, parent, c, refreshers) -> None:
    _section_header(parent, "外观", app, c)
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
            pady=SPACE_SM,
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
        stop_playback,
        touch_sound_history,
    )

    _section_header(parent, "声音", app, c)
    card = _card(parent, c)

    mute_var_holder = {"lbl": None}
    sound_rows = {}

    def _toggle_mute():
        app._sound_muted = not bool(getattr(app, "_sound_muted", False))
        app._save_config()
        _refresh()
        try:
            from services.tray import refresh_tray_menu

            refresh_tray_menu(app)
        except Exception:
            pass

    def _set_sound(sid: str):
        app._sound_id = sid
        app._save_config()
        _refresh()
        try:
            from services.tray import refresh_tray_menu

            refresh_tray_menu(app)
        except Exception:
            pass

    def _import_sound():
        path = filedialog.askopenfilename(
            parent=win,
            title="导入结束音效（将复制到本地库）",
            filetypes=AUDIO_FILETYPES,
        )
        if not path:
            return
        if not is_audio_file(path):
            messagebox.showerror(
                APP_NAME,
                "不支持的音频格式。\n请选择 wav / mp3 / aiff / m4a / ncm 等常见格式。",
                parent=win,
            )
            return
        result = import_custom_sound(path)
        if not result:
            messagebox.showerror(
                APP_NAME,
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
        try:
            from services.tray import refresh_tray_menu

            refresh_tray_menu(app)
        except Exception:
            pass

    def _preview():
        if is_sound_playing():
            stop_playback()
        play_finish_sound_async(
            app.master,
            muted=False,
            sound_id=str(getattr(app, "_sound_id", "soft") or "soft"),
            custom_path=str(getattr(app, "_sound_path", "") or ""),
        )
        _schedule_preview_refresh()

    def _stop_preview():
        stop_playback()
        _schedule_preview_refresh()

    def _schedule_preview_refresh():
        _refresh()
        try:
            win.after(400, _refresh)
            win.after(1500, _refresh)
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
    mute_var_holder["lbl"] = mute_lbl

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
        wraplength=SETTINGS_WIDTH - 80,
        justify=tk.LEFT,
    )
    custom_lbl.pack(fill=tk.X)

    btn_row = tk.Frame(card, bg=c["card"])
    btn_row.pack(fill=tk.X, pady=(SPACE_SM, 0))

    _pill(btn_row, "导入文件…", app=app, c=c, primary=False, command=_import_sound).pack(
        side=tk.LEFT, padx=(0, SPACE_SM)
    )
    preview_btn = _pill(btn_row, "试听", app=app, c=c, primary=True, command=_preview)
    preview_btn.pack(side=tk.LEFT, padx=(0, SPACE_SM))
    stop_btn = _pill(btn_row, "停止试听", app=app, c=c, primary=False, command=_stop_preview)
    stop_btn.pack(side=tk.LEFT)

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
        playing = is_sound_playing()
        try:
            # 播放中禁用试听观感（Label 仍可点，逻辑里会先 stop）
            preview_btn.config(fg=c["text_muted"] if playing else c["bg"])
            stop_btn.config(fg=c["text"] if playing else c["text_muted"])
        except tk.TclError:
            pass

    refreshers.append(_refresh)
    _refresh()


def _build_system_section(app, parent, c, refreshers) -> None:
    _section_header(parent, "系统", app, c)
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
            messagebox.showerror(
                APP_NAME,
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
    _section_header(parent, "关于", app, c)
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

    def _check():
        from services.updater import run_update_check

        run_update_check(app, manual=True)

    def _open_releases():
        try:
            webbrowser.open(GITHUB_RELEASES_PAGE)
        except Exception:
            logger.debug("打开发布页失败", exc_info=True)

    _pill(btn_row, "检查更新…", app=app, c=c, primary=True, command=_check).pack(
        side=tk.LEFT, padx=(0, SPACE_SM)
    )
    _pill(btn_row, "GitHub 发布页", app=app, c=c, primary=False, command=_open_releases).pack(
        side=tk.LEFT
    )


# ---------------------------------------------------------------------------
# 控件与布局工具
# ---------------------------------------------------------------------------


def _pill(parent, text, *, app, c, primary=True, command=None):
    """圆角观感操作按钮。"""
    bg = c["accent"] if primary else c["chip"]
    fg = c["bg"] if primary else c["text"]
    hover = c["accent_hover"] if primary else c.get("chip_hover", c["border"])
    btn = tk.Label(
        parent,
        text=text,
        font=app._font("label", 9, bold=True) if primary else app._font("label", 9),
        bg=bg,
        fg=fg,
        padx=14,
        pady=6,
        cursor="hand2",
    )
    if command:
        btn.bind("<Button-1>", lambda e: command())
    btn.bind("<Enter>", lambda e: btn.config(bg=hover))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn


def _center_window(win, w: int, h: int) -> None:
    try:
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 3)
        win.geometry(f"{w}x{h}+{x}+{y}")
    except tk.TclError:
        pass
