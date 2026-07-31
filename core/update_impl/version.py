# -*- coding: utf-8 -*-
"""版本解析与平台资产选择。"""

from __future__ import annotations

import platform
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple


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

