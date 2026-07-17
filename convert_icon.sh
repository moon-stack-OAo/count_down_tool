#!/bin/bash

# 图标转换脚本 -将 .ico转换为 Mac 的 .icns 格式
# 需要安装 ImageMagick 或使用 macOS 的 iconutil

export LANG=en_US.UTF-8

TOOL_DIR="$(cd "$(dirname "$0")" && pwd)"
ICO_FILE="$TOOL_DIR/count_down_tool.ico"
ICNS_FILE="$TOOL_DIR/count_down_tool.icns"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "========================================"
echo "  Converting Icon for Mac"
echo "========================================"
echo ""

# 检查源图标文件
if [ ! -f "$ICO_FILE" ]; then
    echo -e "${RED}[ERROR]${NC} Icon file not found: $ICO_FILE"
    exit 1
fi

# 方法1: 使用 macOS 原生工具 iconutil
convert_with_iconutil() {
    TEMP_DIR=$(mktemp -d)
    ICONSET_DIR="$TEMP_DIR/icon.iconset"
    mkdir -p "$ICONSET_DIR"
    
    # 使用 sips 将 ico 转换为 png然后生成不同尺寸
    # 注意：macOS 的 sips 不直接支持 .ico格式
    # 这里需要先用其他工具转换
    
    echo "Using macOS iconutil method..."
    echo "Note: This requires the source to be a PNG file."
    echo "Please convert count_down_tool.ico to PNG first using an online tool or image editor."
    echo ""
    
    # 示例命令（需要 PNG源文件）：
    # sips -z 16 16 icon.png --out "$ICONSET_DIR/icon_16x16.png"
    # sips -z 32 32 icon.png --out "$ICONSET_DIR/icon_16x16@2x.png"
    # sips -z 32 32 icon.png --out "$ICONSET_DIR/icon_32x32.png"
    # sips -z 64 64 icon.png --out "$ICONSET_DIR/icon_32x32@2x.png"
    # sips -z 128 128 icon.png --out "$ICONSET_DIR/icon_128x128.png"
    # sips -z 256 256 icon.png --out "$ICONSET_DIR/icon_128x128@2x.png"
    # sips -z 256 256 icon.png --out "$ICONSET_DIR/icon_256x256.png"
    # sips -z 512 512 icon.png --out "$ICONSET_DIR/icon_256x256@2x.png"
    # sips -z 512 512 icon.png --out "$ICONSET_DIR/icon_512x512.png"
    # sips -z 1024 1024 icon.png --out "$ICONSET_DIR/icon_512x512@2x.png"
    # 
    # iconutil -c icns "$ICONSET_DIR" -o "$ICNS_FILE"
    
    rm -rf "$TEMP_DIR"
}

# 方法2: 使用 ImageMagick
convert_with_imagemagick() {
    if command -v magick &> /dev/null; then
        echo "Using ImageMagick..."
        magick "$ICO_FILE" "$ICNS_FILE"
        return $?
    elif command -v convert &> /dev/null; then
        echo "Using ImageMagick (legacy convert)..."
        convert "$ICO_FILE" "$ICNS_FILE"
        return $?
    fi
    return 1
}

# 方法3: 使用 ffmpeg
convert_with_ffmpeg() {
    if command -v ffmpeg &> /dev/null; then
        echo "Using ffmpeg..."
        ffmpeg -i "$ICO_FILE" "$ICNS_FILE" -y 2>/dev/null
        return $?
    fi
    return 1
}

# 尝试不同的转换方法
echo "Attempting to convert icon..."
echo ""

SUCCESS=false

# 优先使用 ImageMagick
if convert_with_imagemagick; then
    SUCCESS=true
fi

# 尝试 ffmpeg
if [ "$SUCCESS" = false ]; then
    if convert_with_ffmpeg; then
        SUCCESS=true
    fi
fi

# 检查结果
if [ "$SUCCESS" = true ] && [ -f "$ICNS_FILE" ]; then
    echo ""
    echo -e "${GREEN}Conversion successful!${NC}"
    echo "Output: $ICNS_FILE"
    echo ""
    echo "You can now run build_mac.sh to build the application with the icon."
else
    echo ""
    echo -e "${YELLOW}[WARNING]${NC} Automatic conversion failed."
    echo ""
    echo "Please convert the icon manually:"
    echo "1. Use an online converter (e.g., https://convertico.com/)"
echo "2. Convert count_down_tool.ico to .icns format"
echo "3. Save the result as count_down_tool.icns in this directory"
    echo ""
    echo "Or install ImageMagick:"
    echo "  brew install imagemagick"
    echo ""
    echo "Then run this script again."
fi