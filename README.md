# 倒计时工具 (Count Down Tool)

![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)
![Windows](https://img.shields.io/badge/Windows%20(v1.4.0)-0078D6?logo=windows&logoColor=white)
![macOS](https://img.shields.io/badge/macOS%20(v1.4.0)-000000?logo=apple&logoColor=white)
![Version](https://img.shields.io/badge/version-1.4.0-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

基于 **Python + Tkinter** 的深色主题桌面倒计时工具（完整模式 + Mini 小组件）。

**当前版本：1.4.0**（变更见 [CHANGELOG.md](CHANGELOG.md)）

---

## 功能特性

- **倒计时**：自定义到期时间（时/分/秒，可直接键入），实时剩余时间与进度条
- **运行锁定**：进行中锁定到期时间与快捷预设；暂停后可改时间/选新目标再继续
- **Mini 桌面小组件**：右下角迷你悬浮窗，始终置顶，可拖动；边缘/四角可缩放并记住大小
- **设置中心**：外观（主题、默认启动模式、Mini 字色）/ 声音 / 系统（开机自启、**启动时**检查更新、配置目录、重置 Mini）/ 关于（**手动
  **检查更新、弹窗查看日志、复制版本）
- **系统托盘**（Windows）/ **菜单栏「设置」**（macOS）— 常用快捷入口
- **开机自启**（Windows）
- **主题切换**：石板青蓝、暗夜紫、暖琥珀、翠绿、浅色
- **结束提醒**：内置预设音效 + 自定义文件（含 **`.ncm` 自动解密**）+ 历史记录；可静音
- **透明 Mini**、跨平台 Windows / macOS / Linux
- **检查更新**：可在启动时自动检查 GitHub Release，或在「关于」中手动检查；支持忽略版本

---

## 环境与运行

- Python **3.11**（与 CI 一致；本地 3.10+ 一般可用）

```bash
# 仅运行
pip install -r requirements.txt
python count_down_tool.py

# 开发 / 测试 / 打包（含 pyinstaller、pytest）
pip install -r requirements-dev.txt
```

依赖：`pystray`、`Pillow`（`requirements.txt`）；开发与打包另见 `requirements-dev.txt`。

---

## 使用说明

### 完整模式

1. 设置到期时间（时/分/秒，可直接输入数字），或使用快捷预设
2. 点击 **开始倒计时**
3. 支持暂停 / 继续 / 重置；运行中不可改时间与预设，暂停后可改
4. 标题栏 **⚙** 或右键菜单打开 **设置中心**
5. 快捷键：`Esc` 隐藏到托盘/后台，`M` 切换 Mini，`T` 切换透明

### Mini 模式

- 默认可出现在桌面右下角；位置与尺寸写入用户配置
- 设置入口：主窗 ⚙、Windows **系统托盘**、macOS **菜单栏「设置」**
- Mini 上：`Esc` 关闭 Mini，`T` 切换透明；无右键菜单（设置统一走上述入口）
- 真正退出：托盘 / 菜单栏「退出」

### 结束音效

| 类型  | 说明                                          |
|-----|---------------------------------------------|
| 预设  | 柔和提示 / 钟声 / 警报；或系统铃声（循环 3 次）                |
| 自定义 | 本地音频；导入后复制到配置目录 `sounds/` 永久备份              |
| 网易云 | 选择 `.ncm` 时自动解密后再播（无额外依赖）                   |
| 历史  | 最多 12 条；可切换；「清空历史与未使用」会清列表并删库中未引用文件（保留当前音效） |

### 配置目录

| 平台            | 路径                                      |
|---------------|-----------------------------------------|
| Windows       | `%APPDATA%/count_down_tool/config.json` |
| macOS / Linux | `~/.config/count_down_tool/config.json` |
| 自定义音效         | 同目录 `sounds/`                           |
| 运行日志          | 同目录 `app.log`（轮转备份 `app.log.1` 等）       |

字段示例见 [`config.example.json`](config.example.json)。

---

## 打包构建

版本号读取自 `core.countdown_core.__version__`（当前 **1.4.0**）。CI 打 tag 时要求 tag 与代码版本一致。

### 统一 PyInstaller 配置

本地脚本与 CI 均通过 [`scripts/pyinstaller_common.py`](scripts/pyinstaller_common.py) 调用 PyInstaller：

- **hiddenimports / add-data / onedir·windowed** 只在该文件维护
- Windows：**onedir** + `pystray._win32`
- macOS：**windowed** app bundle + `pystray._darwin` / `services.mac_menu`

新增 `services.*` / `ui.*` / `core.*` 子包时，请把模块名追加到 `HIDDENIMPORTS_COMMON`（或平台列表）。

```bash
# 仅查看将要打包的 hiddenimports
python scripts/pyinstaller_common.py list-hiddenimports --os windows
python scripts/pyinstaller_common.py print-argv --os windows
```

### Windows

```cmd
scripts\build_exe.bat
```

```text
dist/count_down_tool/          # onedir：exe + _internal 等
dist/count_down_tool-<version>-win64.zip
```

**重要**：请将 zip **完整解压**到固定文件夹后运行其中的 `count_down_tool.exe`。  
不要只从压缩包拖出单个 exe（会缺少 `_internal` 内 DLL，导致启动失败）。  
Windows 发布包内附带 [`docs/readme.txt`](docs/readme.txt)（打进 zip 后文件名为 `readme.txt`）。

### macOS

```bash
./scripts/build_mac_all.sh
```

| 文件                                         | 适用                      |
|--------------------------------------------|-------------------------|
| `count_down_tool-<version>-win64.zip`      | 64 位 Windows（onedir 目录） |
| `count_down_tool-<version>-mac-arm64.zip`  | Apple Silicon           |
| `count_down_tool-<version>-mac-x86_64.zip` | Intel Mac               |

解压后：Windows 为目录内 `count_down_tool.exe`；macOS 为 `count_down_tool.app`。未公证首次打开：

```bash
xattr -cr "/Applications/count_down_tool.app"
open "/Applications/count_down_tool.app"
```

---

## 项目结构

```
count_down_tool/
├── count_down_tool.py       # 入口
├── requirements.txt         # 运行时依赖
├── requirements-dev.txt     # 开发/测试/打包依赖
├── config.example.json
├── docs/readme.txt           # Windows 发布包随附说明
├── core/                    # 纯逻辑：倒计时、主题、字体、更新
├── app/                     # 控制器、配置、主题/模式、窗口 chrome
├── ui/                      # Full / Mini / 设置中心 / 时间选择器
├── services/                # 托盘、音效、ncm、自启、更新、原生
├── assets/                  # 图标、音效、字体
├── scripts/                 # 打包与辅助脚本（含 pyinstaller_common.py）
├── tests/
└── .github/workflows/       # CI 多平台构建与 Release
```

---

## 运行测试

```bash
# 需先安装开发依赖：pip install -r requirements-dev.txt
# Windows
.venv\Scripts\python.exe -m pytest tests/ -q

# macOS / Linux
python -m pytest tests/ -q
```

### 静态检查（Ruff）

```bash
# 需先安装开发依赖：pip install -r requirements-dev.txt
ruff check .
```

---

## 其他说明

- **单实例**：同时只允许运行一个程序实例（Windows 会尝试置前已有窗口）
- **协议**：MIT，见 [LICENSE](LICENSE)

## 技术栈

- **GUI**：Tkinter
- **托盘**：pystray（Windows；macOS 用菜单栏避免与 Tk 双循环冲突）
- **图标 / 图像**：Pillow
- **打包**：PyInstaller
- **更新**：GitHub Releases API
