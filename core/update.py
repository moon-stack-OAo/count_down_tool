# -*- coding: utf-8 -*-
"""自动更新：查 GitHub Release、下载；Windows 可替换 exe，macOS 仅下载。"""

from __future__ import annotations

from core.update_impl.checksum import (
    file_sha256,
    parse_sha256_text,
    resolve_expected_sha256,
    verify_file_sha256,
)
from core.update_impl.download import download_file
from core.update_impl.extract import (
    extract_windows_exe,
    is_allowed_extract_member,
    validate_windows_extract_layout,
)
from core.update_impl.fetch import (
    _format_http_error,
    _synthetic_assets,
    check_for_update,
    fetch_latest_release,
    fetch_latest_tag_via_redirect,
    fetch_release_body,
    parse_release_body_from_atom,
    parse_release_body_from_html,
)
from core.update_impl.models import DownloadCancelled, ReleaseInfo, UpdateCheckResult
from core.update_impl.util import (
    GITHUB_API_LATEST,
    GITHUB_OWNER,
    GITHUB_RELEASES_PAGE,
    GITHUB_REPO,
    USER_AGENT,
    WINDOWS_EXE_NAME,
    ProgressCb,
    current_executable_path,
    default_download_dir,
    is_frozen_app,
    truncate_release_notes,
)
from core.update_impl.version import (
    expected_asset_name,
    is_newer_version,
    normalize_tag_version,
    parse_version,
    platform_asset_suffix,
    platform_key,
    select_asset,
)
from core.update_impl.windows_apply import (
    apply_windows_update_from_zip,
    launch_windows_replace_and_exit_prep,
    write_windows_replace_script,
)

__all__ = [
    "GITHUB_OWNER",
    "GITHUB_REPO",
    "GITHUB_API_LATEST",
    "GITHUB_RELEASES_PAGE",
    "USER_AGENT",
    "WINDOWS_EXE_NAME",
    "ProgressCb",
    "DownloadCancelled",
    "ReleaseInfo",
    "UpdateCheckResult",
    "parse_version",
    "is_newer_version",
    "normalize_tag_version",
    "platform_key",
    "platform_asset_suffix",
    "expected_asset_name",
    "select_asset",
    "_format_http_error",
    "_synthetic_assets",
    "fetch_latest_tag_via_redirect",
    "parse_release_body_from_atom",
    "parse_release_body_from_html",
    "fetch_release_body",
    "fetch_latest_release",
    "check_for_update",
    "file_sha256",
    "parse_sha256_text",
    "verify_file_sha256",
    "resolve_expected_sha256",
    "download_file",
    "is_allowed_extract_member",
    "validate_windows_extract_layout",
    "extract_windows_exe",
    "is_frozen_app",
    "current_executable_path",
    "default_download_dir",
    "write_windows_replace_script",
    "launch_windows_replace_and_exit_prep",
    "apply_windows_update_from_zip",
    "truncate_release_notes",
]
