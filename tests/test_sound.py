# -*- coding: utf-8 -*-
"""services.sound 单元测试。"""

import os
import sys
import tempfile
import unittest
from unittest import mock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from services.sound import (
    SOUND_ID_ALERT,
    SOUND_ID_CHIME,
    SOUND_ID_CUSTOM,
    SOUND_ID_SOFT,
    SOUND_ID_SYSTEM,
    is_audio_file,
    normalize_sound_id,
    normalize_sound_path,
    play_finish_sound,
    preset_path,
    resolve_play_path,
)


class TestNormalize(unittest.TestCase):
    def test_sound_id_defaults(self):
        self.assertEqual(normalize_sound_id(None), SOUND_ID_SOFT)
        self.assertEqual(normalize_sound_id(""), SOUND_ID_SOFT)
        self.assertEqual(normalize_sound_id("CHIME"), SOUND_ID_CHIME)
        self.assertEqual(normalize_sound_id("custom"), SOUND_ID_CUSTOM)
        self.assertEqual(normalize_sound_id("nope"), SOUND_ID_SOFT)

    def test_sound_path(self):
        self.assertEqual(normalize_sound_path(None), "")
        self.assertEqual(normalize_sound_path("  a.wav  "), "a.wav")


class TestResolve(unittest.TestCase):
    def test_system(self):
        mode, path = resolve_play_path(SOUND_ID_SYSTEM, "")
        self.assertEqual(mode, "system")
        self.assertIsNone(path)

    def test_presets_exist(self):
        for sid in (SOUND_ID_SOFT, SOUND_ID_CHIME, SOUND_ID_ALERT):
            p = preset_path(sid)
            self.assertIsNotNone(p, sid)
            self.assertTrue(os.path.isfile(p), p)
            mode, path = resolve_play_path(sid, "")
            self.assertEqual(mode, "file")
            self.assertEqual(path, p)

    def test_custom_valid(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"RIFF")
            path = f.name
        try:
            mode, resolved = resolve_play_path(SOUND_ID_CUSTOM, path)
            self.assertEqual(mode, "file")
            self.assertEqual(resolved, path)
        finally:
            os.unlink(path)

    def test_custom_missing_fallback(self):
        mode, path = resolve_play_path(SOUND_ID_CUSTOM, "/no/such/file.wav")
        # 回退 soft 或 system
        self.assertIn(mode, ("file", "system"))
        if mode == "file":
            self.assertTrue(path.endswith("soft.wav") or "soft" in path)


class TestIsAudio(unittest.TestCase):
    def test_ext(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            self.assertTrue(is_audio_file(path))
        finally:
            os.unlink(path)
        self.assertFalse(is_audio_file("/no/file.wav"))
        self.assertFalse(is_audio_file(""))


class TestPlayMuted(unittest.TestCase):
    def test_muted_skips(self):
        with mock.patch("services.sound.play_file") as pf:
            with mock.patch("services.sound.ring_system_bell_times") as rb:
                play_finish_sound(None, muted=True, sound_id=SOUND_ID_SOFT)
                pf.assert_not_called()
                rb.assert_not_called()


class TestPlayRules(unittest.TestCase):
    def test_file_plays_once(self):
        with mock.patch("services.sound.play_file", return_value=True) as pf:
            with mock.patch("services.sound.ring_system_bell_times") as rb:
                play_finish_sound(None, muted=False, sound_id=SOUND_ID_SOFT)
                pf.assert_called_once()
                rb.assert_not_called()

    def test_system_rings_three(self):
        with mock.patch("services.sound.play_file") as pf:
            with mock.patch("services.sound.ring_system_bell_times") as rb:
                play_finish_sound(None, muted=False, sound_id=SOUND_ID_SYSTEM)
                pf.assert_not_called()
                rb.assert_called_once()
                self.assertEqual(rb.call_args[0][1], 3)

    def test_file_fail_fallback_system_three(self):
        with mock.patch("services.sound.play_file", return_value=False):
            with mock.patch("services.sound.ring_system_bell_times") as rb:
                play_finish_sound(None, muted=False, sound_id=SOUND_ID_SOFT)
                rb.assert_called_once()
                self.assertEqual(rb.call_args[0][1], 3)


if __name__ == "__main__":
    unittest.main()
