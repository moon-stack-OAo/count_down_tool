#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PyInstaller 统一配置与构建入口（M3）。

维护约定
--------
- **hiddenimports 只在此文件维护**（``HIDDENIMPORTS_COMMON`` + 平台附加项）。
- 本地脚本与 CI 均调用本模块的 ``build`` 子命令，避免 bat/sh/yml 各写一份参数。
- Windows 固定 **onedir**；macOS 为 **windowed** app bundle（与历史产物一致）。

用法
----
::

    python scripts/pyinstaller_common.py build --os windows
    python scripts/pyinstaller_common.py build --os macos
    python scripts/pyinstaller_common.py build --os macos --target-arch arm64
    python scripts/pyinstaller_common.py list-hiddenimports [--os windows|macos]
    python scripts/pyinstaller_common.py print-flags [--os windows|macos]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRY = ROOT / "count_down_tool.py"
APP_NAME = "count_down_tool"
OSX_BUNDLE_ID = "com.moon.count-down-tool"

# ---------------------------------------------------------------------------
# hiddenimports：应用包 + 动态/延迟导入 + 第三方后端
# 新增 services.* / ui.* / core.* 子模块时，请同步追加到本列表。
# ---------------------------------------------------------------------------

HIDDENIMPORTS_COMMON: list[str] = [
    # core
    "core",
    "core.countdown_core",
    "core.app_logging",
    "core.themes",
    "core.fonts",
    "core.update",
    "core.update_impl",
    "core.update_impl.models",
    "core.update_impl.fetch",
    "core.update_impl.extract",
    "core.update_impl.download",
    "core.update_impl.checksum",
    "core.update_impl.windows_apply",
    "core.update_impl.util",
    "core.update_impl.version",
    # app
    "app",
    "app.countdown",
    "app.config_store",
    "app.window_chrome",
    "app.theme",
    "app.mode",
    # ui
    "ui",
    "ui.widgets",
    "ui.mini_window",
    "ui.time_picker",
    "ui.chrome_titlebar",
    "ui.full_window",
    "ui.context_menus",
    "ui.mini_text_picker",
    "ui.settings_window",
    "ui.update_dialog",
    "ui.app_dialogs",
    "ui.window_chrome_dialog",
    "ui.design",
    "ui.design.tokens",
    "ui.settings",
    "ui.settings.system_tab",
    "ui.settings.sound_tab",
    "ui.settings.shell",
    "ui.settings.layout",
    "ui.settings.appearance",
    "ui.settings.about_tab",
    # services
    "services",
    "services.autostart",
    "services.tray",
    "services.updater",
    "services.windows_native",
    "services.sound",
    "services.sound.resolve",
    "services.sound.probe",
    "services.sound.playback_state",
    "services.sound.history",
    "services.sound.finish",
    "services.sound.constants",
    "services.sound.backends",
    "services.ncm",
    "services.ncm.aes_ecb",
    "services.ncm.decrypt",
    "services.ncm.cache",
    # third-party
    "pystray",
    "PIL",
    "PIL._tkinter_finder",
]

# 平台相关：托盘后端 / mac 菜单栏（Windows 不打包 mac_menu 亦可，保留显式列表更清晰）
HIDDENIMPORTS_WINDOWS: list[str] = [
    "pystray._win32",
]

HIDDENIMPORTS_MACOS: list[str] = [
    "services.mac_menu",
    "pystray._darwin",
]


def normalize_os(name: str | None) -> str:
    """返回 ``windows`` / ``macos``。"""
    if not name or name in ("auto", "host"):
        if sys.platform == "darwin":
            return "macos"
        if sys.platform.startswith("win"):
            return "windows"
        # Linux CI 极少用到本工具打包；默认按 windows 风格 hiddenimports
        return "windows"
    key = name.strip().lower()
    if key in ("win", "windows", "win32", "win64"):
        return "windows"
    if key in ("mac", "macos", "darwin", "osx"):
        return "macos"
    raise SystemExit(f"未知 --os: {name!r}（期望 windows / macos / auto）")


def get_hiddenimports(os_name: str | None = None) -> list[str]:
    """合并通用与平台 hiddenimports，去重且保持顺序。"""
    plat = normalize_os(os_name)
    items = list(HIDDENIMPORTS_COMMON)
    if plat == "windows":
        items.extend(HIDDENIMPORTS_WINDOWS)
    else:
        items.extend(HIDDENIMPORTS_MACOS)
    seen: set[str] = set()
    out: list[str] = []
    for m in items:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def hiddenimport_flags(os_name: str | None = None) -> list[str]:
    return [f"--hidden-import={m}" for m in get_hiddenimports(os_name)]


def _data_sep(os_name: str) -> str:
    # PyInstaller: Windows 用分号，POSIX 用冒号
    return ";" if os_name == "windows" else ":"


def collect_add_data(os_name: str) -> list[str]:
    """资源 --add-data 参数（图标 / 音效 / 字体）。"""
    sep = _data_sep(os_name)
    args: list[str] = []
    ico = ROOT / "assets" / "count_down_tool.ico"
    if ico.is_file():
        args.append(f"--add-data={ico}{sep}assets")
    sounds = ROOT / "assets" / "sounds"
    if sounds.is_dir():
        args.append(f"--add-data={sounds}{sep}assets/sounds")
    fonts = ROOT / "assets" / "fonts"
    if fonts.is_dir():
        args.append(f"--add-data={fonts}{sep}assets/fonts")
    return args


def collect_icon_args(os_name: str) -> list[str]:
    if os_name == "windows":
        ico = ROOT / "assets" / "count_down_tool.ico"
        if ico.is_file():
            return [f"--icon={ico}"]
        return []
    for rel in (
        ROOT / "assets" / "count_down_tool.icns",
        ROOT / "count_down_tool.icns",
    ):
        if rel.is_file():
            return [f"--icon={rel}"]
    return []


def build_pyinstaller_argv(
    os_name: str | None = None,
    *,
    target_arch: str | None = None,
    distpath: Path | str | None = None,
    workpath: Path | str | None = None,
    specpath: Path | str | None = None,
    noconfirm: bool = True,
    clean: bool = True,
) -> list[str]:
    """组装 ``python -m PyInstaller ...`` 的完整参数列表（不含 python -m）。"""
    plat = normalize_os(os_name)
    dist = Path(distpath) if distpath else ROOT / "dist"
    work = Path(workpath) if workpath else ROOT / "build"
    spec = Path(specpath) if specpath else ROOT

    argv: list[str] = ["PyInstaller"]
    if noconfirm:
        argv.append("--noconfirm")
    if clean:
        argv.append("--clean")

    if plat == "windows":
        # onedir：DLL 与 exe 同目录，避免 onefile %TEMP%\\_MEI* 加载失败
        argv.extend(["--onedir", "--windowed"])
    else:
        argv.append("--windowed")
        if target_arch:
            argv.append(f"--target-arch={target_arch}")
        argv.append(f"--osx-bundle-identifier={OSX_BUNDLE_ID}")

    argv.extend([f"--name={APP_NAME}"])
    argv.extend(collect_icon_args(plat))
    argv.extend(collect_add_data(plat))
    argv.extend(hiddenimport_flags(plat))
    argv.extend(
        [
            f"--distpath={dist}",
            f"--workpath={work}",
            f"--specpath={spec}",
            str(ENTRY),
        ]
    )
    return argv


def run_build(
    os_name: str | None = None,
    *,
    target_arch: str | None = None,
    distpath: Path | str | None = None,
    workpath: Path | str | None = None,
    specpath: Path | str | None = None,
    noconfirm: bool = True,
    clean: bool = True,
) -> int:
    if not ENTRY.is_file():
        print(f"[ERROR] 入口不存在: {ENTRY}", file=sys.stderr)
        return 1
    argv = build_pyinstaller_argv(
        os_name,
        target_arch=target_arch,
        distpath=distpath,
        workpath=workpath,
        specpath=specpath,
        noconfirm=noconfirm,
        clean=clean,
    )
    # 使用当前解释器 -m PyInstaller，保证 venv 一致
    cmd = [sys.executable, "-m", *argv]
    print("Running:", " ".join(cmd))
    env = os.environ.copy()
    # 确保项目根在 path 上（分析阶段 import 项目包）
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), env["PYTHONPATH"]] if env.get("PYTHONPATH") else [str(ROOT)]
    )
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env)
    return int(proc.returncode)


def _cmd_list_hiddenimports(args: argparse.Namespace) -> int:
    for m in get_hiddenimports(args.os):
        print(m)
    return 0


def _cmd_print_flags(args: argparse.Namespace) -> int:
    # 便于 shell 调试；空格分隔一整行
    print(" ".join(hiddenimport_flags(args.os)))
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    return run_build(
        args.os,
        target_arch=args.target_arch,
        distpath=args.distpath,
        workpath=args.workpath,
        specpath=args.specpath,
        noconfirm=not args.confirm,
        clean=not args.no_clean,
    )


def _cmd_print_argv(args: argparse.Namespace) -> int:
    argv = build_pyinstaller_argv(
        args.os,
        target_arch=args.target_arch,
        distpath=args.distpath,
        workpath=args.workpath,
        specpath=args.specpath,
        noconfirm=not args.confirm,
        clean=not args.no_clean,
    )
    # 每行一个，便于检查
    for a in argv:
        print(a)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="count_down_tool PyInstaller 统一配置 / 构建",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list-hiddenimports", help="打印 hiddenimports（每行一个）")
    p_list.add_argument("--os", default="auto", help="windows | macos | auto")
    p_list.set_defaults(func=_cmd_list_hiddenimports)

    p_flags = sub.add_parser("print-flags", help="打印 --hidden-import=... 标志（单行）")
    p_flags.add_argument("--os", default="auto")
    p_flags.set_defaults(func=_cmd_print_flags)

    def _add_build_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--os", default="auto", help="windows | macos | auto")
        p.add_argument(
            "--target-arch",
            default=None,
            help="仅 macOS：传给 PyInstaller --target-arch（如 arm64 / x86_64）",
        )
        p.add_argument("--distpath", default=None)
        p.add_argument("--workpath", default=None)
        p.add_argument("--specpath", default=None)
        p.add_argument(
            "--confirm",
            action="store_true",
            help="不传 --noconfirm（默认 noconfirm）",
        )
        p.add_argument(
            "--no-clean",
            action="store_true",
            help="不传 --clean（默认 clean）",
        )

    p_build = sub.add_parser("build", help="调用 PyInstaller 打包")
    _add_build_args(p_build)
    p_build.set_defaults(func=_cmd_build)

    p_argv = sub.add_parser("print-argv", help="打印完整 PyInstaller 参数（不执行）")
    _add_build_args(p_argv)
    p_argv.set_defaults(func=_cmd_print_argv)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
