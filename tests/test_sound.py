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
    SOUND_HISTORY_MAX,
    SOUND_ID_ALERT,
    SOUND_ID_CHIME,
    SOUND_ID_CUSTOM,
    SOUND_ID_SOFT,
    SOUND_ID_SYSTEM,
    import_custom_sound,
    is_audio_file,
    normalize_sound_history,
    normalize_sound_id,
    normalize_sound_path,
    play_finish_sound,
    preset_path,
    prune_sound_history,
    resolve_play_path,
    touch_sound_history,
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


class TestHistory(unittest.TestCase):
    def test_normalize_and_touch(self):
        h = normalize_sound_history(
            [
                {"path": "C:/a.mp3", "name": "a"},
                {"path": "C:/a.mp3", "name": "dup"},
                "C:/b.wav",
                {"path": "", "name": "x"},
            ]
        )
        self.assertEqual(len(h), 2)
        self.assertEqual(h[0]["path"], "C:/a.mp3")
        self.assertEqual(h[1]["name"], "b.wav")

        h2 = touch_sound_history(h, "C:/b.wav")
        self.assertEqual(h2[0]["path"], "C:/b.wav")
        self.assertEqual(len(h2), 2)

        many = [{"path": f"C:/{i}.mp3", "name": str(i)} for i in range(20)]
        capped = normalize_sound_history(many)
        self.assertEqual(len(capped), SOUND_HISTORY_MAX)

    def test_prune_missing(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"x")
            path = f.name
        try:
            h = prune_sound_history(
                [{"path": path, "name": "ok"}, {"path": "/no/such.mp3", "name": "gone"}]
            )
            self.assertEqual(len(h), 1)
            self.assertEqual(h[0]["path"], path)
        finally:
            os.unlink(path)


class TestImport(unittest.TestCase):
    def test_import_copies_to_user_sounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "bell.wav")
            with open(src, "wb") as f:
                f.write(b"RIFF....WAVEfmt ")
            lib = os.path.join(tmp, "lib_sounds")
            with mock.patch("services.sound.user_sounds_dir", return_value=lib):
                result = import_custom_sound(src)
            self.assertIsNotNone(result)
            stored, name = result
            self.assertTrue(os.path.isfile(stored))
            self.assertTrue(stored.startswith(lib))
            self.assertEqual(name, "bell.wav")
            with open(stored, "rb") as f:
                self.assertEqual(f.read(), b"RIFF....WAVEfmt ")


class TestWindowsPlayChain(unittest.TestCase):
    def test_mp3_prefers_mci_over_startfile(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"ID3fake")
            path = f.name
        try:
            with mock.patch("services.sound._play_windows_mci", return_value=True) as mci:
                with mock.patch(
                    "services.sound._play_windows_media_player", return_value=False
                ) as mp:
                    with mock.patch("os.startfile") as sf:
                        from services.sound import _play_windows

                        self.assertTrue(_play_windows(path))
                        mci.assert_called_once()
                        mp.assert_not_called()
                        sf.assert_not_called()
        finally:
            os.unlink(path)

    def test_mp3_falls_back_media_player(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"ID3fake")
            path = f.name
        try:
            with mock.patch("services.sound._play_windows_mci", return_value=False):
                with mock.patch(
                    "services.sound._play_windows_media_player", return_value=True
                ) as mp:
                    with mock.patch("os.startfile") as sf:
                        from services.sound import _play_windows

                        self.assertTrue(_play_windows(path))
                        mp.assert_called_once()
                        sf.assert_not_called()
        finally:
            os.unlink(path)


class TestStopPlayback(unittest.TestCase):
    def test_play_file_stops_previous(self):
        from services import sound as sound_mod

        with mock.patch.object(sound_mod, "_halt_devices") as halt:
            with mock.patch.object(sound_mod, "prepare_playable_path", return_value=None):
                sound_mod.play_file("x.mp3")
                # prepare 失败时不调用 halt（路径无效）
                halt.assert_not_called()
        with mock.patch.object(sound_mod, "_halt_devices") as halt:
            with mock.patch.object(
                sound_mod, "prepare_playable_path", return_value="/tmp/a.mp3"
            ):
                with mock.patch.object(sound_mod, "_play_windows", return_value=True):
                    with mock.patch.object(sound_mod, "platform") as plat:
                        plat.system.return_value = "Windows"
                        sound_mod.play_file("/tmp/a.mp3")
                        halt.assert_called_once()

    def test_stop_playback_safe(self):
        from services.sound import stop_playback

        stop_playback()  # 无播放时也应安全

    def test_is_sound_playing_until(self):
        from services import sound as sound_mod

        sound_mod.stop_playback()
        self.assertFalse(sound_mod.is_sound_playing())
        sound_mod._mark_playing_until(2.0)
        self.assertTrue(sound_mod.is_sound_playing())
        sound_mod.stop_playback()
        self.assertFalse(sound_mod.is_sound_playing())

    def test_async_cancel_skips_play(self):
        """stop 后旧 generation 不应再开播。"""
        from services import sound as sound_mod

        sound_mod.stop_playback()
        gen = sound_mod._bump_play_gen()
        sound_mod.stop_playback()  # 取消 gen
        with mock.patch.object(sound_mod, "play_file", return_value=True) as pf:
            sound_mod.play_finish_sound(
                None,
                muted=False,
                sound_id=sound_mod.SOUND_ID_SOFT,
                play_gen=gen,
            )
            pf.assert_not_called()

    def test_pending_marks_playing(self):
        from services import sound as sound_mod

        sound_mod.stop_playback()
        self.assertFalse(sound_mod.is_sound_playing())
        sound_mod._set_pending_play(2.0)
        self.assertTrue(sound_mod.is_sound_playing())
        sound_mod.stop_playback()
        self.assertFalse(sound_mod.is_sound_playing())

    def test_old_async_finish_does_not_clear_new_pending(self):
        """旧 generation 结束不得清掉新试听的 pending。"""
        from services import sound as sound_mod

        sound_mod.stop_playback()
        old = sound_mod._bump_play_gen()
        # 模拟新一次试听
        sound_mod._bump_play_gen()
        sound_mod._set_pending_play(5.0)
        self.assertTrue(sound_mod.is_sound_playing())
        sound_mod._finish_async_pending(old)
        self.assertTrue(sound_mod.is_sound_playing())

    def test_play_file_respects_cancelled_gen(self):
        from services import sound as sound_mod

        gen = sound_mod._bump_play_gen()
        sound_mod._bump_play_gen()  # 取消
        with mock.patch.object(
            sound_mod, "prepare_playable_path", return_value="/tmp/a.mp3"
        ):
            with mock.patch.object(sound_mod, "_halt_devices") as halt:
                with mock.patch.object(sound_mod, "_play_windows") as play:
                    self.assertFalse(sound_mod.play_file("/tmp/a.mp3", play_gen=gen))
                    halt.assert_not_called()
                    play.assert_not_called()


class TestPurgeOrphanSounds(unittest.TestCase):
    def test_purge_keeps_history_and_current(self):
        from services import sound as sound_mod

        with tempfile.TemporaryDirectory() as tmp:
            keep_h = os.path.join(tmp, "hist.wav")
            keep_c = os.path.join(tmp, "cur.wav")
            orphan = os.path.join(tmp, "old.wav")
            for p in (keep_h, keep_c, orphan):
                with open(p, "wb") as f:
                    f.write(b"x")
            with mock.patch.object(sound_mod, "user_sounds_dir", return_value=tmp):
                n = sound_mod.purge_orphan_sounds(
                    [{"path": keep_h, "name": "h"}],
                    keep_c,
                )
            self.assertEqual(n, 1)
            self.assertTrue(os.path.isfile(keep_h))
            self.assertTrue(os.path.isfile(keep_c))
            self.assertFalse(os.path.isfile(orphan))

    def test_list_user_sound_files_skips_tmp(self):
        from services import sound as sound_mod

        with tempfile.TemporaryDirectory() as tmp:
            ok = os.path.join(tmp, "a.mp3")
            bad = os.path.join(tmp, "a.mp3.tmp")
            with open(ok, "wb") as f:
                f.write(b"1")
            with open(bad, "wb") as f:
                f.write(b"2")
            with mock.patch.object(sound_mod, "user_sounds_dir", return_value=tmp):
                files = sound_mod.list_user_sound_files()
            bases = {os.path.basename(p) for p in files}
            self.assertIn("a.mp3", bases)
            self.assertNotIn("a.mp3.tmp", bases)


if __name__ == "__main__":
    unittest.main()
