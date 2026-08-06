# -*- coding: utf-8 -*-
"""结构化应用状态：持久化配置态 + 可选倒计时运行时。

与 config.json schema 对齐的字段放在 PersistedState；
app._xxx 由 app.host_bindings.install_state_properties 批量绑定，保持 duck-type 兼容。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.countdown_core import STATE_IDLE
from core.themes import DEFAULT_THEME_ID


@dataclass
class PersistedState:
    """配置态字段（与 config_store 读写一致，不改变 schema）。"""

    theme_id: str = DEFAULT_THEME_ID
    theme_custom: Optional[Dict[str, Any]] = None
    sound_muted: bool = False
    sound_id: str = "soft"
    sound_path: str = ""
    sound_history: List[Any] = field(default_factory=list)
    autostart: bool = False
    check_update_on_start: bool = True
    last_update_check: str = ""
    ignored_update_version: str = ""
    startup_mode: str = "remember"
    last_mode: str = "full"
    transparent_mode: bool = False
    mini_pos: Optional[Tuple[int, int]] = None
    mini_size: Optional[Tuple[int, int]] = None
    mini_text: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CountdownRuntime:
    """倒计时运行时（内存态，不落盘）。"""

    state: str = STATE_IDLE
    countdown_timer_id: Any = None
    preset_duration: Any = None
    applying_preset: bool = False
    duration_total_seconds: float = 0.0
    progress_value: float = 0.0
    paused_remaining: Optional[float] = None
    alarm_count: int = 0
    alarm_timer_id: Any = None
    error_timer_id: Any = None
