# 倒计时工具 (Count Down Tool)

一个基于 Python Tkinter 的现代化深色主题桌面倒计时工具，支持完整模式和 Mini 桌面小组件模式。

**当前版本：1.3.9**（变更见 [CHANGELOG.md](CHANGELOG.md)）

## 功能特性

- **倒计时**：自定义到期时间（时/分/秒），实时显示剩余时间与进度条
- **运行锁定**：倒计时进行中/暂停时锁定到期时间与快捷预设，避免目标与剩余不一致
- **Mini 桌面小组件**：右下角迷你悬浮窗，始终置顶，可拖动；边缘/四角可缩放并记住大小，文字与按钮随窗口缩放；右键可展开/开始暂停/透明/恢复默认大小/隐藏/退出
- **系统托盘**：支持托盘图标；文案随 Mini/完整模式变化；右键切换模式/退出；结束时托盘通知
- **完整窗右键**：切换 Mini、倒计时控制、隐藏到托盘/退出（无托盘时含自启与主题）
- **开机自启**（Windows）：托盘「开机自启」勾选，写入启动文件夹快捷方式
- **主题切换**：托盘「主题」子菜单（无托盘时完整窗右键亦可），5 套预设
- **快捷预设**：+5/+10/+15/+30 分、+1 时一键设置（从现在起相对时长，并同步到到期时刻）
- **结束提醒**：红绿闪烁 + 系统响铃 + 托盘/弹窗通知
- **多主题 UI**：自定义圆角窗口；完整模式为「剩余时间主视觉 + 设置卡」两层结构
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

主界面自上而下：标题栏 → 剩余时间（主视觉，含到期说明与当前时刻小字）→ 设置卡（到期时间 + 快捷预设）→ 操作按钮。

1. 设置到期时间（时/分/秒），或使用快捷预设
2. 点击 **开始倒计时**（主卡内细进度条显示已过比例）
3. 支持暂停 / 继续 / 重置 / 结束后重新开始；运行/暂停中不可改时间与预设
4. 快捷键：`Esc` 隐藏到托盘（无托盘时退出），`M` 切换 Mini 模式，`T` 切换透明模式
5. 右键主界面：切换 Mini / 开始暂停 / 隐藏到托盘 / 退出

### Mini 模式

- 默认出现在桌面右下角迷你悬浮窗（可由配置 `last_mode` 控制）
- 左键拖动调整位置；拖动边缘/四角调整大小（位置与尺寸写入用户配置目录）
- 右键菜单（macOS 亦支持触控板副键 / Control+点击；亦可点 **⋯**）：展开完整模式 / 开始·暂停·继续 / 选择时间 / 透明模式 / **字体颜色**（当前时间与倒计时三态，从主题色键选取）/ 恢复默认大小 / 退出
- 快捷键：`Esc` 隐藏/关闭，`M` 回完整模式，`T` 切换透明（Windows 色键抠底；macOS/Linux 半透明）
- 展开按钮回到完整模式；关闭按钮有托盘时隐藏到托盘，无托盘时回到完整模式
- 真正退出请使用托盘或右键菜单「退出」

### 托盘：开机自启与主题

- 托盘文案：完整模式为「显示主窗口」「Mini 模式」；Mini 时为「展开主窗口」「退出 Mini 模式」
- **开机自启**（Windows）：勾选后在「启动」文件夹创建 `Count Down Tool.lnk`；取消则删除。macOS/Linux 暂不支持。
- **主题**：子菜单中选中一套预设即切换并保存；切换时保留倒计时状态与时间输入。

### 配置与资源

- 用户配置：`%APPDATA%/count_down_tool/config.json`（Windows）或 `~/.config/count_down_tool/config.json`
- 字段示例见 `config.example.json`：`mini_position`、`mini_size`、`transparent_mode`、`last_mode`、`autostart`、`theme_id`、`theme_custom`、`mini_text`（Mini 当前时间/倒计时三态字色，值为主题色键）
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

本地输出可能是 `dist/count_down_tool.app` 和/或 `dist/count_down_tool`。

**GitHub Release（v1.3.5+）请按芯片选择：**

| 文件 | 适用 |
| --- | --- |
| `Count_Down_Tool_mac_arm64.zip` | Apple Silicon（M1/M2/M3/M4…） |
| `Count_Down_Tool_mac_x86_64.zip` | Intel Mac |

「关于本机」可查看芯片类型。解压后将 `Count Down Tool.app` 拖到「应用程序」。

#### 首次打开若提示无法验证 / 已损坏

```bash
# 去掉隔离属性后打开（未公证的自用构建常用）
xattr -cr "/Applications/Count Down Tool.app"
open "/Applications/Count Down Tool.app"
```

或：右键 App →「打开」→ 再点「打开」。正式对外分发需 Apple 开发者证书 + 公证（notarize）。

## 项目结构

```
count_down_tool/
├── count_down_tool.py       # 入口 + CountdownApp 协调层
├── countdown_core.py        # 纯逻辑（路径/时间/配置，无 tkinter）
├── themes.py                # 预设主题
├── autostart.py             # 开机自启（Windows 快捷方式）
├── ui/
│   ├── widgets.py           # RoundedFrame 等通用控件
│   ├── full_window.py       # 完整模式布局
│   ├── mini_window.py       # Mini 窗创建/拖动/缩放/右键
│   ├── context_menus.py     # 托盘/右键共享菜单
│   └── time_picker.py       # 时间选择器
├── services/
│   ├── tray.py              # 托盘菜单与 icon 线程
│   └── windows_native.py    # 圆角/任务栏/透明/单实例
├── tests/
│   ├── test_countdown_core.py
│   └── test_themes.py
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
.venv\Scripts\python.exe -m py_compile count_down_tool.py countdown_core.py themes.py autostart.py ui/widgets.py ui/mini_window.py ui/time_picker.py ui/full_window.py services/tray.py services/windows_native.py
```

纯逻辑与状态机测试在 `tests/test_countdown_core.py`；主题与自启在 `tests/test_themes.py`（无 GUI）。

## 其他说明

- 单实例：同时只允许运行一个程序实例（Windows 互斥量 / 其他平台锁文件 + PID 弱锁）
- 用户配置：Mini 位置、透明模式、上次窗口模式、主题、开机自启等（见上文）
- 业务纯逻辑在 `countdown_core.py` / `themes.py` / `autostart.py`；UI 与系统能力在 `ui/`、`services/`；主程序为协调层

## 技术栈

- **GUI**：Tkinter（Python 标准库）
- **系统托盘**：pystray（可选）
- **图标处理**：Pillow（可选）
- **打包**：PyInstaller
