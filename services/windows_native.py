# -*- coding: utf-8 -*-
"""Windows / 跨平台原生窗口与单实例相关能力。"""

import atexit
import logging
import os
import platform
import time

from core.countdown_core import APP_NAME, APP_NAME_EN, try_acquire_weak_lock, user_config_dir

logger = logging.getLogger("count_down_tool")

# 单实例锁句柄（进程级）
_instance_lock = None

# 二次启动「show 请求」标志文件名（写在用户配置目录）
SHOW_REQUEST_NAME = "show.request"
# Mini 窗可枚举标题（无边框仍可 GetWindowText）
MINI_WINDOW_TITLE = f"{APP_NAME} - Mini"


def path_has_mark_of_the_web(path: str) -> bool:
    """检测 Windows Mark of the Web（从网络/压缩包拖出的 exe 常见）。

    存在 Zone.Identifier 且 ZoneId>=3（Internet/Restricted）时返回 True。
    非 Windows 或无法读取时返回 False。
    """
    if platform.system() != "Windows" or not path:
        return False
    try:
        if not os.path.isfile(path):
            return False
    except OSError:
        return False
    ads = path + ":Zone.Identifier"
    try:
        with open(ads, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except OSError:
        try:
            with open(ads, "r", encoding="utf-16", errors="ignore") as f:
                text = f.read()
        except OSError:
            return False
    # ZoneId=3 Internet；4 Restricted
    for line in text.replace("\r\n", "\n").split("\n"):
        s = line.strip()
        if s.lower().startswith("zoneid="):
            try:
                zid = int(s.split("=", 1)[1].strip())
            except ValueError:
                continue
            if zid >= 3:
                return True
    return False


def try_remove_mark_of_the_web(path: str) -> bool:
    """尝试删除 Zone.Identifier（等同「解除锁定」）。成功返回 True。"""
    if platform.system() != "Windows" or not path:
        return False
    ads = path + ":Zone.Identifier"
    try:
        if os.path.isfile(path):
            os.remove(ads)
            return True
    except OSError:
        logger.debug("删除 Zone.Identifier 失败: %s", path, exc_info=True)
    return False


def frozen_executable_path() -> str:
    """打包后的 exe 路径；开发态返回 sys.executable。"""
    import sys

    return os.path.abspath(sys.executable)


def window_title_matches_app(title: str) -> bool:
    """判断窗口标题是否属于本应用（避免误匹配无关窗口）。"""
    if not title:
        return False
    t = title.strip()
    if not t:
        return False
    if t == APP_NAME or t == APP_NAME_EN:
        return True
    if t == MINI_WINDOW_TITLE:
        return True
    # 本应用对话框：APP_NAME · xxx / APP_NAME - xxx
    for prefix in (f"{APP_NAME} ·", f"{APP_NAME} -", f"{APP_NAME_EN} ·", f"{APP_NAME_EN} -"):
        if t.startswith(prefix):
            return True
    return False


def show_request_path() -> str:
    """二次启动唤醒请求文件路径。"""
    return os.path.join(user_config_dir(), SHOW_REQUEST_NAME)


def request_show_existing() -> bool:
    """次实例：写入 show 请求，通知主实例恢复到前台。"""
    try:
        path = show_request_path()
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # 写入时间戳，便于主实例去抖/排查
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        return True
    except OSError:
        logger.debug("写入 show 请求失败", exc_info=True)
        return False


def consume_show_request() -> bool:
    """主实例：若存在 show 请求则删除并返回 True。"""
    path = show_request_path()
    try:
        if not os.path.isfile(path):
            return False
        os.remove(path)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        logger.debug("消费 show 请求失败", exc_info=True)
        return False


def clear_stale_show_request() -> None:
    """启动时清理残留 show 请求，避免误唤醒。"""
    try:
        path = show_request_path()
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        logger.debug("清理残留 show 请求失败", exc_info=True)


def bring_existing_to_front():
    """已有实例时尝试置前（Windows）；含隐藏窗；失败静默。

    两轮枚举：先可见窗，再全部顶层窗（覆盖 Mini 工具窗 / 托盘 withdraw）。
    """
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        SW_RESTORE = 9
        SW_SHOW = 5
        visible = []
        hidden = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd, _lparam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value or ""
            if not window_title_matches_app(title):
                return True
            if user32.IsWindowVisible(hwnd):
                visible.append(hwnd)
            else:
                hidden.append(hwnd)
            return True

        user32.EnumWindows(_enum, 0)
        # 可见优先；托盘 withdraw 时走 hidden（主窗仍有 APP_NAME 标题）
        found = visible if visible else hidden
        if not found:
            return False
        hwnd = found[0]
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)
        # 突破跨进程前台限制
        fg = user32.GetForegroundWindow()
        cur_tid = kernel32.GetCurrentThreadId()
        fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        attached = False
        if fg_tid and fg_tid != cur_tid:
            attached = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(cur_tid, fg_tid, False)
        return True
    except (OSError, AttributeError, ValueError, TypeError):
        # Win32/ctypes 边界：异常类型平台相关
        logger.debug("置前已有实例失败", exc_info=True)
        return False


def acquire_single_instance():
    """
    单实例保护。成功返回 (True, handle)；已有实例返回 (False, None)；
    锁机制异常时返回 (True, None) 并继续启动。
    """
    global _instance_lock
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            kernel32.CreateMutexW.argtypes = [
                wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR
            ]
            kernel32.CreateMutexW.restype = wintypes.HANDLE
            kernel32.GetLastError.restype = wintypes.DWORD

            mutex = kernel32.CreateMutexW(None, False, "Local\\CountDownTool_SingleInstance")
            if not mutex:
                logger.warning("CreateMutexW 失败，跳过单实例检查")
                return True, None
            ERROR_ALREADY_EXISTS = 183
            if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
                kernel32.CloseHandle(mutex)
                return False, None
            _instance_lock = mutex
            atexit.register(lambda: kernel32.CloseHandle(mutex) if mutex else None)
            return True, mutex

        lock_path = os.path.join(user_config_dir(), "count_down_tool.lock")
        lock_fp = None
        use_fcntl = False
        try:
            import fcntl  # noqa: F401
            use_fcntl = True
        except ImportError:
            use_fcntl = False

        if use_fcntl:
            lock_fp = open(lock_path, "a+", encoding="utf-8")
            try:
                import fcntl
                fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # 写入 PID 便于排查
                try:
                    lock_fp.seek(0)
                    lock_fp.truncate()
                    lock_fp.write(str(os.getpid()))
                    lock_fp.flush()
                except OSError:
                    pass
            except (BlockingIOError, OSError):
                lock_fp.close()
                return False, None

            def _release_fcntl():
                try:
                    try:
                        import fcntl
                        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
                    except (OSError, AttributeError, ImportError):
                        pass
                    lock_fp.close()
                    try:
                        os.remove(lock_path)
                    except OSError:
                        pass
                except OSError:
                    logger.debug("释放锁文件失败", exc_info=True)

            _instance_lock = lock_fp
            atexit.register(_release_fcntl)
            return True, lock_fp

        # 弱锁：PID 检测，避免异常退出残留锁
        if not try_acquire_weak_lock(lock_path):
            return False, None

        def _release_weak():
            try:
                os.remove(lock_path)
            except OSError:
                pass

        _instance_lock = lock_path
        atexit.register(_release_weak)
        return True, lock_path
    except (OSError, AttributeError, ImportError, ValueError, TypeError):
        # 单实例锁失败不得阻断启动
        logger.exception("单实例锁异常，继续启动")
        return True, None


def set_window_rounded_corners(master, corner_radius):
    """设置窗口圆角（DWM，失败则 GDI 回退）。"""
    if platform.system() != "Windows":
        return
    import tkinter as tk

    try:
        import ctypes
        from ctypes import c_int, byref

        hwnd = int(master.frame(), 16)
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2

        dwm = ctypes.windll.dwmapi
        preference = c_int(DWMWCP_ROUND)
        result = dwm.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
            byref(preference), ctypes.sizeof(preference),
        )
        if result != 0:
            set_window_rounded_corners_fallback(master, corner_radius)
    except (OSError, AttributeError, ValueError, TypeError, tk.TclError):
        logger.warning("DWM 圆角设置失败，尝试回退方案", exc_info=True)
        set_window_rounded_corners_fallback(master, corner_radius)


def set_window_rounded_corners_fallback(master, corner_radius):
    """回退方案：GDI 圆角。"""
    if platform.system() != "Windows":
        return
    import tkinter as tk

    try:
        import ctypes
        from ctypes import wintypes

        hwnd = int(master.frame(), 16)
        radius = corner_radius
        width = master.winfo_width()
        height = master.winfo_height()

        create_round_rect_rgn = ctypes.windll.gdi32.CreateRoundRectRgn
        create_round_rect_rgn.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int
        ]
        create_round_rect_rgn.restype = wintypes.HRGN

        rgn = create_round_rect_rgn(0, 0, width, height, radius * 2, radius * 2)

        set_window_rgn = ctypes.windll.user32.SetWindowRgn
        set_window_rgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
        set_window_rgn.restype = ctypes.c_int
        set_window_rgn(hwnd, rgn, True)
    except (OSError, AttributeError, ValueError, TypeError, tk.TclError):
        logger.warning("GDI 圆角设置失败", exc_info=True)


def get_work_area(window=None):
    """返回当前显示器工作区 (x, y, width, height)，排除任务栏。

    Windows：优先窗口所在监视器，否则主监视器。
    其它平台返回 None，由调用方回退 Tk 屏幕尺寸。
    """
    if platform.system() != "Windows":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        import tkinter as tk

        user32 = ctypes.windll.user32
        hwnd = 0
        if window is not None:
            try:
                frame = window.wm_frame()
                hwnd = int(frame, 16) if frame else int(window.winfo_id())
            except (ValueError, TypeError, AttributeError, tk.TclError):
                hwnd = 0

        MONITOR_DEFAULTTONEAREST = 2
        MONITOR_DEFAULTTOPRIMARY = 1
        hmon = user32.MonitorFromWindow(
            hwnd, MONITOR_DEFAULTTONEAREST if hwnd else MONITOR_DEFAULTTOPRIMARY
        )
        if not hmon:
            return None
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            return None
        r = mi.rcWork
        return (
            int(r.left),
            int(r.top),
            int(r.right - r.left),
            int(r.bottom - r.top),
        )
    except (OSError, AttributeError, ValueError, TypeError):
        logger.debug("获取工作区失败", exc_info=True)
        return None


def _tk_hwnd(window):
    """解析 Tk 顶层窗口 HWND（优先 wm_frame）。"""
    import tkinter as tk

    try:
        frame = window.wm_frame()
        if frame:
            return int(frame, 16)
    except (ValueError, TypeError, AttributeError, tk.TclError):
        pass
    try:
        return int(window.winfo_id())
    except (ValueError, TypeError, AttributeError, tk.TclError):
        return 0


def set_taskbar_visible(master):
    """设置窗口在任务栏和 Alt+Tab 中可见。"""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = _tk_hwnd(master)
        if not hwnd:
            return
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080

        get_window_long = ctypes.windll.user32.GetWindowLongW
        set_window_long = ctypes.windll.user32.SetWindowLongW
        get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
        get_window_long.restype = ctypes.c_long
        set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        set_window_long.restype = ctypes.c_long

        style = get_window_long(hwnd, GWL_EXSTYLE)
        style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        set_window_long(hwnd, GWL_EXSTYLE, style)
        try:
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
            )
        except (OSError, AttributeError, ValueError, TypeError):
            logger.debug("SetWindowPos 刷新任务栏样式失败", exc_info=True)
    except (OSError, AttributeError, ValueError, TypeError):
        logger.warning("任务栏可见性设置失败", exc_info=True)


def force_window_to_front(window):
    """将 Tk 窗口强制置前并激活（托盘恢复场景）。

    Windows 会限制跨进程 SetForegroundWindow；先短暂 topmost + AttachThreadInput 再激活。
    非 Windows 仅 lift / focus_force。
    """
    if window is None:
        return
    import tkinter as tk

    try:
        window.lift()
        window.focus_force()
    except tk.TclError:
        pass
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = _tk_hwnd(window)
        if not hwnd:
            return

        try:
            window.update_idletasks()
        except tk.TclError:
            pass

        # 短暂置顶，突破 Z 序限制后再取消，避免常驻 topmost
        try:
            window.attributes("-topmost", True)
            window.attributes("-topmost", False)
            window.lift()
        except tk.TclError:
            pass

        SW_SHOW = 5
        SW_RESTORE = 9
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)

        fg = user32.GetForegroundWindow()
        cur_tid = kernel32.GetCurrentThreadId()
        fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        attached = False
        if fg_tid and fg_tid != cur_tid:
            attached = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetActiveWindow(hwnd)
            user32.SetFocus(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(cur_tid, fg_tid, False)
    except (OSError, AttributeError, ValueError, TypeError):
        logger.debug("强制窗口置前失败", exc_info=True)


def set_tool_window(window):
    """将窗口标为工具窗：不进任务栏 / Alt+Tab（桌面小组件用）。"""
    if platform.system() != "Windows":
        return
    import tkinter as tk

    try:
        import ctypes
        from ctypes import wintypes

        hwnd = int(window.frame(), 16)
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080

        get_window_long = ctypes.windll.user32.GetWindowLongW
        set_window_long = ctypes.windll.user32.SetWindowLongW
        get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
        get_window_long.restype = ctypes.c_long
        set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        set_window_long.restype = ctypes.c_long

        style = get_window_long(hwnd, GWL_EXSTYLE)
        style = (style & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
        set_window_long(hwnd, GWL_EXSTYLE, style)
        # 刷新扩展样式，确保 Alt+Tab 立即生效
        try:
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
            )
        except (OSError, AttributeError, ValueError, TypeError):
            logger.debug("SetWindowPos 刷新工具窗样式失败", exc_info=True)
    except (OSError, AttributeError, ValueError, TypeError, tk.TclError):
        logger.warning("工具窗样式设置失败", exc_info=True)


def start_native_window_drag(window):
    """Windows 原生拖动（ReleaseCapture + WM_NCLBUTTONDOWN）。"""
    if platform.system() != "Windows":
        return False
    import tkinter as tk

    try:
        import ctypes
        hwnd = int(window.frame(), 16)
        ctypes.windll.user32.ReleaseCapture()
        ctypes.windll.user32.PostMessageW(hwnd, 0xA1, 2, 0)
        return True
    except (OSError, AttributeError, ValueError, TypeError, tk.TclError):
        logger.debug("原生拖动失败", exc_info=True)
        return False


def set_transparent_color(window, color):
    """Windows 透明色键。"""
    if platform.system() != "Windows":
        return
    import tkinter as tk

    try:
        window.attributes("-transparentcolor", color)
    except tk.TclError:
        logger.debug("设置透明色失败", exc_info=True)
