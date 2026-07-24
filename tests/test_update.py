# -*- coding: utf-8 -*-
"""core.update 单元测试。"""

import os
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.update import (
    expected_asset_name,
    extract_windows_exe,
    is_newer_version,
    parse_version,
    platform_asset_suffix,
    select_asset,
    write_windows_replace_script,
    check_for_update,
    ReleaseInfo,
)


class TestVersion(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_version("v1.3.23"), (1, 3, 23))
        self.assertEqual(parse_version("1.2"), (1, 2, 0))

    def test_newer(self):
        self.assertTrue(is_newer_version("1.3.24", "1.3.23"))
        self.assertFalse(is_newer_version("1.3.23", "1.3.23"))
        self.assertFalse(is_newer_version("1.3.20", "1.3.23"))


class TestAssetSelect(unittest.TestCase):
    def test_suffixes(self):
        self.assertEqual(platform_asset_suffix("Windows", "AMD64"), "win64.zip")
        self.assertEqual(platform_asset_suffix("Darwin", "arm64"), "mac-arm64.zip")
        self.assertEqual(platform_asset_suffix("Darwin", "x86_64"), "mac-x86_64.zip")

    def test_expected_name(self):
        self.assertEqual(
            expected_asset_name("1.3.24", "Windows"),
            "count_down_tool-1.3.24-win64.zip",
        )

    def test_select_exact(self):
        assets = [
            {"name": "count_down_tool-1.3.24-win64.zip", "browser_download_url": "http://a"},
            {"name": "count_down_tool-1.3.24-mac-arm64.zip", "browser_download_url": "http://b"},
        ]
        a = select_asset(assets, "1.3.24", "Windows", "AMD64")
        self.assertEqual(a["name"], "count_down_tool-1.3.24-win64.zip")
        b = select_asset(assets, "1.3.24", "Darwin", "arm64")
        self.assertEqual(b["name"], "count_down_tool-1.3.24-mac-arm64.zip")


class TestExtractAndScript(unittest.TestCase):
    def test_extract_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            zpath = os.path.join(tmp, "a.zip")
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("count_down_tool.exe", b"MZ-fake")
            out = extract_windows_exe(zpath, os.path.join(tmp, "out"))
            self.assertTrue(os.path.isfile(out))
            with open(out, "rb") as f:
                self.assertEqual(f.read(), b"MZ-fake")

    def test_write_bat(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, "u.bat")
            write_windows_replace_script(
                script,
                target_exe=r"C:\App\count_down_tool.exe",
                source_exe=r"C:\Temp\new.exe",
                pid=12345,
                zip_path=r"C:\Temp\a.zip",
            )
            with open(script, "r", encoding="gbk") as f:
                body = f.read()
            self.assertIn("12345", body)
            self.assertIn("count_down_tool.exe", body)
            self.assertIn("copy /Y", body)


class TestCheckForUpdate(unittest.TestCase):
    def test_has_update_and_asset(self):
        release = ReleaseInfo(
            version="9.9.9",
            tag_name="v9.9.9",
            body="notes",
            html_url="https://example.com",
            assets=(
                {
                    "name": "count_down_tool-9.9.9-win64.zip",
                    "browser_download_url": "https://example.com/w.zip",
                    "size": 10,
                },
            ),
        )
        with mock.patch("core.update.fetch_latest_release", return_value=release):
            r = check_for_update("1.0.0", system="Windows", machine="AMD64")
        self.assertTrue(r.has_update)
        self.assertEqual(r.latest_version, "9.9.9")
        self.assertTrue(r.asset_url.endswith("w.zip"))

    def test_ignored_version(self):
        release = ReleaseInfo(
            version="9.9.9",
            tag_name="v9.9.9",
            body="",
            html_url="https://example.com",
            assets=(),
        )
        with mock.patch("core.update.fetch_latest_release", return_value=release):
            r = check_for_update(
                "1.0.0",
                system="Windows",
                ignored_version="9.9.9",
            )
        self.assertFalse(r.has_update)

    def test_network_error(self):
        with mock.patch(
            "core.update.fetch_latest_release",
            side_effect=RuntimeError("offline"),
        ):
            r = check_for_update("1.0.0")
        self.assertIsNotNone(r.error)
        self.assertFalse(r.has_update)


if __name__ == "__main__":
    unittest.main()
