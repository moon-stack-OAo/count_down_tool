# -*- coding: utf-8 -*-
"""Tk after 定时器安全取消与退出时统一清理。

避免 master.destroy 后仍有 after 回调触发 TclError（幽灵回调）。
"""

from __future__ import annotations

import logging
import tkinter as tk
from typing import Any, Iterable, Optional

logger = logging.getLogger("count_down_tool")

# CountdownApp 及其 duck-type 上登记的周期性 / debounce timer 属性名
APP_TIMER_ATTRS: tuple[str, ...] = (
    "_show_poll_timer_id",
    "_clock_timer_id",
    "_countdown_timer_id",
    "_alarm_timer_id",
    "_error_timer_id",
    "_mini_geo_save_id",
    "_mini_topmost_timer_id",  # mac Mini 周期性 topmost 保活
    "_startup_health_timer_id",
    "_startup_update_timer_id",
)


def safe_after_cancel(widget: Any, timer_id: Any) -> bool:
    """取消 after 定时器；窗口已毁时吞掉 TclError/ValueError。

    Returns:
        True 表示尝试了 after_cancel 且未异常；False 表示跳过或取消失败。
    """
    if timer_id is None or widget is None:
        return False
    try:
        widget.after_cancel(timer_id)
        return True
    except (tk.TclError, ValueError):
        return False
    except AttributeError:
        # Fake / 无 after_cancel 的对象
        return False


def cancel_timer_attr(
    owner: Any,
    attr_name: str,
    *,
    widget: Any = None,
) -> None:
    """读取 owner.attr_name 上的 id，安全 cancel 后置为 None。"""
    tid = getattr(owner, attr_name, None)
    if tid is None:
        return
    w = widget
    if w is None:
        w = getattr(owner, "master", None)
    safe_after_cancel(w, tid)
    try:
        setattr(owner, attr_name, None)
    except (AttributeError, TypeError):
        # property 只读或 owner 异常时忽略
        logger.debug("清空 timer 属性 %s 失败", attr_name, exc_info=True)


def cancel_all_timers(
    app: Any,
    *,
    attrs: Optional[Iterable[str]] = None,
    widget: Any = None,
) -> None:
    """退出前统一 cancel 应用上登记的全部 after id。"""
    master = widget if widget is not None else getattr(app, "master", None)
    for name in attrs if attrs is not None else APP_TIMER_ATTRS:
        cancel_timer_attr(app, name, widget=master)
