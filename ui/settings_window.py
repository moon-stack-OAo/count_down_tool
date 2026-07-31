# -*- coding: utf-8 -*-
"""设置中心：Toplevel 单例，分区管理外观 / 声音 / 系统 / 关于。

薄门面：实现见 ui.settings 包，本文件保持 import 路径兼容。
"""

from __future__ import annotations

from ui.settings.about_tab import build_about_section as _build_about_section
from ui.settings.appearance import build_appearance_section as _build_appearance_section
from ui.settings.layout import (
    bind_wheel_tree as _bind_wheel_tree,
)
from ui.settings.layout import (
    card as _card,
)
from ui.settings.layout import (
    make_scroll_page as _make_scroll_page,
)
from ui.settings.layout import (
    pill as _pill,
)
from ui.settings.shell import (
    _SETTINGS_TAB_KEYS,
    _normalize_settings_tab,
    _show_settings_impl,
    close_settings,
    get_settings_open_tab,
    show_settings,
)
from ui.settings.sound_tab import build_sound_section as _build_sound_section
from ui.settings.system_tab import (
    build_system_section as _build_system_section,
)
from ui.settings.system_tab import (
    open_path_in_file_manager as _open_path_in_file_manager,
)

__all__ = [
    "show_settings",
    "close_settings",
    "get_settings_open_tab",
    "_normalize_settings_tab",
    "_SETTINGS_TAB_KEYS",
    "_show_settings_impl",
    "_make_scroll_page",
    "_bind_wheel_tree",
    "_card",
    "_pill",
    "_build_appearance_section",
    "_build_sound_section",
    "_build_system_section",
    "_build_about_section",
    "_open_path_in_file_manager",
]
