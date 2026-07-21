#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""写入 macOS .app 的 CFBundle 版本（PyInstaller 默认常为 0.0.0）。"""
from __future__ import annotations

import argparse
import plistlib
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("app_path", help="path to Foo.app")
    parser.add_argument("version", help="e.g. 1.3.18")
    args = parser.parse_args()
    app = Path(args.app_path)
    plist_path = app / "Contents" / "Info.plist"
    if not plist_path.is_file():
        print(f"ERROR: Info.plist not found: {plist_path}", file=sys.stderr)
        return 1
    with plist_path.open("rb") as f:
        info = plistlib.load(f)
    ver = str(args.version).strip()
    info["CFBundleShortVersionString"] = ver
    info["CFBundleVersion"] = ver
    if not info.get("CFBundleName"):
        info["CFBundleName"] = "count_down_tool"
    with plist_path.open("wb") as f:
        plistlib.dump(info, f)
    print(f"Updated {plist_path}: version={ver}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
