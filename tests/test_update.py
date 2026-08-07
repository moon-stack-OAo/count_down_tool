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

import hashlib
import http.client
import threading
import urllib.error

from core.update import (
    DownloadCancelled,
    MissingUpdateSha256Error,
    ReleaseInfo,
    _format_http_error,
    _synthetic_assets,
    check_for_update,
    download_file,
    expected_asset_name,
    extract_windows_exe,
    fetch_latest_release,
    file_sha256,
    is_allowed_extract_member,
    is_newer_version,
    parse_release_body_from_atom,
    parse_release_body_from_html,
    parse_sha256_text,
    parse_version,
    platform_asset_suffix,
    require_expected_sha256,
    select_asset,
    validate_windows_extract_layout,
    verify_file_sha256,
    write_windows_replace_script,
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
            # 满足 extract 的 MZ + 最小体积校验
            payload = b"MZ" + b"\0" * 1200
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("count_down_tool.exe", payload)
            out = extract_windows_exe(zpath, os.path.join(tmp, "out"))
            self.assertTrue(os.path.isfile(out))
            with open(out, "rb") as f:
                self.assertEqual(f.read(), payload)

    def test_extract_onedir_layout(self):
        """zip 含 exe + 附属文件（模拟 onedir）时应整包解压。"""
        with tempfile.TemporaryDirectory() as tmp:
            zpath = os.path.join(tmp, "onedir.zip")
            payload = b"MZ" + b"\0" * 1200
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("count_down_tool.exe", payload)
                zf.writestr("_internal/python311.dll", b"DLL" + b"\0" * 100)
                zf.writestr("_internal/base_library.zip", b"PK" + b"\0" * 50)
            out_dir = os.path.join(tmp, "out")
            out = extract_windows_exe(zpath, out_dir)
            self.assertTrue(os.path.isfile(out))
            self.assertTrue(
                os.path.isfile(os.path.join(os.path.dirname(out), "_internal", "python311.dll"))
            )

    def test_extract_missing_exe_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            zpath = os.path.join(tmp, "no_exe.zip")
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("readme.txt", b"hello")
            with self.assertRaises(FileNotFoundError):
                extract_windows_exe(zpath, os.path.join(tmp, "out"))

    def test_extract_exe_too_small_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            zpath = os.path.join(tmp, "tiny.zip")
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("count_down_tool.exe", b"MZ" + b"\0" * 10)
            with self.assertRaises(RuntimeError) as ctx:
                extract_windows_exe(zpath, os.path.join(tmp, "out"))
            self.assertIn("过小", str(ctx.exception))

    def test_extract_exe_bad_magic_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            zpath = os.path.join(tmp, "bad_magic.zip")
            payload = b"XX" + b"\0" * 1200
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("count_down_tool.exe", payload)
            with self.assertRaises(RuntimeError) as ctx:
                extract_windows_exe(zpath, os.path.join(tmp, "out"))
            self.assertIn("不是有效 Windows 可执行文件", str(ctx.exception))

    def test_extract_corrupt_zip_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            zpath = os.path.join(tmp, "corrupt.zip")
            with open(zpath, "wb") as f:
                f.write(b"not a zip at all")
            with self.assertRaises(zipfile.BadZipFile):
                extract_windows_exe(zpath, os.path.join(tmp, "out"))

    def test_extract_zip_slip_dotdot_rejected(self):
        """Zip Slip：含 .. 的成员必须被拒绝，且不得写出目标外。"""
        with tempfile.TemporaryDirectory() as tmp:
            zpath = os.path.join(tmp, "slip.zip")
            out_dir = os.path.join(tmp, "out")
            outside = os.path.join(tmp, "pwned.txt")
            payload = b"MZ" + b"\0" * 1200
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("count_down_tool.exe", payload)
                # 试图写出到 out 之外
                zf.writestr("../pwned.txt", b"evil")
            with self.assertRaises(RuntimeError) as ctx:
                extract_windows_exe(zpath, out_dir)
            self.assertTrue(
                ".." in str(ctx.exception)
                or "拒绝" in str(ctx.exception)
                or "白名单" in str(ctx.exception)
            )
            self.assertFalse(os.path.isfile(outside))

    def test_extract_zip_slip_absolute_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            zpath = os.path.join(tmp, "abs.zip")
            payload = b"MZ" + b"\0" * 1200
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("count_down_tool.exe", payload)
                # Windows 风格绝对/盘符路径（zip 内用正斜杠）
                info = zipfile.ZipInfo("C:/Windows/Temp/evil.dll")
                zf.writestr(info, b"evil")
            with self.assertRaises(RuntimeError) as ctx:
                extract_windows_exe(zpath, os.path.join(tmp, "out"))
            self.assertIn("拒绝", str(ctx.exception))

    def test_extract_non_whitelist_member_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            zpath = os.path.join(tmp, "dirty.zip")
            out_dir = os.path.join(tmp, "out")
            payload = b"MZ" + b"\0" * 1200
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("count_down_tool.exe", payload)
                zf.writestr("malware/payload.bin", b"bad")
            with self.assertRaises(RuntimeError) as ctx:
                extract_windows_exe(zpath, out_dir)
            self.assertIn("白名单", str(ctx.exception))
            # 失败应回滚：解压目录不残留
            self.assertFalse(os.path.isdir(out_dir))

    def test_extract_failure_rolls_back_partial_dir(self):
        """校验失败（exe 过小）时删除整个解压目录。"""
        with tempfile.TemporaryDirectory() as tmp:
            zpath = os.path.join(tmp, "tiny.zip")
            out_dir = os.path.join(tmp, "out")
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("count_down_tool.exe", b"MZ" + b"\0" * 10)
            with self.assertRaises(RuntimeError):
                extract_windows_exe(zpath, out_dir)
            self.assertFalse(os.path.isdir(out_dir))

    def test_allowed_extract_member_rules(self):
        self.assertTrue(is_allowed_extract_member("count_down_tool.exe"))
        self.assertTrue(is_allowed_extract_member("_internal/python311.dll"))
        self.assertTrue(is_allowed_extract_member("docs/readme.txt"))
        self.assertTrue(is_allowed_extract_member("readme.txt"))
        self.assertTrue(
            is_allowed_extract_member("count_down_tool-1.0.0/count_down_tool.exe")
        )
        self.assertTrue(
            is_allowed_extract_member("count_down_tool-1.0.0/_internal/x.dll")
        )
        self.assertFalse(is_allowed_extract_member("malware/x.bin"))
        self.assertFalse(is_allowed_extract_member("other.dll"))

    def test_validate_layout_requires_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "readme.txt"), "w", encoding="utf-8") as f:
                f.write("x")
            with self.assertRaises(FileNotFoundError):
                validate_windows_extract_layout(tmp)

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
            self.assertIn("Test-ExeReady", body)
            self.assertIn("onedir", body.lower())
            self.assertIn("sourceDir", body)
            self.assertIn("count_down_tool_update.log", body)
            self.assertNotIn("tasklist", body)
            self.assertNotIn("find ", body.lower())


class TestDownloadFile(unittest.TestCase):
    def _mock_resp(self, body: bytes, content_length=None):
        class _Resp:
            def __init__(self):
                self.headers = {}
                if content_length is not None:
                    self.headers["Content-Length"] = str(content_length)
                self._data = body
                self._pos = 0

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n=-1):
                if self._pos >= len(self._data):
                    return b""
                if n is None or n < 0:
                    chunk = self._data[self._pos :]
                    self._pos = len(self._data)
                    return chunk
                chunk = self._data[self._pos : self._pos + n]
                self._pos += len(chunk)
                return chunk

        return _Resp()

    def test_download_success(self):
        payload = b"hello-update-payload"
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "pkg.zip")
            with mock.patch(
                "core.update_impl.download.urllib.request.urlopen",
                return_value=self._mock_resp(payload, content_length=len(payload)),
            ):
                path = download_file("https://example.com/a.zip", dest)
            self.assertEqual(path, os.path.abspath(dest))
            with open(dest, "rb") as f:
                self.assertEqual(f.read(), payload)

    def test_download_incomplete_removes_file(self):
        payload = b"partial"
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "pkg.zip")
            with mock.patch(
                "core.update_impl.download.urllib.request.urlopen",
                return_value=self._mock_resp(payload, content_length=100),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    # max_retries=0：本用例只验证不完整落盘清理，不测退避
                    download_file(
                        "https://example.com/a.zip",
                        dest,
                        max_retries=0,
                    )
            self.assertIn("不完整", str(ctx.exception))
            self.assertFalse(os.path.isfile(dest))

    def test_download_retries_remote_disconnected(self):
        """RemoteDisconnected 等瞬时错误应自动重试后成功。"""
        payload = b"retry-ok-payload"
        calls = {"n": 0}

        def _urlopen(*_a, **_k):
            calls["n"] += 1
            if calls["n"] < 3:
                raise http.client.RemoteDisconnected(
                    "Remote end closed connection without response"
                )
            return self._mock_resp(payload, content_length=len(payload))

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "pkg.zip")
            with mock.patch(
                "core.update_impl.download.urllib.request.urlopen",
                side_effect=_urlopen,
            ):
                with mock.patch("core.update_impl.download.time.sleep", return_value=None):
                    path = download_file(
                        "https://example.com/a.zip",
                        dest,
                        max_retries=3,
                    )
            self.assertEqual(calls["n"], 3)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), payload)

    def test_download_empty_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "empty.zip")
            with mock.patch(
                "core.update_impl.download.urllib.request.urlopen",
                return_value=self._mock_resp(b""),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    download_file("https://example.com/a.zip", dest)
            self.assertIn("空", str(ctx.exception))
            self.assertFalse(os.path.isfile(dest))

    def test_download_expected_size_mismatch(self):
        payload = b"12345"
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "pkg.zip")
            with mock.patch(
                "core.update_impl.download.urllib.request.urlopen",
                return_value=self._mock_resp(payload, content_length=5),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    download_file(
                        "https://example.com/a.zip",
                        dest,
                        expected_size=99,
                    )
            self.assertIn("不一致", str(ctx.exception))
            self.assertFalse(os.path.isfile(dest))

    def test_download_sha256_match(self):
        payload = b"hello-sha256-payload"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "pkg.zip")
            with mock.patch(
                "core.update_impl.download.urllib.request.urlopen",
                return_value=self._mock_resp(payload, content_length=len(payload)),
            ):
                path = download_file(
                    "https://example.com/a.zip",
                    dest,
                    expected_sha256=digest,
                )
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(file_sha256(path), digest)

    def test_download_sha256_mismatch_removes_file(self):
        payload = b"hello-sha256-payload"
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "pkg.zip")
            with mock.patch(
                "core.update_impl.download.urllib.request.urlopen",
                return_value=self._mock_resp(payload, content_length=len(payload)),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    download_file(
                        "https://example.com/a.zip",
                        dest,
                        expected_sha256="0" * 64,
                    )
            self.assertIn("SHA256", str(ctx.exception))
            self.assertFalse(os.path.isfile(dest))

    def test_download_cancel_removes_partial(self):
        """取消下载时应清理半成品并抛 DownloadCancelled。"""
        payload = b"x" * (256 * 1024)
        cancel_event = threading.Event()

        class _SlowResp:
            def __init__(self):
                self.headers = {"Content-Length": str(len(payload))}
                self._data = payload
                self._pos = 0
                self._reads = 0

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n=-1):
                self._reads += 1
                # 第一次读后触发取消
                if self._reads >= 2:
                    cancel_event.set()
                if self._pos >= len(self._data):
                    return b""
                if n is None or n < 0:
                    n = len(self._data) - self._pos
                chunk = self._data[self._pos : self._pos + n]
                self._pos += len(chunk)
                return chunk

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "partial.zip")
            with mock.patch(
                "core.update_impl.download.urllib.request.urlopen",
                return_value=_SlowResp(),
            ):
                with self.assertRaises(DownloadCancelled):
                    download_file(
                        "https://example.com/a.zip",
                        dest,
                        cancel_event=cancel_event,
                    )
            self.assertFalse(os.path.isfile(dest))

    def test_download_cancel_before_start(self):
        cancel_event = threading.Event()
        cancel_event.set()
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "never.zip")
            with self.assertRaises(DownloadCancelled):
                download_file(
                    "https://example.com/a.zip",
                    dest,
                    cancel_event=cancel_event,
                )
            self.assertFalse(os.path.isfile(dest))


class TestSha256Helpers(unittest.TestCase):
    def test_parse_sha256_text_formats(self):
        h = "a" * 64
        self.assertEqual(parse_sha256_text(h), h)
        self.assertEqual(
            parse_sha256_text(f"{h}  count_down_tool-1.0.0-win64.zip", "count_down_tool-1.0.0-win64.zip"),
            h,
        )
        self.assertEqual(
            parse_sha256_text(f"{h} *pkg.zip", "pkg.zip"),
            h,
        )
        self.assertEqual(
            parse_sha256_text(f"SHA256(pkg.zip)= {h}", "pkg.zip"),
            h,
        )
        # 不匹配文件名
        self.assertIsNone(
            parse_sha256_text(f"{h}  other.zip", "pkg.zip")
        )

    def test_verify_file_sha256_ok_and_fail(self):
        payload = b"verify-me"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "f.bin")
            with open(path, "wb") as f:
                f.write(payload)
            self.assertEqual(verify_file_sha256(path, digest), digest)
            with self.assertRaises(RuntimeError):
                verify_file_sha256(path, "b" * 64)
            self.assertFalse(os.path.isfile(path))

    def test_require_expected_sha256_blocks_missing(self):
        """无 sha256 / 非法格式：不可走安装路径。"""
        with self.assertRaises(MissingUpdateSha256Error) as ctx:
            require_expected_sha256(None, asset_name="pkg.zip")
        self.assertIn("SHA256", str(ctx.exception))
        with self.assertRaises(MissingUpdateSha256Error):
            require_expected_sha256("", asset_name="pkg.zip")
        with self.assertRaises(MissingUpdateSha256Error):
            require_expected_sha256("not-a-hash", asset_name="pkg.zip")
        with self.assertRaises(MissingUpdateSha256Error):
            require_expected_sha256("abc", asset_name="pkg.zip")

    def test_require_expected_sha256_accepts_valid(self):
        """有有效 sha256：允许进入下载/安装路径（返回规范化哈希）。"""
        h = "A" * 64
        self.assertEqual(require_expected_sha256(h, asset_name="pkg.zip"), "a" * 64)
        self.assertEqual(
            require_expected_sha256("b" * 64),
            "b" * 64,
        )


class TestInAppUpdateRequiresSha256(unittest.TestCase):
    """应用内下载/安装入口：无 SHA256 不得调用 download_file / apply。"""

    def _make_result(self, **kwargs):
        release = ReleaseInfo(
            version="9.9.9",
            tag_name="v9.9.9",
            body="notes",
            html_url="https://github.com/example/releases/tag/v9.9.9",
            assets=(
                {
                    "name": "count_down_tool-9.9.9-win64.zip",
                    "browser_download_url": "https://example.com/w.zip",
                    "size": 10,
                },
            ),
        )
        from core.update import UpdateCheckResult

        base = dict(
            has_update=True,
            current_version="1.0.0",
            latest_version="9.9.9",
            release=release,
            asset_name="count_down_tool-9.9.9-win64.zip",
            asset_url="https://example.com/w.zip",
            asset_size=10,
            platform_key="windows",
            error=None,
        )
        base.update(kwargs)
        return UpdateCheckResult(**base)

    def _attach_ui_actions(self, app, *, progress_win=None):
        """services 经 app.ui_actions 触达 UI（不再 patch ui.* 模块路径）。"""
        ui = mock.MagicMock()
        ui.show_update_progress.return_value = progress_win or object()
        app.ui_actions = ui
        return ui

    def test_windows_install_no_sha256_skips_download(self):
        from services import updater as upd

        app = mock.MagicMock()
        app.master.after = mock.MagicMock(side_effect=lambda _ms, fn: fn())
        ui = self._attach_ui_actions(app)
        result = self._make_result()
        with mock.patch.object(upd, "_try_begin_update", return_value=True), mock.patch.object(
            upd.core_update,
            "resolve_expected_sha256",
            return_value=None,
        ), mock.patch.object(
            upd.core_update,
            "download_file",
        ) as dl, mock.patch.object(
            upd.core_update,
            "apply_windows_update_from_zip",
        ) as apply_fn, mock.patch.object(
            upd,
            "webbrowser",
        ) as wb, mock.patch(
            "threading.Thread",
        ) as th:
            # 同步执行 worker
            th.side_effect = lambda target=None, daemon=None, name=None: mock.Mock(
                start=lambda: target() if target else None
            )
            upd._start_windows_install(app, result)
        dl.assert_not_called()
        apply_fn.assert_not_called()
        ui.show_error.assert_called()
        wb.open.assert_called()
        self.assertIn(
            "SHA256",
            str(ui.show_error.call_args[0][1]) if ui.show_error.call_args else "",
        )

    def test_windows_install_with_sha256_downloads(self):
        from services import updater as upd

        digest = "c" * 64
        app = mock.MagicMock()
        app.master.after = mock.MagicMock(side_effect=lambda _ms, fn: fn())
        self._attach_ui_actions(app)
        result = self._make_result()
        with mock.patch.object(upd, "_try_begin_update", return_value=True), mock.patch.object(
            upd.core_update,
            "resolve_expected_sha256",
            return_value=digest,
        ), mock.patch.object(
            upd.core_update,
            "download_file",
            return_value=r"C:\Temp\pkg.zip",
        ) as dl, mock.patch.object(
            upd.core_update,
            "apply_windows_update_from_zip",
        ) as apply_fn, mock.patch(
            "threading.Thread",
        ) as th:
            th.side_effect = lambda target=None, daemon=None, name=None: mock.Mock(
                start=lambda: target() if target else None
            )
            upd._start_windows_install(app, result)
        dl.assert_called_once()
        kwargs = dl.call_args.kwargs if dl.call_args.kwargs else {}
        # expected_sha256 必须传入有效哈希
        pos_or_kw = (
            dl.call_args.kwargs.get("expected_sha256")
            if dl.call_args.kwargs
            else None
        )
        if pos_or_kw is None and dl.call_args.args:
            # 位置参数：url, path, ... 不一定含 sha
            pos_or_kw = kwargs.get("expected_sha256")
        self.assertEqual(
            dl.call_args.kwargs.get("expected_sha256")
            or (dl.call_args[1].get("expected_sha256") if len(dl.call_args) > 1 else None),
            digest,
        )
        apply_fn.assert_called_once()

    def test_mac_download_no_sha256_skips_download(self):
        from services import updater as upd

        app = mock.MagicMock()
        app.master.after = mock.MagicMock(side_effect=lambda _ms, fn: fn())
        ui = self._attach_ui_actions(app)
        result = self._make_result(
            asset_name="count_down_tool-9.9.9-mac-arm64.zip",
        )
        with mock.patch.object(upd, "_try_begin_update", return_value=True), mock.patch.object(
            upd.core_update,
            "resolve_expected_sha256",
            return_value=None,
        ), mock.patch.object(
            upd.core_update,
            "download_file",
        ) as dl, mock.patch.object(
            upd,
            "webbrowser",
        ) as wb, mock.patch(
            "threading.Thread",
        ) as th:
            th.side_effect = lambda target=None, daemon=None, name=None: mock.Mock(
                start=lambda: target() if target else None
            )
            upd._start_mac_download(app, result)
        dl.assert_not_called()
        ui.show_error.assert_called()
        wb.open.assert_called()


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
        with mock.patch("core.update_impl.fetch.fetch_latest_release", return_value=release):
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
        with mock.patch("core.update_impl.fetch.fetch_latest_release", return_value=release):
            r = check_for_update(
                "1.0.0",
                system="Windows",
                ignored_version="9.9.9",
            )
        self.assertFalse(r.has_update)

    def test_network_error(self):
        with mock.patch(
            "core.update_impl.fetch.fetch_latest_release",
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

        with mock.patch("core.update_impl.fetch.urllib.request.urlopen", return_value=_Resp()):
            with mock.patch(
                "core.update_impl.fetch.fetch_release_body", return_value="## 更新内容\n- 修复"
            ) as body_fn:
                with mock.patch("core.update_impl.fetch._http_get_json") as api:
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
            <content type="html">&lt;h2&gt;更新内容&lt;/h2&gt;&lt;ul&gt;&lt;li&gt;设置中心 Tab&lt;/li&gt;&lt;/ul&gt;
            </content>
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
