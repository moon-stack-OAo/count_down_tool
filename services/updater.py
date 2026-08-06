# -*- coding: utf-8 -*-
"""自动更新 UI 编排：启动检查、手动检查、下载与 Windows 替换。

UI 仅经 app.ui_actions，本模块不 import ui。
"""

from __future__ import annotations

import logging
import os
import threading
import time
import tkinter as tk
import webbrowser
from datetime import date
from typing import Callable, Optional

from core import update as core_update
from core.countdown_core import APP_NAME, __version__

logger = logging.getLogger("count_down_tool.updater")

# 启动后延迟检查（毫秒）
_STARTUP_DELAY_MS = 4000
# 检查 / 下载安装单飞（防连点并发）
_CHECKING = False
_CHECK_LOCK = threading.Lock()
_UPDATING = False
_UPDATE_LOCK = threading.Lock()
# 进度 UI 回调节流：至少间隔或百分比变化才 after
_PROGRESS_UI_INTERVAL_S = 0.1
# 当前下载取消事件（用户关进度窗 / 点取消时 set，worker 轮询）
_DOWNLOAD_CANCEL: Optional[threading.Event] = None

# kind: busy | ok | error | update | info
StatusCb = Optional[Callable[[str, str], None]]


def _ui(app):
    return getattr(app, "ui_actions", None)


def schedule_startup_check(app) -> None:
    """若开启自动检查且今日未查过，则延迟后台检查。"""
    if not getattr(app, "_check_update_on_start", True):
        return
    last = getattr(app, "_last_update_check", "") or ""
    today = date.today().isoformat()
    if last == today:
        return

    def _kick():
        try:
            app._startup_update_timer_id = None
        except (AttributeError, TypeError):
            pass
        run_update_check(app, manual=False)

    try:
        app._startup_update_timer_id = app.master.after(_STARTUP_DELAY_MS, _kick)
    except (RuntimeError, AttributeError, tk.TclError):
        try:
            app._startup_update_timer_id = None
        except (AttributeError, TypeError):
            pass
        logger.debug("调度启动更新检查失败", exc_info=True)


def _emit_status(status_cb: StatusCb, message: str, kind: str = "info") -> None:
    if not status_cb:
        return
    try:
        status_cb(message, kind)
    except Exception:
        # 回调由 UI 注入，异常类型不可控
        logger.debug("更新状态回调失败", exc_info=True)


def _set_checking(value: bool) -> None:
    global _CHECKING
    with _CHECK_LOCK:
        _CHECKING = value


def _try_begin_check() -> bool:
    """尝试占用检查单飞；已在检查中则返回 False。"""
    global _CHECKING
    with _CHECK_LOCK:
        if _CHECKING:
            return False
        _CHECKING = True
        return True


def _try_begin_update() -> bool:
    """尝试占用下载/安装单飞；已在进行中则返回 False。"""
    global _UPDATING
    with _UPDATE_LOCK:
        if _UPDATING:
            return False
        _UPDATING = True
        return True


def _end_update() -> None:
    global _UPDATING, _DOWNLOAD_CANCEL
    with _UPDATE_LOCK:
        _UPDATING = False
        _DOWNLOAD_CANCEL = None


def _request_download_cancel() -> None:
    """UI 关闭/取消时 set event；worker 轮询后清理半成品。"""
    ev = _DOWNLOAD_CANCEL
    if ev is not None:
        ev.set()


def _resolve_download_sha256(result: core_update.UpdateCheckResult) -> Optional[str]:
    """
    若 Release 存在对应 sha256 资产则返回哈希（下载后强制校验）；
    若不存在或解析失败则 warning 并返回 None（调用方须阻断应用内下载/安装）。
    """
    name = (result.asset_name or "").strip()
    url = (result.asset_url or "").strip()
    if not name or not url:
        logger.warning(
            "缺少更新资产名/URL，无法解析 SHA256，禁止应用内下载安装"
        )
        return None
    try:
        digest = core_update.resolve_expected_sha256(
            asset_name=name,
            asset_url=url,
            release=result.release,
        )
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        logger.warning(
            "解析 SHA256 校验源失败，禁止应用内下载安装: %s",
            exc,
        )
        return None
    if digest:
        return digest
    logger.warning(
        "Release 未提供 %s 的 SHA256 资产，禁止应用内静默下载/安装"
        "（请发布时附带 .sha256；用户将改为浏览器手动下载）",
        name,
    )
    return None


def _release_page_url(result: core_update.UpdateCheckResult) -> str:
    """发布页 URL：优先当前 Release 页，否则仓库 Releases 列表。"""
    if result.release and getattr(result.release, "html_url", None):
        return str(result.release.html_url)
    return core_update.GITHUB_RELEASES_PAGE


def _open_release_in_browser(result: core_update.UpdateCheckResult) -> str:
    """打开 Release/下载页，返回实际打开的 URL。"""
    url = _release_page_url(result)
    try:
        webbrowser.open(url)
    except Exception:
        logger.debug("打开浏览器失败: %s", url, exc_info=True)
    return url


def _make_throttled_progress(app, progress_win, update_progress_fn) -> Callable[[int, int], None]:
    """下载进度回调节流：100ms 或百分比变化再调度 UI（完成时强制刷新）。"""
    state = {"last_t": 0.0, "last_pct": -1}

    def _progress(received: int, total: int) -> None:
        now = time.monotonic()
        pct = -1
        if total and total > 0:
            try:
                pct = int(max(0, min(100, (received * 100) // total)))
            except (TypeError, ValueError, ZeroDivisionError, OverflowError):
                pct = -1
        done = total > 0 and received >= total
        elapsed = now - state["last_t"]
        if (
            not done
            and elapsed < _PROGRESS_UI_INTERVAL_S
            and pct == state["last_pct"]
        ):
            return
        state["last_t"] = now
        state["last_pct"] = pct
        try:
            app.master.after(
                0,
                lambda r=received, t=total: update_progress_fn(progress_win, r, t),
            )
        except (RuntimeError, AttributeError):
            logger.debug("调度下载进度 UI 失败", exc_info=True)

    return _progress


def run_update_check(
        app,
        manual: bool = False,
        *,
        status_cb: StatusCb = None,
) -> None:
    """后台线程检查更新；结果回主线程。

    status_cb(message, kind)：设置中心等内联反馈；传入后手动检查不再弹 info/error。
    kind: busy | ok | error | update | info
    """
    if not _try_begin_check():
        if status_cb:
            _emit_status(status_cb, "正在检查更新，请稍候…", "busy")
        elif manual:
            def _busy():
                ui = _ui(app)
                if ui is not None:
                    ui.show_info(app, "正在检查更新，请稍候…")

            try:
                app.master.after(0, _busy)
            except (RuntimeError, AttributeError):
                logger.debug("调度忙碌提示失败", exc_info=True)
        return
    _emit_status(status_cb, "正在检查更新…", "busy")

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
            app.master.after(
                0,
                lambda: _on_check_done(
                    app, result, manual=manual, status_cb=status_cb
                ),
            )
        except (RuntimeError, AttributeError):
            _set_checking(False)
            logger.debug("回传更新检查结果失败", exc_info=True)

    threading.Thread(target=worker, daemon=True, name="cdt-update-check").start()


def _mark_checked_today(app) -> None:
    app._last_update_check = date.today().isoformat()
    try:
        app._save_config()
    except (OSError, TypeError, ValueError, AttributeError):
        logger.debug("保存 last_update_check 失败", exc_info=True)


def set_pending_update(app, result: Optional[core_update.UpdateCheckResult]) -> None:
    """缓存待处理更新并刷新完整窗标题 NEW 角标。"""
    app._pending_update_result = result if (result and result.has_update) else None
    try:
        ui = _ui(app)
        if ui is not None:
            ui.refresh_update_badge(app)
    except Exception:
        # UI 刷新边界，异常类型不可控
        logger.debug("刷新更新角标失败", exc_info=True)


def open_update_from_ui(app) -> None:
    """标题 NEW / 右键菜单：有缓存则直接弹更新窗，否则手动检查。"""
    pending = getattr(app, "_pending_update_result", None)
    if pending is not None and getattr(pending, "has_update", False):
        notes = ""
        if pending.release:
            notes = core_update.truncate_release_notes(pending.release.body)
        _prompt_update(app, pending, notes)
        return
    run_update_check(app, manual=True)


def _on_check_done(
        app,
        result: core_update.UpdateCheckResult,
        manual: bool,
        status_cb: StatusCb = None,
) -> None:
    _set_checking(False)
    _mark_checked_today(app)

    if result.error:
        msg = f"检查失败：{result.error}"
        if status_cb:
            _emit_status(status_cb, msg, "error")
        elif manual:
            ui = _ui(app)
            if ui is not None:
                ui.show_error(
                    app,
                    f"检查更新失败：\n{result.error}\n\n也可手动打开：\n{core_update.GITHUB_RELEASES_PAGE}",
                )
        return

    if not result.has_update:
        set_pending_update(app, None)
        remote = result.latest_version or "—"
        local = result.current_version or "—"
        msg = f"已是最新版本  v{local}"
        if remote and remote != local and remote != "—":
            msg = f"已是最新版本  本地 v{local} · 远程 v{remote}"
        if status_cb:
            _emit_status(status_cb, msg, "ok")
        elif manual:
            ui = _ui(app)
            if ui is not None:
                ui.show_info(
                    app,
                    f"当前已是最新版本。\n\n本地：{result.current_version}\n远程：{result.latest_version or '—'}",
                )
        return

    notes = ""
    if result.release:
        notes = core_update.truncate_release_notes(result.release.body)
    set_pending_update(app, result)
    ver = (result.latest_version or "").strip()
    if status_cb:
        _emit_status(
            status_cb,
            f"发现新版本 v{ver}" if ver else "发现新版本",
            "update",
        )
    # 有更新：托盘气泡（启动静默时尤其有用）
    _notify_update_available(app, result)
    # 设置中心内联模式：不自动弹窗，由用户点「查看更新」；其它入口仍弹安装窗
    if status_cb:
        return
    _prompt_update(app, result, notes)


def _notify_update_available(app, result: core_update.UpdateCheckResult) -> None:
    """系统托盘气泡提示有新版本（Windows pystray；失败静默）。"""
    ver = (result.latest_version or "").strip()
    title = APP_NAME
    message = f"发现新版本 v{ver}" if ver else "发现新版本"
    icon = getattr(app, "tray_icon", None)
    if icon is None:
        return
    try:
        icon.notify(message, title)
    except Exception:
        # 托盘原生 API 边界
        logger.debug("托盘更新提示失败", exc_info=True)


def _prompt_update(app, result: core_update.UpdateCheckResult, notes: str) -> None:
    """产品化更新对话框。"""
    ui = _ui(app)
    if ui is None:
        logger.debug("ui_actions 未装配，跳过更新提示")
        return

    ver = result.latest_version

    def on_action(action: str) -> None:
        if action == "later":
            # 保留 pending，完整窗标题 NEW 角标继续提示
            return
        if action == "ignore":
            app._ignored_update_version = ver
            try:
                app._save_config()
            except (OSError, TypeError, ValueError, AttributeError):
                logger.debug("保存忽略版本失败", exc_info=True)
            set_pending_update(app, None)
            return

        # 用户接受更新 → 清除忽略
        if getattr(app, "_ignored_update_version", "") == ver:
            app._ignored_update_version = ""
            try:
                app._save_config()
            except (OSError, TypeError, ValueError, AttributeError):
                logger.debug("清除忽略版本保存失败", exc_info=True)

        if action == "browser" or not result.asset_url:
            _open_release_in_browser(result)
            return
        if action == "install":
            _start_windows_install(app, result)
        elif action == "download_only":
            _start_mac_download(app, result)

    ui.show_update_available(app, result, notes, on_action=on_action)


def _notify_update_busy(app) -> None:
    """下载/安装已在进行时的轻量提示。"""
    try:
        ui = _ui(app)
        if ui is not None:
            app.master.after(
                0, lambda: ui.show_info(app, "正在下载或安装更新，请稍候…")
            )
    except Exception:
        logger.debug("更新忙碌提示失败", exc_info=True)


def _start_windows_install(app, result: core_update.UpdateCheckResult) -> None:
    global _DOWNLOAD_CANCEL
    if not result.asset_url:
        return
    if not _try_begin_update():
        _notify_update_busy(app)
        return

    ui = _ui(app)
    if ui is None:
        _end_update()
        logger.debug("ui_actions 未装配，跳过 Windows 安装")
        return

    cancel_event = threading.Event()
    _DOWNLOAD_CANCEL = cancel_event

    progress_win = ui.show_update_progress(
        app,
        "正在下载更新",
        "下载完成后将自动安装并重启，请稍候…",
        on_cancel=_request_download_cancel,
        allow_cancel=True,
    )
    progress_cb = _make_throttled_progress(app, progress_win, ui.update_progress)

    def worker():
        err: Optional[str] = None
        cancelled = False
        missing_sha = False
        try:
            # 无有效 SHA256：禁止应用内下载与覆盖安装目录
            expected_sha = core_update.require_expected_sha256(
                _resolve_download_sha256(result),
                asset_name=result.asset_name or "",
            )
            tmp_dir = os.path.join(
                os.environ.get("TEMP") or os.environ.get("TMP") or ".",
                "count_down_tool_update",
            )
            os.makedirs(tmp_dir, exist_ok=True)
            zip_path = os.path.join(
                tmp_dir,
                result.asset_name or f"count_down_tool-{result.latest_version}-win64.zip",
            )

            core_update.download_file(
                result.asset_url,
                zip_path,
                progress=progress_cb,
                expected_size=int(getattr(result, "asset_size", 0) or 0),
                expected_sha256=expected_sha,
                cancel_event=cancel_event,
            )
            if cancel_event.is_set():
                raise core_update.DownloadCancelled("下载已取消")
            core_update.apply_windows_update_from_zip(zip_path)
        except core_update.MissingUpdateSha256Error as exc:
            logger.warning("Windows 更新因缺少 SHA256 已阻断: %s", exc)
            missing_sha = True
            err = str(exc)
        except core_update.DownloadCancelled as exc:
            logger.info("Windows 更新下载已取消: %s", exc)
            cancelled = True
            err = str(exc)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            logger.exception("Windows 自动更新失败")
            err = str(exc)

        def done():
            # 成功退出前也释放标志（进程将结束；失败/取消路径需允许重试）
            if err:
                _end_update()
            ui.close_progress(progress_win)
            if cancelled:
                return
            if err:
                page = _release_page_url(result)
                if missing_sha:
                    ui.show_error(
                        app,
                        f"{err}\n\n将打开发布页供手动下载：\n{page}",
                    )
                    _open_release_in_browser(result)
                else:
                    ui.show_error(
                        app,
                        f"更新失败：\n{err}\n\n可手动下载：\n{page}",
                    )
                return
            # 成功启动替换脚本，退出应用
            try:
                app._quit_app()
            except Exception:
                # 退出路径：尽量 destroy，保证替换脚本可接管
                logger.debug("更新成功后退出失败，回退 destroy", exc_info=True)
                try:
                    app.master.destroy()
                except Exception:
                    logger.debug("destroy 失败", exc_info=True)

        try:
            app.master.after(0, done)
        except (RuntimeError, AttributeError):
            _end_update()
            logger.debug("回传 Windows 更新结果失败", exc_info=True)

    threading.Thread(target=worker, daemon=True, name="cdt-update-win").start()


def _start_mac_download(app, result: core_update.UpdateCheckResult) -> None:
    global _DOWNLOAD_CANCEL
    if not result.asset_url:
        return
    if not _try_begin_update():
        _notify_update_busy(app)
        return

    ui = _ui(app)
    if ui is None:
        _end_update()
        logger.debug("ui_actions 未装配，跳过 macOS 下载")
        return

    cancel_event = threading.Event()
    _DOWNLOAD_CANCEL = cancel_event

    progress_win = ui.show_update_progress(
        app,
        "正在下载更新包",
        "将保存到「下载」文件夹，完成后可手动替换 App。",
        on_cancel=_request_download_cancel,
        allow_cancel=True,
    )
    progress_cb = _make_throttled_progress(app, progress_win, ui.update_progress)

    def worker():
        err: Optional[str] = None
        cancelled = False
        missing_sha = False
        dest = ""
        try:
            # 无有效 SHA256：禁止应用内静默下载
            expected_sha = core_update.require_expected_sha256(
                _resolve_download_sha256(result),
                asset_name=result.asset_name or "",
            )
            folder = core_update.default_download_dir()
            name = result.asset_name or f"count_down_tool-{result.latest_version}.zip"
            dest = os.path.join(folder, name)

            core_update.download_file(
                result.asset_url,
                dest,
                progress=progress_cb,
                expected_size=int(getattr(result, "asset_size", 0) or 0),
                expected_sha256=expected_sha,
                cancel_event=cancel_event,
            )
        except core_update.MissingUpdateSha256Error as exc:
            logger.warning("macOS 下载因缺少 SHA256 已阻断: %s", exc)
            missing_sha = True
            err = str(exc)
        except core_update.DownloadCancelled as exc:
            logger.info("macOS 更新下载已取消: %s", exc)
            cancelled = True
            err = str(exc)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            logger.exception("macOS 下载更新失败")
            err = str(exc)

        def done():
            _end_update()
            ui.close_progress(progress_win)
            if cancelled:
                return
            if err:
                page = _release_page_url(result)
                if missing_sha:
                    ui.show_error(
                        app,
                        f"{err}\n\n将打开发布页供手动下载：\n{page}",
                    )
                    _open_release_in_browser(result)
                else:
                    ui.show_error(
                        app,
                        f"下载失败：\n{err}\n\n可手动打开：\n{page}",
                    )
                return
            ui.show_info(
                app,
                f"已下载到：\n{dest}\n\n请解压后手动替换 count_down_tool.app。",
            )
            # 在 Finder 中显示
            try:
                import subprocess

                subprocess.run(["open", "-R", dest], check=False)
            except (OSError, subprocess.SubprocessError):
                logger.debug("Finder 定位下载文件失败", exc_info=True)

        try:
            app.master.after(0, done)
        except (RuntimeError, AttributeError):
            _end_update()
            logger.debug("回传 macOS 下载结果失败", exc_info=True)

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
            # 托盘刷新边界
            logger.debug("刷新托盘菜单失败", exc_info=True)

    app.master.after(0, _do)
