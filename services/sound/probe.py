# -*- coding: utf-8 -*-
"""音频时长探测。"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from typing import Optional

from services.sound.constants import _DEFAULT_AUDIO_SECONDS

logger = logging.getLogger("count_down_tool")

_AFINFO_DURATION_RE = re.compile(
    r"(?:estimated\s+duration|duration)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*sec",
    re.IGNORECASE,
)


def _pkg():
    import services.sound as m

    return m


def _estimate_audio_seconds(path: str) -> float:
    """粗估时长（秒），用于菜单「停止」可点状态；失败则给保守上限。"""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".wav", ".wave"):
        try:
            import wave

            with wave.open(path, "rb") as w:
                rate = float(w.getframerate() or 1)
                return max(0.3, w.getnframes() / rate + 0.2)
        except (OSError, TypeError, ValueError, ZeroDivisionError, ImportError):
            # wave.Error 等损坏/非标准 wav 时粗估回退
            pass
    return _DEFAULT_AUDIO_SECONDS


def _parse_afinfo_duration(text: str) -> Optional[float]:
    """从 afinfo 输出解析时长（秒）。"""
    if not text:
        return None
    m = _AFINFO_DURATION_RE.search(text)
    if not m:
        return None
    try:
        sec = float(m.group(1))
    except ValueError:
        return None
    if sec <= 0:
        return None
    return max(0.3, sec + 0.2)


def _probe_macos_audio_seconds(path: str) -> float:
    """macOS：优先 afinfo 读真实时长，失败再粗估。"""
    S = _pkg()
    try:
        r = S.subprocess.run(
            ["afinfo", path],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        blob = (r.stdout or "") + "\n" + (r.stderr or "")
        sec = S._parse_afinfo_duration(blob)
        if sec is not None:
            return sec
    except (OSError, subprocess.SubprocessError, TimeoutError, TypeError, ValueError):
        logger.debug("afinfo 探测时长失败: %s", path, exc_info=True)
    return S._estimate_audio_seconds(path)
