# -*- coding: utf-8 -*-
"""从 GitHub 获取 Release 信息与版本检查。"""

from __future__ import annotations

import html as html_lib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from core.update_impl.models import ReleaseInfo, UpdateCheckResult
from core.update_impl.util import (
    GITHUB_API_LATEST,
    GITHUB_OWNER,
    GITHUB_RELEASES_PAGE,
    GITHUB_REPO,
    USER_AGENT,
    logger,
)
from core.update_impl.version import (
    is_newer_version,
    normalize_tag_version,
    platform_key,
    select_asset,
)


def _format_http_error(exc: BaseException) -> str:
    """将 urllib HTTP 错误转为可读说明（尤其是 API 限流）。"""
    if isinstance(exc, urllib.error.HTTPError):
        code = int(exc.code or 0)
        reason = str(exc.reason or "")
        if code == 403 and "rate limit" in (reason + str(exc)).lower():
            return (
                "GitHub API 请求过于频繁（未登录每小时约 60 次）。"
                "请稍后再试，或直接打开发布页下载。"
            )
        if code == 403:
            return f"GitHub 拒绝访问（HTTP 403）。{reason}".strip()
        if code == 404:
            return "未找到 Release（仓库可能无发布或地址有误）。"
        return f"HTTP Error {code}: {reason}".strip()
    return str(exc)


def _http_get_json(url: str, timeout: float = 15.0) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(_format_http_error(exc)) from exc
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("GitHub API 返回非对象 JSON")
    return data


def _release_download_url(version: str, asset_name: str) -> str:
    ver = normalize_tag_version(version)
    tag = f"v{ver}"
    return (
        f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/releases/download/{tag}/{asset_name}"
    )


def _synthetic_assets(version: str) -> Tuple[Dict[str, Any], ...]:
    """按命名约定生成三平台附件（无需 API assets 列表）。"""
    ver = normalize_tag_version(version)
    names = (
        f"count_down_tool-{ver}-win64.zip",
        f"count_down_tool-{ver}-mac-arm64.zip",
        f"count_down_tool-{ver}-mac-x86_64.zip",
    )
    out: List[Dict[str, Any]] = []
    for name in names:
        out.append(
            {
                "name": name,
                "browser_download_url": _release_download_url(ver, name),
                "size": 0,
            }
        )
    return tuple(out)


def fetch_latest_tag_via_redirect(timeout: float = 15.0) -> str:
    """
    通过 GitHub 网页 releases/latest 的 302 解析最新 tag。
    不走 api.github.com，避免未认证 60 次/小时限流。
    """
    req = urllib.request.Request(
        GITHUB_RELEASES_PAGE,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final = str(resp.geturl() or "")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(_format_http_error(exc)) from exc
    # .../releases/tag/v1.3.26 或 .../releases/tag/1.3.26
    m = re.search(r"/releases/tag/([^/?#]+)", final)
    if not m:
        raise RuntimeError(f"无法从发布页解析版本：{final or GITHUB_RELEASES_PAGE}")
    return urllib.parse.unquote(m.group(1))


def _http_get_text(url: str, timeout: float = 15.0, accept: str = "*/*") -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(_format_http_error(exc)) from exc
    return raw.decode("utf-8", errors="replace")


def _html_fragment_to_text(fragment: str) -> str:
    """粗略将 HTML 片段转为纯文本（发布说明展示用）。"""
    text = fragment or ""
    text = re.sub(r"(?is)<script\b[^>]*>.*?</script>", "", text)
    text = re.sub(r"(?is)<style\b[^>]*>.*?</style>", "", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = re.sub(r"(?i)</li\s*>", "\n", text)
    text = re.sub(r"(?i)</h[1-6]\s*>", "\n", text)
    text = re.sub(r"(?i)</tr\s*>", "\n", text)
    text = re.sub(r"(?i)</div\s*>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", "", text)
    text = html_lib.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 压缩多余空行
    lines = [ln.rstrip() for ln in text.split("\n")]
    out: List[str] = []
    blank = False
    for ln in lines:
        if not ln.strip():
            if out and not blank:
                out.append("")
            blank = True
            continue
        blank = False
        out.append(ln.strip() if len(ln) - len(ln.lstrip()) > 40 else ln)
    return "\n".join(out).strip()


def parse_release_body_from_atom(atom_xml: str, tag_name: str) -> str:
    """从 releases.atom 中取指定 tag 的 content（HTML）。"""
    ver = normalize_tag_version(tag_name)
    tag_v = tag_name if str(tag_name).lower().startswith("v") else f"v{ver}"
    # 按 entry 切分
    entries = re.findall(r"(?is)<entry\b[^>]*>(.*?)</entry>", atom_xml or "")
    for entry in entries:
        link_m = re.search(
            r'(?is)<link[^>]+href="([^"]+/releases/tag/[^"]+)"',
            entry,
        )
        href = urllib.parse.unquote(link_m.group(1)) if link_m else ""
        id_m = re.search(r"(?is)<id>(.*?)</id>", entry)
        entry_id = (id_m.group(1) if id_m else "").strip()
        title_m = re.search(r"(?is)<title[^>]*>(.*?)</title>", entry)
        title = _html_fragment_to_text(title_m.group(1) if title_m else "")
        hit = (
            f"/releases/tag/{tag_v}" in href
            or f"/releases/tag/{ver}" in href
            or entry_id.endswith(f"/{tag_v}")
            or entry_id.endswith(f"/{ver}")
            or title.startswith(tag_v)
            or title.startswith(ver)
            or title.startswith(f"v{ver}")
        )
        if not hit:
            continue
        content_m = re.search(
            r'(?is)<content\b[^>]*type="html"[^>]*>(.*?)</content>',
            entry,
        )
        if not content_m:
            content_m = re.search(r"(?is)<content\b[^>]*>(.*?)</content>", entry)
        if not content_m:
            return ""
        raw = html_lib.unescape(content_m.group(1).strip())
        return _html_fragment_to_text(raw)
    return ""


def _extract_open_div_inner(html: str, open_match_end: int) -> str:
    """从已匹配的开标签之后，按嵌套深度截取到对应 </div> 之前。"""
    i = open_match_end
    depth = 1
    lower = html.lower()
    n = len(html)
    while i < n and depth > 0:
        next_open = lower.find("<div", i)
        next_close = lower.find("</div", i)
        if next_close < 0:
            return html[open_match_end:].strip()
        if next_open >= 0 and next_open < next_close:
            # 确认是标签起始
            depth += 1
            gt = html.find(">", next_open)
            i = gt + 1 if gt >= 0 else next_open + 4
            continue
        depth -= 1
        if depth == 0:
            return html[open_match_end:next_close].strip()
        gt = html.find(">", next_close)
        i = gt + 1 if gt >= 0 else next_close + 5
    return html[open_match_end:].strip()


def parse_release_body_from_html(page_html: str) -> str:
    """从 GitHub Release 网页解析 markdown-body 发布说明。"""
    html = page_html or ""
    open_patterns = (
        r'(?is)<div[^>]*data-test-selector=["\']body-content["\'][^>]*>',
        r'(?is)<div[^>]*class=["\'][^"\']*markdown-body[^"\']*["\'][^>]*>',
    )
    for pat in open_patterns:
        m = re.search(pat, html)
        if not m:
            continue
        inner = _extract_open_div_inner(html, m.end())
        text = _html_fragment_to_text(inner)
        if text:
            return text
    # og:description 兜底（通常较短）
    og = re.search(
        r'(?is)<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        html,
    )
    if not og:
        og = re.search(
            r'(?is)<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
            html,
        )
    if og:
        return html_lib.unescape(og.group(1)).strip()
    return ""


def fetch_release_body(tag_name: str, html_url: str, timeout: float = 15.0) -> str:
    """
    在已知 tag 时尽量取发布说明（不依赖 latest API）。
    顺序：releases.atom → 发布页 HTML → API tags/{tag}。
    任一步失败则尝试下一步；全部失败返回空串。
    """
    ver = normalize_tag_version(tag_name)
    tag_v = tag_name if str(tag_name).lower().startswith("v") else f"v{ver}"

    # 1) Atom（不占 API 配额）
    try:
        atom_url = (
            f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases.atom"
        )
        atom = _http_get_text(
            atom_url, timeout=timeout, accept="application/atom+xml, application/xml, text/xml"
        )
        body = parse_release_body_from_atom(atom, tag_v)
        if body.strip():
            return body
    except (OSError, urllib.error.URLError, RuntimeError, ValueError, TypeError) as exc:
        logger.debug("Atom 取发布说明失败: %s", exc)

    # 2) 发布页 HTML
    try:
        page = _http_get_text(
            html_url or (
                f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
                f"/releases/tag/{tag_v}"
            ),
            timeout=timeout,
            accept="text/html,application/xhtml+xml",
        )
        body = parse_release_body_from_html(page)
        if body.strip():
            return body
    except (OSError, urllib.error.URLError, RuntimeError, ValueError, TypeError) as exc:
        logger.debug("HTML 取发布说明失败: %s", exc)

    # 3) API（可能限流，失败则空说明，不影响版本检查）
    try:
        api_url = (
            f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
            f"/releases/tags/{urllib.parse.quote(tag_v)}"
        )
        data = _http_get_json(api_url, timeout=timeout)
        body = str(data.get("body") or "").strip()
        if body:
            return body
    except (OSError, urllib.error.URLError, RuntimeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.debug("API 取发布说明失败: %s", exc)

    return ""


def fetch_latest_release(timeout: float = 15.0) -> ReleaseInfo:
    """获取最新 Release：优先网页重定向（不占 API 配额），失败再回退 API。"""
    # 1) 网页重定向 + 按约定合成下载链接（不请求 api.github.com）
    try:
        tag = fetch_latest_tag_via_redirect(timeout=timeout)
        version = normalize_tag_version(tag)
        if not version:
            raise RuntimeError("解析到空版本号")
        tag_name = tag if str(tag).lower().startswith("v") else f"v{version}"
        html_url = (
            f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
            f"/releases/tag/{tag_name}"
        )
        body = fetch_release_body(tag_name, html_url, timeout=timeout)
        return ReleaseInfo(
            version=version,
            tag_name=tag_name,
            body=body,
            html_url=html_url,
            assets=_synthetic_assets(version),
        )
    except (OSError, urllib.error.URLError, RuntimeError, ValueError, TypeError) as web_exc:
        logger.info("网页方式检查更新失败，回退 API: %s", web_exc)

    # 2) API 回退（可能触发未认证限流）
    try:
        data = _http_get_json(GITHUB_API_LATEST, timeout=timeout)
    except (OSError, urllib.error.URLError, RuntimeError, ValueError, TypeError, json.JSONDecodeError) as api_exc:
        raise RuntimeError(_format_http_error(api_exc)) from api_exc
    tag = str(data.get("tag_name") or "")
    version = normalize_tag_version(tag)
    assets_raw = data.get("assets") or []
    assets: List[Dict[str, Any]] = [
        a for a in assets_raw if isinstance(a, dict)
    ]
    if not assets and version:
        assets = list(_synthetic_assets(version))
    return ReleaseInfo(
        version=version,
        tag_name=tag,
        body=str(data.get("body") or ""),
        html_url=str(data.get("html_url") or GITHUB_RELEASES_PAGE),
        assets=tuple(assets),
    )


def check_for_update(
    current_version: str,
    system: Optional[str] = None,
    machine: Optional[str] = None,
    timeout: float = 15.0,
    ignored_version: Optional[str] = None,
) -> UpdateCheckResult:
    """
    检查是否有新版本。
    ignored_version 非空且等于 latest 时 has_update=False（用户忽略此版本）。
    """
    pk = platform_key(system)
    try:
        release = fetch_latest_release(timeout=timeout)
    except (OSError, urllib.error.URLError, RuntimeError, ValueError, TypeError) as exc:
        logger.info("检查更新失败: %s", exc)
        return UpdateCheckResult(
            current_version=current_version,
            latest_version="",
            has_update=False,
            release=None,
            asset_name=None,
            asset_url=None,
            asset_size=0,
            platform_key=pk,
            error=_format_http_error(exc),
        )

    newer = is_newer_version(release.version, current_version)
    if ignored_version and normalize_tag_version(ignored_version) == release.version:
        newer = False

    asset = select_asset(release.assets, release.version, system, machine) if newer else None
    name = str(asset.get("name") or "") if asset else None
    url = str(asset.get("browser_download_url") or "") if asset else None
    size = int(asset.get("size") or 0) if asset else 0

    # 有新版本但本平台无包：仍 has_update，但 asset 为空，UI 引导打开网页
    return UpdateCheckResult(
        current_version=current_version,
        latest_version=release.version,
        has_update=newer,
        release=release,
        asset_name=name or None,
        asset_url=url or None,
        asset_size=size,
        platform_key=pk,
        error=None,
    )
