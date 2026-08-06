# -*- coding: utf-8 -*-
"""host_bindings：state/runtime → app._xxx 属性绑定。"""

from __future__ import annotations

from app.host_bindings import install_state_properties
from app.state import CountdownRuntime, PersistedState
from core.countdown_core import STATE_IDLE


@install_state_properties
class FakeHost:
    """最小宿主：只挂 state/_runtime，验证绑定读写。"""

    def __init__(self):
        self.state = PersistedState()
        self._runtime = CountdownRuntime()


class TestInstallStateProperties:
    def test_persisted_roundtrip(self):
        h = FakeHost()
        assert h._theme_id == h.state.theme_id
        h._theme_id = "nord"
        assert h.state.theme_id == "nord"
        assert h._theme_id == "nord"

        h._sound_muted = 1  # coerce bool
        assert h.state.sound_muted is True
        assert h._sound_muted is True

        h._autostart = 0
        assert h.state.autostart is False

        h._sound_history = None
        assert h.state.sound_history == []

        h._last_update_check = None
        assert h.state.last_update_check == ""

        h._ignored_update_version = None
        assert h.state.ignored_update_version == ""

        h._mini_text = None
        assert h.state.mini_text == {}

        h._mini_pos = (10, 20)
        assert h.state.mini_pos == (10, 20)
        assert h._mini_pos == (10, 20)

    def test_runtime_roundtrip(self):
        h = FakeHost()
        assert h._state == STATE_IDLE
        h._state = "running"
        assert h._runtime.state == "running"
        assert h._state == "running"

        h._applying_preset = 1
        assert h._runtime.applying_preset is True

        h._duration_total_seconds = None
        assert h._runtime.duration_total_seconds == 0.0

        h._progress_value = "3.5"
        assert h._runtime.progress_value == 3.5

        h._alarm_count = None
        assert h._runtime.alarm_count == 0
        h._alarm_count = 4
        assert h._runtime.alarm_count == 4

        h._countdown_timer_id = "tid-1"
        assert h._runtime.countdown_timer_id == "tid-1"

    def test_all_persisted_and_runtime_fields_bound(self):
        from dataclasses import fields

        h = FakeHost()
        for f in fields(PersistedState):
            assert hasattr(FakeHost, f"_{f.name}")
            getattr(h, f"_{f.name}")  # 可读
        for f in fields(CountdownRuntime):
            assert hasattr(FakeHost, f"_{f.name}")
            getattr(h, f"_{f.name}")

    def test_idempotent_install_skips_existing(self):
        """已有同名 attr 时不再覆盖。"""

        class WithOverride:
            @property
            def _theme_id(self):
                return "hardcoded"

            def __init__(self):
                self.state = PersistedState()
                self._runtime = CountdownRuntime()

        install_state_properties(WithOverride)
        w = WithOverride()
        assert w._theme_id == "hardcoded"
        # 其它字段仍绑定
        w._sound_id = "beep"
        assert w.state.sound_id == "beep"

    def test_countdown_app_has_bindings(self):
        """真实 CountdownApp 类上已装绑定（不实例化 Tk）。"""
        from count_down_tool import CountdownApp
        from dataclasses import fields

        for f in fields(PersistedState):
            assert isinstance(getattr(CountdownApp, f"_{f.name}"), property)
        for f in fields(CountdownRuntime):
            assert isinstance(getattr(CountdownApp, f"_{f.name}"), property)
