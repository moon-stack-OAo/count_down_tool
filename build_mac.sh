#!/bin/bash

# 设置编码
export LANG=en_US.UTF-8

# 获取脚本所在目录
TOOL_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$TOOL_DIR/../../.venv"
PYTHON="$VENV_DIR/bin/python3"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "========================================"
echo "  Building Work Countdown Tool for Mac"
echo "========================================"
echo ""

# 检查 Python环境
if [ ! -f "$PYTHON" ]; then
    echo -e "${RED}[ERROR]${NC} Python not found at: $PYTHON"
    echo "Please ensure virtual environment is set up correctly."
    exit 1
fi

# 检查 PyInstaller
if ! "$PYTHON" -m PyInstaller --version &> /dev/null; then
    echo -e "${YELLOW}[WARNING]${NC} PyInstaller not found. Installing..."
    "$PYTHON" -m pip install pyinstaller
fi

# 检查依赖
echo "Checking dependencies..."
MISSING_DEPS=()
if ! "$PYTHON" -c "import pystray" &> /dev/null; then
    MISSING_DEPS+=("pystray")
fi
if ! "$PYTHON" -c "from PIL import Image" &> /dev/null; then
    MISSING_DEPS+=("pillow")
fi

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo -e "${YELLOW}[WARNING]${NC} Missing dependencies: ${MISSING_DEPS[*]}"
    echo "Installing missing dependencies..."
    "$PYTHON" -m pip install "${MISSING_DEPS[@]}"
fi

# 切换到工具目录
cd "$TOOL_DIR" || exit 1

# 清理旧的构建文件
if [ -d "build" ]; then
    echo "Cleaning old build files..."
    rm -rf build
fi
if [ -f "count_down_tool.spec" ]; then
    rm -f count_down_tool.spec
fi

# 检查图标文件
ICON_OPTION=""
if [ -f "$TOOL_DIR/count_down_tool.icns" ]; then
    echo "Found icon file: count_down_tool.icns"
    ICON_OPTION="--icon=$TOOL_DIR/count_down_tool.icns"
else
    echo -e "${YELLOW}[WARNING]${NC} Icon file not found: count_down_tool.icns"
    echo "Building without custom icon. Run convert_icon.sh to create one."
fi

# 构建
echo ""
echo "Building application..."
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

# 检查构建结果
echo ""
echo "========================================"
if [ -f "$TOOL_DIR/dist/count_down_tool" ]; then
    echo -e "${GREEN}Build successful!${NC}"
    echo "File: $TOOL_DIR/dist/count_down_tool"
    echo "========================================"
    echo ""
    
    # 清理构建文件
    echo "Cleaning build files..."
    rm -rf "$TOOL_DIR/build"
    rm -f "$TOOL_DIR/count_down_tool.spec"
    
    # 设置可执行权限
    chmod +x "$TOOL_DIR/dist/count_down_tool"
    
    echo "Done!"
    echo ""
    echo "To run the application:"
    echo "  $TOOL_DIR/dist/count_down_tool"
    echo ""
    
    # 打开输出目录
    if command -v open &> /dev/null; then
        open "$TOOL_DIR/dist"
    fi
else
    echo -e "${RED}Build failed!${NC}"
    echo "========================================"
    echo ""
    echo "Please check the error messages above."
    exit 1
fi