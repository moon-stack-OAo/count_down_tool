# -*- coding: utf-8 -*-
"""托盘/菜单栏文案纯函数（无 UI 依赖，供 services 与 ui re-export）。"""

from typing import List, Tuple

# 托盘/菜单栏「快捷开始」预设：(文案, 时, 分, 秒)
TRAY_QUICK_START_PRESETS: Tuple[Tuple[str, int, int, int], ...] = (
    ("5 分钟", 0, 5, 0),
    ("10 分钟", 0, 10, 0),
    ("30 分钟", 0, 30, 0),
    ("1 小时", 1, 0, 0),
    ("8 小时", 8, 0, 0),
)

TRAY_QUICK_START_MENU_LABEL = "快捷开始"


def tray_window_menu_label(is_mini: bool) -> str:
    """托盘「显示/展开」文案。"""
    return "展开主窗口" if is_mini else "显示主窗口"


def tray_mini_menu_label(is_mini: bool) -> str:
    """托盘 Mini 切换文案。"""
    return "退出 Mini 模式" if is_mini else "Mini 模式"


def tray_quick_start_labels() -> List[str]:
    """快捷开始菜单项文案列表（测试/展示用）。"""
    return [label for label, _h, _m, _s in TRAY_QUICK_START_PRESETS]
