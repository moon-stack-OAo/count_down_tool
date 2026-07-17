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


if __name__ == "__main__":
    unittest.main()
