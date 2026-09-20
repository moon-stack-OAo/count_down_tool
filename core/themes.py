# -*- coding: utf-8 -*-
"""预设主题定义与解析。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_THEME_ID = "slate_cyan"

# #RGB / #RRGGBB / #RRGGBBAA
_HEX_COLOR_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def _with_aliases(colors: Dict[str, str]) -> Dict[str, str]:
    """补齐设计规范别名键，保持旧键兼容。"""
    out = dict(colors)
    out.setdefault("border_subtle", out.get("card_border", out["border"]))
    out.setdefault("text_secondary", out["text_dim"])
    out.setdefault("muted", out["text_muted"])
    out.setdefault("accent_muted", out["accent_soft"])
    out.setdefault("chip_active", out.get("accent_soft", out["chip"]))
    out.setdefault("chip_text", out.get("accent_glow", out["text"]))
    out.setdefault("toast_bg", out["card"])
    out.setdefault("tab_active", out["accent"])
    out.setdefault("input_focus", out["accent"])
    out.setdefault("info", out["accent"])
    out.setdefault("btn_danger_bg", out.get("btn_hover_close", out["error"]))
    out.setdefault("btn_danger_fg", out["white"])
    return out


# 完整 colors 键与主程序 COLORS 兼容（视觉焕新：精致深色工具风）
_SLATE_CYAN_COLORS = _with_aliases(
    {
        "bg": "#0F172A",
        "card": "#1E293B",
        "card_border": "#334155",
        "glass": "#243447",
        "accent": "#38BDF8",
        "accent_hover": "#7DD3FC",
        "accent_glow": "#7DD3FC",
        "accent_soft": "#0C4A6E",
        "success": "#34D399",
        "error": "#F87171",
        "warning": "#FBBF24",
        "text": "#F1F5F9",
        "text_dim": "#94A3B8",
        "text_muted": "#64748B",
        "input_bg": "#152033",
        "border": "#334155",
        "title_bar": "#0F172A",
        "chip": "#1E3A4F",
        "chip_hover": "#2A4A62",
        "chip_active": "#164E63",
        "chip_text": "#E0F2FE",
        "btn_default": "#334155",
        "btn_hover_min": "#FBBF24",
        "btn_hover_close": "#EF4444",
        "white": "#FFFFFF",
        "btn_primary": "#38BDF8",
        "btn_primary_hover": "#7DD3FC",
        "btn_running": "#FBBF24",
        "btn_running_hover": "#F59E0B",
        "btn_finished": "#34D399",
        "btn_finished_hover": "#22C55E",
        "btn_on_primary": "#0C1222",
        "toast_bg": "#1E293B",
        "border_subtle": "#2A3648",
    }
)

_MIDNIGHT_PURPLE_COLORS = _with_aliases(
    {
        "bg": "#0F0A1A",
        "card": "#1A1228",
        "card_border": "#2E2440",
        "glass": "#221830",
        "accent": "#C084FC",
        "accent_hover": "#D8B4FE",
        "accent_glow": "#D8B4FE",
        "accent_soft": "#4C1D95",
        "success": "#34D399",
        "error": "#F87171",
        "warning": "#FBBF24",
        "text": "#F3E8FF",
        "text_dim": "#C4B5FD",
        "text_muted": "#A78BBA",
        "input_bg": "#140E20",
        "border": "#2E2440",
        "title_bar": "#0F0A1A",
        "chip": "#241A38",
        "chip_hover": "#342A4A",
        "chip_active": "#3B0764",
        "chip_text": "#F3E8FF",
        "btn_default": "#3D3555",
        "btn_hover_min": "#FBBF24",
        "btn_hover_close": "#EF4444",
        "white": "#FFFFFF",
        "btn_primary": "#C084FC",
        "btn_primary_hover": "#D8B4FE",
        "btn_running": "#FBBF24",
        "btn_running_hover": "#F59E0B",
        "btn_finished": "#34D399",
        "btn_finished_hover": "#22C55E",
        "btn_on_primary": "#1A0B2E",
        "toast_bg": "#1A1228",
        "border_subtle": "#241C36",
    }
)

_WARM_AMBER_COLORS = _with_aliases(
    {
        "bg": "#1A1208",
        "card": "#261C0F",
        "card_border": "#3D2E1A",
        "glass": "#2E2214",
        "accent": "#FBBF24",
        "accent_hover": "#FCD34D",
        "accent_glow": "#FCD34D",
        "accent_soft": "#78350F",
        "success": "#34D399",
        "error": "#F87171",
        "warning": "#FBBF24",
        "text": "#FFF7ED",
        "text_dim": "#D6D3D1",
        "text_muted": "#A8A29E",
        "input_bg": "#1C140A",
        "border": "#3D2E1A",
        "title_bar": "#1A1208",
        "chip": "#2A2116",
        "chip_hover": "#3F3120",
        "chip_active": "#92400E",
        "chip_text": "#FFFBEB",
        "btn_default": "#4A3B28",
        "btn_hover_min": "#FBBF24",
        "btn_hover_close": "#EF4444",
        "white": "#FFFFFF",
        "btn_primary": "#FBBF24",
        "btn_primary_hover": "#FCD34D",
        "btn_running": "#F59E0B",
        "btn_running_hover": "#D97706",
        "btn_finished": "#34D399",
        "btn_finished_hover": "#22C55E",
        "btn_on_primary": "#1C1408",
        "toast_bg": "#261C0F",
        "border_subtle": "#322618",
    }
)

_EMERALD_COLORS = _with_aliases(
    {
        "bg": "#0A1410",
        "card": "#12201A",
        "card_border": "#1E332A",
        "glass": "#163028",
        "accent": "#34D399",
        "accent_hover": "#6EE7B7",
        "accent_glow": "#6EE7B7",
        "accent_soft": "#064E3B",
        "success": "#34D399",
        "error": "#F87171",
        "warning": "#FBBF24",
        "text": "#ECFDF5",
        "text_dim": "#A7F3D0",
        "text_muted": "#6B9080",
        "input_bg": "#0E1A14",
        "border": "#1E332A",
        "title_bar": "#0A1410",
        "chip": "#163028",
        "chip_hover": "#224538",
        "chip_active": "#065F46",
        "chip_text": "#D1FAE5",
        "btn_default": "#2A4A3C",
        "btn_hover_min": "#FBBF24",
        "btn_hover_close": "#EF4444",
        "white": "#FFFFFF",
        "btn_primary": "#34D399",
        "btn_primary_hover": "#6EE7B7",
        "btn_running": "#FBBF24",
        "btn_running_hover": "#F59E0B",
        "btn_finished": "#34D399",
        "btn_finished_hover": "#22C55E",
        "btn_on_primary": "#052E1C",
        "toast_bg": "#12201A",
        "border_subtle": "#183028",
    }
)

# 浅色：title_bar 用浅灰，避免 Windows transparentcolor 纯白误抠。
# 对比度约定（勿大改色值）：text≠bg、accent≠bg、btn_on_primary 与 btn_primary 可辨。
_LIGHT_COLORS = _with_aliases(
    {
        "bg": "#F1F5F9",
        "card": "#FFFFFF",
        "card_border": "#CBD5E1",
        "glass": "#E8EEF5",
        "accent": "#0284C7",
        "accent_hover": "#0369A1",
        "accent_glow": "#0EA5E9",
        "accent_soft": "#BAE6FD",
        "success": "#16A34A",
        "error": "#E11D48",
        "warning": "#D97706",
        "text": "#0F172A",
        "text_dim": "#475569",
        "text_muted": "#64748B",
        "input_bg": "#FFFFFF",
        "border": "#CBD5E1",
        "title_bar": "#E2E8F0",
        "chip": "#E0F2FE",
        "chip_hover": "#BAE6FD",
        "chip_active": "#BAE6FD",
        "chip_text": "#0C4A6E",
        "btn_default": "#94A3B8",
        "btn_hover_min": "#D97706",
        "btn_hover_close": "#E11D48",
        "white": "#FFFFFF",
        "btn_primary": "#0284C7",
        "btn_primary_hover": "#0369A1",
        "btn_running": "#D97706",
        "btn_running_hover": "#B45309",
        "btn_finished": "#16A34A",
        "btn_finished_hover": "#15803D",
        "btn_on_primary": "#FFFFFF",
        "toast_bg": "#FFFFFF",
        "border_subtle": "#E2E8F0",
    }
)

THEMES: Dict[str, Dict[str, Any]] = {
    "slate_cyan": {
        "name": "石板青蓝",
        "colors": dict(_SLATE_CYAN_COLORS),
    },
    "midnight_purple": {
        "name": "暗夜紫",
        "colors": dict(_MIDNIGHT_PURPLE_COLORS),
    },
    "warm_amber": {
        "name": "暖琥珀",
        "colors": dict(_WARM_AMBER_COLORS),
    },
    "emerald": {
        "name": "翠绿",
        "colors": dict(_EMERALD_COLORS),
    },
    "light": {
        "name": "浅色",
        "colors": dict(_LIGHT_COLORS),
    },
}


def list_themes() -> List[Tuple[str, str]]:
    """返回 [(theme_id, name), ...]，顺序与 THEMES 定义一致。"""
    return [(tid, meta["name"]) for tid, meta in THEMES.items()]


def is_valid_theme_id(theme_id: Any) -> bool:
    return isinstance(theme_id, str) and theme_id in THEMES


def is_valid_hex_color(value: Any) -> bool:
    """校验主题自定义色值（#RGB / #RRGGBB / #RRGGBBAA）。"""
    return isinstance(value, str) and bool(_HEX_COLOR_RE.match(value.strip()))


def sanitize_theme_custom(custom: Any) -> Optional[Dict[str, str]]:
    """过滤非法 theme_custom 色值；无有效项返回 None。"""
    if not isinstance(custom, dict):
        return None
    cleaned: Dict[str, str] = {}
    for key, value in custom.items():
        if not isinstance(key, str) or not key:
            continue
        if is_valid_hex_color(value):
            cleaned[key] = value.strip()
    return cleaned or None


def resolve_theme(
    theme_id: Optional[str] = None,
    custom: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    解析主题颜色。
    未知 id 回退 DEFAULT_THEME_ID；custom 为 dict 时仅合法 hex 覆盖对应键。
    """
    tid = theme_id if is_valid_theme_id(theme_id) else DEFAULT_THEME_ID
    colors = dict(THEMES[tid]["colors"])
    sanitized = sanitize_theme_custom(custom)
    if sanitized:
        for key, value in sanitized.items():
            if key in colors:
                colors[key] = value
    return colors
