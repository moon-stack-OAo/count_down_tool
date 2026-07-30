# -*- coding: utf-8 -*-
"""网易云音乐 .ncm 解密为可播放音频（通常为 mp3 / flac）。"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import struct
import tempfile
import threading
from typing import Dict, Optional, Tuple

logger = logging.getLogger("count_down_tool")

_MAGIC = b"CTENFDAM"

# header 字段上限，防止恶意超大 length 导致 OOM
_MAX_KEY_LEN = 256 * 1024  # 256 KiB
_MAX_META_LEN = 1024 * 1024  # 1 MiB
_MAX_IMAGE_SIZE = 16 * 1024 * 1024  # 16 MiB
# 缓存治理：最多 N 个文件 / 总大小上限
_CACHE_MAX_FILES = 64
_CACHE_MAX_BYTES = 512 * 1024 * 1024  # 512 MiB
_cache_global_lock = threading.Lock()
_cache_key_locks: Dict[str, threading.Lock] = {}
_CORE_KEY = bytes(
    [
        0x68,
        0x7A,
        0x48,
        0x52,
        0x41,
        0x6D,
        0x73,
        0x6F,
        0x35,
        0x6B,
        0x49,
        0x6E,
        0x62,
        0x61,
        0x78,
        0x57,
    ]
)
_META_KEY = bytes(
    [
        0x23,
        0x31,
        0x34,
        0x6C,
        0x6A,
        0x6B,
        0x5F,
        0x21,
        0x5C,
        0x5D,
        0x26,
        0x30,
        0x55,
        0x3C,
        0x27,
        0x28,
    ]
)

# AES-128 S-box / 逆表 / Rcon（仅 ECB 解密）
_SBOX = (
    0x63,
    0x7C,
    0x77,
    0x7B,
    0xF2,
    0x6B,
    0x6F,
    0xC5,
    0x30,
    0x01,
    0x67,
    0x2B,
    0xFE,
    0xD7,
    0xAB,
    0x76,
    0xCA,
    0x82,
    0xC9,
    0x7D,
    0xFA,
    0x59,
    0x47,
    0xF0,
    0xAD,
    0xD4,
    0xA2,
    0xAF,
    0x9C,
    0xA4,
    0x72,
    0xC0,
    0xB7,
    0xFD,
    0x93,
    0x26,
    0x36,
    0x3F,
    0xF7,
    0xCC,
    0x34,
    0xA5,
    0xE5,
    0xF1,
    0x71,
    0xD8,
    0x31,
    0x15,
    0x04,
    0xC7,
    0x23,
    0xC3,
    0x18,
    0x96,
    0x05,
    0x9A,
    0x07,
    0x12,
    0x80,
    0xE2,
    0xEB,
    0x27,
    0xB2,
    0x75,
    0x09,
    0x83,
    0x2C,
    0x1A,
    0x1B,
    0x6E,
    0x5A,
    0xA0,
    0x52,
    0x3B,
    0xD6,
    0xB3,
    0x29,
    0xE3,
    0x2F,
    0x84,
    0x53,
    0xD1,
    0x00,
    0xED,
    0x20,
    0xFC,
    0xB1,
    0x5B,
    0x6A,
    0xCB,
    0xBE,
    0x39,
    0x4A,
    0x4C,
    0x58,
    0xCF,
    0xD0,
    0xEF,
    0xAA,
    0xFB,
    0x43,
    0x4D,
    0x33,
    0x85,
    0x45,
    0xF9,
    0x02,
    0x7F,
    0x50,
    0x3C,
    0x9F,
    0xA8,
    0x51,
    0xA3,
    0x40,
    0x8F,
    0x92,
    0x9D,
    0x38,
    0xF5,
    0xBC,
    0xB6,
    0xDA,
    0x21,
    0x10,
    0xFF,
    0xF3,
    0xD2,
    0xCD,
    0x0C,
    0x13,
    0xEC,
    0x5F,
    0x97,
    0x44,
    0x17,
    0xC4,
    0xA7,
    0x7E,
    0x3D,
    0x64,
    0x5D,
    0x19,
    0x73,
    0x60,
    0x81,
    0x4F,
    0xDC,
    0x22,
    0x2A,
    0x90,
    0x88,
    0x46,
    0xEE,
    0xB8,
    0x14,
    0xDE,
    0x5E,
    0x0B,
    0xDB,
    0xE0,
    0x32,
    0x3A,
    0x0A,
    0x49,
    0x06,
    0x24,
    0x5C,
    0xC2,
    0xD3,
    0xAC,
    0x62,
    0x91,
    0x95,
    0xE4,
    0x79,
    0xE7,
    0xC8,
    0x37,
    0x6D,
    0x8D,
    0xD5,
    0x4E,
    0xA9,
    0x6C,
    0x56,
    0xF4,
    0xEA,
    0x65,
    0x7A,
    0xAE,
    0x08,
    0xBA,
    0x78,
    0x25,
    0x2E,
    0x1C,
    0xA6,
    0xB4,
    0xC6,
    0xE8,
    0xDD,
    0x74,
    0x1F,
    0x4B,
    0xBD,
    0x8B,
    0x8A,
    0x70,
    0x3E,
    0xB5,
    0x66,
    0x48,
    0x03,
    0xF6,
    0x0E,
    0x61,
    0x35,
    0x57,
    0xB9,
    0x86,
    0xC1,
    0x1D,
    0x9E,
    0xE1,
    0xF8,
    0x98,
    0x11,
    0x69,
    0xD9,
    0x8E,
    0x94,
    0x9B,
    0x1E,
    0x87,
    0xE9,
    0xCE,
    0x55,
    0x28,
    0xDF,
    0x8C,
    0xA1,
    0x89,
    0x0D,
    0xBF,
    0xE6,
    0x42,
    0x68,
    0x41,
    0x99,
    0x2D,
    0x0F,
    0xB0,
    0x54,
    0xBB,
    0x16,
)
_INV_SBOX = (
    0x52,
    0x09,
    0x6A,
    0xD5,
    0x30,
    0x36,
    0xA5,
    0x38,
    0xBF,
    0x40,
    0xA3,
    0x9E,
    0x81,
    0xF3,
    0xD7,
    0xFB,
    0x7C,
    0xE3,
    0x39,
    0x82,
    0x9B,
    0x2F,
    0xFF,
    0x87,
    0x34,
    0x8E,
    0x43,
    0x44,
    0xC4,
    0xDE,
    0xE9,
    0xCB,
    0x54,
    0x7B,
    0x94,
    0x32,
    0xA6,
    0xC2,
    0x23,
    0x3D,
    0xEE,
    0x4C,
    0x95,
    0x0B,
    0x42,
    0xFA,
    0xC3,
    0x4E,
    0x08,
    0x2E,
    0xA1,
    0x66,
    0x28,
    0xD9,
    0x24,
    0xB2,
    0x76,
    0x5B,
    0xA2,
    0x49,
    0x6D,
    0x8B,
    0xD1,
    0x25,
    0x72,
    0xF8,
    0xF6,
    0x64,
    0x86,
    0x68,
    0x98,
    0x16,
    0xD4,
    0xA4,
    0x5C,
    0xCC,
    0x5D,
    0x65,
    0xB6,
    0x92,
    0x6C,
    0x70,
    0x48,
    0x50,
    0xFD,
    0xED,
    0xB9,
    0xDA,
    0x5E,
    0x15,
    0x46,
    0x57,
    0xA7,
    0x8D,
    0x9D,
    0x84,
    0x90,
    0xD8,
    0xAB,
    0x00,
    0x8C,
    0xBC,
    0xD3,
    0x0A,
    0xF7,
    0xE4,
    0x58,
    0x05,
    0xB8,
    0xB3,
    0x45,
    0x06,
    0xD0,
    0x2C,
    0x1E,
    0x8F,
    0xCA,
    0x3F,
    0x0F,
    0x02,
    0xC1,
    0xAF,
    0xBD,
    0x03,
    0x01,
    0x13,
    0x8A,
    0x6B,
    0x3A,
    0x91,
    0x11,
    0x41,
    0x4F,
    0x67,
    0xDC,
    0xEA,
    0x97,
    0xF2,
    0xCF,
    0xCE,
    0xF0,
    0xB4,
    0xE6,
    0x73,
    0x96,
    0xAC,
    0x74,
    0x22,
    0xE7,
    0xAD,
    0x35,
    0x85,
    0xE2,
    0xF9,
    0x37,
    0xE8,
    0x1C,
    0x75,
    0xDF,
    0x6E,
    0x47,
    0xF1,
    0x1A,
    0x71,
    0x1D,
    0x29,
    0xC5,
    0x89,
    0x6F,
    0xB7,
    0x62,
    0x0E,
    0xAA,
    0x18,
    0xBE,
    0x1B,
    0xFC,
    0x56,
    0x3E,
    0x4B,
    0xC6,
    0xD2,
    0x79,
    0x20,
    0x9A,
    0xDB,
    0xC0,
    0xFE,
    0x78,
    0xCD,
    0x5A,
    0xF4,
    0x1F,
    0xDD,
    0xA8,
    0x33,
    0x88,
    0x07,
    0xC7,
    0x31,
    0xB1,
    0x12,
    0x10,
    0x59,
    0x27,
    0x80,
    0xEC,
    0x5F,
    0x60,
    0x51,
    0x7F,
    0xA9,
    0x19,
    0xB5,
    0x4A,
    0x0D,
    0x2D,
    0xE5,
    0x7A,
    0x9F,
    0x93,
    0xC9,
    0x9C,
    0xEF,
    0xA0,
    0xE0,
    0x3B,
    0x4D,
    0xAE,
    0x2A,
    0xF5,
    0xB0,
    0xC8,
    0xEB,
    0xBB,
    0x3C,
    0x83,
    0x53,
    0x99,
    0x61,
    0x17,
    0x2B,
    0x04,
    0x7E,
    0xBA,
    0x77,
    0xD6,
    0x26,
    0xE1,
    0x69,
    0x14,
    0x63,
    0x55,
    0x21,
    0x0C,
    0x7D,
)
_RCON = (
    0x00,
    0x01,
    0x02,
    0x04,
    0x08,
    0x10,
    0x20,
    0x40,
    0x80,
    0x1B,
    0x36,
)


def _xtime(a: int) -> int:
    return ((a << 1) ^ 0x1B) & 0xFF if (a & 0x80) else (a << 1) & 0xFF


def _mul(a: int, b: int) -> int:
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        a = _xtime(a)
        b >>= 1
    return p & 0xFF


def _aes_key_expansion(key: bytes) -> list:
    w = list(key)
    rcon_i = 1
    while len(w) < 176:
        t = w[-4:]
        if len(w) % 16 == 0:
            t = [t[1], t[2], t[3], t[0]]
            t = [_SBOX[b] for b in t]
            t[0] ^= _RCON[rcon_i]
            rcon_i += 1
        # 一次扩展 4 字节，必须基于扩展前的 w[-16:-12]
        base = w[-16:-12]
        for j in range(4):
            w.append(base[j] ^ t[j])
    return [bytes(w[i : i + 16]) for i in range(0, 176, 16)]


def _add_round_key(state: bytearray, rk: bytes) -> None:
    for i in range(16):
        state[i] ^= rk[i]


def _inv_sub_bytes(state: bytearray) -> None:
    for i in range(16):
        state[i] = _INV_SBOX[state[i]]


def _inv_shift_rows(state: bytearray) -> None:
    # row 1 right 1
    state[1], state[5], state[9], state[13] = state[13], state[1], state[5], state[9]
    # row 2 right 2
    state[2], state[6], state[10], state[14] = state[10], state[14], state[2], state[6]
    # row 3 right 3
    state[3], state[7], state[11], state[15] = state[7], state[11], state[15], state[3]


def _inv_mix_columns(state: bytearray) -> None:
    for c in range(4):
        i = c * 4
        a0, a1, a2, a3 = state[i], state[i + 1], state[i + 2], state[i + 3]
        state[i] = _mul(a0, 0x0E) ^ _mul(a1, 0x0B) ^ _mul(a2, 0x0D) ^ _mul(a3, 0x09)
        state[i + 1] = _mul(a0, 0x09) ^ _mul(a1, 0x0E) ^ _mul(a2, 0x0B) ^ _mul(a3, 0x0D)
        state[i + 2] = _mul(a0, 0x0D) ^ _mul(a1, 0x09) ^ _mul(a2, 0x0E) ^ _mul(a3, 0x0B)
        state[i + 3] = _mul(a0, 0x0B) ^ _mul(a1, 0x0D) ^ _mul(a2, 0x09) ^ _mul(a3, 0x0E)


def _aes_ecb_decrypt_block(block: bytes, round_keys: list) -> bytes:
    state = bytearray(block)
    _add_round_key(state, round_keys[10])
    for r in range(9, 0, -1):
        _inv_shift_rows(state)
        _inv_sub_bytes(state)
        _add_round_key(state, round_keys[r])
        _inv_mix_columns(state)
    _inv_shift_rows(state)
    _inv_sub_bytes(state)
    _add_round_key(state, round_keys[0])
    return bytes(state)


def _aes_ecb_decrypt(key: bytes, data: bytes) -> bytes:
    if len(key) != 16:
        raise ValueError("AES-128 key required")
    if len(data) % 16 != 0:
        raise ValueError("AES data length must be multiple of 16")
    try:
        from Crypto.Cipher import AES  # type: ignore

        return AES.new(key, AES.MODE_ECB).decrypt(data)
    except (ImportError, ValueError, TypeError, AttributeError):
        # 无 pycryptodome 或调用失败时回退内置 AES
        pass
    rks = _aes_key_expansion(key)
    out = bytearray()
    for i in range(0, len(data), 16):
        out.extend(_aes_ecb_decrypt_block(data[i : i + 16], rks))
    return bytes(out)


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        return data
    pad = data[-1]
    if pad < 1 or pad > 16:
        return data
    if data[-pad:] != bytes([pad]) * pad:
        return data
    return data[:-pad]


def is_ncm_file(path: str) -> bool:
    if not path or not os.path.isfile(path):
        return False
    if os.path.splitext(path)[1].lower() != ".ncm":
        return False
    try:
        with open(path, "rb") as f:
            return f.read(8) == _MAGIC
    except OSError:
        return False


def _build_key_box(key_data: bytes) -> bytearray:
    box = bytearray(range(256))
    key_len = len(key_data)
    if key_len == 0:
        return box
    j = 0
    for i in range(256):
        j = (box[i] + j + key_data[i % key_len]) & 0xFF
        box[i], box[j] = box[j], box[i]
    return box


def _decrypt_audio_chunk(chunk: bytearray, key_box: bytearray) -> None:
    for i in range(len(chunk)):
        j = (i + 1) & 0xFF
        chunk[i] ^= key_box[(key_box[j] + key_box[(key_box[j] + j) & 0xFF]) & 0xFF]


def _file_size(f) -> int:
    pos = f.tell()
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(pos, os.SEEK_SET)
    return size


def _read_u32_len(f, name: str, max_len: int, file_size: int) -> int:
    """读取 uint32 长度字段并校验上限与剩余文件长度。"""
    raw = f.read(4)
    if len(raw) != 4:
        raise ValueError(f"ncm 文件损坏：无法读取 {name}")
    length = struct.unpack("<I", raw)[0]
    if length > max_len:
        raise ValueError(f"ncm {name} 过大: {length} > {max_len}")
    remaining = file_size - f.tell()
    if length > remaining:
        raise ValueError(
            f"ncm {name} 超出文件剩余长度: {length} > {remaining}"
        )
    return length


def decrypt_ncm(path: str) -> Tuple[bytes, str]:
    """
    解密 ncm。
    返回 (audio_bytes, format_ext) 如 (b'...', 'mp3')。
    TODO: 大音频可改为流式写缓存，避免整文件驻留内存。
    """
    with open(path, "rb") as f:
        file_size = _file_size(f)
        if f.read(8) != _MAGIC:
            raise ValueError("不是有效的 ncm 文件")
        f.seek(2, os.SEEK_CUR)

        key_len = _read_u32_len(f, "key_len", _MAX_KEY_LEN, file_size)
        key_data = bytearray(f.read(key_len))
        if len(key_data) != key_len:
            raise ValueError("ncm 文件损坏：key 数据不完整")
        for i in range(len(key_data)):
            key_data[i] ^= 0x64
        key_data = _pkcs7_unpad(_aes_ecb_decrypt(_CORE_KEY, bytes(key_data)))
        # 前缀 "neteasecloudmusic"
        if key_data.startswith(b"neteasecloudmusic"):
            key_data = key_data[17:]
        key_box = _build_key_box(key_data)

        meta_len = _read_u32_len(f, "meta_len", _MAX_META_LEN, file_size)
        meta_data = bytearray(f.read(meta_len))
        if len(meta_data) != meta_len:
            raise ValueError("ncm 文件损坏：meta 数据不完整")
        for i in range(len(meta_data)):
            meta_data[i] ^= 0x63
        # 跳过 "163 key(Don't modify):"
        b64 = bytes(meta_data)
        if b64.startswith(b"163 key(Don't modify):"):
            b64 = b64[22:]
        meta_plain = _pkcs7_unpad(_aes_ecb_decrypt(_META_KEY, base64.b64decode(b64)))
        if meta_plain.startswith(b"music:"):
            meta_plain = meta_plain[6:]
        fmt = "mp3"
        try:
            meta = json.loads(meta_plain.decode("utf-8", errors="ignore"))
            raw_fmt = str(meta.get("format") or "mp3").strip().lower()
            if raw_fmt in ("mp3", "flac", "wav", "m4a", "aac", "ogg"):
                fmt = raw_fmt
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError, AttributeError):
            logger.debug("解析 ncm meta 失败，默认 mp3", exc_info=True)

        crc_raw = f.read(4)  # crc32
        if len(crc_raw) != 4:
            raise ValueError("ncm 文件损坏：缺少 crc")
        f.seek(5, os.SEEK_CUR)
        image_size = _read_u32_len(f, "image_size", _MAX_IMAGE_SIZE, file_size)
        image_data = f.read(image_size)
        if len(image_data) != image_size:
            raise ValueError("ncm 文件损坏：封面数据不完整")

        # 音频体仍整段读入内存；流式解密写盘见上方 TODO
        audio = bytearray()
        while True:
            chunk = bytearray(f.read(0x8000))
            if not chunk:
                break
            _decrypt_audio_chunk(chunk, key_box)
            audio.extend(chunk)

    return bytes(audio), fmt


def _cache_dir() -> str:
    d = os.path.join(tempfile.gettempdir(), "count_down_tool_ncm_cache")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = tempfile.gettempdir()
    return d


def _cache_key(path: str) -> str:
    st = os.stat(path)
    raw = f"{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}"
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:24]


def _key_lock(key: str) -> threading.Lock:
    with _cache_global_lock:
        lock = _cache_key_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _cache_key_locks[key] = lock
        return lock


def _list_cache_files(cache_root: str):
    """返回 [(path, mtime, size), ...]，忽略 .tmp。"""
    items = []
    try:
        names = os.listdir(cache_root)
    except OSError:
        return items
    for name in names:
        if name.endswith(".tmp"):
            continue
        path = os.path.join(cache_root, name)
        try:
            if not os.path.isfile(path):
                continue
            st = os.stat(path)
            items.append((path, st.st_mtime, st.st_size))
        except OSError:
            continue
    return items


def cleanup_ncm_cache(
    cache_root: Optional[str] = None,
    max_files: int = _CACHE_MAX_FILES,
    max_bytes: int = _CACHE_MAX_BYTES,
    keep_paths: Optional[set] = None,
) -> int:
    """
    按数量/总大小上限清理缓存（删除最旧文件）。
    返回删除的文件数。
    """
    root = cache_root if cache_root is not None else _cache_dir()
    keep = keep_paths or set()
    items = _list_cache_files(root)
    # 旧文件优先删除
    items.sort(key=lambda x: x[1])
    total_bytes = sum(sz for _, _, sz in items)
    removed = 0
    # 先按数量，再按体积；保留 keep 中的路径
    while items and (
        len(items) > max_files or total_bytes > max_bytes
    ):
        path, _, size = items[0]
        if path in keep:
            # 把受保护项移到末尾，避免死循环
            items.append(items.pop(0))
            # 若全部受保护则退出
            if all(p in keep for p, _, _ in items):
                break
            continue
        items.pop(0)
        try:
            os.remove(path)
            removed += 1
            total_bytes -= size
        except OSError:
            continue
    return removed


def _find_cached(cache_root: str, key: str) -> Optional[str]:
    for ext in (".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg"):
        candidate = os.path.join(cache_root, key + ext)
        if os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
            try:
                os.utime(candidate, None)
            except OSError:
                pass
            return candidate
    return None


def resolve_ncm_play_path(path: str) -> Optional[str]:
    """
    将 .ncm 解密到缓存目录并返回可播放路径。
    非 ncm / 失败返回 None。
    """
    if not is_ncm_file(path):
        return None
    try:
        key = _cache_key(path)
        cache_root = _cache_dir()
        hit = _find_cached(cache_root, key)
        if hit:
            return hit

        lock = _key_lock(key)
        with lock:
            # 双重检查，防并发双写
            hit = _find_cached(cache_root, key)
            if hit:
                return hit

            audio, fmt = decrypt_ncm(path)
            if not audio:
                return None
            out = os.path.join(cache_root, f"{key}.{fmt}")
            tmp = out + ".tmp"
            with open(tmp, "wb") as f:
                f.write(audio)
            os.replace(tmp, out)
            cleanup_ncm_cache(cache_root, keep_paths={out})
            return out
    except (OSError, ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        # base64/binascii 错误亦属 ValueError
        logger.debug("ncm 解密失败: %s", path, exc_info=True)
        return None
