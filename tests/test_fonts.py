# -*- coding: utf-8 -*-
"""core.fonts 单元测试。"""

import os
import sys
import unittest
from unittest import mock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.fonts import (
    BUNDLED_MONO_FAMILY,
    bundled_font_paths,
    pick_family,
    reset_font_registration_state_for_tests,
    resolve_font_families,
    resolve_fonts,
)


class TestPickFamily(unittest.TestCase):
    def test_prefers_first_available(self):
        available = {"consolas": "Consolas", "courier new": "Courier New"}
        self.assertEqual(
            pick_family(("Cascadia Mono", "Consolas", "Courier New"), available),
            "Consolas",
        )

    def test_case_insensitive(self):
        available = {"segoe ui": "Segoe UI"}
        self.assertEqual(pick_family(("SEGOE UI", "Arial"), available), "Segoe UI")

    def test_fallback_last_when_none(self):
        available = {"arial": "Arial"}
        self.assertEqual(
            pick_family(("Missing One", "Missing Two"), available),
            "Missing Two",
        )

    def test_no_lookup_uses_first(self):
        self.assertEqual(pick_family(("Menlo", "Monaco"), None), "Menlo")


class TestBundledFonts(unittest.TestCase):
    def test_bundled_files_present(self):
        paths = bundled_font_paths()
        self.assertGreaterEqual(len(paths), 2)
        for p in paths:
            self.assertTrue(os.path.isfile(p), p)
            self.assertTrue(p.lower().endswith(".ttf"))

    def test_mono_prefers_bundled_when_listed(self):
        families = [BUNDLED_MONO_FAMILY, "Consolas", "Segoe UI"]
        ui, mono = resolve_font_families(
            "Windows",
            available_families=families,
            register_bundled=False,
        )
        self.assertEqual(mono, BUNDLED_MONO_FAMILY)
        self.assertEqual(ui, "Segoe UI")

    def test_mono_falls_back_without_bundled_name(self):
        families = ["Consolas", "Segoe UI"]
        ui, mono = resolve_font_families(
            "Windows",
            available_families=families,
            register_bundled=False,
        )
        self.assertEqual(mono, "Consolas")


class TestResolveFonts(unittest.TestCase):
    def setUp(self):
        reset_font_registration_state_for_tests()

    def test_windows_picks_cascadia_when_present(self):
        families = ["Cascadia Mono", "Consolas", "Segoe UI", "Arial"]
        ui, mono = resolve_font_families(
            "Windows",
            available_families=families,
            register_bundled=False,
        )
        # 无内嵌名时 Cascadia 优先于 Consolas
        self.assertEqual(ui, "Segoe UI")
        self.assertEqual(mono, "Cascadia Mono")

    def test_darwin_menlo_and_helvetica(self):
        families = ["Menlo", "Helvetica Neue", "Arial"]
        ui, mono = resolve_font_families(
            "Darwin",
            available_families=families,
            register_bundled=False,
        )
        self.assertEqual(ui, "Helvetica Neue")
        self.assertEqual(mono, "Menlo")

    def test_linux_avoids_missing_ubuntu(self):
        families = ["DejaVu Sans", "DejaVu Sans Mono", "Noto Sans"]
        ui, mono = resolve_font_families(
            "Linux",
            available_families=families,
            register_bundled=False,
        )
        self.assertEqual(ui, "Noto Sans")
        self.assertEqual(mono, "DejaVu Sans Mono")

    def test_roles_share_families(self):
        fonts = resolve_fonts(
            "Windows",
            available_families=["Consolas", "Segoe UI"],
            register_bundled=False,
        )
        self.assertEqual(fonts["label"][0], fonts["title"][0])
        self.assertEqual(fonts["time"][0], fonts["countdown"][0])
        self.assertEqual(fonts["mini_time"][0], fonts["countdown"][0])
        self.assertEqual(fonts["title"][2], "bold")
        self.assertEqual(len(fonts["label"]), 2)

    def test_darwin_mini_sizes_larger(self):
        win = resolve_fonts(
            "Windows",
            available_families=["Consolas", "Segoe UI"],
            register_bundled=False,
        )
        mac = resolve_fonts(
            "Darwin",
            available_families=["Menlo", "Helvetica Neue"],
            register_bundled=False,
        )
        self.assertGreater(mac["mini_countdown"][1], win["mini_countdown"][1])

    def test_register_then_prefer_bundled(self):
        """注册后即使 available 不含内嵌名，也应注入并优先。"""
        reset_font_registration_state_for_tests()
        with mock.patch("core.fonts.bundled_font_paths", return_value=["/fake/JetBrainsMono-Regular.ttf"]):
            with mock.patch("core.fonts._register_windows", return_value=1):
                with mock.patch("core.fonts._register_darwin", return_value=1):
                    with mock.patch("core.fonts._register_linux", return_value=1):
                        # 模拟注册成功写入 _registered_paths
                        import core.fonts as fonts_mod

                        fonts_mod._registered_paths = ["/fake/JetBrainsMono-Regular.ttf"]
                        fonts_mod._register_attempted = True
                        ui, mono = resolve_font_families(
                            "Windows",
                            available_families=["Segoe UI", "Consolas"],
                            register_bundled=False,
                        )
        # register_bundled=False 时不会注入；测 inject 路径需 register 流程
        # 直接测 inject 逻辑：
        reset_font_registration_state_for_tests()
        with mock.patch("core.fonts.list_available_families", return_value=["Segoe UI", "Consolas"]):
            with mock.patch("core.fonts.bundled_font_paths", return_value=["/fake/a.ttf"]):
                with mock.patch("core.fonts.register_bundled_fonts", return_value=1) as reg:
                    import core.fonts as fonts_mod

                    def _fake_reg(root=None, force=False):
                        fonts_mod._registered_paths = ["/fake/a.ttf"]
                        fonts_mod._register_attempted = True
                        return 1

                    reg.side_effect = _fake_reg
                    ui, mono = resolve_font_families("Windows", root=None, register_bundled=True)
        self.assertEqual(mono, BUNDLED_MONO_FAMILY)
        self.assertEqual(ui, "Segoe UI")


if __name__ == "__main__":
    unittest.main()
