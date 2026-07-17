# -*- coding: utf-8 -*-
"""context_menus 纯函数单元测试（无 GUI）。"""

import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ui.context_menus import tray_mini_menu_label, tray_window_menu_label


class TestTrayMenuLabels(unittest.TestCase):
    def test_window_label_full(self):
        self.assertEqual(tray_window_menu_label(False), "显示主窗口")

    def test_window_label_mini(self):
        self.assertEqual(tray_window_menu_label(True), "展开主窗口")

    def test_mini_label_full(self):
        self.assertEqual(tray_mini_menu_label(False), "Mini 模式")

    def test_mini_label_mini(self):
        self.assertEqual(tray_mini_menu_label(True), "退出 Mini 模式")

    def test_labels_follow_is_mini_flag(self):
        """模拟启动先进 Mini：_is_mini=True 时文案必须是退出/展开。"""
        is_mini = True
        self.assertEqual(tray_mini_menu_label(is_mini), "退出 Mini 模式")
        self.assertEqual(tray_window_menu_label(is_mini), "展开主窗口")
        is_mini = False
        self.assertEqual(tray_mini_menu_label(is_mini), "Mini 模式")
        self.assertEqual(tray_window_menu_label(is_mini), "显示主窗口")


class TestRefreshTrayMenuImport(unittest.TestCase):
    def test_refresh_tray_menu_noop_without_icon(self):
        from services.tray import refresh_tray_menu

        class _App:
            tray_icon = None

        refresh_tray_menu(_App())  # 不应抛异常


if __name__ == "__main__":
    unittest.main()
