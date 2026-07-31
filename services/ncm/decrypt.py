# -*- coding: utf-8 -*-
"""NCM 格式解析与解密。"""

from __future__ import annotations

import base64
import json
import logging
import os
import struct
import tempfile
from typing import Tuple

from services.ncm.aes_ecb import _aes_ecb_decrypt, _pkcs7_unpad

logger = logging.getLogger("count_down_tool")

_MAGIC = b"CTENFDAM"

# header 字段上限，防止恶意超大 length 导致 OOM
_MAX_KEY_LEN = 256 * 1024  # 256 KiB
_MAX_META_LEN = 1024 * 1024  # 1 MiB
_MAX_IMAGE_SIZE = 16 * 1024 * 1024  # 16 MiB

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


# 音频体流式解密块大小（仅驻留一块，不攒整曲）
_AUDIO_CHUNK = 0x8000


def _decrypt_audio_chunk(
    chunk: bytearray, key_box: bytearray, offset: int = 0
) -> None:
    """按音频体全局偏移解密一块（密钥流以 256 为周期）。"""
    for i in range(len(chunk)):
        j = (offset + i + 1) & 0xFF
        chunk[i] ^= key_box[
            (key_box[j] + key_box[(key_box[j] + j) & 0xFF]) & 0xFF
        ]


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


def _parse_ncm_header(f) -> Tuple[bytearray, str]:
    """解析 ncm 头并定位到音频体起点。返回 (key_box, format_ext)。

    封面只 seek 跳过，不读入内存。
    """
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
    # 封面不进内存：只校验长度并跳过
    remaining = file_size - f.tell()
    if image_size > remaining:
        raise ValueError(
            f"ncm image_size 超出文件剩余长度: {image_size} > {remaining}"
        )
    f.seek(image_size, os.SEEK_CUR)
    return key_box, fmt


def _stream_decrypt_audio(f, key_box: bytearray, out) -> int:
    """从当前文件位置流式解密音频体到 out（file-like write）。返回写入字节数。"""
    offset = 0
    written = 0
    while True:
        raw = f.read(_AUDIO_CHUNK)
        if not raw:
            break
        chunk = bytearray(raw)
        _decrypt_audio_chunk(chunk, key_box, offset)
        out.write(chunk)
        n = len(chunk)
        offset += n
        written += n
    return written


def decrypt_ncm_to_file(path: str, dest_path: str) -> str:
    """流式解密 ncm 到 dest_path，返回 format_ext（如 mp3）。

    峰值内存约一块音频缓冲 + 头字段，不把整曲驻留在内存。
    """
    abs_dest = os.path.abspath(dest_path)
    parent = os.path.dirname(abs_dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = abs_dest + ".tmp"
    try:
        with open(path, "rb") as src, open(tmp, "wb") as out:
            key_box, fmt = _parse_ncm_header(src)
            written = _stream_decrypt_audio(src, key_box, out)
            out.flush()
            try:
                os.fsync(out.fileno())
            except OSError:
                pass
        if written <= 0:
            raise ValueError("ncm 解密结果为空")
        os.replace(tmp, abs_dest)
        return fmt
    except (OSError, ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        try:
            if os.path.isfile(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise


def decrypt_ncm(path: str) -> Tuple[bytes, str]:
    """
    解密 ncm。
    返回 (audio_bytes, format_ext) 如 (b'...', 'mp3')。

    实现上流式写临时文件再读回，避免解密过程中双份驻留；
    调用方若只需落盘请用 decrypt_ncm_to_file / resolve_ncm_play_path。
    """
    fd, tmp = tempfile.mkstemp(suffix=".ncmdec")
    try:
        os.close(fd)
        fmt = decrypt_ncm_to_file(path, tmp)
        with open(tmp, "rb") as f:
            audio = f.read()
        return audio, fmt
    finally:
        try:
            if os.path.isfile(tmp):
                os.remove(tmp)
        except OSError:
            pass

