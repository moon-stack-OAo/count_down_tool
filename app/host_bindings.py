# -*- coding: utf-8 -*-
"""宿主 state/runtime 字段 → app._xxx 属性绑定。

用 dataclass fields 批量生成 property，替代 CountdownApp 上手写数十个
@property / setter，保持 duck-type（app._theme_id 等）读写语义不变。
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from app.state import CountdownRuntime, PersistedState

T = TypeVar("T")

# setter 规范化（与原先手写 property 一致）
_PERSISTED_COERCE: Dict[str, Callable[[Any], Any]] = {
    "sound_muted": bool,
    "autostart": bool,
    "check_update_on_start": bool,
    "transparent_mode": bool,
    "sound_history": lambda v: v if v is not None else [],
    "last_update_check": lambda v: v if v is not None else "",
    "ignored_update_version": lambda v: v if v is not None else "",
    "mini_text": lambda v: v if v is not None else {},
}

_RUNTIME_COERCE: Dict[str, Callable[[Any], Any]] = {
    "applying_preset": bool,
    "duration_total_seconds": lambda v: float(v) if v is not None else 0.0,
    "progress_value": lambda v: float(v) if v is not None else 0.0,
    "alarm_count": lambda v: int(v) if v is not None else 0,
}


def _bind_property(
    container_attr: str,
    field_name: str,
    coerce: Optional[Callable[[Any], Any]] = None,
) -> property:
    """生成 app._<field> ↔ getattr(self, container).<field> 的 property。"""

    def getter(self):
        return getattr(getattr(self, container_attr), field_name)

    if coerce is None:

        def setter(self, value):
            setattr(getattr(self, container_attr), field_name, value)

    else:

        def setter(self, value, _coerce=coerce):  # type: ignore[misc]
            setattr(getattr(self, container_attr), field_name, _coerce(value))

    return property(getter, setter)


def install_state_properties(cls: Type[T]) -> Type[T]:
    """在类上安装 PersistedState / CountdownRuntime 全部 _field 属性。

    要求实例具备：
      - self.state: PersistedState
      - self._runtime: CountdownRuntime
    """
    for f in fields(PersistedState):
        attr = f"_{f.name}"
        if attr in cls.__dict__:
            continue
        setattr(
            cls,
            attr,
            _bind_property("state", f.name, _PERSISTED_COERCE.get(f.name)),
        )
    for f in fields(CountdownRuntime):
        attr = f"_{f.name}"
        if attr in cls.__dict__:
            continue
        setattr(
            cls,
            attr,
            _bind_property("_runtime", f.name, _RUNTIME_COERCE.get(f.name)),
        )
    return cls
