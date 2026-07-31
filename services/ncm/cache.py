# -*- coding: utf-8 -*-
"""NCM 解密缓存与可播放路径解析。"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
from typing import Dict, Optional

from services.ncm.decrypt import decrypt_ncm_to_file, is_ncm_file

logger = logging.getLogger("count_down_tool")

# 缓存治理：最多 N 个文件 / 总大小上限
_CACHE_MAX_FILES = 64
_CACHE_MAX_BYTES = 512 * 1024 * 1024  # 512 MiB
_cache_global_lock = threading.Lock()
_cache_key_locks: Dict[str, threading.Lock] = {}

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

            # 先写到固定后缀前：格式在头里才知道，用 .part 再 rename
            part = os.path.join(cache_root, f"{key}.part")
            fmt = decrypt_ncm_to_file(path, part)
            out = os.path.join(cache_root, f"{key}.{fmt}")
            try:
                if os.path.isfile(out):
                    os.remove(out)
            except OSError:
                pass
            os.replace(part, out)
            cleanup_ncm_cache(cache_root, keep_paths={out})
            return out
    except (OSError, ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        # base64/binascii 错误亦属 ValueError
        logger.debug("ncm 解密失败: %s", path, exc_info=True)
        try:
            part = os.path.join(_cache_dir(), f"{_cache_key(path)}.part")
            if os.path.isfile(part):
                os.remove(part)
        except OSError:
            pass
        return None
