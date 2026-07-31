# -*- coding: utf-8 -*-
"""Windows 更新包解压与布局校验。"""

from __future__ import annotations

import os
import re
import shutil
import zipfile
from typing import List

from core.update_impl.util import (
    _EXTRACT_ALLOWED_ROOT_FILES,
    _EXTRACT_ALLOWED_TOP_DIRS,
    WINDOWS_EXE_NAME,
    logger,
)


def _normalize_zip_member_name(name: str) -> str:
    """规范化 zip 成员路径为相对 POSIX 风格；非法则抛错。"""
    if name is None:
        raise RuntimeError("zip 成员名为空")
    raw = str(name).replace("\\", "/").strip()
    if not raw or raw.endswith("/"):
        # 目录项由文件路径隐式创建
        raise RuntimeError("zip 成员为空目录名")
    # 拒绝绝对路径、盘符、UNC
    if raw.startswith("/") or raw.startswith("//"):
        raise RuntimeError(f"拒绝绝对路径 zip 成员: {name!r}")
    if re.match(r"^[A-Za-z]:", raw):
        raise RuntimeError(f"拒绝盘符路径 zip 成员: {name!r}")
    # 去掉多余 ./ 与重复斜杠，拆段检查 ..
    parts: List[str] = []
    for seg in raw.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            raise RuntimeError(f"拒绝含 '..' 的 zip 成员: {name!r}")
        parts.append(seg)
    if not parts:
        raise RuntimeError(f"zip 成员规范化后为空: {name!r}")
    return "/".join(parts)


def is_allowed_extract_member(rel_posix: str) -> bool:
    """判断规范化后的相对路径是否在安装包白名单内。"""
    parts = [p for p in (rel_posix or "").split("/") if p]
    if not parts:
        return False
    # 顶层文件
    if len(parts) == 1:
        return parts[0].lower() in _EXTRACT_ALLOWED_ROOT_FILES
    top = parts[0].lower()
    # onedir：_internal/** 或 docs/**
    if top in _EXTRACT_ALLOWED_TOP_DIRS:
        return True
    # 兼容 zip 内多一层根目录：count_down_tool-xxx/count_down_tool.exe
    # 或 count_down_tool-xxx/_internal/**
    if len(parts) >= 2:
        second = parts[1].lower()
        if second in _EXTRACT_ALLOWED_ROOT_FILES and len(parts) == 2:
            return True
        if second in _EXTRACT_ALLOWED_TOP_DIRS:
            return True
    return False


def _safe_extract_member(zf: zipfile.ZipFile, member: zipfile.ZipInfo, dest_dir: str) -> str:
    """
    安全解压单个成员到 dest_dir。
    返回写入的绝对路径；目录项返回空串。
    """
    name = member.filename
    # 跳过纯目录
    if not name or name.endswith("/") or name.endswith("\\"):
        return ""
    rel = _normalize_zip_member_name(name)
    if not is_allowed_extract_member(rel):
        raise RuntimeError(f"拒绝非白名单路径 zip 成员: {name!r}")

    dest_root = os.path.abspath(dest_dir)
    # 用相对段拼接，避免 os.path.join 在绝对段时重置根
    target = os.path.abspath(os.path.join(dest_root, *rel.split("/")))
    try:
        common = os.path.commonpath([dest_root, target])
    except ValueError as exc:
        # 不同盘符等
        raise RuntimeError(f"拒绝越界 zip 成员: {name!r}") from exc
    if common != dest_root:
        raise RuntimeError(f"拒绝越界 zip 成员: {name!r}")

    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    # 显式流式写出，避免 extract 内部路径歧义
    with zf.open(member, "r") as src, open(target, "wb") as out:
        shutil.copyfileobj(src, out)
    return target


def validate_windows_extract_layout(extract_dir: str) -> str:
    """
    校验解压目录结构：必须有 count_down_tool.exe，附属路径应合理。
    返回主程序绝对路径。
    """
    root = os.path.abspath(extract_dir)
    if not os.path.isdir(root):
        raise FileNotFoundError(f"解压目录不存在: {root}")

    candidates: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # 限制 walk 不跟出 root（防御）
        try:
            if os.path.commonpath([root, os.path.abspath(dirpath)]) != root:
                dirnames[:] = []
                continue
        except ValueError:
            dirnames[:] = []
            continue
        for fname in filenames:
            if fname.lower() == WINDOWS_EXE_NAME.lower():
                candidates.append(os.path.join(dirpath, fname))

    if not candidates:
        raise FileNotFoundError("解压后未找到 count_down_tool.exe")

    # 优先路径最短（顶层 exe）
    candidates.sort(key=lambda p: (p.count(os.sep), len(p)))
    abs_target = os.path.abspath(candidates[0])
    try:
        if os.path.commonpath([root, abs_target]) != root:
            raise RuntimeError("主程序路径越界")
    except ValueError as exc:
        raise RuntimeError("主程序路径越界") from exc

    size = os.path.getsize(abs_target)
    if size < 1024:
        raise RuntimeError(f"解压得到的 exe 过小（{size} 字节），包可能损坏")
    with open(abs_target, "rb") as f:
        magic = f.read(2)
    if magic != b"MZ":
        raise RuntimeError("解压得到的文件不是有效 Windows 可执行文件")

    # 目录结构白名单：根下仅允许 exe/说明文件/_internal/docs 及一层包装目录
    exe_dir = os.path.dirname(abs_target)
    try:
        rel_exe_dir = os.path.relpath(exe_dir, root)
    except ValueError as exc:
        raise RuntimeError("安装目录结构异常") from exc
    # 允许：root 本身，或 root 下单层包装目录
    if rel_exe_dir not in (".", os.curdir):
        parts = [p for p in rel_exe_dir.replace("\\", "/").split("/") if p and p != "."]
        if len(parts) > 1:
            raise RuntimeError(f"安装目录嵌套过深: {rel_exe_dir}")

    # 检查 exe 同级是否存在可疑顶层项（非白名单）
    scan_root = exe_dir if os.path.isdir(exe_dir) else root
    try:
        for entry in os.listdir(scan_root):
            low = entry.lower()
            full = os.path.join(scan_root, entry)
            if os.path.isfile(full):
                if low not in _EXTRACT_ALLOWED_ROOT_FILES and not low.endswith(".exe"):
                    # 允许同级其它附属小文件？收敛：仅白名单文件名
                    if low != WINDOWS_EXE_NAME.lower():
                        logger.warning("安装包含非白名单顶层文件（已解压）: %s", entry)
            elif os.path.isdir(full):
                if low not in _EXTRACT_ALLOWED_TOP_DIRS:
                    # 包装目录内不应再有奇怪目录
                    if low not in ("_internal", "docs"):
                        logger.warning("安装包含非白名单顶层目录: %s", entry)
    except OSError as exc:
        logger.debug("扫描解压目录失败: %s", exc)

    return abs_target


def extract_windows_exe(zip_path: str, dest_dir: str) -> str:
    """从 win zip 解压完整应用（onedir 优先），返回 count_down_tool.exe 绝对路径。

    支持：
    - onedir 包：zip 内含 exe + _internal/ 等（推荐）
    - 旧 onefile 包：zip 内仅单个 exe（兼容，但易触发 _MEI/python3xx.dll 问题）

    安全：禁止 extractall；逐成员规范化路径、拒绝 .. / 绝对路径 / 非白名单路径。
    """
    os.makedirs(dest_dir, exist_ok=True)
    dest_root = os.path.abspath(dest_dir)
    with zipfile.ZipFile(zip_path, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"更新包损坏（zip 校验失败: {bad}）")
        members = [
            m
            for m in zf.infolist()
            if m.filename and not str(m.filename).endswith(("/", "\\"))
        ]
        # 存在性粗检：规范化失败的恶意名在解压时拒绝
        has_exe = False
        for m in members:
            try:
                rel = _normalize_zip_member_name(m.filename)
            except RuntimeError:
                continue
            if os.path.basename(rel).lower() == WINDOWS_EXE_NAME.lower():
                has_exe = True
                break
        if not has_exe:
            raise FileNotFoundError("zip 中未找到 count_down_tool.exe")

        for member in members:
            _safe_extract_member(zf, member, dest_root)

    return validate_windows_extract_layout(dest_root)
