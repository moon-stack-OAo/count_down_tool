# -*- coding: utf-8 -*-
"""托盘/菜单栏文案纯函数（无 UI 依赖，供 services 与 ui re-export）。"""


def tray_window_menu_label(is_mini: bool) -> str:
    """托盘「显示/展开」文案。"""
    return "展开主窗口" if is_mini else "显示主窗口"


def tray_mini_menu_label(is_mini: bool) -> str:
    """托盘 Mini 切换文案。"""
    return "退出 Mini 模式" if is_mini else "Mini 模式"
