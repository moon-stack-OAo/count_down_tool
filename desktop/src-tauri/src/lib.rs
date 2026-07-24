use serde::Serialize;
use serde_json::Value;
use sha1::{Digest, Sha1};
use std::fs;
use std::path::{Path, PathBuf};
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager,
};
use tauri_plugin_autostart::MacosLauncher;

const APP_DIR: &str = "count_down_tool";
const CONFIG_FILE: &str = "config.json";

fn config_dir() -> PathBuf {
    if let Ok(appdata) = std::env::var("APPDATA") {
        if !appdata.is_empty() {
            return PathBuf::from(appdata).join(APP_DIR);
        }
    }
    if let Ok(home) = std::env::var("HOME") {
        return PathBuf::from(home).join(".config").join(APP_DIR);
    }
    if let Ok(home) = std::env::var("USERPROFILE") {
        return PathBuf::from(home).join(".config").join(APP_DIR);
    }
    PathBuf::from(".").join(APP_DIR)
}

fn config_path() -> PathBuf {
    config_dir().join(CONFIG_FILE)
}

fn sounds_dir() -> PathBuf {
    config_dir().join("sounds")
}

#[tauri::command]
fn load_config() -> Result<Value, String> {
    let path = config_path();
    if !path.exists() {
        return Ok(serde_json::json!({}));
    }
    let text = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    serde_json::from_str(&text).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_config(config: Value) -> Result<(), String> {
    let dir = config_dir();
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let text = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    fs::write(config_path(), text).map_err(|e| e.to_string())
}

#[derive(Serialize)]
struct ImportSoundResult {
    path: String,
    name: String,
}

fn safe_stem(path: &Path) -> String {
    path.file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("sound")
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '-' || c == '_' || ('\u{4e00}'..='\u{9fff}').contains(&c)
            {
                c
            } else {
                '_'
            }
        })
        .collect::<String>()
        .trim_matches(|c| c == '_' || c == '.')
        .chars()
        .take(48)
        .collect::<String>()
}

#[tauri::command]
fn import_sound(path: String) -> Result<ImportSoundResult, String> {
    let src = PathBuf::from(&path);
    if !src.is_file() {
        return Err("文件不存在".into());
    }
    let ext = src
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();
    if ext == "ncm" {
        return Err("暂不支持 .ncm，请先转换为 mp3/wav 后导入".into());
    }
    let allowed = [
        "wav", "wave", "mp3", "aiff", "aif", "m4a", "aac", "ogg", "flac",
    ];
    if !allowed.iter().any(|a| *a == ext.as_str()) {
        return Err("不支持的音频格式".into());
    }

    let dir = sounds_dir();
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;

    let abs = fs::canonicalize(&src).unwrap_or(src.clone());
    let mut hasher = Sha1::new();
    hasher.update(abs.to_string_lossy().as_bytes());
    let digest = format!("{:x}", hasher.finalize());
    let digest12 = &digest[..12.min(digest.len())];
    let stem = safe_stem(&src);
    let dest_name = format!("{}_{}.{}", stem, digest12, ext);
    let dest = dir.join(&dest_name);

    // 已在库内则直接返回
    if let Ok(sounds_root) = fs::canonicalize(&dir) {
        if let Ok(abs_src) = fs::canonicalize(&src) {
            if abs_src.starts_with(&sounds_root) {
                let name = src
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("sound")
                    .to_string();
                return Ok(ImportSoundResult {
                    path: abs_src.to_string_lossy().to_string(),
                    name,
                });
            }
        }
    }

    if dest.is_file() {
        let name = src
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or(&dest_name)
            .to_string();
        return Ok(ImportSoundResult {
            path: dest.to_string_lossy().to_string(),
            name,
        });
    }

    let tmp = dir.join(format!("{}.tmp", dest_name));
    fs::copy(&src, &tmp).map_err(|e| e.to_string())?;
    fs::rename(&tmp, &dest).map_err(|e| e.to_string())?;
    let name = src
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or(&dest_name)
        .to_string();
    Ok(ImportSoundResult {
        path: dest.to_string_lossy().to_string(),
        name,
    })
}

#[tauri::command]
fn purge_orphan_sounds(history: Vec<Value>, current_path: String) -> Result<u32, String> {
    let dir = sounds_dir();
    if !dir.is_dir() {
        return Ok(0);
    }
    let mut keep: std::collections::HashSet<String> = std::collections::HashSet::new();
    if !current_path.is_empty() {
        if let Ok(p) = fs::canonicalize(&current_path) {
            keep.insert(p.to_string_lossy().to_string());
        } else {
            keep.insert(current_path);
        }
    }
    for item in history {
        if let Some(path) = item.get("path").and_then(|v| v.as_str()) {
            if path.is_empty() {
                continue;
            }
            if let Ok(p) = fs::canonicalize(path) {
                keep.insert(p.to_string_lossy().to_string());
            } else {
                keep.insert(path.to_string());
            }
        }
    }

    let mut removed = 0u32;
    let entries = fs::read_dir(&dir).map_err(|e| e.to_string())?;
    for entry in entries.flatten() {
        let p = entry.path();
        if !p.is_file() {
            continue;
        }
        let key = fs::canonicalize(&p)
            .map(|x| x.to_string_lossy().to_string())
            .unwrap_or_else(|_| p.to_string_lossy().to_string());
        if !keep.contains(&key) {
            if fs::remove_file(&p).is_ok() {
                removed += 1;
            }
        }
    }
    Ok(removed)
}

#[tauri::command]
fn user_sounds_dir() -> Result<String, String> {
    let d = sounds_dir();
    fs::create_dir_all(&d).map_err(|e| e.to_string())?;
    Ok(d.to_string_lossy().to_string())
}

#[tauri::command]
fn hide_main_window(app: AppHandle) -> Result<(), String> {
    if let Some(w) = app.get_webview_window("main") {
        w.hide().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn show_main_window(app: AppHandle) -> Result<(), String> {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.unminimize();
        w.show().map_err(|e| e.to_string())?;
        w.set_focus().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn enter_full_mode(app: AppHandle) -> Result<(), String> {
    if let Some(w) = app.get_webview_window("main") {
        w.set_size(tauri::Size::Logical(tauri::LogicalSize {
            width: 500.0,
            height: 560.0,
        }))
        .map_err(|e| e.to_string())?;
        let _ = w.set_resizable(false);
        let _ = w.set_always_on_top(false);
        let _ = w.center();
        w.show().map_err(|e| e.to_string())?;
        w.set_focus().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn enter_mini_mode(app: AppHandle) -> Result<(), String> {
    if let Some(w) = app.get_webview_window("main") {
        w.set_size(tauri::Size::Logical(tauri::LogicalSize {
            width: 260.0,
            height: 56.0,
        }))
        .map_err(|e| e.to_string())?;
        let _ = w.set_resizable(true);
        let _ = w.set_always_on_top(true);
        if let Ok(Some(m)) = w.current_monitor() {
            let size = m.size();
            let scale = m.scale_factor();
            let ww = (260.0 * scale) as i32;
            let wh = (56.0 * scale) as i32;
            let x = size.width as i32 - ww - (20.0 * scale) as i32;
            let y = size.height as i32 - wh - (60.0 * scale) as i32;
            let _ = w.set_position(tauri::Position::Physical(tauri::PhysicalPosition {
                x,
                y,
            }));
        }
        w.show().map_err(|e| e.to_string())?;
        w.set_focus().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn quit_app(app: AppHandle) -> Result<(), String> {
    app.exit(0);
    Ok(())
}

fn emit_tray_action(app: &AppHandle, action: &str) {
    let _ = app.emit("tray://action", action.to_string());
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            Some(vec![]),
        ))
        .invoke_handler(tauri::generate_handler![
            load_config,
            save_config,
            import_sound,
            purge_orphan_sounds,
            user_sounds_dir,
            hide_main_window,
            show_main_window,
            enter_full_mode,
            enter_mini_mode,
            quit_app
        ])
        .setup(|app| {
            let show_i = MenuItem::with_id(app, "show", "显示主窗口", true, None::<&str>)?;
            let mini_i = MenuItem::with_id(app, "mini", "Mini 模式", true, None::<&str>)?;
            let settings_i = MenuItem::with_id(app, "settings", "设置…", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_i, &mini_i, &settings_i, &quit_i])?;

            let icon = app
                .default_window_icon()
                .cloned()
                .expect("missing default window icon");

            let _tray = TrayIconBuilder::new()
                .icon(icon)
                .menu(&menu)
                .tooltip("倒计时工具")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        let _ = show_main_window(app.clone());
                        emit_tray_action(app, "show");
                    }
                    "mini" => {
                        emit_tray_action(app, "mini");
                    }
                    "settings" => {
                        let _ = show_main_window(app.clone());
                        emit_tray_action(app, "settings");
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        let _ = show_main_window(app.clone());
                        emit_tray_action(app, "show");
                    }
                })
                .build(app)?;

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
