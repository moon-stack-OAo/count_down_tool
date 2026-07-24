# 倒计时工具 · Tauri + Vue 3

Python/Tkinter 版本的并行实现。配置目录与旧版兼容：

- Windows: `%APPDATA%/count_down_tool/config.json`
- 其它: `~/.config/count_down_tool/config.json`
- 自定义音效: 同目录下 `sounds/`

## 环境

- Node.js 18+
- Rust stable（`rustup default stable`）
- **Windows**：[Build Tools for Visual Studio](https://visualstudio.microsoft.com/visual-cpp-build-tools/)，勾选 **「使用 C++ 的桌面开发」**
- WebView2（Win10/11 一般已自带）

## 开发

```bash
cd desktop
npm install
npm run tauri:dev
```

仅前端：

```bash
npm run dev
# http://localhost:1420
```

## 打包

```bash
npm run tauri:build
```

CI：`.github/workflows/desktop-build.yml`（Win / macOS）。

## 已实现

| 能力 | 说明 |
|------|------|
| 倒计时 Full / Mini | 预设、进度、状态机 |
| 主题 5 套 | CSS 变量 |
| 设置中心 | 主题 / 声音 / 系统 / 关于 |
| 音效 | 预设 wav、系统铃、导入 mp3/wav、试听、历史、清理未使用 |
| 开机自启 | `tauri-plugin-autostart` |
| 透明 Mini | 窗口 transparent + Mini 半透明样式 |
| 检查更新 | updater 插件 + GitHub API 回退 + 打开发布页 |
| 托盘 | 显示 / Mini / 设置 / 退出 |
| 配置兼容 | 与 Python 共用用户目录 |

## 限制与后续

- **`.ncm`**：导入时明确提示暂不支持（请转 mp3/wav）
- **自动安装更新**：需在 Release 提供 Tauri `latest.json` 与签名公钥（`tauri.conf.json` → `plugins.updater.pubkey`）。未配置时会回退到「打开发布页」
- 音效资源在 `public/sounds/`（soft / chime / alert）

## 与 Python 版关系

根目录 Python 工程仍可独立使用。Tauri 版在 `desktop/`，可并行维护。
