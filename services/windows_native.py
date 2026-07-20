# -*- coding: utf-8 -*-
"""Windows / 跨平台原生窗口与单实例相关能力。"""

import atexit
import logging
import os
import platform

from countdown_core import APP_NAME, APP_NAME_EN, try_acquire_weak_lock, user_config_dir

logger = logging.getLogger("count_down_tool")

# 单实例锁句柄（进程级）
_instance_lock = None


def bring_existing_to_front():
    """已有实例时尝试置前（Windows）；失败静默。"""
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value or ""
            if APP_NAME in title or APP_NAME_EN in title:
                found.append(hwnd)
            return True

        user32.EnumWindows(_enum, 0)
        if not found:
            return False
        hwnd = found[0]
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
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
                except Exception:
                    pass
            except (BlockingIOError, OSError):
                lock_fp.close()
                return False, None

            def _release_fcntl():
                try:
                    try:
                        import fcntl
                        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
                    except Exception:
                        pass
                    lock_fp.close()
                    try:
                        os.remove(lock_path)
                    except OSError:
                        pass
                except Exception:
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
    except Exception:
        logger.exception("单实例锁异常，继续启动")
        return True, None


def set_window_rounded_corners(master, corner_radius):
    """设置窗口圆角（DWM，失败则 GDI 回退）。"""
    if platform.system() != "Windows":
        return
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
    except Exception:
        logger.warning("DWM 圆角设置失败，尝试回退方案", exc_info=True)
        set_window_rounded_corners_fallback(master, corner_radius)


def set_window_rounded_corners_fallback(master, corner_radius):
    """回退方案：GDI 圆角。"""
    if platform.system() != "Windows":
        return
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
    except Exception:
        logger.warning("GDI 圆角设置失败", exc_info=True)


def set_taskbar_visible(master):
    """设置窗口在任务栏和 Alt+Tab 中可见。"""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = int(master.frame(), 16)
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
        except Exception:
            pass
    except Exception:
        logger.warning("任务栏可见性设置失败", exc_info=True)


def set_tool_window(window):
    """将窗口标为工具窗：不进任务栏 / Alt+Tab（桌面小组件用）。"""
    if platform.system() != "Windows":
        return
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
        except Exception:
            pass
    except Exception:
        logger.warning("工具窗样式设置失败", exc_info=True)


def start_native_window_drag(window):
    """Windows 原生拖动（ReleaseCapture + WM_NCLBUTTONDOWN）。"""
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        hwnd = int(window.frame(), 16)
        ctypes.windll.user32.ReleaseCapture()
        ctypes.windll.user32.PostMessageW(hwnd, 0xA1, 2, 0)
        return True
    except Exception:
        logger.debug("原生拖动失败", exc_info=True)
        return False


def set_transparent_color(window, color):
    """Windows 透明色键。"""
    if platform.system() != "Windows":
        return
    try:
        window.attributes("-transparentcolor", color)
    except Exception:
        logger.debug("设置透明色失败", exc_info=True)
