# -*- coding: utf-8 -*-
"""SHA256 校验与期望哈希解析。"""

from __future__ import annotations

import hashlib
import os
import re
import urllib.error
import urllib.parse
from typing import List, Optional

from core.update_impl.fetch import _http_get_text
from core.update_impl.models import ReleaseInfo
from core.update_impl.util import GITHUB_OWNER, GITHUB_REPO, logger


def file_sha256(path: str, chunk_size: int = 1024 * 1024) -> str:
    """计算文件 SHA256（小写十六进制）。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            buf = f.read(chunk_size)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def parse_sha256_text(text: str, asset_name: Optional[str] = None) -> Optional[str]:
    """
    从 .sha256 / SHA256SUMS 文本解析期望哈希。
    支持：
    - 仅一行 64 位十六进制
    - ``<hash>  <filename>`` / ``<hash> *<filename>``（GNU coreutils）
    - ``SHA256(<filename>)= <hash>``（OpenSSL）
    """
    if not text:
        return None
    want_name = (asset_name or "").strip().lower()
    only_hash: Optional[str] = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # OpenSSL: SHA256(name)= hash
        m_ssl = re.match(
            r"(?i)^SHA256\((.+)\)\s*=\s*([0-9a-f]{64})\s*$",
            line,
        )
        if m_ssl:
            name, digest = m_ssl.group(1).strip(), m_ssl.group(2).lower()
            if not want_name or os.path.basename(name).lower() == want_name:
                return digest
            continue
        # 纯 hash
        m_only = re.match(r"(?i)^([0-9a-f]{64})$", line)
        if m_only:
            only_hash = m_only.group(1).lower()
            continue
        # hash + 文件名
        m_pair = re.match(
            r"(?i)^([0-9a-f]{64})\s+\*?(.+?)\s*$",
            line,
        )
        if m_pair:
            digest, name = m_pair.group(1).lower(), m_pair.group(2).strip()
            base = os.path.basename(name.replace("\\", "/"))
            if not want_name or base.lower() == want_name:
                return digest
            continue
    # 单行纯 hash 且未按文件名筛选失败时可用
    if only_hash and (not want_name or text.count("\n") <= 1):
        return only_hash
    return only_hash if only_hash and not want_name else None


def verify_file_sha256(path: str, expected_sha256: str) -> str:
    """
    校验文件 SHA256；不匹配则删除坏文件并抛错。
    返回实际哈希（小写）。
    """
    expect = (expected_sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expect):
        raise RuntimeError(f"无效的 SHA256 期望值：{expected_sha256!r}")
    actual = file_sha256(path)
    if actual != expect:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass
        raise RuntimeError(
            f"SHA256 校验失败（期望 {expect}，实际 {actual}），文件可能被篡改或损坏"
        )
    return actual


class MissingUpdateSha256Error(RuntimeError):
    """Release 未提供可用 SHA256，禁止应用内静默下载/安装。"""


def require_expected_sha256(
    expected_sha256: Optional[str],
    asset_name: str = "",
) -> str:
    """
    应用内下载/安装必须提供有效 SHA256。
    返回规范化（小写）哈希；缺失或格式无效则抛 MissingUpdateSha256Error。
    """
    digest = (expected_sha256 or "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{64}", digest):
        return digest
    name = (asset_name or "").strip() or "安装包"
    raise MissingUpdateSha256Error(
        f"Release 未提供 {name} 的有效 SHA256 校验，"
        f"为安全起见已禁止应用内自动下载/安装。请从发布页手动下载。"
    )


def resolve_expected_sha256(
    asset_name: str,
    asset_url: str,
    release: Optional[ReleaseInfo] = None,
    timeout: float = 15.0,
) -> Optional[str]:
    """
    尝试从 GitHub Release 获取同名 .sha256 或 SHA256SUMS 类资产中的哈希。
    找到则返回 64 位十六进制；找不到返回 None
   （调用方应对应用内下载/安装路径强制阻断，并引导用户走浏览器）。
    """
    name = (asset_name or "").strip()
    if not name:
        return None
    candidates: List[str] = []
    # 1) 与 zip 同名的 .sha256 / .sha256sum
    for suffix in (".sha256", ".sha256sum", ".sha256.txt"):
        candidates.append(_release_download_url_from_asset_url(asset_url, name + suffix)
                          if asset_url else "")
        if release:
            ver = release.version
            tag = release.tag_name or f"v{ver}"
            candidates.append(
                f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
                f"/releases/download/{tag}/{name}{suffix}"
            )
    # 2) 通用汇总文件
    for sums_name in (
        "SHA256SUMS",
        "SHA256SUMS.txt",
        "sha256sums",
        "sha256sums.txt",
        "checksums.sha256",
        "checksums.txt",
    ):
        if release:
            tag = release.tag_name or f"v{release.version}"
            candidates.append(
                f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
                f"/releases/download/{tag}/{sums_name}"
            )
        if asset_url:
            candidates.append(
                _release_download_url_from_asset_url(asset_url, sums_name)
            )
    # 3) release.assets 中已有的校验文件
    if release:
        by_name = {
            str(a.get("name") or ""): str(a.get("browser_download_url") or "")
            for a in release.assets
            if isinstance(a, dict)
        }
        for key, url in by_name.items():
            kl = key.lower()
            if kl == f"{name.lower()}.sha256" or kl.endswith(".sha256"):
                if url:
                    candidates.insert(0, url)
            if kl in (
                "sha256sums",
                "sha256sums.txt",
                "checksums.sha256",
                "checksums.txt",
            ):
                if url:
                    candidates.insert(0, url)

    seen: set = set()
    for url in candidates:
        url = (url or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            text = _http_get_text(url, timeout=timeout, accept="text/plain,*/*")
        except (OSError, urllib.error.URLError, RuntimeError, ValueError, TypeError) as exc:
            logger.debug("拉取 SHA256 资产失败 %s: %s", url, exc)
            continue
        digest = parse_sha256_text(text, asset_name=name)
        if digest:
            logger.info("已获取 SHA256 校验源: %s", url)
            return digest
    return None


def _release_download_url_from_asset_url(asset_url: str, new_name: str) -> str:
    """将 release 资产 URL 的文件名替换为 new_name。"""
    try:
        parts = urllib.parse.urlsplit(asset_url)
        path = parts.path or ""
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        new_path = f"{parent}/{new_name}" if parent else f"/{new_name}"
        return urllib.parse.urlunsplit(
            (parts.scheme, parts.netloc, new_path, "", "")
        )
    except (TypeError, ValueError, AttributeError):
        return ""
