# -*- coding: utf-8 -*-
"""自定义音效历史：规范化、探测、置顶、清理。"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from core.countdown_core import user_config_dir
from services.sound.constants import SOUND_HISTORY_MAX

logger = logging.getLogger("count_down_tool")


def _pkg():
    """包门面（晚绑定，便于测试 monkeypatch）。"""
    import services.sound as m

    return m


def normalize_sound_id(value) -> str:
    S = _pkg()
    if not isinstance(value, str):
        return S.SOUND_ID_SOFT
    v = value.strip().lower()
    if v in (
        S.SOUND_ID_SYSTEM,
        S.SOUND_ID_SOFT,
        S.SOUND_ID_CHIME,
        S.SOUND_ID_ALERT,
        S.SOUND_ID_CUSTOM,
    ):
        return v
    return S.SOUND_ID_SOFT


def normalize_sound_path(value) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def user_sounds_dir(create: bool = True) -> str:
    """用户自定义音效永久目录：{config}/sounds。"""
    d = os.path.join(user_config_dir(create=create), "sounds")
    if create:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            logger.debug("创建 sounds 目录失败: %s", d, exc_info=True)
    return d


def sound_display_name(path: str, fallback: str = "") -> str:
    """用于菜单展示的文件名。"""
    if fallback and isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    if not path:
        return "未命名"
    base = os.path.basename(path.replace("\\", "/"))
    return base or "未命名"


def normalize_sound_history(value) -> List[Dict[str, str]]:
    """
    规范化历史列表：[{path, name}, ...]，最多 SOUND_HISTORY_MAX，
    去重（按绝对路径）、去掉空路径；不强制文件存在（由 prune 处理）。
    """
    if not isinstance(value, list):
        return []
    seen = set()
    out: List[Dict[str, str]] = []
    for item in value:
        path = ""
        name = ""
        if isinstance(item, str):
            path = item.strip()
        elif isinstance(item, dict):
            path = normalize_sound_path(item.get("path", ""))
            n = item.get("name")
            if isinstance(n, str):
                name = n.strip()
        if not path:
            continue
        try:
            key = os.path.normcase(os.path.abspath(path))
        except OSError:
            key = path
        if key in seen:
            continue
        seen.add(key)
        out.append({"path": path, "name": sound_display_name(path, name)})
        if len(out) >= SOUND_HISTORY_MAX:
            break
    return out


def path_is_file_quick(
        path: str,
        timeout: Optional[float] = None,
) -> bool:
    """带超时的 isfile。超时或异常视为不存在，避免 UI 卡死。

    timeout 默认读模块常量 _PATH_EXIST_TIMEOUT_S（便于测试 monkeypatch）。
    超时后探测线程可能仍在后台挂起（daemon），属可接受代价。
    """
    S = _pkg()
    if not path:
        return False
    if timeout is None:
        t_limit = float(S._PATH_EXIST_TIMEOUT_S)
    else:
        try:
            t_limit = float(timeout)
        except (TypeError, ValueError):
            t_limit = float(S._PATH_EXIST_TIMEOUT_S)
    if t_limit <= 0:
        try:
            return S.os.path.isfile(path)
        except OSError:
            return False

    box: Dict[str, bool] = {"ok": False}

    def _check() -> None:
        try:
            box["ok"] = bool(S.os.path.isfile(path))
        except OSError:
            box["ok"] = False

    th = S.threading.Thread(
        target=_check,
        name="CdtPathExist",
        daemon=True,
    )
    th.start()
    th.join(t_limit)
    if th.is_alive():
        logger.debug("路径探测超时(%.2fs): %s", t_limit, path)
        return False
    return bool(box.get("ok"))


def prune_sound_history(history) -> List[Dict[str, str]]:
    """去掉不存在的文件（路径探测带超时，防网络盘卡死）。"""
    S = _pkg()
    items = S.normalize_sound_history(history)
    kept: List[Dict[str, str]] = []
    for it in items:
        p = it.get("path") or ""
        if p and S.path_is_file_quick(p):
            kept.append(it)
    return kept


def touch_sound_history(history, path: str, name: str = "") -> List[Dict[str, str]]:
    """将 path 置顶并写入/更新历史。"""
    S = _pkg()
    path = S.normalize_sound_path(path)
    if not path:
        return S.normalize_sound_history(history)
    entry = {"path": path, "name": S.sound_display_name(path, name)}
    try:
        key = os.path.normcase(os.path.abspath(path))
    except OSError:
        key = path
    rest: List[Dict[str, str]] = []
    for it in S.normalize_sound_history(history):
        p = it.get("path") or ""
        try:
            k = os.path.normcase(os.path.abspath(p))
        except OSError:
            k = p
        if k == key:
            # 保留旧展示名（若新 name 为空）
            if not name and it.get("name"):
                entry["name"] = it["name"]
            continue
        rest.append(it)
    return ([entry] + rest)[:SOUND_HISTORY_MAX]


def _path_key(path: str) -> str:
    try:
        return os.path.normcase(os.path.abspath(path))
    except OSError:
        return path


def list_user_sound_files() -> List[str]:
    """列出用户 sounds 库内的普通文件（忽略 .tmp）。"""
    S = _pkg()
    d = S.user_sounds_dir(create=False)
    if not d or not os.path.isdir(d):
        return []
    out: List[str] = []
    try:
        names = os.listdir(d)
    except OSError:
        return []
    for name in names:
        if not name or name.endswith(".tmp"):
            continue
        p = os.path.join(d, name)
        try:
            if os.path.isfile(p):
                out.append(p)
        except OSError:
            continue
    return out


def purge_orphan_sounds(history, current_path: str = "") -> int:
    """删除用户 sounds 库中不在历史且非当前路径的文件。返回删除数量。"""
    S = _pkg()
    keep = set()
    for it in S.normalize_sound_history(history):
        p = it.get("path") or ""
        if p:
            keep.add(_path_key(p))
    cur = S.normalize_sound_path(current_path)
    if cur:
        keep.add(_path_key(cur))
    removed = 0
    for p in S.list_user_sound_files():
        if _path_key(p) in keep:
            continue
        try:
            os.remove(p)
            removed += 1
        except OSError:
            logger.debug("删除未使用音效失败: %s", p, exc_info=True)
    return removed
