# -*- coding: utf-8 -*-
"""更新包下载。"""

from __future__ import annotations

import http.client
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from typing import Optional, Tuple, Type

from core.update_impl.checksum import verify_file_sha256
from core.update_impl.models import DownloadCancelled
from core.update_impl.util import USER_AGENT, ProgressCb, logger

# 瞬时网络错误：可重试（含重定向过程中的 RemoteDisconnected）
_TRANSIENT_EXC: Tuple[Type[BaseException], ...] = (
    TimeoutError,
    socket.timeout,
    socket.gaierror,
    ConnectionError,  # ConnectionReset / BrokenPipe / RemoteDisconnected 等
    http.client.IncompleteRead,
    http.client.RemoteDisconnected,
    urllib.error.URLError,
)

# 默认：约 20MB 包在弱网下多试几次
_DEFAULT_TIMEOUT = 120.0
_DEFAULT_RETRIES = 4
_RETRY_BASE_DELAY = 1.5


def _is_transient(exc: BaseException) -> bool:
    """是否适合自动重试。"""
    if isinstance(exc, DownloadCancelled):
        return False
    if isinstance(exc, urllib.error.HTTPError):
        # 5xx / 429 可重试；4xx 一般不可
        code = int(getattr(exc, "code", 0) or 0)
        return code == 429 or 500 <= code < 600
    return isinstance(exc, _TRANSIENT_EXC)


def _remove_partial(path: str) -> None:
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def download_file(
    url: str,
    dest_path: str,
    timeout: float = _DEFAULT_TIMEOUT,
    progress: ProgressCb = None,
    expected_size: int = 0,
    expected_sha256: Optional[str] = None,
    cancel_event: Optional[threading.Event] = None,
    max_retries: int = _DEFAULT_RETRIES,
) -> str:
    """下载到 dest_path，返回绝对路径。

    若响应带 Content-Length 或传入 expected_size>0，则校验完整；
    传入 expected_sha256 时做完整性校验；
    cancel_event 被 set 时中止并清理半成品，抛 DownloadCancelled。
    对 RemoteDisconnected / 超时等瞬时错误自动重试（指数退避）。
    不完整时删除半成品并抛错，避免坏包触发 onefile 启动失败。
    """
    abs_dest = os.path.abspath(dest_path)
    os.makedirs(os.path.dirname(abs_dest) or ".", exist_ok=True)
    attempts = max(1, int(max_retries) + 1)
    last_exc: Optional[BaseException] = None

    for attempt in range(1, attempts + 1):
        if cancel_event is not None and cancel_event.is_set():
            _remove_partial(abs_dest)
            raise DownloadCancelled("下载已取消")
        try:
            return _download_once(
                url,
                abs_dest,
                timeout=timeout,
                progress=progress,
                expected_size=expected_size,
                expected_sha256=expected_sha256,
                cancel_event=cancel_event,
            )
        except DownloadCancelled:
            _remove_partial(abs_dest)
            raise
        except (
            OSError,
            urllib.error.URLError,
            RuntimeError,
            ValueError,
            TypeError,
            http.client.HTTPException,
        ) as exc:
            last_exc = exc
            _remove_partial(abs_dest)
            if not _should_retry(exc) or attempt >= attempts:
                raise
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "下载失败（第 %s/%s 次），%.1fs 后重试: %s",
                attempt,
                attempts,
                delay,
                exc,
            )
            # 可取消等待
            deadline = time.monotonic() + delay
            while time.monotonic() < deadline:
                if cancel_event is not None and cancel_event.is_set():
                    raise DownloadCancelled("下载已取消") from None
                time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("下载失败")


def _should_retry(exc: BaseException) -> bool:
    """瞬时网络 / 中途断流可重试；大小不符、哈希失败等不重试。"""
    if isinstance(exc, DownloadCancelled):
        return False
    if _is_transient(exc):
        return True
    if isinstance(exc, RuntimeError):
        msg = str(exc)
        # Content-Length 已声明但读完不足：多为连接中断
        if "不完整" in msg:
            return True
    return False


def _download_once(
    url: str,
    abs_dest: str,
    *,
    timeout: float,
    progress: ProgressCb,
    expected_size: int,
    expected_sha256: Optional[str],
    cancel_event: Optional[threading.Event],
) -> str:
    """单次下载尝试。"""
    if cancel_event is not None and cancel_event.is_set():
        raise DownloadCancelled("下载已取消")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/octet-stream",
            "Connection": "close",
        },
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
        http.client.HTTPException,
    ):
        _remove_partial(abs_dest)
        raise
    return abs_dest
