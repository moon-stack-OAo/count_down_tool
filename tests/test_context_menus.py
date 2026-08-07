# -*- coding: utf-8 -*-
"""context_menus 纯函数单元测试（无 GUI）。"""

import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from services.menu_labels import (
    TRAY_QUICK_START_MENU_LABEL,
    TRAY_QUICK_START_PRESETS,
    tray_mini_menu_label,
    tray_quick_start_labels,
    tray_window_menu_label,
)
from ui.context_menus import (  # re-export 兼容
    tray_mini_menu_label as _ui_tray_mini_menu_label,
)
from ui.context_menus import (
    tray_window_menu_label as _ui_tray_window_menu_label,
)


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

    def test_ui_context_menus_reexports(self):
        """ui.context_menus 继续 re-export，对外 API 不变。"""
        self.assertIs(tray_window_menu_label, _ui_tray_window_menu_label)
        self.assertIs(tray_mini_menu_label, _ui_tray_mini_menu_label)


class TestTrayQuickStartPresets(unittest.TestCase):
    def test_menu_label(self):
        self.assertEqual(TRAY_QUICK_START_MENU_LABEL, "快捷开始")

    def test_presets_labels_and_durations(self):
        labels = tray_quick_start_labels()
        self.assertEqual(
            labels,
            ["5 分钟", "10 分钟", "30 分钟", "1 小时", "8 小时"],
        )
        # (文案, 时, 分, 秒)
        expected = (
            ("5 分钟", 0, 5, 0),
            ("10 分钟", 0, 10, 0),
            ("30 分钟", 0, 30, 0),
            ("1 小时", 1, 0, 0),
            ("8 小时", 8, 0, 0),
        )
        self.assertEqual(TRAY_QUICK_START_PRESETS, expected)

    def test_each_preset_positive_duration(self):
        for label, h, m, s in TRAY_QUICK_START_PRESETS:
            total = h * 3600 + m * 60 + s
            self.assertGreater(total, 0, msg=label)


class TestRefreshTrayMenuImport(unittest.TestCase):
    def test_refresh_tray_menu_noop_without_icon(self):
        from services.tray import refresh_tray_menu

        class _App:
            tray_icon = None
            _status_menu_active = False

        refresh_tray_menu(_App())  # 不应抛异常


class TestHasTray(unittest.TestCase):
    def test_status_menu_counts_as_tray(self):
        from app.mode import has_tray

        class _App:
            tray_icon = None
            _status_menu_active = True

        self.assertTrue(has_tray(_App()))

    def test_no_status_no_icon(self):
        from app.mode import has_tray

        class _App:
            tray_icon = None
            _status_menu_active = False

        self.assertFalse(has_tray(_App()))


if __name__ == "__main__":
    unittest.main()
