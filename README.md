# 倒计时工具 (Count Down Tool) · Python 版

![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)
![Windows](https://img.shields.io/badge/Windows%20(v1.3.23)-0078D6?logo=windows&logoColor=white)
![macOS](https://img.shields.io/badge/macOS%20(v1.3.23)-000000?logo=apple&logoColor=white)
![Version](https://img.shields.io/badge/version-1.3.23-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

基于 **Python + Tkinter** 的深色主题桌面倒计时工具（完整模式 + Mini 小组件）。

> **主产品已迁至独立仓库（Tauri + Vue 3）**  
> 👉 [count_down_tool-desktop](https://github.com/moon-stack-OAo/count_down_tool-desktop)  
> 本地路径：`D:\Moon\tools\count_down_tool-desktop`  
> 本仓库进入 **维护模式**（严重 bug 修复；新功能优先在桌面端开发）。

两版 **共用用户配置目录**，可切换使用。

**当前版本：1.3.23**（变更见 [CHANGELOG.md](CHANGELOG.md)）

---

## 功能特性

- **倒计时**：自定义到期时间（时/分/秒），实时剩余时间与进度条
- **运行锁定**：进行中/暂停时锁定到期时间与快捷预设
- **Mini 桌面小组件**：右下角迷你悬浮窗，始终置顶，可拖动；边缘/四角可缩放并记住大小
- **系统托盘**（Windows）/ **菜单栏「设置」**（macOS）
- **开机自启**（Windows）
- **主题切换**：多套预设
- **结束提醒**：音效（含预设 / 自定义 / `.ncm`）+ 通知
- **透明 Mini**、跨平台 Windows / macOS / Linux

---

## 环境与运行

- Python 3.11（与 CI 一致）

```bash
pip install -r requirements.txt
python count_down_tool.py
```

---

## 使用说明

### 完整模式

1. 设置到期时间（时/分/秒），或使用快捷预设  
2. 点击 **开始倒计时**  
3. 支持暂停 / 继续 / 重置；运行/暂停中不可改时间与预设  
4. 快捷键：`Esc` 隐藏到托盘，`M` 切换 Mini，`T` 切换透明  

### Mini 模式

- 默认可出现在桌面右下角；位置与尺寸写入用户配置  
- 设置入口：Windows **系统托盘**，macOS **菜单栏「设置」**  
- 真正退出：托盘 / 菜单栏「退出」

### 配置目录

| 平台 | 路径 |
|------|------|
| Windows | `%APPDATA%/count_down_tool/config.json` |
| macOS / Linux | `~/.config/count_down_tool/config.json` |
| 自定义音效 | 同目录 `sounds/` |

字段示例见 [`config.example.json`](config.example.json)。

---

## 打包构建

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

| 文件 | 适用 |
|------|------|
| `count_down_tool-<version>-win64.zip` | 64 位 Windows |
| `count_down_tool-<version>-mac-arm64.zip` | Apple Silicon |
| `count_down_tool-<version>-mac-x86_64.zip` | Intel Mac |

未公证首次打开：

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
├── core/                    # 纯逻辑
├── app/                     # 控制器 / 主题 / 模式
├── ui/                      # Full / Mini / 设置
├── services/                # 托盘、自启、原生
├── assets/                  # 图标、音效、字体
├── scripts/                 # 打包脚本
└── tests/
```

> 原嵌套的 `desktop/`（Tauri）已拆出为独立项目，不再包含在本仓库。

---

## 运行测试

```bash
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

---

## 其他说明

- 单实例：同时只允许运行一个程序实例  
- 协议：MIT，见 [LICENSE](LICENSE)  

## 技术栈

- **GUI**：Tkinter  
- **托盘**：pystray（可选）  
- **图标**：Pillow（可选）  
- **打包**：PyInstaller  

## 相关项目

| 项目 | 说明 |
|------|------|
| [count_down_tool-desktop](https://github.com/moon-stack-OAo/count_down_tool-desktop) | **主产品** · Tauri 2 + Vue 3 |
| 本仓库 | Python 维护版 |
