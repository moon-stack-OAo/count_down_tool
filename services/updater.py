# -*- coding: utf-8 -*-
"""自动更新 UI 编排：启动检查、手动检查、下载与 Windows 替换。"""

from __future__ import annotations

import logging
import os
import threading
import webbrowser
from datetime import date
from tkinter import messagebox
from typing import Optional

from core.countdown_core import APP_NAME, __version__
from core import update as core_update

logger = logging.getLogger("count_down_tool.updater")

# 启动后延迟检查（毫秒）
_STARTUP_DELAY_MS = 4000
_CHECKING = False


def schedule_startup_check(app) -> None:
    """若开启自动检查且今日未查过，则延迟后台检查。"""
    if not getattr(app, "_check_update_on_start", True):
        return
    last = getattr(app, "_last_update_check", "") or ""
    today = date.today().isoformat()
    if last == today:
        return

    def _kick():
        run_update_check(app, manual=False)

    try:
        app.master.after(_STARTUP_DELAY_MS, _kick)
    except Exception:
        logger.debug("调度启动更新检查失败", exc_info=True)


def run_update_check(app, manual: bool = False) -> None:
    """后台线程检查更新；结果回主线程。"""
    global _CHECKING
    if _CHECKING:
        if manual:
            messagebox.showinfo(APP_NAME, "正在检查更新，请稍候…", parent=app.master)
        return
    _CHECKING = True

    def worker():
        # 手动检查不受「忽略此版本」影响；启动检查会尊重忽略
        ignored = None
        if not manual:
            ignored = getattr(app, "_ignored_update_version", None) or None
        result = core_update.check_for_update(
            current_version=__version__,
            ignored_version=ignored,
        )
        try:
            app.master.after(0, lambda: _on_check_done(app, result, manual=manual))
        except Exception:
            global _CHECKING
            _CHECKING = False
            logger.debug("回传更新检查结果失败", exc_info=True)

    threading.Thread(target=worker, daemon=True, name="cdt-update-check").start()


def _mark_checked_today(app) -> None:
    app._last_update_check = date.today().isoformat()
    try:
        app._save_config()
    except Exception:
        logger.debug("保存 last_update_check 失败", exc_info=True)


def _on_check_done(app, result: core_update.UpdateCheckResult, manual: bool) -> None:
    global _CHECKING
    _CHECKING = False
    _mark_checked_today(app)

    if result.error:
        if manual:
            messagebox.showerror(
                APP_NAME,
                f"检查更新失败：\n{result.error}\n\n也可手动打开：\n{core_update.GITHUB_RELEASES_PAGE}",
                parent=app.master,
            )
        return

    if not result.has_update:
        if manual:
            messagebox.showinfo(
                APP_NAME,
                f"当前已是最新版本。\n\n本地：{result.current_version}\n远程：{result.latest_version or '—'}",
                parent=app.master,
            )
        return

    notes = ""
    if result.release:
        notes = core_update.truncate_release_notes(result.release.body)
    _prompt_update(app, result, notes)


def _prompt_update(app, result: core_update.UpdateCheckResult, notes: str) -> None:
    """产品化更新对话框。"""
    from ui.update_dialog import show_update_available

    ver = result.latest_version

    def on_action(action: str) -> None:
        if action == "later":
            return
        if action == "ignore":
            app._ignored_update_version = ver
            try:
                app._save_config()
            except Exception:
                pass
            return

        # 用户接受更新 → 清除忽略
        if getattr(app, "_ignored_update_version", "") == ver:
            app._ignored_update_version = ""
            try:
                app._save_config()
            except Exception:
                pass

        if action == "browser" or not result.asset_url:
            webbrowser.open(
                result.release.html_url if result.release else core_update.GITHUB_RELEASES_PAGE
            )
            return
        if action == "install":
            _start_windows_install(app, result)
        elif action == "download_only":
            _start_mac_download(app, result)

    show_update_available(app, result, notes, on_action=on_action)


def _start_windows_install(app, result: core_update.UpdateCheckResult) -> None:
    if not result.asset_url:
        return

    from ui.update_dialog import close_progress, show_update_progress, update_progress

    progress_win = show_update_progress(
        app,
        "正在下载更新",
        "下载完成后将自动安装并重启，请稍候…",
    )

    def worker():
        err: Optional[str] = None
        try:
            tmp_dir = os.path.join(
                os.environ.get("TEMP") or os.environ.get("TMP") or ".",
                "count_down_tool_update",
            )
            os.makedirs(tmp_dir, exist_ok=True)
            zip_path = os.path.join(
                tmp_dir,
                result.asset_name or f"count_down_tool-{result.latest_version}-win64.zip",
            )

            def _progress(received: int, total: int) -> None:
                try:
                    app.master.after(
                        0, lambda r=received, t=total: update_progress(progress_win, r, t)
                    )
                except Exception:
                    pass

            core_update.download_file(result.asset_url, zip_path, progress=_progress)
            core_update.apply_windows_update_from_zip(zip_path)
        except Exception as exc:
            logger.exception("Windows 自动更新失败")
            err = str(exc)

        def done():
            close_progress(progress_win)
            if err:
                messagebox.showerror(
                    APP_NAME,
                    f"更新失败：\n{err}\n\n可手动下载：\n{core_update.GITHUB_RELEASES_PAGE}",
                    parent=app.master,
                )
                return
            # 成功启动替换脚本，退出应用
            try:
                app._quit_app()
            except Exception:
                app.master.destroy()

        try:
            app.master.after(0, done)
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True, name="cdt-update-win").start()


def _start_mac_download(app, result: core_update.UpdateCheckResult) -> None:
    if not result.asset_url:
        return

    from ui.update_dialog import close_progress, show_update_progress, update_progress

    progress_win = show_update_progress(
        app,
        "正在下载更新包",
        "将保存到「下载」文件夹，完成后可手动替换 App。",
    )

    def worker():
        err: Optional[str] = None
        dest = ""
        try:
            folder = core_update.default_download_dir()
            name = result.asset_name or f"count_down_tool-{result.latest_version}.zip"
            dest = os.path.join(folder, name)

            def _progress(received: int, total: int) -> None:
                try:
                    app.master.after(
                        0, lambda r=received, t=total: update_progress(progress_win, r, t)
                    )
                except Exception:
                    pass

            core_update.download_file(result.asset_url, dest, progress=_progress)
        except Exception as exc:
            logger.exception("macOS 下载更新失败")
            err = str(exc)

        def done():
            close_progress(progress_win)
            if err:
                messagebox.showerror(
                    APP_NAME,
                    f"下载失败：\n{err}\n\n可手动打开：\n{core_update.GITHUB_RELEASES_PAGE}",
                    parent=app.master,
                )
                return
            messagebox.showinfo(
                APP_NAME,
                f"已下载到：\n{dest}\n\n请解压后手动替换 count_down_tool.app。",
                parent=app.master,
            )
            # 在 Finder 中显示
            try:
                import subprocess

                subprocess.run(["open", "-R", dest], check=False)
            except Exception:
                pass

        try:
            app.master.after(0, done)
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True, name="cdt-update-mac").start()


def tray_check_update(app, icon=None, item=None) -> None:
    app.master.after(0, lambda: run_update_check(app, manual=True))


def tray_toggle_check_update_on_start(app, icon=None, item=None) -> None:
    def _do():
        app._check_update_on_start = not bool(getattr(app, "_check_update_on_start", True))
        app._save_config()
        try:
            from services.tray import refresh_tray_menu

            refresh_tray_menu(app)
        except Exception:
            pass

    app.master.after(0, _do)
