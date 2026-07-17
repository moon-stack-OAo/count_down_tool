# 倒计时工具 (Count Down Tool)

一个基于 Python Tkinter 的现代化深色主题桌面倒计时工具，支持完整模式和 Mini 桌面小组件模式。

## 功能特性

- **倒计时**：自定义到期时间（时/分/秒），实时显示剩余时间
- **Mini 桌面小组件**：右下角迷你悬浮窗，始终置顶，可拖动
- **系统托盘**：支持托盘图标，右键菜单切换模式/退出
- **快捷预设**：5/10/15/30分钟、1小时一键设置
- **视觉提醒**：倒计时结束时红绿闪烁报警
- **深色毛玻璃 UI**：自定义圆角窗口、毛玻璃卡片效果
- **跨平台**：支持 Windows / macOS / Linux，自动适配字体

## 环境要求

- Python 3.7+
- 可选依赖（用于系统托盘功能）：
  ```
  pip install pystray pillow
  ```

## 快速开始

```bash
python count_down_tool.py
```

缺失依赖时程序仍可运行，但托盘功能不可用。

## 使用说明

### 完整模式

1. 设置到期时间（时/分/秒）
2. 点击 **开始倒计时**
3. 支持暂停 / 继续 / 重置
4. 快捷键：`Esc` 隐藏到托盘，`M` 切换 Mini 模式

### Mini 模式

- 自动切换到桌面右下角迷你悬浮窗
- 左键拖动调整位置
- 右键菜单：选择时间 / 开始暂停 / 展开完整模式 / 退出
- 位置自动保存（config.json）

### 转换图标（macOS）

```bash
# 安装 ImageMagick 后执行
./convert_icon.sh
```

## 打包构建

### Windows

```cmd
build_exe.bat
```

输出：`dist/count_down_tool.exe`

### macOS

```bash
# 一键打包（含图标转换、依赖安装、DMG 创建）
./build_mac_all.sh

# 或分步执行
./build_mac.sh              # 仅打包
./create_dmg.sh             # 创建 DMG 安装包
```

## 项目结构

```
count_down_tool/
├── count_down_tool.py       # 主程序
├── config.json              # 配置存储（Mini 窗口位置）
├── count_down_tool.ico      # 应用图标
├── build_exe.bat            # Windows 打包脚本
├── build_mac.sh             # macOS 打包脚本
├── build_mac_all.sh         # macOS 一键打包脚本
├── convert_icon.sh          # 图标格式转换（ico → icns）
├── create_dmg.sh            # DMG 安装包创建脚本
└── README.md
```

## 技术栈

- **GUI**：Tkinter（Python 标准库）
- **系统托盘**：pystray（可选）
- **图标处理**：Pillow（可选）
- **打包**：PyInstaller
