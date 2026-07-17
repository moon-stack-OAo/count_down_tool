# Changelog

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
