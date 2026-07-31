# -*- coding: utf-8 -*-
"""更新相关数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


class DownloadCancelled(RuntimeError):
    """用户取消下载。"""


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
