# -*- coding: utf-8 -*-
"""UI 动作端口：services 只经 app.ui_actions 触达 UI，禁止 import ui。

装配：CountdownApp 初始化时调用 bind_default_ui_actions(app)。
测试：给 app.ui_actions 挂 mock / SimpleNamespace 即可注入。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol, runtime_checkable

logger = logging.getLogger("count_down_tool")


@runtime_checkable
class UIActions(Protocol):
    """services 层可见的 UI 能力集合。"""

    show_settings: Callable[..., Any]
    show_info: Callable[..., Any]
    show_error: Callable[..., Any]
    reset_mini_size: Callable[..., Any]
    show_mini_text_picker: Callable[..., Any]
    show_update_available: Callable[..., Any]
    show_update_progress: Callable[..., Any]
    update_progress: Callable[..., Any]
    close_progress: Callable[..., Any]
    refresh_update_badge: Callable[..., Any]


@dataclass
class UIActionsBundle:
    """可注入的具体实现（函数引用）。"""

    show_settings: Callable[..., Any]
    show_info: Callable[..., Any]
    show_error: Callable[..., Any]
    reset_mini_size: Callable[..., Any]
    show_mini_text_picker: Callable[..., Any]
    show_update_available: Callable[..., Any]
    show_update_progress: Callable[..., Any]
    update_progress: Callable[..., Any]
    close_progress: Callable[..., Any]
    refresh_update_badge: Callable[..., Any]


def bind_default_ui_actions(app) -> UIActionsBundle:
    """把真实 UI 函数绑到 app.ui_actions（仅在装配点调用，此处可 import ui）。"""
    from ui.app_dialogs import show_error, show_info
    from ui.full_window import refresh_update_badge
    from ui.mini_text_picker import show_mini_text_picker
    from ui.mini_window import reset_mini_size
    from ui.settings_window import show_settings
    from ui.update_dialog import (
        close_progress,
        show_update_available,
        show_update_progress,
        update_progress,
    )

    bundle = UIActionsBundle(
        show_settings=show_settings,
        show_info=show_info,
        show_error=show_error,
        reset_mini_size=reset_mini_size,
        show_mini_text_picker=show_mini_text_picker,
        show_update_available=show_update_available,
        show_update_progress=show_update_progress,
        update_progress=update_progress,
        close_progress=close_progress,
        refresh_update_badge=refresh_update_badge,
    )
    app.ui_actions = bundle
    return bundle


def get_ui_actions(app) -> Optional[Any]:
    """读取 app.ui_actions；未装配返回 None。"""
    return getattr(app, "ui_actions", None)


def call_ui(app, name: str, *args, default=None, **kwargs):
    """安全调用 app.ui_actions.<name>(*args, **kwargs)。"""
    ui = get_ui_actions(app)
    if ui is None:
        logger.debug("ui_actions 未装配，跳过 %s", name)
        return default
    fn = getattr(ui, name, None)
    if not callable(fn):
        logger.debug("ui_actions.%s 不可用", name)
        return default
    try:
        return fn(*args, **kwargs)
    except Exception:
        # UI 回调边界：不因弹窗失败打断业务
        logger.debug("ui_actions.%s 调用失败", name, exc_info=True)
        return default
