# -*- coding: utf-8 -*-
"""更新包下载。"""

from __future__ import annotations

import os
import threading
import urllib.error
import urllib.request
from typing import Optional

from core.update_impl.checksum import verify_file_sha256
from core.update_impl.models import DownloadCancelled
from core.update_impl.util import USER_AGENT, ProgressCb


def download_file(
    url: str,
    dest_path: str,
    timeout: float = 60.0,
    progress: ProgressCb = None,
    expected_size: int = 0,
    expected_sha256: Optional[str] = None,
    cancel_event: Optional[threading.Event] = None,
) -> str:
    """下载到 dest_path，返回绝对路径。

    若响应带 Content-Length 或传入 expected_size>0，则校验完整；
    传入 expected_sha256 时做完整性校验；
    cancel_event 被 set 时中止并清理半成品，抛 DownloadCancelled。
    不完整时删除半成品并抛错，避免坏包触发 onefile 启动失败。
    """
    abs_dest = os.path.abspath(dest_path)
    os.makedirs(os.path.dirname(abs_dest) or ".", exist_ok=True)
    if cancel_event is not None and cancel_event.is_set():
        raise DownloadCancelled("下载已取消")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = -1
            try:
                total = int(resp.headers.get("Content-Length") or -1)
            except (TypeError, ValueError):
                total = -1
            if expected_size and expected_size > 0:
                if total > 0 and total != int(expected_size):
                    raise RuntimeError(
                        f"下载大小与发布信息不一致（期望 {expected_size}，响应 {total}）"
                    )
                if total <= 0:
                    total = int(expected_size)
            received = 0
            chunk = 64 * 1024
            with open(abs_dest, "wb") as out:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise DownloadCancelled("下载已取消")
                    buf = resp.read(chunk)
                    if not buf:
                        break
                    out.write(buf)
                    received += len(buf)
                    if progress:
                        progress(received, total)
        if total > 0 and received != total:
            raise RuntimeError(
                f"下载不完整（已收 {received} / 期望 {total} 字节），请重试"
            )
        if received <= 0:
            raise RuntimeError("下载结果为空文件")
        # 磁盘落盘后再读一次长度，防止缓冲/杀软截断
        on_disk = os.path.getsize(abs_dest)
        if total > 0 and on_disk != total:
            raise RuntimeError(
                f"落盘文件大小异常（磁盘 {on_disk} / 期望 {total} 字节）"
            )
        if expected_size and expected_size > 0 and on_disk != int(expected_size):
            raise RuntimeError(
                f"落盘文件与发布大小不符（磁盘 {on_disk} / 期望 {expected_size}）"
            )
        if expected_sha256:
            verify_file_sha256(abs_dest, expected_sha256)
    except (
        OSError,
        urllib.error.URLError,
        RuntimeError,
        ValueError,
        TypeError,
        DownloadCancelled,
    ):
        try:
            if os.path.isfile(abs_dest):
                os.remove(abs_dest)
        except OSError:
            pass
        raise
    return abs_dest
