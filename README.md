# 倒计时工具 (Count Down Tool)

![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)
![Windows](https://img.shields.io/badge/Windows%20(v1.3.26)-0078D6?logo=windows&logoColor=white)
![macOS](https://img.shields.io/badge/macOS%20(v1.3.26)-000000?logo=apple&logoColor=white)
![Version](https://img.shields.io/badge/version-1.3.26-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

基于 **Python + Tkinter** 的深色主题桌面倒计时工具（完整模式 + Mini 小组件）。

**当前版本：1.3.26**（变更见 [CHANGELOG.md](CHANGELOG.md)）

---

## 功能特性

- **倒计时**：自定义到期时间（时/分/秒，可直接键入），实时剩余时间与进度条
- **运行锁定**：进行中/暂停时锁定到期时间与快捷预设
- **Mini 桌面小组件**：右下角迷你悬浮窗，始终置顶，可拖动；边缘/四角可缩放并记住大小
- **设置中心**：外观（主题）/ 声音 / 系统（自启、检查更新）/ 关于
- **系统托盘**（Windows）/ **菜单栏「设置」**（macOS）— 常用快捷入口
- **开机自启**（Windows）
- **主题切换**：石板青蓝、暗夜紫、暖琥珀、翠绿、浅色
- **结束提醒**：内置预设音效 + 自定义文件（含 **`.ncm` 自动解密**）+ 历史记录；可静音
- **透明 Mini**、跨平台 Windows / macOS / Linux
- **检查更新**：启动时可检查 GitHub Release；支持忽略版本

---

## 环境与运行

- Python **3.11**（与 CI 一致；本地 3.10+ 一般可用）

```bash
pip install -r requirements.txt
python count_down_tool.py
```

依赖：`pystray`、`Pillow`；打包另需 `pyinstaller`（见 `requirements.txt`）。

---

## 使用说明

### 完整模式

1. 设置到期时间（时/分/秒，可直接输入数字），或使用快捷预设
2. 点击 **开始倒计时**
3. 支持暂停 / 继续 / 重置；运行/暂停中不可改时间与预设
4. 标题栏 **⚙** 或右键菜单打开 **设置中心**
5. 快捷键：`Esc` 隐藏到托盘/后台，`M` 切换 Mini，`T` 切换透明

### Mini 模式

- 默认可出现在桌面右下角；位置与尺寸写入用户配置
- 设置入口：主窗 ⚙、Windows **系统托盘**、macOS **菜单栏「设置」**
- Mini 上：`Esc` 关闭 Mini，`T` 切换透明；无右键菜单（设置统一走上述入口）
- 真正退出：托盘 / 菜单栏「退出」

### 结束音效

| 类型  | 说明                             |
|-----|--------------------------------|
| 预设  | 柔和提示 / 钟声 / 警报；或系统铃声（循环 3 次）   |
| 自定义 | 本地音频；导入后复制到配置目录 `sounds/` 永久备份 |
| 网易云 | 选择 `.ncm` 时自动解密后再播（无额外依赖）      |
| 历史  | 最多 12 条；托盘/菜单可切换、清空历史、清理未引用文件  |

### 配置目录

| 平台            | 路径                                      |
|---------------|-----------------------------------------|
| Windows       | `%APPDATA%/count_down_tool/config.json` |
| macOS / Linux | `~/.config/count_down_tool/config.json` |
| 自定义音效         | 同目录 `sounds/`                           |

字段示例见 [`config.example.json`](config.example.json)。

---

## 打包构建

版本号读取自 `core.countdown_core.__version__`（当前 **1.3.26**）。CI 打 tag 时要求 tag 与代码版本一致。

### Windows

```cmd
scripts\build_exe.bat
```

```text
dist/count_down_tool.exe
dist/count_down_tool-<version>-win64.zip
```

### macOS

```bash
./scripts/build_mac_all.sh
```

| 文件                                         | 适用            |
|--------------------------------------------|---------------|
| `count_down_tool-<version>-win64.zip`      | 64 位 Windows  |
| `count_down_tool-<version>-mac-arm64.zip`  | Apple Silicon |
| `count_down_tool-<version>-mac-x86_64.zip` | Intel Mac     |

解压后固定为 `count_down_tool.exe` / `count_down_tool.app`。未公证首次打开：

```bash
xattr -cr "/Applications/count_down_tool.app"
open "/Applications/count_down_tool.app"
```

---

## 项目结构

```
count_down_tool/
├── count_down_tool.py       # 入口
├── requirements.txt
├── config.example.json
├── core/                    # 纯逻辑：倒计时、主题、字体、更新
├── app/                     # 控制器、配置、主题/模式、窗口 chrome
├── ui/                      # Full / Mini / 设置中心 / 时间选择器
├── services/                # 托盘、音效、ncm、自启、更新、原生
├── assets/                  # 图标、音效、字体
├── scripts/                 # 打包与辅助脚本
├── tests/
└── .github/workflows/       # CI 多平台构建与 Release
```

---

## 运行测试

```bash
# Windows
.venv\Scripts\python.exe -m unittest discover -s tests -v

# macOS / Linux
python -m unittest discover -s tests -v
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
