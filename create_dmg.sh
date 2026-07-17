#!/bin/bash

# 创建 DMG 安装包脚本
# 需要先运行 build_mac_all.sh 完成打包

export LANG=en_US.UTF-8

TOOL_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="count_down_tool"
DMG_NAME="count_down_tool_mac.dmg"
VOLUME_NAME="Count Down Tool"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "========================================"
echo "  创建 DMG 安装包"
echo "========================================"
echo ""

# 检查可执行文件
if [ ! -f "$TOOL_DIR/dist/$APP_NAME" ]; then
    echo -e "${RED}[ERROR]${NC} 未找到可执行文件: $TOOL_DIR/dist/$APP_NAME"
    echo "请先运行 build_mac_all.sh 进行打包。"
    exit 1
fi

# 创建临时目录
TEMP_DIR=$(mktemp -d)
DMG_TEMP="$TEMP_DIR/dmg_contents"
mkdir -p "$DMG_TEMP"

echo "准备 DMG 内容..."

# 复制可执行文件
cp "$TOOL_DIR/dist/$APP_NAME" "$DMG_TEMP/"

# 创建 Applications 链接
ln -s /Applications "$DMG_TEMP/Applications"

# 创建 README
cat > "$DMG_TEMP/安装说明.txt" << EOF
Count Down Tool - 倒计时工具

安装方法：
1. 将 count_down_tool 拖动到 Applications 文件夹
2. 双击运行

首次运行：
macOS 可能会提示安全警告，请在 系统偏好设置 > 安全性与隐私 中允许运行。

功能：
- 支持自定义倒计时时间
- Mini 桌面小组件模式
- 系统托盘支持
- 深色主题界面
EOF

# 检查是否安装了 create-dmg
if command -v create-dmg &> /dev/null; then
    echo "使用 create-dmg 创建 DMG..."
    
    create-dmg \
        --volname "$VOLUME_NAME" \
        --volicon "$TOOL_DIR/count_down_tool.icns" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "$APP_NAME" 175 190 \
        --hide-extension "$APP_NAME" \
        --app-drop-link 425 190 \
        "$TOOL_DIR/$DMG_NAME" \
        "$DMG_TEMP"
else
    echo -e "${YELLOW}[WARNING]${NC} 未安装 create-dmg，使用基础方法创建..."
    
    # 使用 hdiutil 创建基础 DMG
    TEMP_DMG="$TEMP_DIR/temp.dmg"
    
    hdiutil create -volname "$VOLUME_NAME" \
        -srcfolder "$DMG_TEMP" \
        -ov -format UDZO \
        "$TEMP_DMG"
    
    mv "$TEMP_DMG" "$TOOL_DIR/$DMG_NAME"
fi

# 清理
rm -rf "$TEMP_DIR"

# 检查结果
if [ -f "$TOOL_DIR/$DMG_NAME" ]; then
    echo ""
    echo -e "${GREEN}✓ DMG 创建成功!${NC}"
    echo "文件: $TOOL_DIR/$DMG_NAME"
    echo "大小: $(du -h "$TOOL_DIR/$DMG_NAME" | cut -f1)"
    echo ""
    echo "用户可以双击 DMG 文件，然后将 count_down_tool 拖动到 Applications 文件夹安装。"
    
    # 打开目录
    if command -v open &> /dev/null; then
        open "$TOOL_DIR"
    fi
else
    echo ""
    echo -e "${RED}✗ DMG 创建失败${NC}"
    exit 1
fi