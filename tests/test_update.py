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
    fetch_latest_release,
    parse_release_body_from_atom,
    parse_release_body_from_html,
    _format_http_error,
    _synthetic_assets,
    ReleaseInfo,
)
import urllib.error


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
            # 满足 extract 的 MZ + 最小体积校验
            payload = b"MZ" + b"\0" * 1200
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("count_down_tool.exe", payload)
            out = extract_windows_exe(zpath, os.path.join(tmp, "out"))
            self.assertTrue(os.path.isfile(out))
            with open(out, "rb") as f:
                self.assertEqual(f.read(), payload)

    def test_write_replace_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, "apply_update.ps1")
            write_windows_replace_script(
                script,
                target_exe=r"C:\App\count_down_tool.exe",
                source_exe=r"C:\Temp\new.exe",
                pid=12345,
                zip_path=r"C:\Temp\a.zip",
            )
            with open(script, "r", encoding="utf-8-sig") as f:
                body = f.read()
            self.assertIn("12345", body)
            self.assertIn("count_down_tool.exe", body)
            self.assertIn("Copy-Item", body)
            self.assertIn("Get-Process", body)
            self.assertIn("Start-Process", body)
            self.assertNotIn("tasklist", body)
            self.assertNotIn("find ", body.lower())


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

    def test_rate_limit_message(self):
        err = urllib.error.HTTPError(
            url="https://api.github.com/x",
            code=403,
            msg="rate limit exceeded",
            hdrs=None,
            fp=None,
        )
        text = _format_http_error(err)
        self.assertIn("过于频繁", text)

    def test_synthetic_assets(self):
        assets = _synthetic_assets("1.3.26")
        names = {a["name"] for a in assets}
        self.assertIn("count_down_tool-1.3.26-win64.zip", names)
        self.assertTrue(
            assets[0]["browser_download_url"].startswith(
                "https://github.com/moon-stack-OAo/count_down_tool/releases/download/"
            )
        )

    def test_fetch_via_redirect_no_api(self):
        class _Resp:
            def geturl(self):
                return "https://github.com/moon-stack-OAo/count_down_tool/releases/tag/v1.3.26"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b""

        with mock.patch("core.update.urllib.request.urlopen", return_value=_Resp()):
            with mock.patch(
                "core.update.fetch_release_body", return_value="## 更新内容\n- 修复"
            ) as body_fn:
                with mock.patch("core.update._http_get_json") as api:
                    info = fetch_latest_release()
        api.assert_not_called()
        body_fn.assert_called_once()
        self.assertEqual(info.version, "1.3.26")
        self.assertIn("修复", info.body)
        self.assertTrue(any(a["name"].endswith("win64.zip") for a in info.assets))

    def test_parse_release_body_from_atom(self):
        atom = """<?xml version="1.0" encoding="UTF-8"?>
        <feed>
          <entry>
            <id>tag:github.com,2008:Repository/1/v1.3.27</id>
            <link rel="alternate" type="text/html"
              href="https://github.com/moon-stack-OAo/count_down_tool/releases/tag/v1.3.27"/>
            <title>v1.3.27</title>
            <content type="html">&lt;h2&gt;更新内容&lt;/h2&gt;&lt;ul&gt;&lt;li&gt;设置中心 Tab&lt;/li&gt;&lt;/ul&gt;</content>
          </entry>
        </feed>
        """
        body = parse_release_body_from_atom(atom, "v1.3.27")
        self.assertIn("设置中心 Tab", body)
        self.assertIn("更新内容", body)

    def test_parse_release_body_from_html_nested(self):
        page = """
        <html><body>
        <div class="markdown-body my-3">
          <h2>更新内容</h2>
          <div><p>主题弹窗统一</p></div>
          <ul><li>NEW 角标</li></ul>
        </div>
        </body></html>
        """
        body = parse_release_body_from_html(page)
        self.assertIn("主题弹窗统一", body)
        self.assertIn("NEW 角标", body)


if __name__ == "__main__":
    unittest.main()
