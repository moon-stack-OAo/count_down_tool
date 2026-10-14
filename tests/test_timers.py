# -*- coding: utf-8 -*-
"""app.timers：退出时集中取消 after 定时器。"""

import os
import sys
import unittest
from types import SimpleNamespace

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import tkinter as tk

from app.timers import (
    APP_TIMER_ATTRS,
    cancel_all_timers,
    cancel_timer_attr,
    safe_after,
    safe_after_cancel,
)


class FakeMaster:
    """记录 after / after_cancel 调用的假 Tk master。"""

    def __init__(self, *, raise_on_cancel=None, exists=True, raise_on_after=None):
        self.cancelled = []
        self.scheduled = []
        self._raise_on_cancel = raise_on_cancel
        self._exists = exists
        self._raise_on_after = raise_on_after
        self._seq = 0

    def winfo_exists(self):
        return self._exists

    def after(self, delay_ms, callback):
        if self._raise_on_after is not None:
            raise self._raise_on_after
        self._seq += 1
        tid = f"after-{self._seq}"
        self.scheduled.append((delay_ms, callback, tid))
        return tid

    def after_cancel(self, tid):
        if self._raise_on_cancel is not None:
            raise self._raise_on_cancel
        self.cancelled.append(tid)


class TestSafeAfter(unittest.TestCase):
    def test_missing_widget_does_not_call(self):
        called = []
        self.assertIsNone(safe_after(None, 0, lambda: called.append(1)))
        dead = FakeMaster(exists=False)
        self.assertIsNone(safe_after(dead, 0, lambda: called.append(1)))
        self.assertEqual(called, [])
        self.assertEqual(dead.scheduled, [])

    def test_schedules_when_alive(self):
        m = FakeMaster()
        called = []
        tid = safe_after(m, 10, lambda: called.append("ok"))
        self.assertEqual(tid, "after-1")
        self.assertEqual(len(m.scheduled), 1)
        _delay, cb, _tid = m.scheduled[0]
        cb()
        self.assertEqual(called, ["ok"])

    def test_swallows_tcl_error_in_callback(self):
        m = FakeMaster()

        def boom():
            raise tk.TclError("invalid command name")

        safe_after(m, 0, boom)
        _delay, cb, _tid = m.scheduled[0]
        cb()

    def test_reraises_business_error(self):
        m = FakeMaster()

        def boom():
            raise ValueError("biz")

        safe_after(m, 0, boom)
        _delay, cb, _tid = m.scheduled[0]
        with self.assertRaises(ValueError):
            cb()

    def test_dead_at_fire_skips_callback(self):
        m = FakeMaster()
        called = []
        safe_after(m, 0, lambda: called.append(1))
        m._exists = False
        _delay, cb, _tid = m.scheduled[0]
        cb()
        self.assertEqual(called, [])


class TestSafeAfterCancel(unittest.TestCase):
    def test_cancel_records_id(self):
        m = FakeMaster()
        self.assertTrue(safe_after_cancel(m, "tid-1"))
        self.assertEqual(m.cancelled, ["tid-1"])

    def test_none_id_skipped(self):
        m = FakeMaster()
        self.assertFalse(safe_after_cancel(m, None))
        self.assertEqual(m.cancelled, [])

    def test_swallows_tcl_error(self):
        m = FakeMaster(raise_on_cancel=tk.TclError("invalid command name"))
        self.assertFalse(safe_after_cancel(m, "gone"))

    def test_swallows_value_error(self):
        m = FakeMaster(raise_on_cancel=ValueError("bad id"))
        self.assertFalse(safe_after_cancel(m, "bad"))


class TestCancelTimerAttr(unittest.TestCase):
    def test_clears_attr_and_cancels(self):
        m = FakeMaster()
        owner = SimpleNamespace(master=m, _clock_timer_id="clock-9")
        cancel_timer_attr(owner, "_clock_timer_id")
        self.assertIsNone(owner._clock_timer_id)
        self.assertEqual(m.cancelled, ["clock-9"])

    def test_none_noop(self):
        m = FakeMaster()
        owner = SimpleNamespace(master=m, _error_timer_id=None)
        cancel_timer_attr(owner, "_error_timer_id")
        self.assertEqual(m.cancelled, [])


class TestCancelAllTimers(unittest.TestCase):
    def test_cancels_all_registered_attrs(self):
        m = FakeMaster()
        app = SimpleNamespace(master=m)
        expected = []
        for i, name in enumerate(APP_TIMER_ATTRS):
            tid = f"t-{i}-{name}"
            setattr(app, name, tid)
            expected.append(tid)
        # 未登记字段不应参与
        app._other_thing = "skip-me"

        cancel_all_timers(app)

        self.assertEqual(sorted(m.cancelled), sorted(expected))
        for name in APP_TIMER_ATTRS:
            self.assertIsNone(getattr(app, name))
        self.assertEqual(app._other_thing, "skip-me")

    def test_partial_and_property_like(self):
        """仅部分 id 有值；property setter 可写时也能清空。"""
        m = FakeMaster()

        class Host:
            def __init__(self):
                self.master = m
                self._runtime_countdown = "cd-1"
                self._show_poll_timer_id = "poll-1"
                self._clock_timer_id = None
                self._alarm_timer_id = "al-1"
                self._error_timer_id = None
                self._mini_geo_save_id = "geo-1"
                self._startup_health_timer_id = None
                self._startup_update_timer_id = "upd-1"

            @property
            def _countdown_timer_id(self):
                return self._runtime_countdown

            @_countdown_timer_id.setter
            def _countdown_timer_id(self, value):
                self._runtime_countdown = value

        app = Host()
        cancel_all_timers(app)
        self.assertEqual(
            set(m.cancelled),
            {"cd-1", "poll-1", "al-1", "geo-1", "upd-1"},
        )
        self.assertIsNone(app._countdown_timer_id)
        self.assertIsNone(app._show_poll_timer_id)
        self.assertIsNone(app._alarm_timer_id)
        self.assertIsNone(app._mini_geo_save_id)
        self.assertIsNone(app._startup_update_timer_id)

    def test_app_timer_attrs_cover_required(self):
        """静态清单须覆盖任务要求的核心 id。"""
        required = {
            "_show_poll_timer_id",
            "_clock_timer_id",
            "_countdown_timer_id",
            "_alarm_timer_id",
            "_error_timer_id",
            "_mini_geo_save_id",
        }
        self.assertTrue(required.issubset(set(APP_TIMER_ATTRS)))


class TestQuitAppWiresCancel(unittest.TestCase):
    """静态：CountdownApp._quit_app 应调用 _cancel_all_timers。"""

    def test_quit_app_source_calls_cancel(self):
        path = os.path.join(_ROOT, "count_down_tool.py")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("def _cancel_all_timers", src)
        self.assertIn("self._cancel_all_timers()", src)
        # update_clock 必须登记 id（经 safe_after，避免窗口已毁再调度）
        self.assertIn("safe_after(self.master, next_second_delay_ms(), self.update_clock)", src)
        self.assertIn("self._clock_timer_id = tid", src)
        self.assertIn("cancel_all_timers(self)", src)


if __name__ == "__main__":
    unittest.main()
