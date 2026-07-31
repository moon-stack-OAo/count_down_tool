# -*- coding: utf-8 -*-
"""设置 · 系统分区。"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import tkinter as tk

from services.autostart import is_autostart_enabled, set_autostart
from ui.app_dialogs import show_error, show_info
from ui.design.tokens import SPACE_SM, SPACE_XS
from ui.settings.layout import card, pill

logger = logging.getLogger("count_down_tool")


def open_path_in_file_manager(path: str) -> None:
    """用系统文件管理器打开目录或选中文件。"""
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


def build_system_section(app, parent, c, refreshers) -> None:
    sys_card = card(parent, c)
    win = getattr(app, "_settings_window", None)

    is_win = platform.system() == "Windows"

    auto_lbl = None
    if is_win:
        auto_lbl = tk.Label(
            sys_card,
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
        sys_card,
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
        sys_card,
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
    tk.Frame(sys_card, bg=c["border"], height=1).pack(fill=tk.X, pady=SPACE_SM)

    util_row = tk.Frame(sys_card, bg=c["card"])
    util_row.pack(fill=tk.X, pady=(SPACE_XS, 0))

    def _open_config_dir():
        from core.countdown_core import user_config_dir

        try:
            path = user_config_dir(create=True)
            open_path_in_file_manager(path)
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

    pill(
        util_row,
        "打开配置目录",
        app=app,
        c=c,
        primary=False,
        command=_open_config_dir,
    ).pack(side=tk.LEFT, padx=(0, SPACE_SM))
    pill(
        util_row,
        "重置 Mini 位置/大小",
        app=app,
        c=c,
        primary=False,
        command=_reset_mini_layout,
    ).pack(side=tk.LEFT)

    # —— 忽略的更新版本 ——
    tk.Frame(sys_card, bg=c["border"], height=1).pack(fill=tk.X, pady=SPACE_SM)

    ign_lbl = tk.Label(
        sys_card,
        text="",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
        padx=SPACE_SM,
    )
    ign_lbl.pack(fill=tk.X, pady=(0, SPACE_XS))

    ign_btn_row = tk.Frame(sys_card, bg=c["card"])
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

    clear_ign_btn = pill(
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
