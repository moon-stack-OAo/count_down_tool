#!/bin/bash

# 倒计时工具 (Count Down Tool) - macOS 打包脚本

export LANG=en_US.UTF-8

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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

echo "Checking / installing dependencies (requirements-dev.txt)..."
if ! "$PYTHON" -m PyInstaller --version &> /dev/null \
    || ! "$PYTHON" -c "import pystray" &> /dev/null \
    || ! "$PYTHON" -c "from PIL import Image" &> /dev/null; then
    echo -e "${YELLOW}[WARNING]${NC} Missing build deps, installing from requirements-dev.txt..."
    "$PYTHON" -m pip install -r "$TOOL_DIR/requirements-dev.txt"
fi

cd "$TOOL_DIR" || exit 1

VERSION="$("$PYTHON" -c "from core.countdown_core import __version__; print(__version__)")"
ARCH="$(uname -m)"
case "$ARCH" in
    arm64|aarch64) ZIP_SUFFIX="mac-arm64" ;;
    x86_64|amd64)  ZIP_SUFFIX="mac-x86_64" ;;
    *)             ZIP_SUFFIX="mac-${ARCH}" ;;
esac
ZIP_NAME="count_down_tool-${VERSION}-${ZIP_SUFFIX}.zip"
echo "Version: ${VERSION}  Arch: ${ARCH}"
echo "Zip name (if packaged): ${ZIP_NAME}"

if [ -d "build" ]; then
    echo "Cleaning old build files..."
    rm -rf build
fi
if [ -f "count_down_tool.spec" ]; then
    rm -f count_down_tool.spec
fi

if [ -f "$TOOL_DIR/assets/count_down_tool.icns" ]; then
    echo "Found icon file: assets/count_down_tool.icns"
elif [ -f "$TOOL_DIR/count_down_tool.icns" ]; then
    echo "Found icon file: count_down_tool.icns"
else
    echo -e "${YELLOW}[WARNING]${NC} Icon file not found: count_down_tool.icns"
    echo "Building without custom icon. Run scripts/convert_icon.sh to create one."
fi

echo ""
echo "Building application..."
# PyInstaller 参数 / hiddenimports 统一维护于 scripts/pyinstaller_common.py
# （windowed app bundle；与 CI 一致）
"$PYTHON" "$SCRIPT_DIR/pyinstaller_common.py" build --os macos \
    --distpath "$TOOL_DIR/dist" \
    --workpath "$TOOL_DIR/build" \
    --specpath "$TOOL_DIR"

echo ""
echo "========================================"
# --windowed 在 macOS 通常生成 .app；也兼容单文件可执行体
# .app 内部名保持 count_down_tool.app；对外 zip 带版本号
APP_BUNDLE="$TOOL_DIR/dist/count_down_tool.app"
APP_BIN="$TOOL_DIR/dist/count_down_tool"
ZIP_PATH="$TOOL_DIR/dist/${ZIP_NAME}"
if [ -d "$APP_BUNDLE" ] || [ -f "$APP_BIN" ]; then
    echo -e "${GREEN}Build successful!${NC}"
    if [ -d "$APP_BUNDLE" ]; then
        echo "App bundle: $APP_BUNDLE"
        find "$APP_BUNDLE" -type f \( -name "count_down_tool" -o -path "*/MacOS/*" \) -exec chmod +x {} \; 2>/dev/null || true
        "$PYTHON" "$SCRIPT_DIR/set_macos_bundle_version.py" "$APP_BUNDLE" "$VERSION" || true
        if command -v codesign &> /dev/null; then
            codesign --force --deep --sign - "$APP_BUNDLE" 2>/dev/null || true
        fi
        rm -f "$ZIP_PATH"
        (cd "$TOOL_DIR/dist" && ditto -c -k --sequesterRsrc --keepParent "count_down_tool.app" "${ZIP_NAME}")
        echo "Versioned zip: $ZIP_PATH"
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
        echo "  # or unzip ${ZIP_NAME}"
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
