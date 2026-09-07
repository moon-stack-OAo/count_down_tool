# -*- coding: utf-8 -*-
"""自定义主题色编辑：纯逻辑与轻量 mock。"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.themes import THEMES, resolve_theme, sanitize_theme_custom
from ui.settings import theme_custom_editor as editor


class TestThemeCustomEditorLogic(unittest.TestCase):
    def _app(self, *, theme_id="slate_cyan", custom=None):
        app = mock.MagicMock()
        app._theme_id = theme_id
        app._theme_custom = sanitize_theme_custom(custom)
        app.COLORS = resolve_theme(theme_id, app._theme_custom)
        return app

    def test_editable_keys_are_known_colors(self):
        base = THEMES["slate_cyan"]["colors"]
        for key, label in editor.EDITABLE_THEME_COLOR_KEYS:
            self.assertIn(key, base)
            self.assertTrue(label)

    def test_set_custom_color_preview(self):
        app = self._app()
        with mock.patch("app.theme.refresh_theme_colors") as m_ref:
            ok = editor.set_custom_color(app, "accent", "#112233", preview=True)
        self.assertTrue(ok)
        self.assertEqual(app._theme_custom["accent"], "#112233")
        m_ref.assert_called_once_with(app, save=False)

    def test_set_custom_color_rejects_invalid(self):
        app = self._app()
        with mock.patch("app.theme.refresh_theme_colors") as m_ref:
            ok = editor.set_custom_color(app, "accent", "red", preview=True)
        self.assertFalse(ok)
        self.assertIsNone(app._theme_custom)
        m_ref.assert_not_called()

    def test_set_custom_color_rejects_unknown_key(self):
        app = self._app()
        with mock.patch("app.theme.refresh_theme_colors") as m_ref:
            ok = editor.set_custom_color(app, "not_a_key", "#112233", preview=True)
        self.assertFalse(ok)
        m_ref.assert_not_called()

    def test_clear_custom_color(self):
        app = self._app(custom={"accent": "#112233", "bg": "#010203"})
        with mock.patch("app.theme.refresh_theme_colors"):
            editor.clear_custom_color(app, "accent", preview=True)
        self.assertEqual(app._theme_custom, {"bg": "#010203"})

    def test_clear_all_custom_colors(self):
        app = self._app(custom={"accent": "#112233"})
        with mock.patch("app.theme.refresh_theme_colors") as m_ref:
            editor.clear_all_custom_colors(app, preview=True, save=True)
        self.assertEqual(app._theme_custom, {})
        m_ref.assert_called_once_with(app, save=True)

    def test_effective_and_preset(self):
        app = self._app(custom={"accent": "#AABBCC"})
        self.assertEqual(editor.effective_color_for(app, "accent"), "#AABBCC")
        self.assertEqual(
            editor.preset_color_for(app, "accent"),
            THEMES["slate_cyan"]["colors"]["accent"],
        )

    def test_save_theme_custom(self):
        app = self._app(custom={"accent": "#112233"})
        with mock.patch("app.theme.refresh_theme_colors") as m_ref:
            editor.save_theme_custom(app)
        m_ref.assert_called_once_with(app, save=True)


class TestRefreshThemeColors(unittest.TestCase):
    def test_refresh_updates_colors_without_closing_settings(self):
        from app import theme as theme_mod

        app = mock.MagicMock()
        app._theme_id = "slate_cyan"
        app._theme_custom = {"accent": "#112233"}
        app.COLORS = {"bg": "#000"}
        app.master = mock.MagicMock()
        app.master.winfo_exists.return_value = True
        app.master.winfo_children.return_value = [mock.MagicMock()]
        app.countdown_label = mock.MagicMock()
        app.countdown_label.winfo_exists.return_value = True
        app._settings_window = mock.MagicMock()
        app._settings_window.winfo_exists.return_value = True

        with mock.patch(
            "ui.design.themed.recolor_app", return_value=3
        ) as m_recolor, mock.patch.object(
            theme_mod, "recolor_settings_window", return_value=2
        ) as m_settings, mock.patch.object(
            theme_mod, "resolve_theme", wraps=resolve_theme
        ):
            n = theme_mod.refresh_theme_colors(app, save=True)

        self.assertEqual(n, 3)
        self.assertEqual(app.COLORS["accent"], "#112233")
        m_recolor.assert_called_once()
        m_settings.assert_called_once()
        app._save_config.assert_called_once()
        app._setup_styles.assert_called()


if __name__ == "__main__":
    unittest.main()
