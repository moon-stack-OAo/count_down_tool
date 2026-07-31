# -*- coding: utf-8 -*-
"""设置 · 声音分区。"""

from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import filedialog

from ui.app_dialogs import ask_yes_no, show_error, show_info, temporary_withdraw
from ui.design.tokens import SETTINGS_WIDTH, SPACE_SM, SPACE_XS
from ui.settings.layout import bind_wheel_tree, card, pill

logger = logging.getLogger("count_down_tool")


def build_sound_section(app, parent, c, refreshers, win) -> None:
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

    sound_card = card(parent, c)

    sound_rows = {}
    history_frame = tk.Frame(sound_card, bg=c["card"])

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
        sound_card,
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

    tk.Frame(sound_card, bg=c["border"], height=1).pack(fill=tk.X, pady=SPACE_SM)

    tk.Label(
        sound_card,
        text="结束音效",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))

    for sid, name in SOUND_PRESETS:
        row = tk.Label(
            sound_card,
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
        sound_card,
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

    btn_row = tk.Frame(sound_card, bg=c["card"])
    btn_row.pack(fill=tk.X, pady=(SPACE_SM, 0))

    pill(btn_row, "导入文件…", app=app, c=c, primary=False, command=_import_sound).pack(
        side=tk.LEFT, padx=(0, SPACE_SM)
    )
    preview_btn = pill(btn_row, "试听", app=app, c=c, primary=True, command=_preview)
    preview_btn.pack(side=tk.LEFT, padx=(0, SPACE_SM))
    stop_btn = pill(btn_row, "停止试听", app=app, c=c, primary=False, command=_stop_preview)
    stop_btn.pack(side=tk.LEFT)

    util_row = tk.Frame(sound_card, bg=c["card"])
    util_row.pack(fill=tk.X, pady=(SPACE_SM, 0))
    pill(
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
            bind_wheel_tree(history_frame, canvas)

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
