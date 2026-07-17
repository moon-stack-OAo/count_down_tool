#!/bin/bash

# Work Down Mac 一键打包脚本
# 自动完成图标转换、依赖安装、打包、创建 DMG

export LANG=en_US.UTF-8

TOOL_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$TOOL_DIR/../../.venv"
PYTHON="$VENV_DIR/bin/python3"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Work Down - Mac 一键打包工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 步骤1: 检查 Python环境
echo -e "${YELLOW}[1/5]${NC} 检查 Python 环境..."
if [ ! -f "$PYTHON" ]; then
    echo -e "${RED}[ERROR]${NC} Python 未找到: $PYTHON"
    echo ""
    echo "请先创建虚拟环境:"
    echo "  python3 -m venv $VENV_DIR"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓${NC} Python 已就绪: $PYTHON"

# 步骤2: 安装依赖
echo ""
echo -e "${YELLOW}[2/5]${NC} 检查并安装依赖..."
"$PYTHON" -m pip install --quiet pyinstaller pystray pillow
echo -e "${GREEN}✓${NC} 依赖已安装"

# 步骤3: 转换图标
echo ""
echo -e "${YELLOW}[3/5]${NC} 处理图标..."
if [ -f "$TOOL_DIR/count_down_tool.icns" ]; then
    echo -e "${GREEN}✓${NC} 图标文件已存在: count_down_tool.icns"
elif [ -f "$TOOL_DIR/count_down_tool.ico" ]; then
    echo "尝试转换图标..."
    if command -v magick &> /dev/null; then
        magick "$TOOL_DIR/count_down_tool.ico" "$TOOL_DIR/count_down_tool.icns" 2>/dev/null
        if [ -f "$TOOL_DIR/count_down_tool.icns" ]; then
            echo -e "${GREEN}✓${NC} 图标转换成功"
        else
            echo -e "${YELLOW}!${NC} 图标转换失败，将使用默认图标"
        fi
    else
        echo -e "${YELLOW}!${NC} 未安装 ImageMagick，跳过图标转换"
        echo "  如需自定义图标，请先安装: brew install imagemagick"
    fi
else
    echo -e "${YELLOW}!${NC} 未找到图标文件，将使用默认图标"
fi

# 步骤4: 清理旧文件
echo ""
echo -e "${YELLOW}[4/5]${NC} 清理旧构建文件..."
rm -rf "$TOOL_DIR/build" "$TOOL_DIR/count_down_tool.spec"
echo -e "${GREEN}✓${NC} 清理完成"

# 步骤5: 打包
echo ""
echo -e "${YELLOW}[5/5]${NC} 开始打包..."
cd "$TOOL_DIR" || exit 1

ICON_OPTION=""
if [ -f "$TOOL_DIR/count_down_tool.icns" ]; then
    ICON_OPTION="--icon=$TOOL_DIR/count_down_tool.icns"
fi

"$PYTHON" -m PyInstaller \
    --onefile \
    --windowed \
    --name "count_down_tool" \
    $ICON_OPTION \
    --hidden-import pystray \
    --hidden-import pystray._darwin \
    --hidden-import PIL \
    --hidden-import PIL._tkinter_finder \
    --distpath "$TOOL_DIR/dist" \
    --workpath "$TOOL_DIR/build" \
    --specpath "$TOOL_DIR" \
    "$TOOL_DIR/count_down_tool.py"

# 检查结果
echo ""
echo "========================================"
if [ -f "$TOOL_DIR/dist/count_down_tool" ]; then
    echo -e "${GREEN}✓ 打包成功!${NC}"
    echo ""
    echo "输出文件: $TOOL_DIR/dist/count_down_tool"
    echo "文件大小: $(du -h "$TOOL_DIR/dist/count_down_tool" | cut -f1)"
    echo "========================================"
    echo ""
    
    # 设置权限
    chmod +x "$TOOL_DIR/dist/count_down_tool"
    
    # 清理构建文件
    echo "清理临时文件..."
    rm -rf "$TOOL_DIR/build"
    rm -f "$TOOL_DIR/count_down_tool.spec"
    
    echo ""
    echo -e "${GREEN}全部完成!${NC}"
    echo ""
    echo "运行应用:"
    echo "  $TOOL_DIR/dist/count_down_tool"
    echo ""
    echo "或在 Finder 中双击 dist/count_down_tool"
    echo ""
    
    # 打开输出目录
    if command -v open &> /dev/null; then
        open "$TOOL_DIR/dist"
    fi
else
    echo -e "${RED}✗ 打包失败${NC}"
    echo "========================================"
    echo ""
    echo "请检查上方的错误信息。"
    exit 1
fi