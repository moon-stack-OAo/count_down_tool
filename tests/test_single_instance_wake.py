# -*- coding: utf-8 -*-
"""单实例二次启动唤醒：标题匹配与 show 请求协议。"""

import os
import sys
import tempfile
import unittest
from unittest import mock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.countdown_core import APP_NAME, APP_NAME_EN
from services.windows_native import (
    MINI_WINDOW_TITLE,
    SHOW_POLL_INTERVAL_MS,
    SHOW_REQUEST_NAME,
    clear_stale_show_request,
    consume_show_request,
    request_show_existing,
    show_request_path,
    window_title_matches_app,
)


class TestWindowTitleMatchesApp(unittest.TestCase):
    def test_exact_app_names(self):
        self.assertTrue(window_title_matches_app(APP_NAME))
        self.assertTrue(window_title_matches_app(APP_NAME_EN))
        self.assertTrue(window_title_matches_app(f"  {APP_NAME}  "))

    def test_mini_title(self):
        self.assertTrue(window_title_matches_app(MINI_WINDOW_TITLE))
        self.assertEqual(MINI_WINDOW_TITLE, f"{APP_NAME} - Mini")

    def test_dialog_prefixes(self):
        self.assertTrue(window_title_matches_app(f"{APP_NAME} · 设置"))
        self.assertTrue(window_title_matches_app(f"{APP_NAME} - 提示"))
        self.assertTrue(window_title_matches_app(f"{APP_NAME_EN} · About"))

    def test_reject_unrelated(self):
        self.assertFalse(window_title_matches_app(""))
        self.assertFalse(window_title_matches_app("   "))
        self.assertFalse(window_title_matches_app(None if False else "记事本"))
        # 仅包含 APP_NAME 子串、非本应用前缀
        self.assertFalse(window_title_matches_app(f"我的{APP_NAME}收藏"))
        self.assertFalse(window_title_matches_app(f"foo {APP_NAME}"))


class TestShowRequestProtocol(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._cfg_patch = mock.patch(
            "services.windows_native.user_config_dir",
            return_value=self._tmp,
        )
        self._cfg_patch.start()

    def tearDown(self):
        self._cfg_patch.stop()
        path = os.path.join(self._tmp, SHOW_REQUEST_NAME)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass
        try:
            os.rmdir(self._tmp)
        except OSError:
            pass

    def test_path_under_config(self):
        self.assertEqual(
            show_request_path(),
            os.path.join(self._tmp, SHOW_REQUEST_NAME),
        )

    def test_request_then_consume(self):
        self.assertFalse(consume_show_request())
        self.assertTrue(request_show_existing())
        self.assertTrue(os.path.isfile(show_request_path()))
        self.assertTrue(consume_show_request())
        self.assertFalse(os.path.isfile(show_request_path()))
        self.assertFalse(consume_show_request())

    def test_clear_stale(self):
        self.assertTrue(request_show_existing())
        clear_stale_show_request()
        self.assertFalse(os.path.isfile(show_request_path()))
        # 无文件时不抛
        clear_stale_show_request()

    def test_request_writes_content(self):
        self.assertTrue(request_show_existing())
        with open(show_request_path(), "r", encoding="utf-8") as f:
            body = f.read().strip()
        self.assertTrue(body)
        float(body)  # 时间戳


class TestShowPollInterval(unittest.TestCase):
    def test_show_poll_interval_in_range(self):
        # 二次启动唤起延迟上限：1–2s，默认 1.5s
        self.assertIsInstance(SHOW_POLL_INTERVAL_MS, int)
        self.assertGreaterEqual(SHOW_POLL_INTERVAL_MS, 1000)
        self.assertLessEqual(SHOW_POLL_INTERVAL_MS, 2000)


if __name__ == "__main__":
    unittest.main()
