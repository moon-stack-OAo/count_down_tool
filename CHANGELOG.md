# Changelog

本项目变更记录遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)
风格，版本号尽量遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## 1.3.33

### 文档

- Windows 发布包增加 `readme.txt`（完整解压、勿只拖 exe、配置目录、常见 DLL 错误）

## 1.3.32

### 修复

- **Failed to load Python DLL（`%TEMP%\_MEI*\python311.dll`）**：Windows 分发由 PyInstaller **onefile 改为 onedir**。`python311.dll` 等与 exe 同目录加载，不再每次启动解压到临时目录
- **自动更新**：解压完整目录并整目录同步安装；兼容旧版仅含单 exe 的 zip

### 说明

- 请**完整解压** zip 到固定文件夹后运行 `count_down_tool.exe`，不要只拖出单个 exe
- 从 1.3.31 及更早（onefile）升级：建议手动下载 1.3.32 zip 完整解压覆盖，或删旧 exe 后使用新目录

## 1.3.31

### 修复

- **Windows 自动更新后缺 DLL**：替换脚本改为 `exe.new` 中转再 rename、校验 MZ/大小与可独占打开，等待残留进程与杀软释放后再启动，降低 onefile 解压失败
- **从 zip 拖出运行导致托盘/设置异常**：启动检测 Mark of the Web，可删则自动解除锁定并提示；托盘创建失败改为弹窗说明；设置窗强制居中/短暂置顶，打开失败时提示

### 优化

- 更新脚本写入 `%TEMP%\count_down_tool_update.log` 便于排查

## 1.3.30

### 修复

- **暂停不冻结剩余时间**：暂停以 remaining 为准，恢复后不扣掉暂停期间流逝的时间
- **运行/暂停中锁定输入**：到期时间与快捷预设在 running、paused 均不可改
- **单实例唤起**：Mini / 托盘时二次启动可写 show 请求并置前已有实例
- **NCM 解密**：header 长度校验，避免损坏文件导致异常内存占用；缓存数量/体积上限与按 key 加锁
- **开机自启**：快捷方式 Arguments 对含空格路径正确加引号
- **配置写入**：原子写（临时文件 + replace），避免半截 JSON
- **主题配置**：非法 theme_id 回退默认；非法自定义色值丢弃
- **音效试听**：Windows 调度播放后 pending 生命周期修正，避免停止按钮闪断
- **更新检查/安装**：检查与下载安装单飞，进度 UI 节流

### 优化

- **Mini**：负坐标 geometry 下尺寸可持久化；几何保存 debounce；透明色键改用专用稀有色
- **预设**：快捷预设统一走状态机，不再直接写 `_state`
- **设置中心**：历史音效列表重建后重绑滚轮
- **完整窗**：主题重建时快捷键先 unbind 再 bind，避免叠加
- **时间选择器**：打开后 grab，关闭时释放
- **mac 菜单**：透明模式显示勾选前缀
- **构建**：PyInstaller 补全 hidden-import；mac 本地与 CI 对齐为 windowed app；CI 增加 PR 触发
- **仓库**：停止跟踪根目录 `config.json`

## 1.3.29

### 修复

- **Windows 更新黑窗 / FOUND 死循环**：替换脚本改为静默 PowerShell（`Get-Process`），去掉 `tasklist|find`；启动避免 `DETACHED_PROCESS` 导致脚本不执行
- **设置中心空滚**：内容未超出视口时禁用滚轮并锁定 scrollregion

### 优化

- **关于页检查更新**：状态内联显示在按钮下方；有更新时再点「查看更新…」

## 1.3.28

### 修复

- **更新说明为空**：网页检查更新路径补充从 Atom / 发布页 / API 拉取 Release body
- **Windows 安装后 python311.dll 失败**：下载完整性校验、zip/exe 校验；替换脚本复制重试、大小比对、延迟启动

### 优化

- **设置中心尺寸**：宽度与主窗对齐为 500，高度 560

## 1.3.27

### 功能

- **设置中心 Tab 布局**：外观 / 声音 / 系统 / 关于分页；窗口尺寸与间距收紧
- **主题弹窗统一**：业务路径改用 `app_dialogs`；导入音效时临时取消置顶以免挡住系统文件框
- **音效清理合并**：清空历史与清理未使用文件为同一操作；保留当前自定义音效
- **更新提示**：发现新版本时 Windows 托盘气泡；完整窗标题显示 `v` 版本号，有更新时显示 `NEW` 角标（点击打开更新）
- **完整窗右键**：增加「检查更新… / 更新到 vX.Y.Z…」

### 优化

- **胶囊按钮统一**：`widgets.make_pill` 复用 `btn_primary` 语义色；设置 / 更新 / 时间选择器共用
- **时间选择器**：无边框 chrome + 工作区居中
- **分层**：tray / updater / mac_menu 对 UI 改为懒加载，减轻模块级耦合

## 1.3.26

### 修复

- **CI 跨平台测试**：macOS 上 mock `os.startfile` 使用 `create=True`；`test_resolve_frozen` 改用本机路径分隔符
- **检查更新 403 限流**：优先用 releases/latest 网页重定向解析版本（不占 API 配额）；限流时给出中文说明

## 1.3.25

### 修复

- **CI 测试失败**：Windows 上 mock macOS `os.getpgid` / `os.killpg` 需 `create=True`，否则 patch 报错导致构建中断

## 1.3.24

### 功能

- **主按钮状态色**：空闲 / 运行·暂停 / 完成三态样式；主题补充 `btn_primary` 等语义色
- **完整窗布局**：剩余时间层次与字号优化；进度条完成态用 success 色；Spinbox 支持滚轮步进

### 优化

- **设置中心尺寸**：窗口 480×600，收紧边距与分区间距，减少空白滚动
- **README**：同步功能说明；移除与 desktop 项目关系描述

## 1.3.23

### 功能

- **自定义音效永久备份**：导入时复制到用户配置目录 `sounds/`（`.ncm` 解密后存可播格式）；源文件删除后仍可播放
- **历史选择记忆**：配置 `sound_history`（最多 12 条）；托盘/mac 菜单「结束音效」动态列出历史并可一键切换
- **清空历史 / 清理未使用音效**：托盘与 mac 结束音效菜单支持清空历史记录、清理库中未引用文件

### 修复

- **Windows 自定义/ ncm 试听无声**：非 WAV 不再依赖 `startfile`；优先 winmm MCI 播 mp3 等，失败再回退 MediaPlayer /
  startfile
- **试听可停止**：结束音效菜单「停止试听」；未播放时置灰；再次试听先停上一路
- **导入 MP3 后「停止试听」掐不断**：MCI 设备线程亲和，open/play/stop 统一走专用工作线程
- **停止试听置灰 / 连点叠播**：异步播放 generation 取消 + pending 状态；旧任务结束不得清掉新试听 pending
- **导入后历史不刷新**：Windows 结束音效子菜单改为每次 `update_menu` 动态重建

## 1.3.22

### 功能

- **自定义结束音效支持网易云 .ncm**：选择或播放时自动解密到临时缓存后再播（无额外依赖）
- **手动调试脚本**：`scripts/test_ncm_decode.py` 可解密/导出/试播真实 ncm 文件

## 1.3.21

### 功能

- **结束音效可自定义**：默认「柔和提示」；内置柔和/钟声/警报预设 + 系统铃声；支持选择本地音频文件
- **播放规则**：系统铃声循环 3 次；预设/自定义音频文件完整播放 1 次
- **结束静音开关**：托盘 / mac 菜单栏「结束静音」；配置 `sound_muted` / `sound_id` / `sound_path`

### 修复

- **macOS Mini / 透明模式仍带系统边框**：`MacWindowStyle` 必须在首次 map 前设置；创建时先 `withdraw`，设 chrome 与透明后再
  `deiconify`；去掉 map 后无效的重复 style 调用
- **透明模式切换后 Mini 跳到左上角**：重建窗口前记住位置，map/idle 后多次重钉 geometry；`parse_mini_geometry` 支持负坐标

## 1.3.20

### 修复

- **macOS Mini 置顶后出现系统边框**：1.3.19 的 `overrideredirect(True→False)` 会带回标题栏；改用
  `MacWindowStyle plain none` 去边框并保留 `-topmost`，失败时再回退 `overrideredirect(True)`

## 1.3.19

### 功能

- **时间选择器支持直接输入**：完整窗与 Mini 时间选择器可直接键入数字，输入过程实时校验；失焦/回车自动规范化为 HH:MM:
  SS；非法输入回退为进入前的有效时间

### 修复

- **macOS Mini 无法置顶**：Aqua 下 `overrideredirect(True)` 会破坏 `-topmost`；改为 True→False 双调无边框，并在 map /
  定时任务中反复确认 topmost

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
