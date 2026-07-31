# -*- coding: utf-8 -*-
"""运行日志配置测试。"""

from __future__ import annotations

import logging
import os
import tempfile
import unittest

from core.app_logging import reset_logging_for_tests, setup_app_logging
from core.countdown_core import user_log_path
from ui.app_dialogs import _read_log_tail


class TestAppLogging(unittest.TestCase):
    def setUp(self):
        reset_logging_for_tests()

    def tearDown(self):
        reset_logging_for_tests()

    def test_user_log_path_ends_with_app_log(self):
        p = user_log_path().replace("\\", "/")
        self.assertTrue(p.endswith("count_down_tool/app.log"))

    def test_setup_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "app.log")
            try:
                out = setup_app_logging(
                    level=logging.INFO, log_path=path, also_console=False
                )
                self.assertEqual(out, path)
                self.assertTrue(os.path.isfile(path))
                logging.getLogger("count_down_tool").info("hello-test")
                for h in logging.getLogger().handlers:
                    h.flush()
                with open(path, "r", encoding="utf-8") as f:
                    body = f.read()
                self.assertIn("hello-test", body)
                self.assertIn("日志已启用", body)
            finally:
                reset_logging_for_tests()

    def test_setup_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "app.log")
            try:
                a = setup_app_logging(
                    level=logging.INFO, log_path=path, also_console=False
                )
                b = setup_app_logging(
                    level=logging.DEBUG, log_path=path, also_console=False
                )
                self.assertEqual(a, b)
                # 不应重复加 handler
                self.assertEqual(len(logging.getLogger().handlers), 1)
            finally:
                reset_logging_for_tests()


class TestReadLogTail(unittest.TestCase):
    def test_missing_file(self):
        body, note = _read_log_tail(os.path.join(tempfile.gettempdir(), "no_such_app.log"))
        self.assertEqual(body, "")
        self.assertIn("不存在", note)

    def test_full_and_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "app.log")
            with open(path, "w", encoding="utf-8") as f:
                f.write("line1\nline2\n")
            body, note = _read_log_tail(path)
            self.assertIn("line1", body)
            self.assertIn("line2", body)
            self.assertIn("字节", note)

            with open(path, "wb") as f:
                f.write(b"x" * 5000 + b"\nTAIL\n")
            body, note = _read_log_tail(path, max_bytes=100)
            self.assertIn("TAIL", body)
            self.assertIn("末尾", note)


if __name__ == "__main__":
    unittest.main()
