# -*- coding: utf-8 -*-
"""跨平台 UI / 等宽字体：内嵌字体注册 + 系统探测回退。"""

from __future__ import annotations

import logging
import os
import platform
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger("count_down_tool.fonts")

FontTuple = Tuple

# 内嵌等宽（倒计时数字）；OFL，见 assets/fonts/OFL.txt
BUNDLED_MONO_FAMILY = "JetBrains Mono"
_BUNDLED_MONO_FILES = (
    "JetBrainsMono-Regular.ttf",
    "JetBrainsMono-Bold.ttf",
)
_BUNDLED_FONTS_DIR = os.path.join("assets", "fonts")

# 注册结果缓存：避免重复 AddFontResource
_registered_paths: List[str] = []
_register_attempted = False

# UI 正文（标题、标签、按钮）：优先系统 UI，再中文/西文回退
_UI_CANDIDATES = {
    "Windows": (
        "Segoe UI",
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "Arial",
        "Tahoma",
    ),
    "Darwin": (
        "Helvetica Neue",
        "PingFang SC",
        "Helvetica",
        "Arial",
    ),
    "Linux": (
        "Ubuntu",
        "Noto Sans CJK SC",
        "Noto Sans SC",
        "Noto Sans",
        "DejaVu Sans",
        "Liberation Sans",
        "FreeSans",
        "Arial",
    ),
}

# 数字/倒计时等宽：内嵌优先，再系统 mono
_MONO_CANDIDATES = {
    "Windows": (
        BUNDLED_MONO_FAMILY,
        "Cascadia Mono",
        "Cascadia Code",
        "Consolas",
        "Courier New",
        "Lucida Console",
    ),
    "Darwin": (
        BUNDLED_MONO_FAMILY,
        "Menlo",
        "SF Mono",
        "Monaco",
        "Courier New",
    ),
    "Linux": (
        BUNDLED_MONO_FAMILY,
        "DejaVu Sans Mono",
        "Noto Sans Mono",
        "Ubuntu Mono",
        "Liberation Mono",
        "FreeMono",
        "Courier New",
        "Monospace",
    ),
}

# 各角色字号（平台仅 Mini 数字区不同，适配 macOS 点阵/Retina）
_SIZES = {
    "Windows": {
        "title": 20,
        "time": 32,
        "countdown": 42,
        "label": 11,
        "button": 12,
        "mini_time": 10,
        "mini_countdown": 16,
    },
    "Darwin": {
        "title": 20,
        "time": 32,
        "countdown": 42,
        "label": 11,
        "button": 12,
        "mini_time": 18,
        "mini_countdown": 28,
    },
    "Linux": {
        "title": 20,
        "time": 32,
        "countdown": 42,
        "label": 11,
        "button": 12,
        "mini_time": 10,
        "mini_countdown": 16,
    },
}


def _system_key(system: Optional[str] = None) -> str:
    s = system or platform.system()
    if s in _UI_CANDIDATES:
        return s
    return "Linux"


def _family_lookup(families: Iterable[str]) -> Dict[str, str]:
    """小写名 -> Tk 实际 family 名。"""
    out: Dict[str, str] = {}
    for name in families:
        if not name:
            continue
        key = name.strip().lower()
        if key and key not in out:
            out[key] = name.strip()
    return out


def bundled_font_paths() -> List[str]:
    """返回存在的内嵌字体文件绝对路径。"""
    from core.countdown_core import resource_path

    paths: List[str] = []
    for name in _BUNDLED_MONO_FILES:
        p = resource_path(os.path.join(_BUNDLED_FONTS_DIR, name))
        if os.path.isfile(p):
            paths.append(os.path.abspath(p))
        else:
            logger.debug("内嵌字体缺失: %s", p)
    return paths


def _register_windows(paths: Sequence[str]) -> int:
    import ctypes

    FR_PRIVATE = 0x10
    gdi32 = ctypes.windll.gdi32  # type: ignore[attr-defined]
    ok = 0
    for path in paths:
        try:
            if gdi32.AddFontResourceExW(path, FR_PRIVATE, 0):
                ok += 1
                _registered_paths.append(path)
            else:
                logger.warning("AddFontResourceExW 失败: %s", path)
        except Exception as exc:
            logger.warning("注册字体失败 %s: %s", path, exc)
    return ok


def _register_darwin(paths: Sequence[str]) -> int:
    """CTFontManagerRegisterFontsForURL，进程内私有作用域。"""
    import ctypes
    import ctypes.util

    cf_path = ctypes.util.find_library("CoreFoundation")
    ct_path = ctypes.util.find_library("CoreText")
    if not cf_path or not ct_path:
        logger.warning("CoreFoundation/CoreText 不可用，跳过内嵌字体注册")
        return 0

    cf = ctypes.cdll.LoadLibrary(cf_path)
    ct = ctypes.cdll.LoadLibrary(ct_path)

    # CFURLRef CFURLCreateFromFileSystemRepresentation(CFAllocatorRef, const UInt8*, CFIndex, Boolean)
    cf.CFURLCreateFromFileSystemRepresentation.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_long,
        ctypes.c_bool,
    ]
    cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
    cf.CFRelease.argtypes = [ctypes.c_void_p]

    # bool CTFontManagerRegisterFontsForURL(CFURLRef, CTFontManagerScope, CFErrorRef*)
    # scope process = 1
    ct.CTFontManagerRegisterFontsForURL.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool

    kCTFontManagerScopeProcess = 1
    ok = 0
    for path in paths:
        try:
            b = path.encode("utf-8")
            url = cf.CFURLCreateFromFileSystemRepresentation(None, b, len(b), False)
            if not url:
                logger.warning("无法创建字体 URL: %s", path)
                continue
            try:
                if ct.CTFontManagerRegisterFontsForURL(url, kCTFontManagerScopeProcess, None):
                    ok += 1
                    _registered_paths.append(path)
                else:
                    logger.warning("CTFontManager 注册失败: %s", path)
            finally:
                cf.CFRelease(url)
        except Exception as exc:
            logger.warning("注册字体失败 %s: %s", path, exc)
    return ok


def _register_linux(paths: Sequence[str]) -> int:
    """
    Linux：优先 fontconfig 用户目录软链/复制，再尝试 Tk -file。
    返回成功登记的路径数（尽力而为）。
    """
    ok = 0
    fonts_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "fonts", "count_down_tool")
    try:
        os.makedirs(fonts_dir, exist_ok=True)
        for path in paths:
            dest = os.path.join(fonts_dir, os.path.basename(path))
            try:
                if not os.path.isfile(dest) or os.path.getsize(dest) != os.path.getsize(path):
                    import shutil

                    shutil.copy2(path, dest)
                ok += 1
                _registered_paths.append(dest)
            except Exception as exc:
                logger.warning("复制字体失败 %s: %s", path, exc)
        # 刷新 fontconfig（有则调用）
        try:
            import subprocess

            subprocess.run(
                ["fc-cache", "-f", fonts_dir],
                check=False,
                capture_output=True,
                timeout=15,
            )
        except Exception:
            pass
    except Exception as exc:
        logger.warning("Linux 字体目录准备失败: %s", exc)
    return ok


def register_bundled_fonts(root=None, force: bool = False) -> int:
    """
    将 assets/fonts 内嵌 TTF 注册到当前进程/系统（私有优先）。
    返回成功注册文件数；无文件或失败返回 0。
    """
    global _register_attempted
    if _register_attempted and not force:
        return len(_registered_paths)
    _register_attempted = True

    paths = bundled_font_paths()
    if not paths:
        return 0

    system = platform.system()
    if system == "Windows":
        n = _register_windows(paths)
    elif system == "Darwin":
        n = _register_darwin(paths)
    else:
        n = _register_linux(paths)

    # Tk 侧再尝试用 -file 创建命名字体，提升可见性（失败忽略）
    if root is not None:
        _try_tk_file_fonts(root, paths)

    logger.debug("内嵌字体注册完成 count=%s paths=%s", n, paths)
    return n


def _try_tk_file_fonts(root, paths: Sequence[str]) -> None:
    """部分 Tk 构建支持 font create -file。"""
    for i, path in enumerate(paths):
        name = f"_cdt_bundled_mono_{i}"
        try:
            root.tk.call("font", "create", name, "-file", path)
        except Exception:
            try:
                # 已存在则跳过
                root.tk.call("font", "configure", name, "-file", path)
            except Exception:
                pass


def list_available_families(root=None) -> Optional[List[str]]:
    """
    列出当前 Tk 可用字体族。
    root 为空时尝试临时创建隐藏 Tk；失败（无显示等）返回 None。
    """
    import tkinter as tk
    import tkinter.font as tkfont

    created = False
    win = root
    try:
        if win is None:
            win = tk.Tk()
            win.withdraw()
            created = True
        return list(tkfont.families(win))
    except Exception as exc:
        logger.debug("无法枚举系统字体: %s", exc)
        return None
    finally:
        if created and win is not None:
            try:
                win.destroy()
            except Exception:
                pass


def pick_family(
    candidates: Sequence[str],
    available: Optional[Dict[str, str]] = None,
) -> str:
    """
    从候选链中选第一个可用字体；无探测表时用链首。
    全部不可用时仍返回链末，避免抛错（由 Tk 再回退）。
    """
    if not candidates:
        return "TkDefaultFont"
    if available is None:
        return candidates[0]
    for name in candidates:
        hit = available.get(name.lower())
        if hit:
            return hit
    return candidates[-1]


def resolve_font_families(
    system: Optional[str] = None,
    available_families: Optional[Sequence[str]] = None,
    root=None,
    register_bundled: bool = True,
) -> Tuple[str, str]:
    """
    解析 (ui_family, mono_family)。
    默认先注册内嵌字体，再探测系统族。
    """
    if register_bundled:
        register_bundled_fonts(root=root)

    key = _system_key(system)
    ui_cands = _UI_CANDIDATES[key]
    mono_cands = _MONO_CANDIDATES[key]

    lookup: Optional[Dict[str, str]] = None
    if available_families is not None:
        lookup = _family_lookup(available_families)
    else:
        families = list_available_families(root)
        if families is not None:
            lookup = _family_lookup(families)
            # 注册后仍未出现在 Tk 列表时，若文件在则强制优先内嵌族名
            if (
                BUNDLED_MONO_FAMILY.lower() not in lookup
                and bundled_font_paths()
                and _registered_paths
            ):
                lookup[BUNDLED_MONO_FAMILY.lower()] = BUNDLED_MONO_FAMILY

    ui = pick_family(ui_cands, lookup)
    mono = pick_family(mono_cands, lookup)
    if lookup is not None:
        logger.debug("字体选择 system=%s ui=%s mono=%s", key, ui, mono)
    return ui, mono


def resolve_fonts(
    system: Optional[str] = None,
    available_families: Optional[Sequence[str]] = None,
    root=None,
    register_bundled: bool = True,
) -> Dict[str, FontTuple]:
    """
    返回与 CountdownApp.FONTS 相同结构的字体字典。
    等宽角色统一 mono，界面角色统一 ui，避免混用导致样式漂移。
    """
    key = _system_key(system)
    sizes = _SIZES[key]
    ui, mono = resolve_font_families(
        system=key,
        available_families=available_families,
        root=root,
        register_bundled=register_bundled,
    )
    return {
        "title": (ui, sizes["title"], "bold"),
        "time": (mono, sizes["time"], "bold"),
        "countdown": (mono, sizes["countdown"], "bold"),
        "label": (ui, sizes["label"]),
        "button": (ui, sizes["button"], "bold"),
        "mini_time": (mono, sizes["mini_time"], "bold"),
        "mini_countdown": (mono, sizes["mini_countdown"], "bold"),
    }


def reset_font_registration_state_for_tests() -> None:
    """测试用：重置注册缓存。"""
    global _register_attempted, _registered_paths
    _register_attempted = False
    _registered_paths = []
