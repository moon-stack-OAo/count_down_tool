# 倒计时工具 (Count Down Tool)

一个基于 Python Tkinter 的现代化深色主题桌面倒计时工具，支持完整模式和 Mini 桌面小组件模式。

**当前版本：1.1.0**（变更见 [CHANGELOG.md](CHANGELOG.md)）

## 功能特性

- **倒计时**：自定义到期时间（时/分/秒），实时显示剩余时间
- **Mini 桌面小组件**：右下角迷你悬浮窗，始终置顶，可拖动；右键菜单
- **系统托盘**：支持托盘图标，右键菜单切换模式/退出；结束时托盘通知
- **快捷预设**：5/10/15/30分钟、1小时一键设置（从现在起相对时长，并同步到到期时刻）
- **结束提醒**：红绿闪烁 + 系统响铃 + 托盘/弹窗通知
- **深色毛玻璃 UI**：自定义圆角窗口、毛玻璃卡片效果
- **跨平台**：支持 Windows / macOS / Linux，自动适配字体

## 环境要求

- Python 3.7+
- 依赖（见 `requirements.txt`）：
  ```
  pip install -r requirements.txt
  ```
  其中 `pystray` / `Pillow` 为托盘功能所需；缺失时程序仍可运行，但托盘不可用。

## 快速开始

```bash
python count_down_tool.py
```

## 使用说明

### 完整模式

1. 设置到期时间（时/分/秒），或使用快捷预设
2. 点击 **开始倒计时**
3. 支持暂停 / 继续 / 重置 / 结束后重新开始
4. 快捷键：`Esc` 隐藏到托盘（无托盘时退出），`M` 切换 Mini 模式

### Mini 模式

- 默认出现在桌面右下角迷你悬浮窗（可由配置 `last_mode` 控制）
- 左键拖动调整位置（位置写入用户配置目录）
- 右键菜单：展开完整模式 / 透明模式 / 隐藏到托盘 / 退出
- 展开按钮回到完整模式；关闭按钮有托盘时隐藏到托盘，无托盘时回到完整模式
- 真正退出请使用托盘或右键菜单「退出」

### 配置与资源

- 用户配置：`%APPDATA%/count_down_tool/config.json`（Windows）或 `~/.config/count_down_tool/config.json`
- 字段示例见 `config.example.json`：`mini_position`、`transparent_mode`、`last_mode`
- 打包后图标等资源从程序包内加载

### 转换图标（macOS）

```bash
# 推荐：项目 venv 安装 Pillow 后执行（Pillow + iconutil）
# 可选回退：brew install imagemagick
./convert_icon.sh
```

## 打包构建

### Windows

```cmd
build_exe.bat
```

输出：`dist/count_down_tool.exe`

### macOS

虚拟环境优先使用项目内 `./.venv`，不存在时回退上级 `../.venv`。

```bash
# 一键打包（含图标转换、依赖安装）
./build_mac_all.sh

# 或分步执行
./build_mac.sh              # 仅打包（--windowed，尽量产出 .app）
./create_dmg.sh             # 创建 DMG：优先打包 .app，否则打包可执行文件
```

输出可能是 `dist/count_down_tool.app` 和/或 `dist/count_down_tool`。

## 项目结构

```
count_down_tool/
├── count_down_tool.py       # 主程序（UI 入口，可 PyInstaller 打包）
├── countdown_core.py        # 纯逻辑（路径/时间/配置，无 tkinter）
├── tests/
│   └── test_countdown_core.py
├── requirements.txt         # 依赖
├── count_down_tool.ico      # 应用图标
├── build_exe.bat            # Windows 打包脚本
├── build_mac.sh             # macOS 打包脚本
├── build_mac_all.sh         # macOS 一键打包脚本
├── convert_icon.sh          # 图标格式转换（ico → icns）
├── create_dmg.sh            # DMG 安装包创建脚本
└── README.md
```

## 运行测试

```bash
# Windows 项目 venv
.venv\Scripts\python.exe -m unittest discover -s tests -v

# 语法检查
.venv\Scripts\python.exe -m py_compile count_down_tool.py countdown_core.py
```

纯逻辑与状态机测试在 `tests/test_countdown_core.py`（无 GUI）。

## 其他说明

- 单实例：同时只允许运行一个程序实例（Windows 互斥量 / 其他平台锁文件 + PID 弱锁）
- 用户配置：Mini 位置、透明模式、上次窗口模式等（见上文）
- 业务纯逻辑在 `countdown_core.py`，便于单元测试；主程序仅负责 UI

## 技术栈

- **GUI**：Tkinter（Python 标准库）
- **系统托盘**：pystray（可选）
- **图标处理**：Pillow（可选）
- **打包**：PyInstaller
