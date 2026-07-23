# -*- coding: utf-8 -*-
"""services.ncm 单元测试（合成 ncm 往返）。"""

import base64
import json
import os
import struct
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from services.ncm import (
    _CORE_KEY,
    _MAGIC,
    _META_KEY,
    _aes_ecb_decrypt,
    _build_key_box,
    _decrypt_audio_chunk,
    decrypt_ncm,
    is_ncm_file,
    resolve_ncm_play_path,
)
from services.sound import is_audio_file, prepare_playable_path


def _pkcs7_pad(data: bytes, block: int = 16) -> bytes:
    n = block - (len(data) % block)
    return data + bytes([n]) * n


def _aes_ecb_encrypt(key: bytes, data: bytes) -> bytes:
    try:
        from Crypto.Cipher import AES  # type: ignore

        return AES.new(key, AES.MODE_ECB).encrypt(data)
    except Exception:
        pass
    # 用解密逆运算实现：先扩展密钥后正向 AES
    from services.ncm import (
        _SBOX,
        _RCON,
        _add_round_key,
        _mul,
    )

    def key_expansion(k: bytes):
        w = list(k)
        rcon_i = 1
        while len(w) < 176:
            t = w[-4:]
            if len(w) % 16 == 0:
                t = [t[1], t[2], t[3], t[0]]
                t = [_SBOX[b] for b in t]
                t[0] ^= _RCON[rcon_i]
                rcon_i += 1
            base = w[-16:-12]
            for j in range(4):
                w.append(base[j] ^ t[j])
        return [bytes(w[i : i + 16]) for i in range(0, 176, 16)]

    def sub_bytes(state):
        for i in range(16):
            state[i] = _SBOX[state[i]]

    def shift_rows(state):
        state[1], state[5], state[9], state[13] = state[5], state[9], state[13], state[1]
        state[2], state[6], state[10], state[14] = state[10], state[14], state[2], state[6]
        state[3], state[7], state[11], state[15] = state[15], state[3], state[7], state[11]

    def mix_columns(state):
        for c in range(4):
            i = c * 4
            a0, a1, a2, a3 = state[i], state[i + 1], state[i + 2], state[i + 3]
            state[i] = _mul(a0, 2) ^ _mul(a1, 3) ^ a2 ^ a3
            state[i + 1] = a0 ^ _mul(a1, 2) ^ _mul(a2, 3) ^ a3
            state[i + 2] = a0 ^ a1 ^ _mul(a2, 2) ^ _mul(a3, 3)
            state[i + 3] = _mul(a0, 3) ^ a1 ^ a2 ^ _mul(a3, 2)

    def enc_block(block, rks):
        state = bytearray(block)
        _add_round_key(state, rks[0])
        for r in range(1, 10):
            sub_bytes(state)
            shift_rows(state)
            mix_columns(state)
            _add_round_key(state, rks[r])
        sub_bytes(state)
        shift_rows(state)
        _add_round_key(state, rks[10])
        return bytes(state)

    rks = key_expansion(key)
    out = bytearray()
    for i in range(0, len(data), 16):
        out.extend(enc_block(data[i : i + 16], rks))
    return bytes(out)


def _build_ncm(audio: bytes, fmt: str = "mp3") -> bytes:
    # 密钥：任意 16 字节
    raw_key = b"0123456789abcdef"
    key_payload = _pkcs7_pad(b"neteasecloudmusic" + raw_key)
    key_enc = bytearray(_aes_ecb_encrypt(_CORE_KEY, key_payload))
    for i in range(len(key_enc)):
        key_enc[i] ^= 0x64

    meta = json.dumps({"format": fmt, "musicName": "test"}).encode("utf-8")
    meta_payload = _pkcs7_pad(b"music:" + meta)
    meta_aes = _aes_ecb_encrypt(_META_KEY, meta_payload)
    meta_b64 = base64.b64encode(meta_aes)
    meta_line = b"163 key(Don't modify):" + meta_b64
    meta_xor = bytearray(meta_line)
    for i in range(len(meta_xor)):
        meta_xor[i] ^= 0x63

    key_box = _build_key_box(raw_key)
    audio_enc = bytearray(audio)
    _decrypt_audio_chunk(audio_enc, key_box)  # 与解密同一 XOR，自逆

    image = b""
    out = bytearray()
    out.extend(_MAGIC)
    out.extend(b"\x00\x00")
    out.extend(struct.pack("<I", len(key_enc)))
    out.extend(key_enc)
    out.extend(struct.pack("<I", len(meta_xor)))
    out.extend(meta_xor)
    out.extend(struct.pack("<I", 0))  # crc
    out.extend(b"\x00" * 5)
    out.extend(struct.pack("<I", len(image)))
    out.extend(image)
    out.extend(audio_enc)
    return bytes(out)


class TestAes(unittest.TestCase):
    def test_nist_vector(self):
        key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
        ct = bytes.fromhex("3ad77bb40d7a3660a89ecaf32466ef97")
        pt = bytes.fromhex("6bc1bee22e409f96e93d7e117393172a")
        self.assertEqual(_aes_ecb_decrypt(key, ct), pt)


class TestNcmRoundtrip(unittest.TestCase):
    def test_decrypt_roundtrip(self):
        audio = b"ID3fake-mp3-content-" + os.urandom(200)
        blob = _build_ncm(audio, "mp3")
        with tempfile.NamedTemporaryFile(suffix=".ncm", delete=False) as f:
            f.write(blob)
            path = f.name
        try:
            self.assertTrue(is_ncm_file(path))
            self.assertTrue(is_audio_file(path))
            out, fmt = decrypt_ncm(path)
            self.assertEqual(fmt, "mp3")
            self.assertEqual(out, audio)
            play = resolve_ncm_play_path(path)
            self.assertIsNotNone(play)
            self.assertTrue(os.path.isfile(play))
            with open(play, "rb") as pf:
                self.assertEqual(pf.read(), audio)
            # 再次解析应命中缓存
            play2 = prepare_playable_path(path)
            self.assertEqual(play2, play)
        finally:
            os.unlink(path)

    def test_not_ncm(self):
        with tempfile.NamedTemporaryFile(suffix=".ncm", delete=False) as f:
            f.write(b"not-ncm")
            path = f.name
        try:
            self.assertFalse(is_ncm_file(path))
            self.assertFalse(is_audio_file(path))
            self.assertIsNone(resolve_ncm_play_path(path))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
