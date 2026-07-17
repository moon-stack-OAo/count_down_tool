# Changelog

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
