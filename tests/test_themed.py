# -*- coding: utf-8 -*-
"""ui.design.themed 工厂层单元测试。"""

import os
import sys
import tkinter as tk
import unittest
from unittest import mock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.themes import resolve_theme
from ui.design.themed import (
    color_of,
    recolor_app,
    recolor_one,
    recolor_widget_tree,
    register_themed,
    resolve_colors,
    themed_button,
    themed_frame,
    themed_label,
)


class _FakeApp:
    COLORS = resolve_theme("slate_cyan")

    def _font(self, _kind, size, bold=False):
        return ("Segoe UI", size, "bold") if bold else ("Segoe UI", size)


class TestThemedFactory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        if cls.root is not None:
            try:
                cls.root.destroy()
            except tk.TclError:
                pass

    def setUp(self):
        if self.root is None:
            self.skipTest("Tk 不可用")
        self.app = _FakeApp()

    def test_resolve_colors_prefers_explicit(self):
        custom = {"card": "#111111"}
        self.assertIs(resolve_colors(self.app, custom), custom)
        self.assertEqual(resolve_colors(self.app, None)["accent"], self.app.COLORS["accent"])

    def test_color_of_fallback(self):
        colors = {"text_dim": "#abc"}
        self.assertEqual(color_of(colors, "text_muted", "text_dim"), "#abc")
        self.assertEqual(color_of({}, "missing", default="#zzz"), "#zzz")

    def test_register_themed_merge(self):
        w = tk.Frame(self.root)
        register_themed(w, bg="card")
        self.assertEqual(w._theme_roles, {"bg": "card"})
        register_themed(w, fg="text")
        self.assertEqual(w._theme_roles, {"bg": "card", "fg": "text"})

    def test_themed_frame_roles(self):
        fr = themed_frame(self.root, self.app, role="bg")
        self.assertEqual(fr["bg"], self.app.COLORS["bg"])
        self.assertEqual(fr._theme_roles["bg"], "bg")

        card = themed_frame(self.root, self.app, role="card")
        self.assertEqual(card["bg"], self.app.COLORS["card"])
        self.assertEqual(card._theme_roles["bg"], "card")

        # 未知 role 回退 card
        bad = themed_frame(self.root, self.app, role="nope")
        self.assertEqual(bad._theme_roles["bg"], "card")

    def test_themed_label_fg_role_and_alias(self):
        a = themed_label(
            self.root, self.app, "hi", fg_role="text_muted", bg_role="card"
        )
        self.assertEqual(a["fg"], self.app.COLORS["text_muted"])
        self.assertEqual(a._theme_roles, {"bg": "card", "fg": "text_muted"})

        b = themed_label(self.root, self.app, "hi", role="accent", bg_role="card")
        self.assertEqual(b["fg"], self.app.COLORS["accent"])
        self.assertEqual(b._theme_roles["fg"], "accent")

    def test_themed_button_delegates_make_pill(self):
        with mock.patch("ui.widgets.make_pill") as mp:
            mp.return_value = tk.Label(self.root, text="ok")
            themed_button(self.root, self.app, "确定", primary=True, command=lambda: None)
            mp.assert_called_once()
            kwargs = mp.call_args.kwargs
            self.assertTrue(kwargs.get("primary"))
            self.assertIs(kwargs.get("app"), self.app)


class TestRecolor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        if cls.root is not None:
            try:
                cls.root.destroy()
            except tk.TclError:
                pass

    def setUp(self):
        if self.root is None:
            self.skipTest("Tk 不可用")
        self.colors_a = resolve_theme("slate_cyan")
        self.colors_b = resolve_theme("emerald")

    def test_recolor_one_calls_configure_for_roles(self):
        w = tk.Frame(self.root, bg=self.colors_a["card"])
        register_themed(w, bg="card")
        with mock.patch.object(w, "configure", wraps=w.configure) as cfg:
            ok = recolor_one(w, self.colors_b)
        self.assertTrue(ok)
        cfg.assert_called()
        self.assertEqual(w["bg"], self.colors_b["card"])

    def test_recolor_widget_tree_counts_nested(self):
        outer = tk.Frame(self.root, bg=self.colors_a["bg"])
        register_themed(outer, bg="bg")
        inner = tk.Label(
            outer,
            text="x",
            bg=self.colors_a["card"],
            fg=self.colors_a["text"],
        )
        register_themed(inner, bg="card", fg="text")
        n = recolor_widget_tree(outer, self.colors_b)
        self.assertGreaterEqual(n, 2)
        self.assertEqual(outer["bg"], self.colors_b["bg"])
        self.assertEqual(inner["bg"], self.colors_b["card"])
        self.assertEqual(inner["fg"], self.colors_b["text"])

    def test_recolor_rounded_frame(self):
        from ui.widgets import RoundedFrame

        card = RoundedFrame(
            self.root,
            bg_color=self.colors_a["card"],
            border_color=self.colors_a["card_border"],
        )
        register_themed(card, bg="card", border="card_border")
        with mock.patch.object(card, "configure_colors", wraps=card.configure_colors) as cc:
            ok = recolor_one(card, self.colors_b)
        self.assertTrue(ok)
        cc.assert_called()
        self.assertEqual(card._bg_color, self.colors_b["card"])
        self.assertEqual(card._border_color, self.colors_b["card_border"])

    def test_recolor_app_progress_and_tree(self):
        colors_a = self.colors_a
        colors_b = self.colors_b

        class _App:
            def __init__(self, master, colors):
                self.COLORS = colors
                self.master = master
                self.progress_canvas = tk.Canvas(
                    master, bg=colors["card"], width=10, height=4
                )
                register_themed(self.progress_canvas, bg="card")
                self._refresh_called = False

            def _refresh_progress_bar(self):
                self._refresh_called = True

        app = _App(self.root, colors_a)
        fr = tk.Frame(self.root, bg=colors_a["bg"])
        register_themed(fr, bg="bg")
        n = recolor_app(app, colors_b)
        self.assertGreaterEqual(n, 1)
        self.assertTrue(app._refresh_called)
        # 进度条底板随倒计时主卡，用 card（非 glass）
        self.assertEqual(app.progress_canvas["bg"], colors_b["card"])


if __name__ == "__main__":
    unittest.main()
