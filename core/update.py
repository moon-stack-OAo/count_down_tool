# -*- coding: utf-8 -*-
"""自动更新：查 GitHub Release、下载；Windows 可替换 exe，macOS 仅下载。"""

from __future__ import annotations

import html as html_lib
import json
import logging
import os
import platform
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("count_down_tool.update")

# 与 origin 一致；公开仓库无需 token
GITHUB_OWNER = "moon-stack-OAo"
GITHUB_REPO = "count_down_tool"
GITHUB_API_LATEST = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
GITHUB_RELEASES_PAGE = (
    f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
USER_AGENT = f"{GITHUB_REPO}-updater"

ProgressCb = Optional[Callable[[int, int], None]]  # received, total(-1 if unknown)


@dataclass(frozen=True)
class ReleaseInfo:
    """最新 Release 摘要。"""

    version: str
    tag_name: str
    body: str
    html_url: str
    assets: Tuple[Dict[str, Any], ...]


@dataclass(frozen=True)
class UpdateCheckResult:
    """版本检查结果。"""

    current_version: str
    latest_version: str
    has_update: bool
    release: Optional[ReleaseInfo]
    asset_name: Optional[str]
    asset_url: Optional[str]
    asset_size: int
    platform_key: str  # windows | darwin | other
    error: Optional[str] = None


def parse_version(text: str) -> Tuple[int, int, int]:
    """将 v1.2.3 / 1.2.3-beta 等解析为 (major, minor, patch)。"""
    s = (text or "").strip()
    if s.lower().startswith("v"):
        s = s[1:]
    parts: List[int] = []
    for chunk in s.split("."):
        m = re.match(r"(\d+)", chunk)
        parts.append(int(m.group(1)) if m else 0)
        if len(parts) >= 3:
            break
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def is_newer_version(remote: str, local: str) -> bool:
    """remote 是否严格大于 local。"""
    return parse_version(remote) > parse_version(local)


def normalize_tag_version(tag: str) -> str:
    t = (tag or "").strip()
    if t.lower().startswith("v"):
        t = t[1:]
    return t


def platform_key(system: Optional[str] = None) -> str:
    s = system or platform.system()
    if s == "Windows":
        return "windows"
    if s == "Darwin":
        return "darwin"
    return "other"


def platform_asset_suffix(
    system: Optional[str] = None,
    machine: Optional[str] = None,
) -> Optional[str]:
    """
    返回 Release 附件后缀（不含版本前缀）。
    例：win64.zip / mac-arm64.zip / mac-x86_64.zip
    """
    sys_name = system or platform.system()
    mach = (machine or platform.machine() or "").lower()
    if sys_name == "Windows":
        return "win64.zip"
    if sys_name == "Darwin":
        if mach in ("arm64", "aarch64"):
            return "mac-arm64.zip"
        return "mac-x86_64.zip"
    return None


def expected_asset_name(version: str, system: Optional[str] = None, machine: Optional[str] = None) -> Optional[str]:
    suffix = platform_asset_suffix(system, machine)
    if not suffix:
        return None
    ver = normalize_tag_version(version)
    return f"count_down_tool-{ver}-{suffix}"


def select_asset(
    assets: Sequence[Dict[str, Any]],
    version: str,
    system: Optional[str] = None,
    machine: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """按平台从 assets 中选中 zip；优先精确文件名，再按后缀匹配。"""
    want = expected_asset_name(version, system, machine)
    suffix = platform_asset_suffix(system, machine)
    if not suffix:
        return None
    by_name = {str(a.get("name") or ""): a for a in assets if isinstance(a, dict)}
    if want and want in by_name:
        return by_name[want]
    # 宽松：名字以正确后缀结尾
    for name, asset in by_name.items():
        if name.endswith(suffix) and name.startswith("count_down_tool-"):
            return asset
    return None


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
    except Exception as exc:
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
    except Exception as exc:
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
    except Exception as exc:
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
    except Exception as web_exc:
        logger.info("网页方式检查更新失败，回退 API: %s", web_exc)

    # 2) API 回退（可能触发未认证限流）
    try:
        data = _http_get_json(GITHUB_API_LATEST, timeout=timeout)
    except Exception as api_exc:
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
    except Exception as exc:
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


def download_file(
    url: str,
    dest_path: str,
    timeout: float = 60.0,
    progress: ProgressCb = None,
    expected_size: int = 0,
) -> str:
    """下载到 dest_path，返回绝对路径。

    若响应带 Content-Length 或传入 expected_size>0，则校验完整；
    不完整时删除半成品并抛错，避免坏包触发 onefile 启动失败。
    """
    abs_dest = os.path.abspath(dest_path)
    os.makedirs(os.path.dirname(abs_dest) or ".", exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = -1
            try:
                total = int(resp.headers.get("Content-Length") or -1)
            except (TypeError, ValueError):
                total = -1
            if expected_size and expected_size > 0:
                if total > 0 and total != int(expected_size):
                    raise RuntimeError(
                        f"下载大小与发布信息不一致（期望 {expected_size}，响应 {total}）"
                    )
                if total <= 0:
                    total = int(expected_size)
            received = 0
            chunk = 64 * 1024
            with open(abs_dest, "wb") as out:
                while True:
                    buf = resp.read(chunk)
                    if not buf:
                        break
                    out.write(buf)
                    received += len(buf)
                    if progress:
                        progress(received, total)
        if total > 0 and received != total:
            raise RuntimeError(
                f"下载不完整（已收 {received} / 期望 {total} 字节），请重试"
            )
        if received <= 0:
            raise RuntimeError("下载结果为空文件")
        # 磁盘落盘后再读一次长度，防止缓冲/杀软截断
        on_disk = os.path.getsize(abs_dest)
        if total > 0 and on_disk != total:
            raise RuntimeError(
                f"落盘文件大小异常（磁盘 {on_disk} / 期望 {total} 字节）"
            )
        if expected_size and expected_size > 0 and on_disk != int(expected_size):
            raise RuntimeError(
                f"落盘文件与发布大小不符（磁盘 {on_disk} / 期望 {expected_size}）"
            )
    except Exception:
        try:
            if os.path.isfile(abs_dest):
                os.remove(abs_dest)
        except OSError:
            pass
        raise
    return abs_dest


def extract_windows_exe(zip_path: str, dest_dir: str) -> str:
    """从 win zip 中取出 count_down_tool.exe，返回 exe 绝对路径。"""
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        # 先校验 zip 本身
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"更新包损坏（zip 校验失败: {bad}）")
        names = zf.namelist()
        exe_name = None
        for n in names:
            base = os.path.basename(n.replace("\\", "/"))
            if base.lower() == "count_down_tool.exe":
                exe_name = n
                break
        if not exe_name:
            raise FileNotFoundError("zip 中未找到 count_down_tool.exe")
        target = os.path.join(dest_dir, "count_down_tool.exe")
        with zf.open(exe_name) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
    abs_target = os.path.abspath(target)
    size = os.path.getsize(abs_target)
    if size < 1024:
        raise RuntimeError(f"解压得到的 exe 过小（{size} 字节），包可能损坏")
    with open(abs_target, "rb") as f:
        magic = f.read(2)
    if magic != b"MZ":
        raise RuntimeError("解压得到的文件不是有效 Windows 可执行文件")
    return abs_target


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def current_executable_path() -> str:
    """打包后为 exe/.app 内可执行路径；开发态为 python。"""
    return os.path.abspath(sys.executable)


def default_download_dir() -> str:
    """用户下载目录；失败则用临时目录。"""
    home = os.path.expanduser("~")
    for name in ("Downloads", "下载"):
        p = os.path.join(home, name)
        if os.path.isdir(p):
            return p
    return tempfile.gettempdir()


def _ps_single_quoted(path: str) -> str:
    """PowerShell 单引号字符串（内部 ' 写成 ''）。"""
    return "'" + (path or "").replace("'", "''") + "'"


def write_windows_replace_script(
    script_path: str,
    target_exe: str,
    source_exe: str,
    pid: int,
    zip_path: Optional[str] = None,
) -> str:
    """
    生成静默 PowerShell：等待 PID 退出 → 重试覆盖 → 校验 → 延迟启动 → 清理。
    不再使用 bat + tasklist/find（易弹黑窗、find 误匹配死循环）。
    返回 script_path。
    """
    target_abs = os.path.abspath(target_exe)
    source_abs = os.path.abspath(source_exe)
    target_dir = os.path.dirname(target_abs) or "."
    zip_abs = os.path.abspath(zip_path) if zip_path else ""
    # 延迟启动：给 Defender / 句柄释放时间，降低 onefile _MEI 加载失败
    lines = [
        "$ErrorActionPreference = 'Stop'",
        f"$target = {_ps_single_quoted(target_abs)}",
        f"$source = {_ps_single_quoted(source_abs)}",
        f"$targetDir = {_ps_single_quoted(target_dir)}",
        f"$pidWait = {int(pid)}",
        f"$zipPath = {_ps_single_quoted(zip_abs)}",
        "$self = $MyInvocation.MyCommand.Path",
        # 等待旧进程退出（最多约 120 秒，避免永久卡住）
        "$deadline = (Get-Date).AddSeconds(120)",
        "while ((Get-Date) -lt $deadline) {",
        "  $p = Get-Process -Id $pidWait -ErrorAction SilentlyContinue",
        "  if (-not $p) { break }",
        "  Start-Sleep -Milliseconds 500",
        "}",
        "Start-Sleep -Seconds 2",
        "$ok = $false",
        "for ($i = 0; $i -lt 12; $i++) {",
        "  try {",
        "    Copy-Item -LiteralPath $source -Destination $target -Force",
        "    $ss = (Get-Item -LiteralPath $source).Length",
        "    $ts = (Get-Item -LiteralPath $target).Length",
        "    if ($ss -gt 1024 -and $ss -eq $ts) { $ok = $true; break }",
        "  } catch {}",
        "  Start-Sleep -Seconds 1",
        "}",
        "if (-not $ok) { exit 1 }",
        "Start-Sleep -Seconds 3",
        "Start-Process -FilePath $target -WorkingDirectory $targetDir",
        "try { Remove-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue } catch {}",
        "if ($zipPath) {",
        "  try { Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue } catch {}",
        "}",
        "try { Remove-Item -LiteralPath $self -Force -ErrorAction SilentlyContinue } catch {}",
        "exit 0",
    ]
    parent = os.path.dirname(script_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    # UTF-8 BOM：Windows PowerShell 5.1 更稳妥识别中文路径
    text = "\r\n".join(lines) + "\r\n"
    with open(script_path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(text)
    return os.path.abspath(script_path)


def launch_windows_replace_and_exit_prep(
    target_exe: str,
    new_exe: str,
    zip_path: Optional[str] = None,
) -> str:
    """
    启动静默替换脚本（不等待）。调用方应随后退出进程。
    返回脚本路径。
    """
    import subprocess

    work = tempfile.mkdtemp(prefix="cdt_update_")
    script = os.path.join(work, "apply_update.ps1")
    write_windows_replace_script(
        script,
        target_exe=os.path.abspath(target_exe),
        source_exe=os.path.abspath(new_exe),
        pid=os.getpid(),
        zip_path=os.path.abspath(zip_path) if zip_path else None,
    )
    # 仅 CREATE_NO_WINDOW：DETACHED_PROCESS 在部分环境下会导致
    # powershell -File 静默起不来（替换脚本不执行）。
    creation = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creation |= subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creation |= subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    startup = None
    try:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0  # SW_HIDE
    except Exception:
        startup = None
    # 用 -Command 执行脚本内容，避免 -File + 临时目录偶发策略问题
    # 仍 -WindowStyle Hidden，不弹控制台
    ps_cmd = (
        f"$ErrorActionPreference='Stop'; "
        f"& {_ps_single_quoted(os.path.abspath(script))}"
    )
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-Command",
            ps_cmd,
        ],
        cwd=work,
        close_fds=True,
        creationflags=creation,
        startupinfo=startup,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return script


def apply_windows_update_from_zip(zip_path: str, target_exe: Optional[str] = None) -> str:
    """
    解压 zip 并启动替换脚本。返回脚本路径；调用方需退出应用。
    """
    target = target_exe or current_executable_path()
    work = tempfile.mkdtemp(prefix="cdt_new_exe_")
    new_exe = extract_windows_exe(zip_path, work)
    return launch_windows_replace_and_exit_prep(target, new_exe, zip_path=zip_path)


def truncate_release_notes(body: str, max_len: int = 600) -> str:
    text = (body or "").strip()
    if not text:
        return "（无更新说明）"
    # 去掉过长 markdown 噪声
    text = re.sub(r"\r\n", "\n", text)
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text
