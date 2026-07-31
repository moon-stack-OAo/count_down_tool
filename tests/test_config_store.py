# -*- coding: utf-8 -*-
"""app.config_store 单元测试（非法 theme / 缺键默认）。"""

import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app import config_store
from core.themes import DEFAULT_THEME_ID, resolve_theme


def _make_app(config_file: str, **overrides):
    """构造最小 app 替身，避免拉起 GUI。"""
    base = {
        "MINI_WIDTH": 400,
        "MINI_HEIGHT": 80,
        "MINI_MIN_WIDTH": 200,
        "MINI_MIN_HEIGHT": 40,
        "MINI_MAX_WIDTH": 1200,
        "MINI_MAX_HEIGHT": 400,
        "MINI_WIDTH_MAC": 450,
        "MINI_HEIGHT_MAC": 90,
        "MINI_MIN_WIDTH_MAC": 200,
        "MINI_MIN_HEIGHT_MAC": 40,
        "MINI_MAX_WIDTH_MAC": 1200,
        "MINI_MAX_HEIGHT_MAC": 400,
        "_config_file": config_file,
        "_loaded_keys": set(),
        "_mini_pos": None,
        "_mini_size": None,
        "_transparent_mode": False,
        "_last_mode": "full",
        "_startup_mode": "remember",
        "_theme_id": DEFAULT_THEME_ID,
        "_theme_custom": None,
        "COLORS": resolve_theme(DEFAULT_THEME_ID),
        "_mini_text": {},
        "_sound_muted": False,
        "_sound_id": "soft",
        "_sound_path": "",
        "_sound_history": [],
        "_check_update_on_start": True,
        "_last_update_check": "",
        "_ignored_update_version": "",
        "_autostart": False,
        "_is_mini": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestConfigStoreLoad(unittest.TestCase):
    def test_invalid_theme_id_falls_back_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"theme_id": "no_such_theme_xyz"}, f)
            app = _make_app(path)
            with mock.patch(
                "app.config_store.is_autostart_enabled", return_value=False
            ):
                config_store.load_config(app)
            self.assertEqual(app._theme_id, DEFAULT_THEME_ID)
            self.assertEqual(
                app.COLORS["accent"],
                resolve_theme(DEFAULT_THEME_ID)["accent"],
            )

    def test_missing_keys_keep_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({}, f)
            app = _make_app(path)
            with mock.patch(
                "app.config_store.is_autostart_enabled", return_value=False
            ):
                config_store.load_config(app)
            self.assertEqual(app._theme_id, DEFAULT_THEME_ID)
            self.assertIsNone(app._theme_custom)
            self.assertEqual(app._mini_text, {})
            self.assertFalse(app._sound_muted)
            self.assertEqual(app._sound_id, "soft")
            self.assertEqual(app._sound_path, "")
            self.assertEqual(app._sound_history, [])
            self.assertTrue(app._check_update_on_start)
            self.assertEqual(app._last_update_check, "")
            self.assertEqual(app._ignored_update_version, "")
            self.assertEqual(app._startup_mode, "remember")
            self.assertFalse(app._autostart)

    def test_startup_mode_load_and_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"startup_mode": "mini", "last_mode": "full"}, f)
            app = _make_app(path)
            with mock.patch(
                "app.config_store.is_autostart_enabled", return_value=False
            ):
                config_store.load_config(app)
            self.assertEqual(app._startup_mode, "mini")
            app._startup_mode = "full"
            app._is_mini = False
            with mock.patch(
                "app.config_store.is_autostart_enabled", return_value=False
            ):
                config_store.save_config(app)
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved.get("startup_mode"), "full")

    def test_invalid_startup_mode_falls_back_remember(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"startup_mode": "nope"}, f)
            app = _make_app(path)
            with mock.patch(
                "app.config_store.is_autostart_enabled", return_value=False
            ):
                config_store.load_config(app)
            self.assertEqual(app._startup_mode, "remember")

    def test_save_clears_mini_position_when_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"mini_position": [10, 20], "mini_size": [300, 60]}, f)
            app = _make_app(path, _mini_pos=None, _mini_size=None)
            with mock.patch(
                "app.config_store.is_autostart_enabled", return_value=False
            ):
                config_store.save_config(app)
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self.assertNotIn("mini_position", saved)
            self.assertNotIn("mini_size", saved)

    def test_valid_theme_id_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "theme_id": "emerald",
                        "theme_custom": {"accent": "#112233"},
                    },
                    f,
                )
            app = _make_app(path)
            with mock.patch(
                "app.config_store.is_autostart_enabled", return_value=False
            ):
                config_store.load_config(app)
            self.assertEqual(app._theme_id, "emerald")
            self.assertEqual(app._theme_custom, {"accent": "#112233"})
            self.assertEqual(app.COLORS["accent"], "#112233")

    def test_invalid_theme_custom_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "theme_id": "slate_cyan",
                        "theme_custom": {"accent": "not-a-color", "x": "nope"},
                    },
                    f,
                )
            app = _make_app(path)
            with mock.patch(
                "app.config_store.is_autostart_enabled", return_value=False
            ):
                config_store.load_config(app)
            # 非法 custom 全部无效 → sanitize 返回 None
            self.assertIsNone(app._theme_custom)
            self.assertEqual(
                app.COLORS["accent"],
                resolve_theme("slate_cyan")["accent"],
            )


if __name__ == "__main__":
    unittest.main()
