# -*- coding: utf-8 -*-
"""Mark of the Web / 启动健康相关纯函数测试。"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from services.windows_native import (
    path_has_mark_of_the_web,
    try_remove_mark_of_the_web,
)


class TestMarkOfTheWeb(unittest.TestCase):
    def test_non_windows_false(self):
        with mock.patch("services.windows_native.platform.system", return_value="Linux"):
            self.assertFalse(path_has_mark_of_the_web(r"C:\a.exe"))

    def test_missing_file_false(self):
        with mock.patch("services.windows_native.platform.system", return_value="Windows"):
            self.assertFalse(path_has_mark_of_the_web(os.path.join(tempfile.gettempdir(), "no_such_cdt.exe")))

    def test_detect_zone3(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "app.exe")
            with open(path, "wb") as f:
                f.write(b"MZ")
            ads = path + ":Zone.Identifier"
            # 非 NTFS 环境可能无法写 ADS，此时跳过
            try:
                with open(ads, "w", encoding="utf-8") as f:
                    f.write("[ZoneTransfer]\nZoneId=3\n")
            except OSError:
                self.skipTest("当前文件系统不支持 ADS")
            with mock.patch("services.windows_native.platform.system", return_value="Windows"):
                self.assertTrue(path_has_mark_of_the_web(path))
                removed = try_remove_mark_of_the_web(path)
                if not removed:
                    # 可写 ADS 但策略/权限禁止删除时跳过，避免误报
                    self.skipTest("当前环境不允许删除 Zone.Identifier ADS")
                self.assertFalse(path_has_mark_of_the_web(path))

    def test_zone_local_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "app2.exe")
            with open(path, "wb") as f:
                f.write(b"MZ")
            ads = path + ":Zone.Identifier"
            try:
                with open(ads, "w", encoding="utf-8") as f:
                    f.write("[ZoneTransfer]\nZoneId=1\n")
            except OSError:
                self.skipTest("当前文件系统不支持 ADS")
            with mock.patch("services.windows_native.platform.system", return_value="Windows"):
                self.assertFalse(path_has_mark_of_the_web(path))


if __name__ == "__main__":
    unittest.main()
