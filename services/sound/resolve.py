# -*- coding: utf-8 -*-
"""音效路径解析、导入与可播放路径准备。"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
from typing import Optional, Tuple

from core.countdown_core import resource_path
from services.sound.constants import (
    _AUDIO_EXTS,
    _PRESET_FILES,
    SOUND_ID_CUSTOM,
    SOUND_ID_SOFT,
    SOUND_ID_SYSTEM,
)

logger = logging.getLogger("count_down_tool")


def _pkg():
    import services.sound as m

    return m


def _safe_stem(name: str) -> str:
    stem = os.path.splitext(os.path.basename(name or ""))[0]
    stem = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", stem, flags=re.UNICODE)
    stem = stem.strip("._") or "sound"
    return stem[:48]


def _import_dest_path(src_path: str, play_ext: str) -> str:
    """按源路径稳定生成目标文件名，便于重复导入复用。"""
    S = _pkg()
    abs_src = os.path.abspath(src_path)
    digest = hashlib.sha1(abs_src.encode("utf-8", errors="ignore")).hexdigest()[:12]
    stem = _safe_stem(src_path)
    ext = play_ext if play_ext.startswith(".") else f".{play_ext}"
    return os.path.join(S.user_sounds_dir(True), f"{stem}_{digest}{ext}")


def import_custom_sound(src_path: str) -> Optional[Tuple[str, str]]:
    """
    将自定义音效导入用户 sounds 目录（永久备份）。
    .ncm 先解密再保存为 mp3/flac 等。
    返回 (stored_path, display_name)；失败返回 None。
    """
    S = _pkg()
    src_path = S.normalize_sound_path(src_path)
    if not src_path or not os.path.isfile(src_path):
        return None
    if not S.is_audio_file(src_path):
        return None

    display = S.sound_display_name(src_path)
    abs_src = os.path.abspath(src_path)
    sounds_root = os.path.abspath(S.user_sounds_dir(True))

    # 已在用户库内：直接使用
    try:
        if os.path.commonpath([abs_src, sounds_root]) == sounds_root:
            return abs_src, display
    except ValueError:
        pass

    # ncm / 需转换：先得到可播放文件
    play_src = S.prepare_playable_path(src_path)
    if not play_src or not os.path.isfile(play_src):
        return None

    play_ext = os.path.splitext(play_src)[1].lower() or ".mp3"
    if play_ext == ".ncm":
        return None

    # 展示名：ncm 保留原名但扩展改为实际格式
    if os.path.splitext(src_path)[1].lower() == ".ncm":
        display = _safe_stem(src_path) + play_ext
    else:
        display = S.sound_display_name(src_path)

    dest = _import_dest_path(src_path, play_ext)
    try:
        # 已有同名目标且非空则复用
        if os.path.isfile(dest) and os.path.getsize(dest) > 0:
            # 源更新时覆盖
            try:
                if os.path.getmtime(play_src) <= os.path.getmtime(dest) + 0.001:
                    return dest, display
            except OSError:
                return dest, display
        parent = os.path.dirname(dest)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp = dest + ".tmp"
        shutil.copy2(play_src, tmp)
        os.replace(tmp, dest)
        return dest, display
    except (OSError, shutil.Error, TypeError, ValueError):
        logger.debug("导入自定义音效失败: %s -> %s", src_path, dest, exc_info=True)
        return None


def preset_path(sound_id: str) -> Optional[str]:
    rel = _PRESET_FILES.get(sound_id)
    if not rel:
        return None
    path = resource_path(rel)
    return path if os.path.isfile(path) else None


def resolve_play_path(sound_id: str, custom_path: str = "") -> Tuple[str, Optional[str]]:
    """返回 (mode, path)。mode: mute 不在此处理；system | file。"""
    S = _pkg()
    sid = S.normalize_sound_id(sound_id)
    if sid == SOUND_ID_SYSTEM:
        return "system", None
    if sid == SOUND_ID_CUSTOM:
        path = S.normalize_sound_path(custom_path)
        if path and os.path.isfile(path):
            return "file", path
        # 自定义失效时回退柔和预设
        fallback = S.preset_path(SOUND_ID_SOFT)
        if fallback:
            return "file", fallback
        return "system", None
    path = S.preset_path(sid)
    if path:
        return "file", path
    return "system", None


def is_audio_file(path: str) -> bool:
    if not path or not os.path.isfile(path):
        return False
    ext = os.path.splitext(path)[1].lower()
    if ext == ".ncm":
        from services.ncm import is_ncm_file

        return is_ncm_file(path)
    return ext in _AUDIO_EXTS


def prepare_playable_path(path: str) -> Optional[str]:
    """将路径解析为系统可直接播放的文件（.ncm 先解密到缓存）。"""
    if not path or not os.path.isfile(path):
        return None
    ext = os.path.splitext(path)[1].lower()
    if ext == ".ncm":
        from services.ncm import resolve_ncm_play_path

        return resolve_ncm_play_path(path)
    return path
