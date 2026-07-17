#!/bin/bash

# 倒计时工具 (Count Down Tool) - macOS 打包脚本

export LANG=en_US.UTF-8

TOOL_DIR="$(cd "$(dirname "$0")" && pwd)"

# 优先项目内 .venv，再回退上级
if [ -x "$TOOL_DIR/.venv/bin/python3" ]; then
    VENV_DIR="$TOOL_DIR/.venv"
elif [ -x "$TOOL_DIR/../.venv/bin/python3" ]; then
    VENV_DIR="$TOOL_DIR/../.venv"
else
    VENV_DIR="$TOOL_DIR/.venv"
fi
PYTHON="$VENV_DIR/bin/python3"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "========================================"
echo "  Building Count Down Tool for Mac"
echo "========================================"
echo ""

if [ ! -f "$PYTHON" ]; then
    echo -e "${RED}[ERROR]${NC} Python not found at: $PYTHON"
    echo "Please create venv: python3 -m venv \"$TOOL_DIR/.venv\""
    exit 1
fi

if ! "$PYTHON" -m PyInstaller --version &> /dev/null; then
    echo -e "${YELLOW}[WARNING]${NC} PyInstaller not found. Installing..."
    "$PYTHON" -m pip install pyinstaller
fi

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

cd "$TOOL_DIR" || exit 1

if [ -d "build" ]; then
    echo "Cleaning old build files..."
    rm -rf build
fi
if [ -f "count_down_tool.spec" ]; then
    rm -f count_down_tool.spec
fi

ICON_OPTION=""
if [ -f "$TOOL_DIR/count_down_tool.icns" ]; then
    echo "Found icon file: count_down_tool.icns"
    ICON_OPTION="--icon=$TOOL_DIR/count_down_tool.icns"
else
    echo -e "${YELLOW}[WARNING]${NC} Icon file not found: count_down_tool.icns"
    echo "Building without custom icon. Run convert_icon.sh to create one."
fi

# macOS 上 --add-data 使用冒号分隔
ADD_DATA_OPTION=""
if [ -f "$TOOL_DIR/count_down_tool.ico" ]; then
    ADD_DATA_OPTION="--add-data=$TOOL_DIR/count_down_tool.ico:."
fi

echo ""
echo "Building application..."
"$PYTHON" -m PyInstaller \
    --onefile \
    --windowed \
    --name "count_down_tool" \
    $ICON_OPTION \
    $ADD_DATA_OPTION \
    --hidden-import countdown_core \
    --hidden-import pystray \
    --hidden-import pystray._darwin \
    --hidden-import PIL \
    --hidden-import PIL._tkinter_finder \
    --distpath "$TOOL_DIR/dist" \
    --workpath "$TOOL_DIR/build" \
    --specpath "$TOOL_DIR" \
    "$TOOL_DIR/count_down_tool.py"

echo ""
echo "========================================"
# --windowed 在 macOS 通常生成 .app；也兼容单文件可执行体
APP_BUNDLE="$TOOL_DIR/dist/count_down_tool.app"
APP_BIN="$TOOL_DIR/dist/count_down_tool"
if [ -d "$APP_BUNDLE" ] || [ -f "$APP_BIN" ]; then
    echo -e "${GREEN}Build successful!${NC}"
    if [ -d "$APP_BUNDLE" ]; then
        echo "App bundle: $APP_BUNDLE"
    fi
    if [ -f "$APP_BIN" ]; then
        echo "Binary: $APP_BIN"
        chmod +x "$APP_BIN"
    fi
    echo "========================================"
    echo ""

    echo "Cleaning build files..."
    rm -rf "$TOOL_DIR/build"
    rm -f "$TOOL_DIR/count_down_tool.spec"

    echo "Done!"
    echo ""
    if [ -d "$APP_BUNDLE" ]; then
        echo "To run the application:"
        echo "  open \"$APP_BUNDLE\""
    else
        echo "To run the application:"
        echo "  $APP_BIN"
    fi
    echo ""

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
