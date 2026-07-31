# -*- coding: utf-8 -*-
"""设置 · 关于分区。"""

from __future__ import annotations

import logging
import platform
import tkinter as tk
import webbrowser

from core.countdown_core import APP_NAME, __version__
from core.update import GITHUB_RELEASES_PAGE
from ui.app_dialogs import show_error, show_info, show_log_viewer
from ui.design.tokens import SETTINGS_WIDTH, SPACE_MD, SPACE_SM, SPACE_XS
from ui.settings.layout import card, pill

logger = logging.getLogger("count_down_tool")


def build_about_section(app, parent, c) -> None:
    about_card = card(parent, c)

    tk.Label(
        about_card,
        text=APP_NAME,
        font=app._font("label", 11, bold=True),
        bg=c["card"],
        fg=c["text"],
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM)
    tk.Label(
        about_card,
        text=f"版本 {__version__}",
        font=app._font("label", 10),
        bg=c["card"],
        fg=c["text_dim"],
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(SPACE_XS, SPACE_XS))

    last_check_lbl = tk.Label(
        about_card,
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

    btn_row = tk.Frame(about_card, bg=c["card"])
    btn_row.pack(fill=tk.X)

    status_lbl = tk.Label(
        about_card,
        text="",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
        justify=tk.LEFT,
        wraplength=SETTINGS_WIDTH - 96,
    )
    status_lbl.pack(fill=tk.X, padx=SPACE_SM, pady=(SPACE_MD, 0))

    action_row = tk.Frame(about_card, bg=c["card"])

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

    pill(btn_row, "检查更新…", app=app, c=c, primary=True, command=_check).pack(
        side=tk.LEFT, padx=(0, SPACE_SM)
    )
    pill(btn_row, "GitHub 发布页", app=app, c=c, primary=False, command=_open_releases).pack(
        side=tk.LEFT
    )
    pill(
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
    tk.Frame(about_card, bg=c["border"], height=1).pack(fill=tk.X, pady=SPACE_MD)

    util_row = tk.Frame(about_card, bg=c["card"])
    util_row.pack(fill=tk.X)

    parent_win = getattr(app, "_settings_window", None)

    def _open_log():
        try:
            show_log_viewer(app, parent=parent_win or app.master)
        except (tk.TclError, OSError, AttributeError, RuntimeError, TypeError) as exc:
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

    pill(
        util_row,
        "查看日志",
        app=app,
        c=c,
        primary=False,
        command=_open_log,
    ).pack(side=tk.LEFT, padx=(0, SPACE_SM))
    pill(
        util_row,
        "复制版本信息",
        app=app,
        c=c,
        primary=False,
        command=_copy_version,
    ).pack(side=tk.LEFT)
