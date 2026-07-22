# Changelog

本项目变更记录遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)
风格，版本号尽量遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 功能

- **时间选择器支持直接输入**：时分秒除 ▲▼ / 滚轮步进外，可键盘输入；仅允许数字并限制范围（时 0–23，分/秒 0–59）；失焦或确认时格式化为两位

## 1.3.18

### 修复

- **macOS 崩溃（TstateNULL / abort）**：不再在 mac 上启用 pystray 后台 `NSApplication.run`（与 Tk 双循环冲突）；改用 **Tk
  菜单栏「设置」** 提供同等入口；Dock 点击用 `tk::mac::ReopenApplication` 恢复窗口
- 隐藏到后台时的提示文案按平台区分（mac 菜单栏 / Windows 托盘）

### 构建

- **写入 .app 真实版本**：打包后更新 `Info.plist` 的 `CFBundleShortVersionString` / `CFBundleVersion`（避免显示 `0.0.0`）

## 1.3.17

### 构建

- **产物文件名带版本号**：分发均为 zip——`count_down_tool-<version>-win64.zip` / `…-mac-arm64.zip` / `…-mac-x86_64.zip`
  ；解压后固定为 `count_down_tool.exe` / `count_down_tool.app`；CI 优先用 tag，本地用 `__version__`

### 文档

- 新增 MIT `LICENSE`（Copyright 2026 Moon）
- README 增加 badges（Python 3.11、平台、Windows/macOS 版本、License）；环境要求改为 Python 3.11

## 1.3.16

### 变更

- **Mini 取消右键/⋯ 菜单**：设置统一走系统托盘（透明、字体颜色、恢复默认大小等）；Mini 仅保留 ↗ / × 与拖动缩放
- **废止 Mini 右键入口**：此前 1.3.13–1.3.15 中「Mini 右键…」相关能力改为托盘（或色块面板）；读史时请以本版为准
- **字体颜色带色块**：托盘「字体颜色…」打开预览面板，用当前主题真实颜色区分选项（系统托盘无法上色）
- 托盘增加「恢复默认大小」（仅 Mini 时可用）

## 1.3.15

### 功能

- **Mini 字体颜色自定义**：配置 `mini_text`，按主题色键设置当前时间与倒计时三态（运行/暂停/结束）字色；换主题后仍用同一键取色
- Mini 右键「字体颜色」子菜单（**1.3.16 起改走托盘色块面板**）：分角色选色、✓ 标记当前项、「恢复默认」
- **完整模式自动居中**：启动、从 Mini/托盘展开时按工作区（排除任务栏）居中，并在显示后再校正一次

### 修复

- **托盘恢复完整窗不置顶**：最小化到托盘后再打开时，用短暂 topmost + AttachThreadInput 强制置前并激活

### 重构

- **结构**：拆分倒计时控制器（`app/countdown.py`）与配置胶水（`app/config_store.py`）；`CountdownApp` 变为薄协调层
- **结构（续）**：再拆窗口 chrome（`app/window_chrome.py`）、主题应用（`app/theme.py`）、模式切换（`app/mode.py`）
- **目录整理**：`countdown_core` / `themes` → `core/`；`autostart` → `services/`；图标 → `assets/`；打包脚本 → `scripts/`；统一
  `from core.*` / `from services.*` import；`resource_path` 开发态基于项目根

## 1.3.14

### 功能

- **Mini 内容随窗口缩放**：字号、内边距、按钮随窗口相对默认尺寸同步放大/缩小

### 修复

- **Mini 不进 Alt+Tab / 任务栏**（Windows）：标为工具窗（`WS_EX_TOOLWINDOW`），避免与完整窗一样出现在切换列表
- **完整窗保留 Alt+Tab / 任务栏**：`WS_EX_APPWINDOW`；从 Mini / 托盘恢复时重新应用，避免 `withdraw` 后丢失
- **恢复默认大小无效**：销毁时不再把当前尺寸写回；配置中 `mini_size` 在恢复默认时正确清除
- **Mini 右键去掉「隐藏到托盘」**（1.3.16 起无 Mini 右键）：已有 ×，避免菜单重复；无托盘时仍保留「关闭」
- **Mini 右键增加「选择时间」**（1.3.16 起改仅托盘）：与托盘一致，调用同一时间选择器
- **倒计时中禁用「选择时间」**：仅 running 时置灰；暂停后可改时间并按新目标重新计时
- **时间选择器无法操作**：改为 ▲▼ 调时（不用 Spinbox）；挂到可见 Mini 父窗；去掉 grab/transient 到隐藏主窗
- **时间选择器样式**：主题圆角卡片、圆形步进按钮、目标预览条；窗口按内容自适应，避免裁切
- **Mini/托盘菜单状态不刷新**（Mini 右键 1.3.16 已废止）：当时右键用 postcommand 每次重建；托盘暂停/开始后强制
  update_menu；预设进 running 也刷托盘

## 1.3.13

### 功能

- **Mini 可调大小**（Windows / macOS）：拖动边缘或四角缩放；尺寸写入 `mini_size` 持久化
- 右键菜单「恢复默认大小」（**1.3.16 起改托盘**）；平台默认尺寸与上下限仍按系统区分

## 1.3.12

### 修复

- **macOS Mini 尺寸**：在 1.3.11 基础上约减半（590×120，字号 25/40），边距与按钮同步缩小

## 1.3.11

### 修复

- **macOS Mini 过小**：Retina / Tk 点阵下窗口与字号放大；强制 geometry / minsize，避免被压成极小条

## 1.3.10

### 修复

- **macOS 透明模式**：改用 `-transparent` + `systemTransparent` 真正抠底；失败时回退 `-alpha`
- Windows 仍使用 `-transparentcolor` 色键透明

## 1.3.9

### 功能

- **快捷键 `T`**：完整窗 / Mini 切换透明模式（与 `M` 同级）
- **macOS/Linux 透明**：Mini 使用窗口半透明（`-alpha`）；Windows 仍为色键抠底
- 右键 / 托盘「透明模式」在全平台可用；Mini 同步绑定 `Esc` / `M` / `T`

## 1.3.8

### 修复

- **macOS Mini 外观**：改回无边框小组件（去掉系统标题栏叠层），菜单仍用 **⋯** / 副键 / Control-点击

## 1.3.7

### 修复

- **macOS Mini 右键菜单**：绑定 `Button-2` / `Button-3` / `Control-Button-1`；增加 **⋯** 菜单按钮
- 弹出前 `lift` + `focus_force`；Mini 略加宽以容纳按钮
- **CI**：Intel 构建 runner 由已退役的 `macos-13` 改为 `macos-15-intel`

## 1.3.6

### 修复

- **托盘菜单不同步**：Windows 上 pystray 缓存原生菜单；启动默认/切换 Mini 后调用 `update_menu()`，正确显示「退出 Mini
  模式」/「展开主窗口」
- Mini 关闭到托盘时同步 `_is_mini` 与托盘文案

## 1.3.5

### 发布 / macOS 架构

- CI 分架构构建并发布：
    - **arm64**（Apple Silicon / M 芯片）：`count_down_tool_mac_arm64.zip`（`macos-14`）
    - **x86_64**（Intel）：`count_down_tool_mac_x86_64.zip`（`macos-15-intel`）
- 使用 `--target-arch` 与对应 runner 原生构建（暂不做 universal2）

## 1.3.4

### 发布 / macOS

- CI 改为产出 **`count_down_tool.app`**（zip），不再发布裸二进制
- 构建后 `chmod +x` + ad-hoc `codesign`，降低「无法打开/已损坏」概率
- Release 说明补充首次打开与 `xattr -cr` 去隔离属性步骤

## 1.3.3

### UI / 菜单

- **托盘模式感知文案**：Mini 时「显示主窗口」→「展开主窗口」、「Mini 模式」→「退出 Mini 模式」
- **Mini 右键增强**：增加开始/暂停/继续；透明以「✓ 透明模式」切换
- **完整窗右键菜单**：切换 Mini、倒计时控制、隐藏到托盘/退出；无托盘时补齐开机自启与主题子菜单
- 抽取 `ui/context_menus.py` 统一菜单构建；主题重建后右键绑定仍有效

## 1.3.2

### UI

- **进度条**：倒计时主卡内显示已过/总时长细条进度（Canvas + accent 色）；暂停冻结，结束满格，重置归零
- **运行中锁定输入**：`running` / `paused` 时禁用到期时间 Spinbox 与快捷预设；`idle` / `finished` 可改；主题重建后按状态恢复

## 1.3.1

### UI

- **主界面 P0 布局**：去掉内容区重复标题/副标题；剩余时间置顶作主视觉；到期时间与快捷预设合并为一张设置卡
- 快捷预设文案改为相对语义（`+5分` / `+10分` 等）
- 窗口尺寸调整为 500×520

## 1.3.0

### 工程

- **中度结构拆分**：主程序瘦身为协调层；UI / 托盘 / Windows 原生能力拆入子包
    - `ui/widgets.py`、`ui/full_window.py`、`ui/mini_window.py`、`ui/time_picker.py`
    - `services/tray.py`、`services/windows_native.py`
- 版本号统一为 `1.3.0`
- 打包脚本补充 `ui` / `services` 及子模块 hidden-import

## 1.2.0

### 功能

- **开机自启**（Windows）：托盘菜单「开机自启」，通过 Startup 快捷方式实现，零新依赖
- **预设主题切换**：托盘「主题」子菜单，内置 5 套（石板青蓝 / 暗夜紫 / 暖琥珀 / 翠绿 / 浅色）
- 配置扩展：`autostart`、`theme_id`、`theme_custom`（自定义色预留，本版无 UI）

### 工程

- 新增 `themes.py`、`autostart.py`
- 版本号统一为 `1.2.0`
- 单元测试覆盖主题解析、配置 merge、启动命令拼接
- 打包脚本补充 `themes` / `autostart` hidden-import

## 1.1.0

### 功能与体验

- **状态机**：显式 `idle / running / paused / finished`，按钮文案由状态映射
- **结束提醒**：保留视觉闪烁；托盘 `notify`（若可用）；系统响铃 2~3 次
- **Mini 右键菜单**：展开完整模式、切换透明、隐藏到托盘/关闭、退出
- **配置增强**：持久化 `mini_position`、`transparent_mode`、`last_mode`
- **单实例**：弱锁写入 PID，死进程残留锁可自动清理；Windows 已有实例尝试置前

### 工程

- 版本号统一为 `1.1.0`
- 单元测试覆盖状态转换、弱锁/PID、配置 merge 边界
- CI：`v*` tag 推送不再被 paths 过滤，可正常构建并创建 Release
- 新增 `config.example.json` 示例字段

## 1.0.0

- 初版：完整模式 / Mini 模式、托盘、快捷预设、深色 UI、跨平台打包
