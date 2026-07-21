# -*- coding: utf-8 -*-
"""themes / autostart / merge 扩展 单元测试。"""

import os
import sys
import unittest
from unittest import mock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.countdown_core import merge_config
from core.themes import (
    DEFAULT_THEME_ID,
    THEMES,
    is_valid_theme_id,
    list_themes,
    resolve_theme,
)
from services import autostart


class TestThemes(unittest.TestCase):
    def test_default_theme_id(self):
        self.assertEqual(DEFAULT_THEME_ID, "slate_cyan")
        self.assertIn(DEFAULT_THEME_ID, THEMES)

    def test_list_themes_at_least_five(self):
        items = list_themes()
        self.assertGreaterEqual(len(items), 5)
        ids = [i[0] for i in items]
        for expected in (
            "slate_cyan",
            "midnight_purple",
            "warm_amber",
            "emerald",
            "light",
        ):
            self.assertIn(expected, ids)
        for tid, name in items:
            self.assertIsInstance(tid, str)
            self.assertIsInstance(name, str)
            self.assertTrue(name)

    def test_is_valid_theme_id(self):
        self.assertTrue(is_valid_theme_id("slate_cyan"))
        self.assertFalse(is_valid_theme_id("no_such_theme"))
        self.assertFalse(is_valid_theme_id(None))
        self.assertFalse(is_valid_theme_id(123))

    def test_resolve_theme_default(self):
        colors = resolve_theme(None)
        self.assertEqual(colors["accent"], THEMES[DEFAULT_THEME_ID]["colors"]["accent"])
        self.assertIn("accent_soft", colors)
        self.assertIn("chip", colors)
        self.assertIn("chip_hover", colors)
        self.assertIn("text_muted", colors)
        self.assertIn("warning", colors)

    def test_resolve_theme_unknown_fallback(self):
        colors = resolve_theme("unknown_xyz")
        self.assertEqual(colors, resolve_theme(DEFAULT_THEME_ID))

    def test_resolve_theme_known(self):
        colors = resolve_theme("emerald")
        self.assertEqual(colors["accent"], THEMES["emerald"]["colors"]["accent"])

    def test_resolve_theme_custom_override(self):
        colors = resolve_theme("slate_cyan", custom={"accent": "#112233"})
        self.assertEqual(colors["accent"], "#112233")
        # 未覆盖键保持原值
        self.assertEqual(colors["bg"], THEMES["slate_cyan"]["colors"]["bg"])

    def test_resolve_theme_custom_none(self):
        colors = resolve_theme("warm_amber", custom=None)
        self.assertEqual(colors["accent"], THEMES["warm_amber"]["colors"]["accent"])

    def test_light_title_bar_not_pure_white(self):
        colors = resolve_theme("light")
        self.assertNotEqual(colors["title_bar"].upper(), "#FFFFFF")
        self.assertNotEqual(colors["title_bar"].upper(), "#FFF")


class TestMergeThemeAutostart(unittest.TestCase):
    def test_merge_theme_id_and_autostart(self):
        cfg = {"mini_position": [1, 2], "extra": 9}
        merged = merge_config(
            cfg,
            theme_id="emerald",
            autostart=True,
            theme_custom={"accent": "#00FF00"},
        )
        self.assertEqual(merged["theme_id"], "emerald")
        self.assertTrue(merged["autostart"])
        self.assertEqual(merged["theme_custom"]["accent"], "#00FF00")
        self.assertEqual(merged["extra"], 9)
        self.assertEqual(merged["mini_position"], [1, 2])

    def test_merge_none_keeps_fields(self):
        cfg = {"theme_id": "light", "autostart": False, "theme_custom": {"a": "1"}}
        again = merge_config(
            cfg,
            theme_id=None,
            autostart=None,
            theme_custom=None,
        )
        self.assertEqual(again["theme_id"], "light")
        self.assertFalse(again["autostart"])
        self.assertEqual(again["theme_custom"], {"a": "1"})

    def test_merge_empty_theme_custom_writes(self):
        cfg = {"theme_custom": {"accent": "#111"}}
        merged = merge_config(cfg, theme_custom={})
        self.assertEqual(merged["theme_custom"], {})


class TestAutostartResolve(unittest.TestCase):
    def test_resolve_frozen(self):
        exe, args, cwd = autostart.resolve_launch_command(
            frozen=True,
            executable=r"C:\Apps\count_down_tool.exe",
        )
        self.assertEqual(exe, r"C:\Apps\count_down_tool.exe")
        self.assertEqual(args, [])
        self.assertEqual(cwd, r"C:\Apps")

    def test_resolve_dev(self):
        script = os.path.join(_ROOT, "count_down_tool.py")
        with mock.patch.object(autostart, "_prefer_pythonw", side_effect=lambda e: e):
            exe, args, cwd = autostart.resolve_launch_command(
                frozen=False,
                executable=sys.executable,
                script_path=script,
                cwd=_ROOT,
            )
        self.assertEqual(exe, sys.executable)
        self.assertEqual(args, [os.path.abspath(script)])
        self.assertEqual(cwd, _ROOT)

    def test_startup_shortcut_path_ends_with_lnk(self):
        path = autostart.startup_shortcut_path()
        self.assertTrue(path.endswith("Count Down Tool.lnk"))
        self.assertIn("Startup", path.replace("/", os.sep))


if __name__ == "__main__":
    unittest.main()
