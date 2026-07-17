# Changelog

## 1.3.5

### 发布 / macOS 架构

- CI 分架构构建并发布：
  - **arm64**（Apple Silicon / M 芯片）：`Count_Down_Tool_mac_arm64.zip`（`macos-14`）
  - **x86_64**（Intel）：`Count_Down_Tool_mac_x86_64.zip`（`macos-13`）
- 使用 `--target-arch` 与对应 runner 原生构建（暂不做 universal2）

## 1.3.4

### 发布 / macOS

- CI 改为产出 **`Count Down Tool.app`**（zip），不再发布裸二进制
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
