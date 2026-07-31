# Changelog

本项目变更记录遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)
风格，版本号尽量遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## 1.4.0

> 自 **1.3.0** 之后至本版的能力与修复统一发布为 **1.4.0**（原 1.3.1–1.3.35 条目已合并整理；含后续安全更新与工程拆分）。

### 功能

- **设置中心**：外观 / 声音 / 系统 / 关于 Tab；主题、默认启动模式（`startup_mode`：记住上次 / 总是完整 / 总是 Mini）、Mini
  字体颜色入口
- **系统页**：开机自启（Windows）、启动时检查更新、打开配置目录、重置 Mini 位置/大小、清除已忽略更新版本
- **关于页**：手动检查更新（状态内联）、上次检查时间、应用内弹窗查看运行日志（刷新/复制/打开目录）、复制版本信息、GitHub 发布页
- **结束音效**：内置预设 + 自定义文件；**.ncm 自动解密**（流式写盘、缓存治理）；历史记录、试听/停止、静音
- **运行日志**：用户目录 `app.log`（约 2MB 轮转、最多 3 备份）；`COUNT_DOWN_TOOL_LOG_LEVEL` 可调
- **倒计时体验**：进度条；主按钮状态色；暂停冻结剩余时间；**仅 running 锁定**改时间，暂停后可选新目标再继续
- **Mini**：可缩放并记忆尺寸；内容随窗缩放；字色按角色自定义；透明模式（Win 色键 / mac 系统透明）；快捷键 `T`
- **更新**：检查 GitHub Release；启动检查 / 手动检查；忽略版本；Win 整目录安装；mac 下载安装包；标题 `NEW` 角标与托盘提示；**下载可取消**
- **菜单与入口**：完整窗右键；托盘（Windows）/ mac 菜单栏「设置」；时间选择器支持直接键入

### 安全

- **自动更新解压**：Windows 安装包防 Zip Slip（路径规范化 + 白名单）；解压后校验布局
- **完整性**：有 Release 校验资产时强制 **SHA256**，无则告警后仅大小/zip 校验
- **下载取消**：进度窗关窗/取消按钮中止下载，清理半成品并释放更新占用

### 修复

- **Windows 分发**：PyInstaller **onedir**（修复 onefile 下 `python311.dll` / 临时目录加载失败）；完整解压使用；MOTW 提示
- **自动更新**：下载/zip 校验；替换脚本加固（静默 PowerShell、重试、日志）；兼容旧 zip
- **macOS**：Mini 尺寸与置顶/去边框；透明；**不再用 pystray**（避免与 Tk 双循环崩溃），改用菜单栏；Intel runner
  `macos-15-intel`
- **音效**：Windows 非 WAV 播放链（MCI / MediaPlayer）；路径探测超时防卡死；`winsound` 导入捕获 `ImportError`（mac CI）
- **设置中心**：原生标题栏；切换主题后重开并尽量回到原 Tab；空滚锁定
- **单实例 / 配置**：二次启动 show 请求唤起；配置原子写；非法 theme 回退

### 优化与工程

- 结构拆分：`core/`、`app/`、`ui/`、`services/`；异常捕获收窄并补 debug 日志
- **模块再拆分**（公开 import 兼容）：`services/ncm/`、`services/sound/`、`core/update_impl/`、`ui/settings/`；门面路径保持不变
- **状态收敛**：`app/state.py`（`PersistedState` / `CountdownRuntime`）+ `app/protocols.py`；`app._xxx` property 映射，配置 schema 不变
- **自绘标题栏组件化**：`ui/chrome_titlebar.py`，完整窗与对话框共用
- **依赖**：`requirements.txt`（运行时）/ `requirements-dev.txt`（pytest、pyinstaller、ruff）
- **静态检查**：`pyproject.toml` + `ruff check .`；CI 测试前跑 ruff
- **打包**：`scripts/pyinstaller_common.py` 统一 hiddenimports 与构建参数；产物 zip 带版本号；mac `.app` 写入真实版本与 ad-hoc 签名；arm64 / x86_64 分架构发布
- 文档：README（开发依赖、Ruff、PyInstaller、项目结构）、Windows 包内 `readme.txt`、`scripts/clear_local_data.bat`
- 单测与 CI 跨平台加固（startfile / killpg mock 等）

### 升级说明

- 自 **1.3.31 及更早（onefile）** 升级 Windows 包：建议下载 **1.4.0** zip **完整解压**到固定目录，勿只拖单个 exe
- 配置目录与 `config.json` 字段向后兼容；新增可选键如 `startup_mode`、`sound_history`、`mini_text` 等

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
