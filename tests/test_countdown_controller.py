# -*- coding: utf-8 -*-
"""CountdownController 编排层单测（假 app + mock after）。"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.countdown import CountdownController
from core.countdown_core import (
    STATE_FINISHED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RUNNING,
)


class _FakeVar:
    def __init__(self, value="00"):
        self._v = str(value)

    def get(self):
        return self._v

    def set(self, v):
        self._v = str(v)


class _FakeLabel:
    def __init__(self):
        self.text = ""
        self.style = None
        self.kw = {}

    def config(self, **kwargs):
        self.kw.update(kwargs)
        if "text" in kwargs:
            self.text = kwargs["text"]
        if "style" in kwargs:
            self.style = kwargs["style"]


class _FakeMaster:
    def __init__(self):
        self.after_calls = []
        self.cancelled = []
        self._seq = 0

    def after(self, ms, cb=None):
        self._seq += 1
        tid = f"t{self._seq}"
        self.after_calls.append((ms, cb, tid))
        return tid

    def after_cancel(self, tid):
        self.cancelled.append(tid)


def _make_app(**over):
    master = _FakeMaster()
    app = SimpleNamespace(
        master=master,
        _state=STATE_IDLE,
        _countdown_timer_id=None,
        _alarm_timer_id=None,
        _alarm_count=0,
        _preset_duration=None,
        _applying_preset=False,
        _duration_total_seconds=0.0,
        _progress_value=0.0,
        _paused_remaining=None,
        _last_hour="18",
        _last_minute="00",
        _last_second="00",
        hour_var=_FakeVar("18"),
        minute_var=_FakeVar("00"),
        second_var=_FakeVar("00"),
        target_time=None,
        countdown_text="--:--:--",
        countdown_label=_FakeLabel(),
        target_time_label=_FakeLabel(),
        error_label=_FakeLabel(),
        progress_canvas=None,
        _progress_fill_id=None,
        _progress_track_id=None,
        btn_start=_FakeLabel(),
        COLORS={"accent": "#38BDF8", "border": "#333", "chip": "#222", "success": "#0f0"},
        FONTS={},
        _preset_chips=[],
        _time_spinboxes=[],
        _saved=[],
    )

    def _save():
        app._saved.append(
            (app._last_hour, app._last_minute, app._last_second)
        )

    def _sync():
        app._synced = True

    def _show_error(msg):
        app._last_error = msg

    app._save_config = _save
    app._sync_mini_state = _sync
    app.show_error = _show_error
    app._font = lambda *a, **k: ("Segoe UI", 10)
    for k, v in over.items():
        setattr(app, k, v)
    return app


class TestCountdownController(unittest.TestCase):
    def test_reset_restores_last_hms(self):
        app = _make_app(_last_hour="09", _last_minute="30", _last_second="15")
        ctrl = CountdownController(app)
        app.hour_var.set("12")
        app.minute_var.set("00")
        app.second_var.set("00")
        ctrl.reset()
        self.assertEqual(app.hour_var.get(), "09")
        self.assertEqual(app.minute_var.get(), "30")
        self.assertEqual(app.second_var.get(), "15")
        self.assertEqual(app._state, STATE_IDLE)
        self.assertIsNone(app.target_time)

    def test_start_remembers_last_hms(self):
        app = _make_app()
        app.hour_var.set("20")
        app.minute_var.set("15")
        app.second_var.set("30")
        ctrl = CountdownController(app)
        future = datetime.now() + timedelta(hours=10)
        with mock.patch(
            "app.countdown.target_from_hms",
            return_value=future,
        ):
            with mock.patch.object(CountdownController, "update_countdown"):
                ctrl.start_countdown()
        self.assertEqual(app._last_hour, "20")
        self.assertEqual(app._last_minute, "15")
        self.assertEqual(app._last_second, "30")
        self.assertTrue(app._saved)

    def test_set_preset_force_when_running(self):
        app = _make_app(_state=STATE_RUNNING)
        app.target_time = datetime.now() + timedelta(hours=1)
        ctrl = CountdownController(app)
        fixed = datetime(2026, 8, 7, 12, 0, 0)
        with mock.patch("app.countdown.datetime") as dt:
            dt.now.return_value = fixed
            # 允许真实 target_from_duration
            ctrl.set_preset_time(0, 5, 0, force=True)
        self.assertEqual(app._state, STATE_RUNNING)
        self.assertIsNotNone(app._preset_duration)
        self.assertAlmostEqual(
            app._preset_duration.total_seconds(), 300, places=0
        )

    def test_set_preset_blocked_when_running_without_force(self):
        app = _make_app(_state=STATE_RUNNING)
        before = app.hour_var.get()
        ctrl = CountdownController(app)
        ctrl.set_preset_time(0, 10, 0, force=False)
        self.assertEqual(app.hour_var.get(), before)
        self.assertIsNone(app._preset_duration)

    def test_pause_and_resume(self):
        app = _make_app(_state=STATE_RUNNING)
        original = datetime.now() + timedelta(minutes=5)
        app.target_time = original
        app._duration_total_seconds = 300.0
        ctrl = CountdownController(app)
        ctrl.pause_countdown()
        self.assertEqual(app._state, STATE_PAUSED)
        self.assertIsNotNone(app._paused_remaining)
        with mock.patch.object(CountdownController, "update_countdown") as upd:
            ctrl.resume_countdown()
        self.assertEqual(app._state, STATE_RUNNING)
        # 继续保留原目标时刻，不按冻结剩余重建
        self.assertEqual(app.target_time, original)
        self.assertIsNone(app._paused_remaining)
        upd.assert_called_once_with(original)

    def test_resume_uses_original_target_not_frozen(self):
        """继续时不重建 target；剩余由 update_countdown(target − now) 决定。"""
        app = _make_app(_state=STATE_RUNNING)
        target = datetime(2026, 8, 7, 18, 0, 0)
        app.target_time = target
        ctrl = CountdownController(app)
        ctrl.pause_countdown()
        frozen = app._paused_remaining
        self.assertIsNotNone(frozen)
        with mock.patch.object(CountdownController, "update_countdown") as upd:
            ctrl.resume_countdown()
        self.assertEqual(app.target_time, target)
        # 若仍用冻结重建，target 会变成 now+frozen，与原 target 不同
        upd.assert_called_once_with(target)


class TestTrayActions(unittest.TestCase):
    def test_tray_quick_start_schedules_main_thread(self):
        from services import tray as tray_mod

        after_calls = []

        class Master:
            def after(self, ms, cb):
                after_calls.append((ms, cb))
                return "id"

        app = SimpleNamespace(
            master=Master(),
            _set_preset_time=mock.Mock(),
        )
        with mock.patch.object(tray_mod, "refresh_tray_menu"):
            tray_mod.tray_quick_start(app, 0, 5, 0)
        self.assertEqual(len(after_calls), 1)
        _ms, cb = after_calls[0]
        cb()
        app._set_preset_time.assert_called_once_with(0, 5, 0, force=True)

    def test_tray_reset_calls_app_reset(self):
        from services import tray as tray_mod

        after_calls = []

        class Master:
            def after(self, ms, cb):
                after_calls.append(cb)
                return "id"

        app = SimpleNamespace(master=Master(), reset=mock.Mock())
        with mock.patch.object(tray_mod, "refresh_tray_menu"):
            tray_mod.tray_reset_countdown(app)
        after_calls[0]()
        app.reset.assert_called_once()

    def test_tray_open_update_calls_open_update_from_ui(self):
        from services import tray as tray_mod

        after_calls = []

        class Master:
            def after(self, ms, cb):
                after_calls.append(cb)
                return "id"

        app = SimpleNamespace(master=Master())
        with mock.patch(
            "services.updater.open_update_from_ui"
        ) as open_upd:
            tray_mod.tray_open_update(app)
            after_calls[0]()
            open_upd.assert_called_once_with(app)


if __name__ == "__main__":
    unittest.main()
