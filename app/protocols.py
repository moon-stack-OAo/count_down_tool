# -*- coding: utf-8 -*-
"""宿主能力 Protocol：小而专，供控制器/配置层类型注解。

不要求运行时 isinstance 校验；字段与方法与 CountdownApp 实际挂载一致。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class ConfigHost(Protocol):
    """配置读写相关字段与方法。"""

    _config_file: str
    _loaded_keys: set
    _theme_id: str
    _theme_custom: Optional[Dict[str, Any]]
    _sound_muted: bool
    _sound_id: str
    _sound_path: str
    _sound_history: List[Any]
    _autostart: bool
    _check_update_on_start: bool
    _last_update_check: str
    _ignored_update_version: str
    _startup_mode: str
    _last_mode: str
    _transparent_mode: bool
    _mini_pos: Optional[Tuple[int, int]]
    _mini_size: Optional[Tuple[int, int]]
    _mini_text: Dict[str, Any]
    _is_mini: bool
    COLORS: Dict[str, str]

    def _load_config(self) -> None: ...

    def _save_config(self) -> None: ...


@runtime_checkable
class CountdownHost(Protocol):
    """倒计时运行时字段与主窗口引用。"""

    master: Any
    running: bool
    _state: str
    _countdown_timer_id: Any
    _preset_duration: Any
    _applying_preset: bool
    _duration_total_seconds: float
    _progress_value: float
    _paused_remaining: Optional[float]
    _time_spinboxes: list
    _preset_chips: list
    progress_canvas: Any
    _alarm_count: int
    _alarm_timer_id: Any
    _bell_count: int
    _error_timer_id: Any
    btn_start: Any
    target_time: Any
    countdown_text: str
    COLORS: Dict[str, str]
    FONTS: Any

    def _sync_mini_state(self) -> None: ...

    def show_error(self, message: str) -> None: ...


@runtime_checkable
class ThemeHost(Protocol):
    """主题相关字段与应用入口。"""

    _theme_id: str
    _theme_custom: Optional[Dict[str, Any]]
    COLORS: Dict[str, str]
    master: Any
    _state: str
    _is_mini: bool
    countdown_text: str
    target_time: Any
    btn_start: Any

    def _setup_styles(self) -> None: ...

    def _setup_ui(self) -> None: ...

    def _save_config(self) -> None: ...

    def _apply_theme(self, theme_id: str) -> None: ...


@runtime_checkable
class ModeHost(Protocol):
    """完整 / Mini / 托盘 模式相关。"""

    master: Any
    _is_mini: bool
    _last_mode: str
    _transparent_mode: bool
    _first_hide: bool
    mini_window: Any
    tray_icon: Any
    _status_menu_active: bool

    def _create_mini_window(self) -> None: ...

    def _destroy_mini_window(self) -> None: ...

    def _recreate_mini_window(self) -> None: ...

    def _set_taskbar_visible(self) -> None: ...

    def _bring_full_to_front(self) -> None: ...

    def _center_window_later(self) -> None: ...

    def _quit_app(self) -> None: ...

    def _save_config(self) -> None: ...


@runtime_checkable
class UpdateHost(Protocol):
    """自动更新相关字段。"""

    master: Any
    _check_update_on_start: bool
    _last_update_check: str
    _ignored_update_version: str
    _pending_update_result: Any

    def _save_config(self) -> None: ...

    def _quit_app(self) -> None: ...
