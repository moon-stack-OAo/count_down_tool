# -*- coding: utf-8 -*-
"""countdown_core 单元测试。"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

# 保证可从项目根导入
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.countdown_core import (
    ACTION_FINISH,
    ACTION_PAUSE,
    ACTION_RESET,
    ACTION_RESTART,
    ACTION_RESUME,
    ACTION_START,
    ACTION_START_FAIL,
    BTN_PAUSE,
    BTN_RESTART,
    BTN_RESUME,
    BTN_START,
    STATE_FINISHED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RUNNING,
    button_text_for_state,
    format_remaining,
    format_target_label,
    is_process_alive,
    load_config_dict,
    merge_config,
    merge_mini_position,
    merge_mini_size,
    merge_mini_text,
    mini_content_scale,
    next_second_delay_ms,
    next_state,
    normalize_mini_size,
    normalize_mini_text,
    parse_mini_geometry,
    parse_mini_size,
    progress_ratio,
    read_lock_pid,
    resolve_mini_text_color,
    resource_path,
    save_config_dict,
    target_from_duration,
    target_from_hms,
    try_acquire_weak_lock,
    validate_hms,
    write_lock_pid,
    MINI_TEXT_DEFAULTS,
)


class TestValidateHms(unittest.TestCase):
    def test_valid(self):
        ok, err = validate_hms(0, 0, 0)
        self.assertTrue(ok)
        self.assertIsNone(err)
        ok, err = validate_hms(23, 59, 59)
        self.assertTrue(ok)
        self.assertIsNone(err)
        ok, err = validate_hms("12", "30", "45")
        self.assertTrue(ok)

    def test_out_of_range(self):
        ok, err = validate_hms(24, 0, 0)
        self.assertFalse(ok)
        self.assertIn("00-23", err)
        ok, err = validate_hms(0, 60, 0)
        self.assertFalse(ok)
        self.assertIn("00-59", err)
        ok, err = validate_hms(0, 0, 60)
        self.assertFalse(ok)
        self.assertIn("00-59", err)
        ok, err = validate_hms(-1, 0, 0)
        self.assertFalse(ok)

    def test_non_numeric(self):
        ok, err = validate_hms("ab", 0, 0)
        self.assertFalse(ok)
        self.assertEqual(err, "请输入有效数字")
        ok, err = validate_hms(None, 0, 0)
        self.assertFalse(ok)
        self.assertEqual(err, "请输入有效数字")


class TestTargetFromHms(unittest.TestCase):
    def test_today_not_passed(self):
        now = datetime(2026, 7, 17, 10, 0, 0)
        target = target_from_hms(18, 0, 0, now)
        self.assertEqual(target, datetime(2026, 7, 17, 18, 0, 0))

    def test_passed_cross_day(self):
        now = datetime(2026, 7, 17, 20, 0, 0)
        target = target_from_hms(18, 0, 0, now)
        self.assertEqual(target, datetime(2026, 7, 18, 18, 0, 0))

    def test_equal_now_is_passed(self):
        # target < now 才跨日；相等时仍为今日
        now = datetime(2026, 7, 17, 18, 0, 0)
        target = target_from_hms(18, 0, 0, now)
        self.assertEqual(target, datetime(2026, 7, 17, 18, 0, 0))


class TestTargetFromDuration(unittest.TestCase):
    def test_duration_and_target(self):
        now = datetime(2026, 7, 17, 12, 0, 0)
        target, duration = target_from_duration(0, 5, 30, now)
        self.assertEqual(duration, timedelta(minutes=5, seconds=30))
        self.assertEqual(target, datetime(2026, 7, 17, 12, 5, 30))

    def test_hours(self):
        now = datetime(2026, 7, 17, 12, 0, 0)
        target, duration = target_from_duration(1, 0, 0, now)
        self.assertEqual(duration, timedelta(hours=1))
        self.assertEqual(target, datetime(2026, 7, 17, 13, 0, 0))

    def test_restart_uses_same_duration(self):
        """重新开始时应用同一 preset_duration。"""
        now1 = datetime(2026, 7, 17, 12, 0, 0)
        _, duration = target_from_duration(0, 5, 0, now1)
        now2 = datetime(2026, 7, 17, 15, 30, 0)
        target2 = now2 + duration
        self.assertEqual(target2, datetime(2026, 7, 17, 15, 35, 0))


class TestFormatRemaining(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(format_remaining(0), "00:00:00")

    def test_59(self):
        self.assertEqual(format_remaining(59), "00:00:59")

    def test_3600_plus(self):
        self.assertEqual(format_remaining(3600), "01:00:00")
        self.assertEqual(format_remaining(3661), "01:01:01")
        self.assertEqual(format_remaining(3600 * 25 + 1), "25:00:01")

    def test_negative_clamped(self):
        self.assertEqual(format_remaining(-5), "00:00:00")


class TestProgressRatio(unittest.TestCase):
    def test_start_zero(self):
        self.assertEqual(progress_ratio(100, 100), 0.0)

    def test_half(self):
        self.assertAlmostEqual(progress_ratio(50, 100), 0.5)

    def test_finished(self):
        self.assertEqual(progress_ratio(0, 100), 1.0)

    def test_clamp_over_one(self):
        self.assertEqual(progress_ratio(-10, 100), 1.0)

    def test_clamp_under_zero(self):
        self.assertEqual(progress_ratio(150, 100), 0.0)

    def test_total_zero_is_done(self):
        self.assertEqual(progress_ratio(0, 0), 1.0)
        self.assertEqual(progress_ratio(5, 0), 1.0)

    def test_invalid_returns_zero(self):
        self.assertEqual(progress_ratio("x", 10), 0.0)
        self.assertEqual(progress_ratio(10, None), 0.0)


class TestFormatTargetLabel(unittest.TestCase):
    def test_today(self):
        now = datetime(2026, 7, 17, 10, 0, 0)
        target = datetime(2026, 7, 17, 18, 30, 0)
        self.assertEqual(format_target_label(target, now), "18:30:00")

    def test_tomorrow(self):
        now = datetime(2026, 7, 17, 20, 0, 0)
        target = datetime(2026, 7, 18, 8, 0, 0)
        self.assertEqual(format_target_label(target, now), "明日 08:00:00")


class TestNextSecondDelayMs(unittest.TestCase):
    def test_range(self):
        for _ in range(20):
            d = next_second_delay_ms()
            self.assertGreaterEqual(d, 1)
            self.assertLessEqual(d, 1000)

    def test_fixed_microsecond(self):
        now = datetime(2026, 7, 17, 12, 0, 0, 0)
        self.assertEqual(next_second_delay_ms(now), 1000)
        now = datetime(2026, 7, 17, 12, 0, 0, 500_000)
        self.assertEqual(next_second_delay_ms(now), 500)
        now = datetime(2026, 7, 17, 12, 0, 0, 999_000)
        self.assertEqual(next_second_delay_ms(now), 1)
        now = datetime(2026, 7, 17, 12, 0, 0, 999_999)
        self.assertEqual(next_second_delay_ms(now), 1)


class TestStateMachine(unittest.TestCase):
    def test_button_text(self):
        self.assertEqual(button_text_for_state(STATE_IDLE), BTN_START)
        self.assertEqual(button_text_for_state(STATE_RUNNING), BTN_PAUSE)
        self.assertEqual(button_text_for_state(STATE_PAUSED), BTN_RESUME)
        self.assertEqual(button_text_for_state(STATE_FINISHED), BTN_RESTART)
        self.assertEqual(button_text_for_state("unknown"), BTN_START)

    def test_transitions(self):
        cases = [
            (STATE_IDLE, ACTION_START, STATE_RUNNING),
            (STATE_IDLE, ACTION_START_FAIL, STATE_IDLE),
            (STATE_RUNNING, ACTION_PAUSE, STATE_PAUSED),
            (STATE_PAUSED, ACTION_RESUME, STATE_RUNNING),
            (STATE_RUNNING, ACTION_FINISH, STATE_FINISHED),
            (STATE_FINISHED, ACTION_RESTART, STATE_RUNNING),
            (STATE_FINISHED, ACTION_START_FAIL, STATE_FINISHED),
            (STATE_RUNNING, ACTION_START_FAIL, STATE_IDLE),
            (STATE_IDLE, ACTION_RESET, STATE_IDLE),
            (STATE_RUNNING, ACTION_RESET, STATE_IDLE),
            (STATE_PAUSED, ACTION_RESET, STATE_IDLE),
            (STATE_FINISHED, ACTION_RESET, STATE_IDLE),
        ]
        for state, action, expected in cases:
            self.assertEqual(
                next_state(action, state),
                expected,
                msg=f"{state} + {action} -> {expected}",
            )

    def test_unknown_keeps_state(self):
        self.assertEqual(next_state("nope", STATE_RUNNING), STATE_RUNNING)

    def test_full_cycle(self):
        s = STATE_IDLE
        s = next_state(ACTION_START, s)
        self.assertEqual(s, STATE_RUNNING)
        s = next_state(ACTION_PAUSE, s)
        self.assertEqual(s, STATE_PAUSED)
        s = next_state(ACTION_RESUME, s)
        self.assertEqual(s, STATE_RUNNING)
        s = next_state(ACTION_FINISH, s)
        self.assertEqual(s, STATE_FINISHED)
        s = next_state(ACTION_RESTART, s)
        self.assertEqual(s, STATE_RUNNING)
        s = next_state(ACTION_RESET, s)
        self.assertEqual(s, STATE_IDLE)


class TestConfigMergeLoadSave(unittest.TestCase):
    def test_merge_keeps_other_fields(self):
        cfg = {"theme": "dark", "mini_position": [1, 2], "extra": 1}
        merged = merge_mini_position(cfg, (100, 200))
        self.assertEqual(merged["theme"], "dark")
        self.assertEqual(merged["extra"], 1)
        self.assertEqual(merged["mini_position"], [100, 200])
        self.assertEqual(cfg["mini_position"], [1, 2])

    def test_merge_none_pos_no_overwrite(self):
        cfg = {"mini_position": [1, 2], "x": 1}
        merged = merge_mini_position(cfg, None)
        self.assertEqual(merged["mini_position"], [1, 2])
        self.assertEqual(merged["x"], 1)

    def test_merge_config_transparent_and_mode(self):
        cfg = {"theme": "dark", "mini_position": [1, 2]}
        merged = merge_config(
            cfg,
            transparent_mode=True,
            last_mode="mini",
            mini_position=[9, 9],
        )
        self.assertEqual(merged["theme"], "dark")
        self.assertTrue(merged["transparent_mode"])
        self.assertEqual(merged["last_mode"], "mini")
        self.assertEqual(merged["mini_position"], [9, 9])
        # None 不覆盖
        again = merge_config(merged, transparent_mode=None, last_mode=None)
        self.assertTrue(again["transparent_mode"])
        self.assertEqual(again["last_mode"], "mini")

    def test_merge_config_empty_base(self):
        merged = merge_config(None, last_mode="full")
        self.assertEqual(merged["last_mode"], "full")

    def test_load_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            self.assertEqual(load_config_dict(path), {})
            save_config_dict(path, {"a": 1, "mini_position": [10, 20]})
            loaded = load_config_dict(path)
            self.assertEqual(loaded["a"], 1)
            self.assertEqual(loaded["mini_position"], [10, 20])
            merged = merge_mini_position(loaded, (30, 40))
            merged = merge_config(merged, transparent_mode=False, last_mode="full")
            save_config_dict(path, merged)
            again = load_config_dict(path)
            self.assertEqual(again["a"], 1)
            self.assertEqual(again["mini_position"], [30, 40])
            self.assertFalse(again["transparent_mode"])
            self.assertEqual(again["last_mode"], "full")

    def test_load_invalid_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("not-json")
            self.assertEqual(load_config_dict(path), {})


class TestMiniText(unittest.TestCase):
    def test_normalize_keeps_valid(self):
        raw = {
            "clock": "accent",
            "countdown_running": "white",
            "countdown_paused": "text_dim",
            "countdown_finished": "success",
        }
        self.assertEqual(normalize_mini_text(raw), raw)

    def test_normalize_drops_invalid(self):
        raw = {
            "clock": "not_a_key",
            "countdown_running": 123,
            "countdown_paused": "text_dim",
            "unknown_role": "white",
            "countdown_finished": None,
        }
        self.assertEqual(
            normalize_mini_text(raw),
            {"countdown_paused": "text_dim"},
        )

    def test_normalize_non_dict(self):
        self.assertEqual(normalize_mini_text(None), {})
        self.assertEqual(normalize_mini_text("x"), {})
        self.assertEqual(normalize_mini_text([]), {})

    def test_merge_writes_and_pops(self):
        cfg = {"theme_id": "slate_cyan", "mini_text": {"clock": "accent"}}
        merged = merge_mini_text(cfg, {"clock": "warning"})
        self.assertEqual(merged["mini_text"], {"clock": "warning"})
        self.assertEqual(merged["theme_id"], "slate_cyan")
        self.assertEqual(cfg["mini_text"], {"clock": "accent"})

        cleared = merge_mini_text(merged, {})
        self.assertNotIn("mini_text", cleared)
        cleared2 = merge_mini_text(merged, None)
        self.assertNotIn("mini_text", cleared2)

    def test_merge_strips_invalid_keys(self):
        merged = merge_mini_text({}, {"clock": "bg", "countdown_running": "white"})
        self.assertEqual(merged["mini_text"], {"countdown_running": "white"})

    def test_resolve_defaults(self):
        colors = {
            "text_dim": "#111",
            "white": "#FFF",
            "success": "#0F0",
            "accent": "#0AF",
        }
        self.assertEqual(
            resolve_mini_text_color(colors, None, "clock"),
            colors[MINI_TEXT_DEFAULTS["clock"]],
        )
        self.assertEqual(
            resolve_mini_text_color(colors, {}, "countdown_running"),
            colors["white"],
        )
        self.assertEqual(
            resolve_mini_text_color(colors, {}, "countdown_finished"),
            colors["success"],
        )

    def test_resolve_custom_and_theme_switch(self):
        mini_text = {"clock": "accent"}
        c1 = {"accent": "#AAA", "text_dim": "#111", "white": "#FFF"}
        c2 = {"accent": "#BBB", "text_dim": "#222", "white": "#EEE"}
        self.assertEqual(resolve_mini_text_color(c1, mini_text, "clock"), "#AAA")
        self.assertEqual(resolve_mini_text_color(c2, mini_text, "clock"), "#BBB")

    def test_resolve_missing_palette_fallback(self):
        self.assertEqual(
            resolve_mini_text_color({}, None, "clock"),
            "#FFFFFF",
        )
        self.assertEqual(
            resolve_mini_text_color({"white": "#EEE"}, {"clock": "accent"}, "clock"),
            "#EEE",
        )


class TestParseMiniGeometry(unittest.TestCase):
    def test_full_geo(self):
        self.assertEqual(parse_mini_geometry("220x48+100+200"), (100, 200))

    def test_pos_only(self):
        self.assertEqual(parse_mini_geometry("+10+20"), (10, 20))

    def test_invalid(self):
        self.assertIsNone(parse_mini_geometry(""))
        self.assertIsNone(parse_mini_geometry("220x48"))
        self.assertIsNone(parse_mini_geometry(None))


class TestParseMiniSize(unittest.TestCase):
    def test_full_geo(self):
        self.assertEqual(parse_mini_size("220x48+100+200"), (220, 48))

    def test_size_only(self):
        self.assertEqual(parse_mini_size("300x80"), (300, 80))

    def test_invalid(self):
        self.assertIsNone(parse_mini_size(""))
        self.assertIsNone(parse_mini_size("+10+20"))
        self.assertIsNone(parse_mini_size("0x48+1+2"))
        self.assertIsNone(parse_mini_size(None))


class TestMiniSizeHelpers(unittest.TestCase):
    def test_normalize_clamps(self):
        self.assertEqual(normalize_mini_size([50, 10], 180, 36, 900, 240), (180, 36))
        self.assertEqual(normalize_mini_size((1000, 300), 180, 36, 900, 240), (900, 240))
        self.assertEqual(normalize_mini_size([400, 80], 180, 36, 900, 240), (400, 80))

    def test_normalize_invalid(self):
        self.assertIsNone(normalize_mini_size(None, 1, 1, 10, 10))
        self.assertIsNone(normalize_mini_size([1], 1, 1, 10, 10))
        self.assertIsNone(normalize_mini_size("bad", 1, 1, 10, 10))
        self.assertIsNone(normalize_mini_size([-1, 20], 1, 1, 10, 10))

    def test_merge_mini_size(self):
        cfg = {"theme": "dark", "mini_position": [1, 2]}
        merged = merge_mini_size(cfg, (300, 60))
        self.assertEqual(merged["mini_size"], [300, 60])
        self.assertEqual(merged["theme"], "dark")
        self.assertEqual(cfg.get("mini_size"), None)

    def test_merge_mini_size_none(self):
        cfg = {"mini_size": [1, 2], "theme": "dark"}
        merged = merge_mini_size(cfg, None)
        self.assertNotIn("mini_size", merged)
        self.assertEqual(merged["theme"], "dark")
        self.assertEqual(cfg["mini_size"], [1, 2])

    def test_mini_content_scale(self):
        self.assertAlmostEqual(mini_content_scale(236, 48, 236, 48), 1.0)
        self.assertAlmostEqual(mini_content_scale(472, 96, 236, 48), 2.0)
        self.assertAlmostEqual(mini_content_scale(118, 48, 236, 48), 0.55, places=2)
        self.assertAlmostEqual(mini_content_scale(236, 24, 236, 48), 0.55, places=2)
        self.assertEqual(mini_content_scale(0, 48, 236, 48), 1.0)


class TestResourcePath(unittest.TestCase):
    def test_dev_mode(self):
        p = resource_path("icon.ico", frozen=False, file_dir=r"D:\app")
        self.assertTrue(p.endswith("icon.ico"))
        self.assertIn("app", p.replace("/", os.sep))

    def test_frozen_meipass(self):
        p = resource_path("icon.ico", frozen=True, meipass=r"C:\tmp\_MEI", file_dir=r"D:\app")
        self.assertEqual(p, os.path.join(r"C:\tmp\_MEI", "icon.ico"))


class TestWeakLockPid(unittest.TestCase):
    def test_write_read_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "app.lock")
            write_lock_pid(path, 12345)
            self.assertEqual(read_lock_pid(path), 12345)

    def test_read_missing(self):
        self.assertIsNone(read_lock_pid(os.path.join(tempfile.gettempdir(), "no_such_lock_xyz")))

    def test_read_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.lock")
            with open(path, "w", encoding="utf-8") as f:
                f.write("not-a-pid")
            self.assertIsNone(read_lock_pid(path))

    def test_is_process_alive_self(self):
        self.assertTrue(is_process_alive(os.getpid()))

    def test_is_process_alive_invalid(self):
        self.assertFalse(is_process_alive(-1))
        self.assertFalse(is_process_alive(0))
        self.assertFalse(is_process_alive("x"))

    def test_is_process_alive_dead_pid(self):
        # 极大 pid 通常不存在
        self.assertFalse(is_process_alive(2_000_000_000))

    def test_try_acquire_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "w.lock")
            self.assertTrue(try_acquire_weak_lock(path, pid=111))
            self.assertEqual(read_lock_pid(path), 111)

    def test_try_acquire_dead_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "w.lock")
            write_lock_pid(path, 2_000_000_000)  # 死 pid
            with mock.patch("core.countdown_core.is_process_alive", return_value=False):
                self.assertTrue(try_acquire_weak_lock(path, pid=222))
            self.assertEqual(read_lock_pid(path), 222)

    def test_try_acquire_live_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "w.lock")
            write_lock_pid(path, 999)
            with mock.patch("core.countdown_core.is_process_alive", return_value=True):
                self.assertFalse(try_acquire_weak_lock(path, pid=333))
            self.assertEqual(read_lock_pid(path), 999)


if __name__ == "__main__":
    unittest.main()
