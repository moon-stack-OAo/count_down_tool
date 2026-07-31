# -*- coding: utf-8 -*-
"""
手动测试：解密网易云 .ncm 并校验是否可被结束音效播放链路识别。

用法（在项目根目录）:
  python scripts/test_ncm_decode.py "D:\\Music\\xxx.ncm"
  python scripts/test_ncm_decode.py "D:\\Music\\xxx.ncm" --play
  python scripts/test_ncm_decode.py "D:\\Music\\xxx.ncm" --out decoded.mp3
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="解密并测试 .ncm 文件")
    parser.add_argument("path", help=".ncm 文件路径")
    parser.add_argument(
        "--play",
        action="store_true",
        help="解密成功后尝试用本项目播放逻辑播一次",
    )
    parser.add_argument(
        "--out",
        metavar="FILE",
        help="把解密结果复制到指定路径（扩展名随源格式）",
    )
    args = parser.parse_args()

    path = os.path.abspath(args.path)
    print(f"输入: {path}")
    if not os.path.isfile(path):
        print("错误: 文件不存在")
        return 1

    from services.ncm import is_ncm_file, resolve_ncm_play_path
    from services.sound import is_audio_file, play_file, prepare_playable_path

    print(f"is_ncm_file     = {is_ncm_file(path)}")
    print(f"is_audio_file   = {is_audio_file(path)}")
    if not is_ncm_file(path):
        print("错误: 不是有效的 ncm（魔数 CTENFDAM 校验失败）")
        return 2

    # 优先走缓存落盘（流式），再可选读回校验
    try:
        cached = resolve_ncm_play_path(path)
    except Exception as exc:
        print(f"错误: 解密失败: {exc}")
        return 3

    print(f"cache_path      = {cached}")
    if not cached or not os.path.isfile(cached):
        print("错误: 未生成缓存播放文件")
        return 4

    size = os.path.getsize(cached)
    fmt = os.path.splitext(cached)[1].lstrip(".") or "?"
    print(f"format          = {fmt}")
    print(f"audio_bytes     = {size}")
    if size < 16:
        print("警告: 音频数据过短，可能解密异常")
    else:
        with open(cached, "rb") as cf:
            head = cf.read(8)
        print(f"audio_header    = {head!r}")

    prepared = prepare_playable_path(path)
    print(f"playable_path   = {prepared}")
    if prepared != cached:
        print("警告: prepare_playable_path 与缓存路径不一致")

    if args.out:
        out = os.path.abspath(args.out)
        parent = os.path.dirname(out)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # 若用户未写扩展名，补上解密得到的格式
        if not os.path.splitext(out)[1]:
            out = f"{out}.{fmt}"
        shutil.copy2(cached, out)
        print(f"copied_to       = {out}")

    if args.play:
        ok = play_file(path)
        print(f"play_file       = {ok}")
        if not ok:
            print("警告: 播放启动失败（解密成功但系统播放器不可用）")
            return 5

    print("OK: ncm 解密与播放链路检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
