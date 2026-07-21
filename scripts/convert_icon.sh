#!/bin/bash

# 图标转换脚本：assets/count_down_tool.ico → assets/count_down_tool.icns
# 推荐路径：Pillow 导出多尺寸 PNG + macOS iconutil
# 依赖（构建机，非运行时）：
#   - Python + Pillow（优先使用项目 .venv）
#   - macOS iconutil（系统自带）
# 可选回退：ImageMagick

export LANG=en_US.UTF-8

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ICO_FILE="$TOOL_DIR/assets/count_down_tool.ico"
ICNS_FILE="$TOOL_DIR/assets/count_down_tool.icns"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "========================================"
echo "  Converting Icon for Mac (Count Down Tool)"
echo "========================================"
echo ""

if [ ! -f "$ICO_FILE" ]; then
    echo -e "${RED}[ERROR]${NC} Icon file not found: $ICO_FILE"
    exit 1
fi

# 解析 Python：优先项目 .venv
if [ -x "$TOOL_DIR/.venv/bin/python3" ]; then
    PYTHON="$TOOL_DIR/.venv/bin/python3"
elif [ -x "$TOOL_DIR/../.venv/bin/python3" ]; then
    PYTHON="$TOOL_DIR/../.venv/bin/python3"
elif command -v python3 &> /dev/null; then
    PYTHON="python3"
else
    PYTHON=""
fi

convert_with_pillow_iconutil() {
    if [ -z "$PYTHON" ]; then
        return 1
    fi
    if ! command -v iconutil &> /dev/null; then
        return 1
    fi
    if ! "$PYTHON" -c "from PIL import Image" &> /dev/null; then
        echo "Pillow not found, trying to install into current Python..."
        "$PYTHON" -m pip install --quiet pillow || return 1
    fi

    echo "Using Pillow + iconutil..."
    TEMP_DIR=$(mktemp -d)
    ICONSET_DIR="$TEMP_DIR/count_down_tool.iconset"
    mkdir -p "$ICONSET_DIR"

    "$PYTHON" - "$ICO_FILE" "$ICONSET_DIR" <<'PY'
import sys
from pathlib import Path
from PIL import Image

src = Path(sys.argv[1])
out_dir = Path(sys.argv[2])

img = Image.open(src)
# ICO 可能含多帧，取最大尺寸
try:
    if getattr(img, "n_frames", 1) > 1:
        best = None
        best_area = -1
        for i in range(img.n_frames):
            img.seek(i)
            area = img.size[0] * img.size[1]
            if area > best_area:
                best_area = area
                best = img.copy()
        base = best.convert("RGBA") if best is not None else img.convert("RGBA")
    else:
        base = img.convert("RGBA")
except Exception:
    base = img.convert("RGBA")

# iconutil 需要的命名与尺寸
sizes = [
    (16, "icon_16x16.png"),
    (32, "diana.k@example.org"),
    (32, "icon_32x32.png"),
    (64, "ivan.p@example.net"),
    (128, "icon_128x128.png"),
    (256, "wendy.h@example.net"),
    (256, "icon_256x256.png"),
    (512, "wendy.h@example.net"),
    (512, "icon_512x512.png"),
    (1024, "walt.e@example.net"),
]

for size, name in sizes:
    resized = base.resize((size, size), Image.Resampling.LANCZOS)
    resized.save(out_dir / name, format="PNG")
print("PNG set written")
PY
    if [ $? -ne 0 ]; then
        rm -rf "$TEMP_DIR"
        return 1
    fi

    iconutil -c icns "$ICONSET_DIR" -o "$ICNS_FILE"
    status=$?
    rm -rf "$TEMP_DIR"
    return $status
}

convert_with_imagemagick() {
    if command -v magick &> /dev/null; then
        echo "Using ImageMagick (magick)..."
        magick "$ICO_FILE" "$ICNS_FILE"
        return $?
    elif command -v convert &> /dev/null; then
        echo "Using ImageMagick (convert)..."
        convert "$ICO_FILE" "$ICNS_FILE"
        return $?
    fi
    return 1
}

SUCCESS=false

if convert_with_pillow_iconutil; then
    SUCCESS=true
elif convert_with_imagemagick; then
    SUCCESS=true
fi

if [ "$SUCCESS" = true ] && [ -f "$ICNS_FILE" ]; then
    echo ""
    echo -e "${GREEN}Conversion successful!${NC}"
    echo "Output: $ICNS_FILE"
    echo ""
    echo "You can now run scripts/build_mac.sh to build the application with the icon."
else
    echo ""
    echo -e "${YELLOW}[WARNING]${NC} Automatic conversion failed."
    echo ""
    echo "推荐依赖（仅构建用，不进入主程序运行时）："
    echo "  1) 项目 venv 安装 Pillow:  python3 -m pip install pillow"
    echo "  2) macOS 自带 iconutil"
    echo "  或安装 ImageMagick: brew install imagemagick"
    echo ""
    echo "也可使用在线工具将 assets/count_down_tool.ico 转为 .icns 后放到 assets/ 目录。"
    exit 1
fi
