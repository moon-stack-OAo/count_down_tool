# -*- coding: utf-8 -*-
"""网易云音乐 .ncm 解密为可播放音频（通常为 mp3 / flac）。"""

from __future__ import annotations

from services.ncm.aes_ecb import (
    _INV_SBOX,
    _RCON,
    _SBOX,
    _add_round_key,
    _aes_ecb_decrypt,
    _aes_ecb_decrypt_block,
    _aes_key_expansion,
    _inv_mix_columns,
    _inv_shift_rows,
    _inv_sub_bytes,
    _mul,
    _pkcs7_unpad,
    _xtime,
)
from services.ncm.cache import (
    _CACHE_MAX_BYTES,
    _CACHE_MAX_FILES,
    cleanup_ncm_cache,
    resolve_ncm_play_path,
)
from services.ncm.decrypt import (
    _AUDIO_CHUNK,
    _CORE_KEY,
    _MAGIC,
    _MAX_IMAGE_SIZE,
    _MAX_KEY_LEN,
    _MAX_META_LEN,
    _META_KEY,
    _build_key_box,
    _decrypt_audio_chunk,
    decrypt_ncm,
    decrypt_ncm_to_file,
    is_ncm_file,
)

__all__ = [
    "is_ncm_file",
    "resolve_ncm_play_path",
    "decrypt_ncm",
    "decrypt_ncm_to_file",
    "cleanup_ncm_cache",
    "_aes_ecb_decrypt",
    "_aes_ecb_decrypt_block",
    "_aes_key_expansion",
    "_build_key_box",
    "_decrypt_audio_chunk",
    "_pkcs7_unpad",
    "_SBOX",
    "_INV_SBOX",
    "_RCON",
    "_add_round_key",
    "_mul",
    "_xtime",
    "_inv_sub_bytes",
    "_inv_shift_rows",
    "_inv_mix_columns",
    "_MAGIC",
    "_CORE_KEY",
    "_META_KEY",
    "_MAX_KEY_LEN",
    "_MAX_META_LEN",
    "_MAX_IMAGE_SIZE",
    "_AUDIO_CHUNK",
    "_CACHE_MAX_FILES",
    "_CACHE_MAX_BYTES",
]
