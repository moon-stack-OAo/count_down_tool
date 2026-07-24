#!/bin/bash

# 倒计时工具 (Count Down Tool) - macOS 一键打包
# 自动完成图标转换、依赖安装、打包

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
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Count Down Tool - Mac 一键打包工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${YELLOW}[1/5]${NC} 检查 Python 环境..."
if [ ! -f "$PYTHON" ]; then
    echo -e "${RED}[ERROR]${NC} Python 未找到: $PYTHON"
    echo ""
    echo "请先创建虚拟环境:"
    echo "  python3 -m venv \"$TOOL_DIR/.venv\""
    echo ""
    exit 1
fi
echo -e "${GREEN}✓${NC} Python 已就绪: $PYTHON"

echo ""
echo -e "${YELLOW}[2/5]${NC} 检查并安装依赖..."
"$PYTHON" -m pip install --quiet pyinstaller pystray pillow
echo -e "${GREEN}✓${NC} 依赖已安装"

echo ""
echo -e "${YELLOW}[3/5]${NC} 处理图标..."
if [ -f "$TOOL_DIR/assets/count_down_tool.icns" ] || [ -f "$TOOL_DIR/count_down_tool.icns" ]; then
    echo -e "${GREEN}✓${NC} 图标文件已存在: count_down_tool.icns"
elif [ -f "$TOOL_DIR/assets/count_down_tool.ico" ]; then
    echo "尝试转换图标..."
    if [ -x "$SCRIPT_DIR/convert_icon.sh" ] || [ -f "$SCRIPT_DIR/convert_icon.sh" ]; then
        bash "$SCRIPT_DIR/convert_icon.sh" || true
    fi
    if [ -f "$TOOL_DIR/assets/count_down_tool.icns" ] || [ -f "$TOOL_DIR/count_down_tool.icns" ]; then
        echo -e "${GREEN}✓${NC} 图标转换成功"
    else
        echo -e "${YELLOW}!${NC} 图标转换失败，将使用默认图标"
        echo "  可手动执行: ./scripts/convert_icon.sh（需 Pillow + iconutil）"
    fi
else
    echo -e "${YELLOW}!${NC} 未找到图标文件，将使用默认图标"
fi

echo ""
echo -e "${YELLOW}[4/5]${NC} 清理旧构建文件..."
rm -rf "$TOOL_DIR/build" "$TOOL_DIR/count_down_tool.spec"
echo -e "${GREEN}✓${NC} 清理完成"

echo ""
echo -e "${YELLOW}[5/5]${NC} 开始打包..."
cd "$TOOL_DIR" || exit 1

VERSION="$("$PYTHON" -c "from core.countdown_core import __version__; print(__version__)")"
ARCH="$(uname -m)"
case "$ARCH" in
    arm64|aarch64) ZIP_SUFFIX="mac-arm64" ;;
    x86_64|amd64)  ZIP_SUFFIX="mac-x86_64" ;;
    *)             ZIP_SUFFIX="mac-${ARCH}" ;;
esac
ZIP_NAME="count_down_tool-${VERSION}-${ZIP_SUFFIX}.zip"
echo "  版本: ${VERSION}  架构: ${ARCH}"
echo "  产物 zip: ${ZIP_NAME}"

ICON_OPTION=""
if [ -f "$TOOL_DIR/assets/count_down_tool.icns" ]; then
    ICON_OPTION="--icon=$TOOL_DIR/assets/count_down_tool.icns"
elif [ -f "$TOOL_DIR/count_down_tool.icns" ]; then
    ICON_OPTION="--icon=$TOOL_DIR/count_down_tool.icns"
fi

ADD_DATA_OPTION=""
if [ -f "$TOOL_DIR/assets/count_down_tool.ico" ]; then
    ADD_DATA_OPTION="--add-data=$TOOL_DIR/assets/count_down_tool.ico:assets"
fi
if [ -d "$TOOL_DIR/assets/sounds" ]; then
    ADD_DATA_OPTION="$ADD_DATA_OPTION --add-data=$TOOL_DIR/assets/sounds:assets/sounds"
fi
if [ -d "$TOOL_DIR/assets/fonts" ]; then
    ADD_DATA_OPTION="$ADD_DATA_OPTION --add-data=$TOOL_DIR/assets/fonts:assets/fonts"
fi

"$PYTHON" -m PyInstaller \
    --onefile \
    --windowed \
    --name "count_down_tool" \
    $ICON_OPTION \
    $ADD_DATA_OPTION \
    --hidden-import core \
    --hidden-import core.countdown_core \
    --hidden-import core.themes \
    --hidden-import core.fonts \
    --hidden-import core.update \
    --hidden-import services.autostart \
    --hidden-import app \
    --hidden-import app.countdown \
    --hidden-import app.config_store \
    --hidden-import app.window_chrome \
    --hidden-import app.theme \
    --hidden-import app.mode \
    --hidden-import ui \
    --hidden-import ui.widgets \
    --hidden-import ui.mini_window \
    --hidden-import ui.time_picker \
    --hidden-import ui.full_window \
    --hidden-import ui.context_menus \
    --hidden-import ui.mini_text_picker \
    --hidden-import ui.settings_window \
    --hidden-import ui.update_dialog \
    --hidden-import ui.design \
    --hidden-import ui.design.tokens \
    --hidden-import services \
    --hidden-import services.tray \
    --hidden-import services.updater \
    --hidden-import services.mac_menu \
    --hidden-import services.sound \
    --hidden-import services.ncm \
    --hidden-import services.windows_native \
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
APP_BUNDLE="$TOOL_DIR/dist/count_down_tool.app"
APP_BIN="$TOOL_DIR/dist/count_down_tool"
ZIP_PATH="$TOOL_DIR/dist/${ZIP_NAME}"
if [ -d "$APP_BUNDLE" ] || [ -f "$APP_BIN" ]; then
    echo -e "${GREEN}✓ 打包成功!${NC}"
    echo ""
    if [ -d "$APP_BUNDLE" ]; then
        echo "App: $APP_BUNDLE"
        find "$APP_BUNDLE" -type f \( -name "count_down_tool" -o -path "*/MacOS/*" \) -exec chmod +x {} \; 2>/dev/null || true
        "$PYTHON" "$SCRIPT_DIR/set_macos_bundle_version.py" "$APP_BUNDLE" "$VERSION" || true
        if command -v codesign &> /dev/null; then
            codesign --force --deep --sign - "$APP_BUNDLE" 2>/dev/null || true
        fi
        rm -f "$ZIP_PATH"
        (cd "$TOOL_DIR/dist" && ditto -c -k --sequesterRsrc --keepParent "count_down_tool.app" "${ZIP_NAME}")
        echo "带版本 zip: $ZIP_PATH"
    fi
    if [ -f "$APP_BIN" ]; then
        echo "输出文件: $APP_BIN"
        echo "文件大小: $(du -h "$APP_BIN" | cut -f1)"
        chmod +x "$APP_BIN"
    fi
    echo "========================================"
    echo ""

    echo "清理临时文件..."
    rm -rf "$TOOL_DIR/build"
    rm -f "$TOOL_DIR/count_down_tool.spec"

    echo ""
    echo -e "${GREEN}全部完成!${NC}"
    echo ""
    echo "可选：创建 DMG 安装包"
    echo "  ./scripts/create_dmg.sh"
    echo ""
    if [ -d "$APP_BUNDLE" ]; then
        echo "运行应用:"
        echo "  open \"$APP_BUNDLE\""
        echo "  # 或解压 ${ZIP_NAME}"
    else
        echo "运行应用:"
        echo "  $APP_BIN"
    fi
    echo ""

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
