# -*- coding: utf-8 -*-
"""统一主题弹窗：info / error / confirm，保证盖过设置窗置顶。"""

from __future__ import annotations

import logging
import os
import platform
import tkinter as tk
from typing import Optional

from core.countdown_core import APP_NAME
from ui.design.tokens import SPACE_MD, SPACE_SM, SPACE_XS
from ui.widgets import ThinScrollbar, make_pill, make_settings_card
from ui.window_chrome_dialog import center_dialog_later, use_borderless_chrome

logger = logging.getLogger("count_down_tool")

# 与设置中心内容宽感接近（设置窗 500，弹窗略窄）
_DIALOG_WIDTH = 420
_DIALOG_CONTENT_PAD = SPACE_MD


def _dialog_parent(app, parent=None):
    """优先设置窗，其次可见主/Mini 窗。"""
    if parent is not None:
        try:
            if parent.winfo_exists():
                return parent
        except tk.TclError:
            pass
    sw = getattr(app, "_settings_window", None)
    if sw is not None:
        try:
            if sw.winfo_exists():
                return sw
        except tk.TclError:
            pass
    if getattr(app, "_is_mini", False):
        mini = getattr(app, "mini_window", None)
        if mini is not None:
            try:
                if mini.winfo_exists():
                    return mini
            except tk.TclError:
                pass
    return app.master


def _activate(win: tk.Misc) -> None:
    try:
        win.lift()
        win.attributes("-topmost", True)
        win.focus_force()
    except tk.TclError:
        pass
    if platform.system() == "Windows":
        try:
            import ctypes

            win.update_idletasks()
            frame = win.wm_frame()
            hwnd = int(frame, 16) if frame else int(win.winfo_id())
            user32 = ctypes.windll.user32
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        except (OSError, AttributeError, ValueError, TypeError, tk.TclError):
            logger.debug("弹窗置前失败", exc_info=True)


def _set_topmost(win: Optional[tk.Misc], value: bool) -> None:
    if win is None:
        return
    try:
        if win.winfo_exists():
            win.attributes("-topmost", bool(value))
    except tk.TclError:
        pass


class _TopmostGuard:
    """打开系统对话框前临时取消设置/主弹窗置顶，结束后恢复。"""

    def __init__(self, *windows):
        self._windows = [w for w in windows if w is not None]
        self._prev = []

    def __enter__(self):
        for w in self._windows:
            try:
                if w.winfo_exists():
                    prev = bool(w.attributes("-topmost"))
                    self._prev.append((w, prev))
                    if prev:
                        w.attributes("-topmost", False)
                else:
                    self._prev.append((w, False))
            except tk.TclError:
                self._prev.append((w, False))
        return self

    def __exit__(self, *exc):
        for w, prev in self._prev:
            try:
                if w.winfo_exists() and prev:
                    w.attributes("-topmost", True)
                    w.lift()
            except tk.TclError:
                pass
        return False


def temporary_release_topmost(*windows) -> _TopmostGuard:
    """with temporary_release_topmost(settings_win): filedialog..."""
    return _TopmostGuard(*windows)


class _WithdrawGuard:
    """打开系统对话框前隐藏无边框窗（Windows overrideredirect 会盖住文件框）。"""

    def __init__(self, *windows):
        self._windows = [w for w in windows if w is not None]
        self._hidden = []

    def __enter__(self):
        for w in self._windows:
            try:
                if not w.winfo_exists():
                    continue
                # 无论是否 viewable 都尝试隐藏；并确保不置顶
                try:
                    w.attributes("-topmost", False)
                except tk.TclError:
                    pass
                try:
                    w.withdraw()
                except tk.TclError:
                    pass
                self._hidden.append(w)
            except tk.TclError:
                pass
        try:
            for w in self._windows:
                w.update_idletasks()
            # 让 WM 先处理 hide，再弹系统对话框
            if self._windows:
                self._windows[0].update()
        except tk.TclError:
            pass
        return self

    def __exit__(self, *exc):
        for w in self._hidden:
            try:
                if w.winfo_exists():
                    try:
                        w.attributes("-topmost", False)
                    except tk.TclError:
                        pass
                    w.deiconify()
                    w.lift()
            except tk.TclError:
                pass
        return False


def temporary_withdraw(*windows) -> _WithdrawGuard:
    """with temporary_withdraw(settings_win): filedialog.askopenfilename(...)"""
    return _WithdrawGuard(*windows)


def _show_message(
    app,
    kind: str,
    message: str,
    *,
    title: str = "",
    parent=None,
) -> None:
    """非阻塞主题提示（info / error）。"""
    parent = _dialog_parent(app, parent)
    c = app.COLORS
    kind = (kind or "info").lower()
    if kind == "error":
        accent = c.get("error", "#FB7185")
        default_title = "出错了"
    else:
        accent = c.get("accent", "#38BDF8")
        default_title = "提示"
    display_title = title or default_title

    win = tk.Toplevel(parent)
    win.title(f"{APP_NAME} · {display_title}")
    win.configure(bg=c["bg"])
    win.resizable(False, False)
    try:
        win.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        win.transient(parent)
    except tk.TclError:
        pass

    def _close(_e=None):
        try:
            win.destroy()
        except tk.TclError:
            pass
        return "break"

    win.protocol("WM_DELETE_WINDOW", _close)
    use_borderless_chrome(win, app, title=display_title, on_close=_close)

    # 内容区对齐设置中心：外层 bg 边距 + card 卡片 + 分区标题/正文/胶囊钮
    shell = tk.Frame(win, bg=c["bg"], padx=_DIALOG_CONTENT_PAD, pady=_DIALOG_CONTENT_PAD)
    shell.pack(fill=tk.BOTH, expand=True)

    body_card = make_settings_card(shell, c, pack=True, fill="x")
    wrap = max(240, _DIALOG_WIDTH - 2 * _DIALOG_CONTENT_PAD - 2 * SPACE_MD - 24)

    tk.Label(
        body_card,
        text=display_title,
        font=app._font("label", 9),
        bg=c["card"],
        fg=c.get("text_muted", c["text_dim"]),
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))
    # 状态色条（error / accent），贴近设置分区层次
    tk.Frame(body_card, bg=accent, height=2).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_SM))
    tk.Label(
        body_card,
        text=message or "",
        font=app._font("label", 10),
        bg=c["card"],
        fg=c["text"],
        wraplength=wrap,
        justify=tk.LEFT,
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_SM))

    btn_row = tk.Frame(shell, bg=c["bg"])
    btn_row.pack(fill=tk.X, pady=(0, 0))
    make_pill(btn_row, "知道了", app=app, c=c, primary=True, command=_close).pack(
        side=tk.RIGHT
    )

    win.update_idletasks()
    w = max(320, min(_DIALOG_WIDTH, win.winfo_reqwidth() + 24))
    h = max(160, win.winfo_reqheight() + 12)
    center_dialog_later(win, int(w), int(h))
    _activate(win)
    # 再抬一次，压过设置窗
    try:
        win.after(30, lambda: _activate(win))
        win.after(120, lambda: _activate(win))
    except tk.TclError:
        pass


def show_info(app, message: str, *, title: str = "", parent=None) -> None:
    _show_message(app, "info", message, title=title or "提示", parent=parent)


def show_error(app, message: str, *, title: str = "", parent=None) -> None:
    _show_message(app, "error", message, title=title or "出错了", parent=parent)


# 日志查看：只读末尾，避免大文件占满内存
_LOG_VIEW_MAX_BYTES = 256 * 1024
_LOG_VIEW_WIDTH = 640
_LOG_VIEW_HEIGHT = 480


def _read_log_tail(path: str, max_bytes: int = _LOG_VIEW_MAX_BYTES) -> tuple[str, str]:
    """读取日志末尾。返回 (正文, 状态说明)。"""
    if not path or not os.path.isfile(path):
        return "", "日志文件尚不存在（启动后写入过日志才会生成）。"
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        return "", f"无法读取日志大小：{exc}"
    try:
        with open(path, "rb") as f:
            if size > max_bytes:
                f.seek(-max_bytes, os.SEEK_END)
                raw = f.read()
                # 丢弃可能被截断的首行半截
                nl = raw.find(b"\n")
                if 0 <= nl < len(raw) - 1:
                    raw = raw[nl + 1 :]
                note = f"仅显示末尾约 {max_bytes // 1024} KB（文件共 {size // 1024} KB）"
            else:
                raw = f.read()
                note = f"共 {size} 字节"
        text = raw.decode("utf-8", errors="replace")
        if not text.strip():
            return "", "日志文件为空。"
        return text, note
    except OSError as exc:
        return "", f"读取失败：{exc}"


def show_log_viewer(app, *, parent=None) -> None:
    """弹窗显示 app.log 内容（可滚动、刷新、复制、打开所在目录）。"""
    import subprocess

    from core.countdown_core import user_log_path

    parent = _dialog_parent(app, parent)
    c = app.COLORS

    existing = getattr(app, "_log_viewer_window", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                _activate(existing)
                refresh = getattr(existing, "_log_refresh", None)
                if callable(refresh):
                    refresh()
                return
        except tk.TclError:
            pass

    log_path = user_log_path()
    win = tk.Toplevel(parent)
    win.title(f"{APP_NAME} · 运行日志")
    win.configure(bg=c["bg"])
    win.minsize(480, 320)
    try:
        win.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        win.transient(parent)
    except tk.TclError:
        pass

    def _close(_e=None):
        try:
            if getattr(app, "_log_viewer_window", None) is win:
                app._log_viewer_window = None
        except AttributeError:
            pass
        try:
            win.destroy()
        except tk.TclError:
            pass
        return "break"

    win.protocol("WM_DELETE_WINDOW", _close)
    use_borderless_chrome(win, app, title="运行日志", on_close=_close)

    shell = tk.Frame(win, bg=c["bg"], padx=_DIALOG_CONTENT_PAD, pady=_DIALOG_CONTENT_PAD)
    shell.pack(fill=tk.BOTH, expand=True)

    # 路径 + 状态：设置分区小标题风格
    meta_card = make_settings_card(shell, c, pack=True, fill="x")
    tk.Label(
        meta_card,
        text="运行日志",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c.get("text_muted", c["text_dim"]),
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))
    tk.Label(
        meta_card,
        text=log_path,
        font=app._font("label", 8),
        bg=c["card"],
        fg=c["text_dim"],
        anchor="w",
        wraplength=_LOG_VIEW_WIDTH - 2 * _DIALOG_CONTENT_PAD - 2 * SPACE_MD - 24,
        justify=tk.LEFT,
    ).pack(fill=tk.X, padx=SPACE_SM)
    status_lbl = tk.Label(
        meta_card,
        text="",
        font=app._font("label", 9),
        bg=c["card"],
        fg=c["text_muted"],
        anchor="w",
    )
    status_lbl.pack(fill=tk.X, padx=SPACE_SM, pady=(SPACE_XS, 0))

    body = make_settings_card(
        shell, c, pack=True, fill="both", expand=True, padx_inner=SPACE_SM, pady_inner=SPACE_SM
    )
    # 卡片已有边距，内部文本区贴齐
    try:
        log_font = app._font("time", 9)
    except (TypeError, AttributeError):
        log_font = app._font("label", 9)

    text = tk.Text(
        body,
        wrap=tk.NONE,
        font=log_font,
        bg=c.get("input_bg", c["card"]),
        fg=c["text"],
        insertbackground=c["accent"],
        relief=tk.FLAT,
        bd=0,
        padx=SPACE_SM,
        pady=SPACE_SM,
        highlightthickness=0,
        state=tk.DISABLED,
    )

    ysb = ThinScrollbar(
        body,
        command=text.yview,
        bg=c.get("card", c["bg"]),
        trough=c.get("input_bg", c.get("border", "#1E293B")),
        thumb=c.get("border", c.get("text_muted", "#64748B")),
        thumb_hover=c.get("text_muted", c.get("text_dim", "#94A3B8")),
        width=6,
        pad=3,
    )
    text.configure(yscrollcommand=ysb.set)
    ysb.pack(side=tk.RIGHT, fill=tk.Y)
    text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _load():
        body_text, note = _read_log_tail(log_path)
        try:
            status_lbl.config(text=note)
            text.configure(state=tk.NORMAL)
            text.delete("1.0", tk.END)
            if body_text:
                text.insert("1.0", body_text)
                text.see(tk.END)
            else:
                text.insert("1.0", note)
            text.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _copy_all():
        try:
            content = text.get("1.0", "end-1c")
            win.clipboard_clear()
            win.clipboard_append(content)
            win.update_idletasks()
            status_lbl.config(text="已复制到剪贴板")
        except tk.TclError as exc:
            logger.debug("复制日志失败", exc_info=True)
            status_lbl.config(text=f"复制失败：{exc}")

    def _open_folder():
        try:
            folder = os.path.dirname(log_path) or log_path
            if folder:
                os.makedirs(folder, exist_ok=True)
            system = platform.system()
            if system == "Windows":
                if os.path.isfile(log_path):
                    subprocess.run(
                        ["explorer", "/select,", os.path.abspath(log_path)],
                        check=False,
                    )
                else:
                    os.startfile(folder)  # type: ignore[attr-defined]
            elif system == "Darwin":
                if os.path.isfile(log_path):
                    subprocess.run(["open", "-R", log_path], check=False)
                else:
                    subprocess.run(["open", folder], check=False)
            else:
                subprocess.run(["xdg-open", folder], check=False)
        except (OSError, AttributeError, TypeError, ValueError, RuntimeError) as exc:
            logger.debug("打开日志目录失败", exc_info=True)
            status_lbl.config(text=f"打开目录失败：{exc}")

    footer = tk.Frame(shell, bg=c["bg"])
    footer.pack(fill=tk.X, pady=(SPACE_MD, 0))

    make_pill(footer, "刷新", app=app, c=c, primary=False, command=_load).pack(
        side=tk.LEFT, padx=(0, SPACE_SM)
    )
    make_pill(footer, "复制", app=app, c=c, primary=False, command=_copy_all).pack(
        side=tk.LEFT, padx=(0, SPACE_SM)
    )
    make_pill(
        footer, "打开所在目录", app=app, c=c, primary=False, command=_open_folder
    ).pack(side=tk.LEFT)
    make_pill(footer, "关闭", app=app, c=c, primary=True, command=_close).pack(
        side=tk.RIGHT
    )

    win._log_refresh = _load  # type: ignore[attr-defined]
    app._log_viewer_window = win
    _load()

    center_dialog_later(win, _LOG_VIEW_WIDTH, _LOG_VIEW_HEIGHT)
    _activate(win)
    try:
        win.after(30, lambda: _activate(win))
    except tk.TclError:
        pass


def ask_yes_no(
    app,
    message: str,
    *,
    title: str = "请确认",
    yes_text: str = "确定",
    no_text: str = "取消",
    danger: bool = False,
    parent=None,
) -> bool:
    """模态确认，返回 True=确定。"""
    parent = _dialog_parent(app, parent)
    c = app.COLORS
    result = {"ok": False}

    win = tk.Toplevel(parent)
    win.title(f"{APP_NAME} · {title}")
    win.configure(bg=c["bg"])
    win.resizable(False, False)
    try:
        win.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        win.transient(parent)
        win.grab_set()
    except tk.TclError:
        pass

    def _finish(ok: bool):
        result["ok"] = ok
        try:
            win.grab_release()
        except tk.TclError:
            pass
        try:
            win.destroy()
        except tk.TclError:
            pass

    win.protocol("WM_DELETE_WINDOW", lambda: _finish(False))
    use_borderless_chrome(win, app, title=title, on_close=lambda: _finish(False))

    shell = tk.Frame(win, bg=c["bg"], padx=_DIALOG_CONTENT_PAD, pady=_DIALOG_CONTENT_PAD)
    shell.pack(fill=tk.BOTH, expand=True)

    accent = c.get("error", "#FB7185") if danger else c.get("accent", "#38BDF8")
    body_card = make_settings_card(shell, c, pack=True, fill="x")
    wrap = max(240, _DIALOG_WIDTH - 2 * _DIALOG_CONTENT_PAD - 2 * SPACE_MD - 24)

    tk.Label(
        body_card,
        text=title,
        font=app._font("label", 9),
        bg=c["card"],
        fg=c.get("text_muted", c["text_dim"]),
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_XS))
    tk.Frame(body_card, bg=accent, height=2).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_SM))
    tk.Label(
        body_card,
        text=message or "",
        font=app._font("label", 10),
        bg=c["card"],
        fg=c["text"],
        wraplength=wrap,
        justify=tk.LEFT,
        anchor="w",
    ).pack(fill=tk.X, padx=SPACE_SM, pady=(0, SPACE_SM))

    row = tk.Frame(shell, bg=c["bg"])
    row.pack(fill=tk.X)
    make_pill(
        row,
        yes_text,
        app=app,
        c=c,
        primary=not danger,
        danger=danger,
        command=lambda: _finish(True),
    ).pack(side=tk.RIGHT, padx=(SPACE_SM, 0))
    make_pill(
        row, no_text, app=app, c=c, primary=False, command=lambda: _finish(False)
    ).pack(side=tk.RIGHT)

    win.update_idletasks()
    w = max(320, min(_DIALOG_WIDTH, win.winfo_reqwidth() + 24))
    h = max(170, win.winfo_reqheight() + 12)
    center_dialog_later(win, int(w), int(h))
    _activate(win)
    try:
        win.after(30, lambda: _activate(win))
    except tk.TclError:
        pass
    try:
        parent.wait_window(win)
    except tk.TclError:
        pass
    return bool(result["ok"])
