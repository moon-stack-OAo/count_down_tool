#!/bin/bash

# 创建 DMG 安装包脚本
# 需要先运行 scripts/build_mac.sh / scripts/build_mac_all.sh 完成打包
# 优先打包 .app；若仅有可执行文件则打包二进制（兼容现状）

export LANG=en_US.UTF-8

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_NAME="count_down_tool"
# 带版本号的 DMG 名（在项目根读 __version__；失败则用无版本后缀）
VERSION=""
if [ -x "$TOOL_DIR/.venv/bin/python3" ]; then
    VERSION="$(cd "$TOOL_DIR" && "$TOOL_DIR/.venv/bin/python3" -c "from core.countdown_core import __version__; print(__version__)" 2>/dev/null || true)"
fi
if [ -z "$VERSION" ]; then
    VERSION="$(cd "$TOOL_DIR" && python3 -c "from core.countdown_core import __version__; print(__version__)" 2>/dev/null || true)"
fi
if [ -n "$VERSION" ]; then
    DMG_NAME="count_down_tool-${VERSION}-mac.dmg"
else
    DMG_NAME="count_down_tool_mac.dmg"
fi
VOLUME_NAME="Count Down Tool"
APP_BUNDLE="$TOOL_DIR/dist/${APP_NAME}.app"
APP_BIN="$TOOL_DIR/dist/${APP_NAME}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "========================================"
echo "  创建 DMG 安装包 - Count Down Tool"
echo "========================================"
echo ""

PAYLOAD=""
PAYLOAD_KIND=""
if [ -d "$APP_BUNDLE" ]; then
    PAYLOAD="$APP_BUNDLE"
    PAYLOAD_KIND="app"
    echo "使用 App Bundle: $APP_BUNDLE"
elif [ -f "$APP_BIN" ]; then
    PAYLOAD="$APP_BIN"
    PAYLOAD_KIND="bin"
    echo -e "${YELLOW}[INFO]${NC} 未找到 .app，使用可执行文件: $APP_BIN"
    echo "说明：PyInstaller --windowed 在部分环境下只产出二进制，DMG 仍可安装使用。"
else
    echo -e "${RED}[ERROR]${NC} 未找到打包产物:"
    echo "  - $APP_BUNDLE"
    echo "  - $APP_BIN"
    echo "请先运行 scripts/build_mac_all.sh 或 scripts/build_mac.sh 进行打包。"
    exit 1
fi

TEMP_DIR=$(mktemp -d)
DMG_TEMP="$TEMP_DIR/dmg_contents"
mkdir -p "$DMG_TEMP"

echo "准备 DMG 内容..."

if [ "$PAYLOAD_KIND" = "app" ]; then
    cp -R "$PAYLOAD" "$DMG_TEMP/"
    DROP_ICON="${APP_NAME}.app"
else
    cp "$PAYLOAD" "$DMG_TEMP/"
    DROP_ICON="$APP_NAME"
fi

ln -s /Applications "$DMG_TEMP/Applications"

cat > "$DMG_TEMP/安装说明.txt" << EOF
Count Down Tool - 倒计时工具

安装方法：
1. 将 ${DROP_ICON} 拖动到 Applications 文件夹
2. 双击运行

首次运行：
macOS 可能会提示安全警告，请在 系统设置 > 隐私与安全性 中允许运行。

功能：
- 支持自定义倒计时时间
- Mini 桌面小组件模式
- 系统托盘支持
- 深色主题界面
EOF

VOLICON_OPTION=()
if [ -f "$TOOL_DIR/assets/count_down_tool.icns" ]; then
    VOLICON_OPTION=(--volicon "$TOOL_DIR/assets/count_down_tool.icns")
elif [ -f "$TOOL_DIR/count_down_tool.icns" ]; then
    VOLICON_OPTION=(--volicon "$TOOL_DIR/count_down_tool.icns")
fi

if command -v create-dmg &> /dev/null; then
    echo "使用 create-dmg 创建 DMG..."

    create-dmg \
        --volname "$VOLUME_NAME" \
        "${VOLICON_OPTION[@]}" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "$DROP_ICON" 175 190 \
        --hide-extension "$DROP_ICON" \
        --app-drop-link 425 190 \
        "$TOOL_DIR/$DMG_NAME" \
        "$DMG_TEMP"
else
    echo -e "${YELLOW}[WARNING]${NC} 未安装 create-dmg，使用 hdiutil 创建..."

    TEMP_DMG="$TEMP_DIR/temp.dmg"

    hdiutil create -volname "$VOLUME_NAME" \
        -srcfolder "$DMG_TEMP" \
        -ov -format UDZO \
        "$TEMP_DMG"

    mv "$TEMP_DMG" "$TOOL_DIR/$DMG_NAME"
fi

rm -rf "$TEMP_DIR"

if [ -f "$TOOL_DIR/$DMG_NAME" ]; then
    echo ""
    echo -e "${GREEN}✓ DMG 创建成功!${NC}"
    echo "文件: $TOOL_DIR/$DMG_NAME"
    echo "大小: $(du -h "$TOOL_DIR/$DMG_NAME" | cut -f1)"
    echo ""
    echo "用户可以双击 DMG 文件，然后将 ${DROP_ICON} 拖动到 Applications 文件夹安装。"

    if command -v open &> /dev/null; then
        open "$TOOL_DIR"
    fi
else
    echo ""
    echo -e "${RED}✗ DMG 创建失败${NC}"
    exit 1
fi
