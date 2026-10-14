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
from core.update_impl.util import (
    GITHUB_OWNER,
    GITHUB_REPO,
    UpdateUrlNotAllowedError,
    assert_allowed_update_url,
    logger,
)

# 与当前安装包精确对应的校验文件后缀（忽略大小写）
_ASSET_CHECKSUM_SUFFIXES = (".sha256", ".sha256sum", ".sha256.txt")


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
    # 单行纯哈希没有文件名：指定了 asset 时不能采用（可能是别的包）。
    # 未指定 asset 时仅在全文只有这一条哈希时返回（兼容直接解析 .sha256 文本）。
    only_hash: Optional[str] = None
    only_hash_count = 0
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
            only_hash_count += 1
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
    if want_name:
        return None
    if only_hash and only_hash_count == 1:
        return only_hash
    return None


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


def _checksum_sidecar_names(asset_name: str) -> frozenset:
    """当前资产允许的旁路校验文件名（小写）。"""
    base = (asset_name or "").strip().lower()
    if not base:
        return frozenset()
    return frozenset(f"{base}{suffix}" for suffix in _ASSET_CHECKSUM_SUFFIXES)


def _is_exact_asset_checksum_name(filename: str, asset_name: str) -> bool:
    """文件名是否精确为 ``{asset}.sha256`` / ``.sha256sum`` / ``.sha256.txt``。"""
    return (filename or "").strip().lower() in _checksum_sidecar_names(asset_name)


def _url_filename(url: str) -> str:
    """取 URL 路径最后一段文件名（已解码）。"""
    try:
        path = urllib.parse.urlsplit(url).path or ""
    except (TypeError, ValueError, AttributeError):
        return ""
    name = path.rsplit("/", 1)[-1]
    return urllib.parse.unquote(name)


def _github_release_download_url(tag: str, filename: str) -> str:
    """自行拼接 GitHub Release 下载地址，不使用资产 API 返回的 URL。"""
    return (
        f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/releases/download/{tag}/{filename}"
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
    tag = ""
    if release:
        tag = (release.tag_name or "").strip() or f"v{release.version}"
    # 只信任自行拼接的 github.com/.../releases/download/{tag}/{filename}。
    # release.assets 的 browser_download_url 不能无条件当校验源：
    # 仅当文件名精确匹配当前包的校验旁路，且 URL 过主机白名单时才采用。
    sidecar_names = _checksum_sidecar_names(name)
    sums_names = (
        "SHA256SUMS",
        "SHA256SUMS.txt",
        "sha256sums",
        "sha256sums.txt",
        "checksums.sha256",
        "checksums.txt",
    )
    # (url, 是否允许单行无文件名哈希)
    candidates: List[tuple] = []
    if tag:
        for suffix in _ASSET_CHECKSUM_SUFFIXES:
            candidates.append(
                (_github_release_download_url(tag, name + suffix), True)
            )
        for sums_name in sums_names:
            candidates.append(
                (_github_release_download_url(tag, sums_name), False)
            )
    if release:
        for asset in release.assets:
            if not isinstance(asset, dict):
                continue
            key = str(asset.get("name") or "").strip()
            url = str(asset.get("browser_download_url") or "").strip()
            if not key or not url:
                continue
            kl = key.lower()
            if kl in sidecar_names:
                bare_ok = True
            elif kl in {s.lower() for s in sums_names}:
                bare_ok = False
            else:
                # 其它 .sha256（例如别的包）一律丢弃
                continue
            try:
                assert_allowed_update_url(url)
            except UpdateUrlNotAllowedError as exc:
                logger.debug("丢弃非白名单校验资产 URL %s: %s", url, exc)
                continue
            candidates.insert(0, (url, bare_ok))

    seen: set = set()
    for url, allow_bare_hash in candidates:
        url = (url or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            assert_allowed_update_url(url)
        except UpdateUrlNotAllowedError as exc:
            logger.debug("丢弃非白名单校验 URL %s: %s", url, exc)
            continue
        try:
            text = _http_get_text(
                url,
                timeout=timeout,
                accept="text/plain,*/*",
                require_allowed_host=True,
            )
        except (OSError, urllib.error.URLError, RuntimeError, ValueError, TypeError) as exc:
            logger.debug("拉取 SHA256 资产失败 %s: %s", url, exc)
            continue
        digest = parse_sha256_text(text, asset_name=name)
        if not digest and allow_bare_hash and _is_exact_asset_checksum_name(
            _url_filename(url), name
        ):
            # 单行纯哈希只在 URL 文件名就是该资产的 .sha256 旁路时接受
            digest = parse_sha256_text(text, asset_name=None)
        if digest:
            logger.info("已获取 SHA256 校验源: %s", url)
            return digest
    return None



