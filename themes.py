# -*- coding: utf-8 -*-
"""预设主题定义与解析。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

DEFAULT_THEME_ID = "slate_cyan"

# 完整 colors 键与主程序 COLORS 兼容
_SLATE_CYAN_COLORS = {
    "bg": "#0F1419",
    "card": "#1A2332",
    "card_border": "#2A3A4E",
    "glass": "#16202C",
    "accent": "#38BDF8",
    "accent_hover": "#0EA5E9",
    "accent_glow": "#7DD3FC",
    "accent_soft": "#0C4A6E",
    "success": "#4ADE80",
    "error": "#FB7185",
    "warning": "#FBBF24",
    "text": "#F1F5F9",
    "text_dim": "#8B9CB3",
    "text_muted": "#64748B",
    "input_bg": "#0C1219",
    "border": "#2A3A4E",
    "title_bar": "#0B1016",
    "chip": "#1E2A3A",
    "chip_hover": "#2A3F55",
    "btn_default": "#334155",
    "btn_hover_min": "#FBBF24",
    "btn_hover_close": "#F43F5E",
    "white": "#FFFFFF",
}

_MIDNIGHT_PURPLE_COLORS = {
    "bg": "#0D0B14",
    "card": "#1A1528",
    "card_border": "#2E2640",
    "glass": "#15101F",
    "accent": "#A78BFA",
    "accent_hover": "#8B5CF6",
    "accent_glow": "#C4B5FD",
    "accent_soft": "#4C1D95",
    "success": "#4ADE80",
    "error": "#FB7185",
    "warning": "#FBBF24",
    "text": "#F3F0FF",
    "text_dim": "#A89BC4",
    "text_muted": "#7C6F9A",
    "input_bg": "#0A0812",
    "border": "#2E2640",
    "title_bar": "#0A0810",
    "chip": "#221A33",
    "chip_hover": "#342A4A",
    "btn_default": "#3D3555",
    "btn_hover_min": "#FBBF24",
    "btn_hover_close": "#F43F5E",
    "white": "#FFFFFF",
}

_WARM_AMBER_COLORS = {
    "bg": "#14110C",
    "card": "#241C12",
    "card_border": "#3D2F1F",
    "glass": "#1C1610",
    "accent": "#F59E0B",
    "accent_hover": "#D97706",
    "accent_glow": "#FCD34D",
    "accent_soft": "#78350F",
    "success": "#4ADE80",
    "error": "#FB7185",
    "warning": "#FBBF24",
    "text": "#FFF7ED",
    "text_dim": "#C4A882",
    "text_muted": "#9A7B52",
    "input_bg": "#0F0C08",
    "border": "#3D2F1F",
    "title_bar": "#0F0C08",
    "chip": "#2A2116",
    "chip_hover": "#3F3120",
    "btn_default": "#4A3B28",
    "btn_hover_min": "#FBBF24",
    "btn_hover_close": "#F43F5E",
    "white": "#FFFFFF",
}

_EMERALD_COLORS = {
    "bg": "#0A1410",
    "card": "#12241C",
    "card_border": "#1E3A2F",
    "glass": "#0F1C16",
    "accent": "#34D399",
    "accent_hover": "#10B981",
    "accent_glow": "#6EE7B7",
    "accent_soft": "#064E3B",
    "success": "#4ADE80",
    "error": "#FB7185",
    "warning": "#FBBF24",
    "text": "#ECFDF5",
    "text_dim": "#8BB8A4",
    "text_muted": "#5C8A76",
    "input_bg": "#08120E",
    "border": "#1E3A2F",
    "title_bar": "#08120E",
    "chip": "#163028",
    "chip_hover": "#224538",
    "btn_default": "#2A4A3C",
    "btn_hover_min": "#FBBF24",
    "btn_hover_close": "#F43F5E",
    "white": "#FFFFFF",
}

# 浅色：title_bar 用浅灰，避免 Windows transparentcolor 纯白误抠
_LIGHT_COLORS = {
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
    "chip": "#E2E8F0",
    "chip_hover": "#CBD5E1",
    "btn_default": "#94A3B8",
    "btn_hover_min": "#D97706",
    "btn_hover_close": "#E11D48",
    "white": "#FFFFFF",
}

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


def resolve_theme(
    theme_id: Optional[str] = None,
    custom: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    解析主题颜色。
    未知 id 回退 DEFAULT_THEME_ID；custom 为 dict 时覆盖对应键。
    """
    tid = theme_id if is_valid_theme_id(theme_id) else DEFAULT_THEME_ID
    colors = dict(THEMES[tid]["colors"])
    if isinstance(custom, dict):
        for key, value in custom.items():
            if isinstance(key, str) and isinstance(value, str) and value:
                colors[key] = value
    return colors
