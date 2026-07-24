import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { disable, enable, isEnabled } from "@tauri-apps/plugin-autostart";
import { type AppConfig, defaultConfig, mergeConfig } from "../core/config";
import type { SoundId } from "../core/constants";
import {
  importSoundFile,
  isSoundPlaying,
  playFinishSound,
  purgeOrphanSounds,
  SOUND_PRESETS,
  stopSound,
} from "../core/sound";
import {
  checkForUpdate,
  installUpdateOrOpenPage,
  openReleasesPage,
  todayIso,
  type UpdateInfo,
} from "../core/update";
import { applyThemeToDom, listThemes, resolveTheme } from "../core/themes";

export const useSettingsStore = defineStore("settings", () => {
  const config = ref<AppConfig>(defaultConfig());
  const settingsOpen = ref(false);
  const mode = ref<"full" | "mini">("full");
  const loaded = ref(false);
  const updateBusy = ref(false);
  const updateMessage = ref("");
  const lastUpdateInfo = ref<UpdateInfo | null>(null);

  const colors = computed(() =>
    resolveTheme(config.value.theme_id, config.value.theme_custom),
  );
  const themes = listThemes();
  const soundPresets = SOUND_PRESETS;

  function applyThemeCss() {
    applyThemeToDom(colors.value);
  }

  async function syncAutostartFromSystem() {
    try {
      const on = await isEnabled();
      if (on !== config.value.autostart) {
        config.value.autostart = on;
      }
    } catch {
      /* 浏览器预览 */
    }
  }

  async function load() {
    try {
      const raw = await invoke<unknown>("load_config");
      config.value = mergeConfig(raw);
    } catch {
      config.value = defaultConfig();
    }
    mode.value = config.value.last_mode === "mini" ? "mini" : "full";
    applyThemeCss();
    await syncAutostartFromSystem();
    loaded.value = true;

    // 启动检查更新（每天一次）
    if (config.value.check_update_on_start) {
      const today = todayIso();
      if (config.value.last_update_check !== today) {
        setTimeout(() => {
          void runUpdateCheck(false);
        }, 4000);
      }
    }
  }

  async function save(partial?: Partial<AppConfig>) {
    if (partial) {
      config.value = { ...config.value, ...partial };
    }
    applyThemeCss();
    try {
      await invoke("save_config", { config: config.value });
    } catch (e) {
      console.error("save_config failed", e);
    }
  }

  async function setTheme(themeId: string) {
    await save({ theme_id: themeId });
  }

  async function setSoundId(id: SoundId) {
    await save({ sound_id: id });
  }

  async function toggleTransparent() {
    await save({ transparent_mode: !config.value.transparent_mode });
  }

  async function setAutostart(on: boolean) {
    try {
      if (on) await enable();
      else await disable();
      const real = await isEnabled();
      await save({ autostart: real });
    } catch (e) {
      console.error("autostart failed", e);
      updateMessage.value = "设置开机自启失败，请检查系统权限";
      await syncAutostartFromSystem();
      await save();
    }
  }

  async function toggleAutostart() {
    await setAutostart(!config.value.autostart);
  }

  async function importSound() {
    try {
      const selected = await open({
        multiple: false,
        filters: [
          {
            name: "音频",
            extensions: ["wav", "mp3", "m4a", "aac", "ogg", "flac", "aiff", "aif", "ncm"],
          },
        ],
      });
      if (!selected || Array.isArray(selected)) return;
      const result = await importSoundFile(selected);
      const history = [
        { path: result.path, name: result.name },
        ...config.value.sound_history.filter((h) => h.path !== result.path),
      ].slice(0, 12);
      await save({
        sound_id: "custom",
        sound_path: result.path,
        sound_history: history,
      });
      updateMessage.value = `已导入：${result.name}`;
    } catch (e) {
      updateMessage.value = String(e);
    }
  }

  async function selectHistorySound(path: string, name: string) {
    const history = [
      { path, name },
      ...config.value.sound_history.filter((h) => h.path !== path),
    ].slice(0, 12);
    await save({ sound_id: "custom", sound_path: path, sound_history: history });
  }

  async function previewSound() {
    await playFinishSound({
      muted: false,
      soundId: config.value.sound_id,
      customPath: config.value.sound_path,
    });
  }

  function stopPreview() {
    stopSound();
  }

  async function clearSoundHistory() {
    await save({ sound_history: [] });
  }

  async function purgeSounds() {
    try {
      const n = await purgeOrphanSounds(
        config.value.sound_history,
        config.value.sound_path,
      );
      updateMessage.value = n ? `已清理 ${n} 个未使用音效` : "没有可清理的文件";
    } catch (e) {
      updateMessage.value = String(e);
    }
  }

  async function playFinishIfNeeded() {
    await playFinishSound({
      muted: config.value.sound_muted,
      soundId: config.value.sound_id,
      customPath: config.value.sound_path,
    });
  }

  async function runUpdateCheck(manual: boolean) {
    if (updateBusy.value) {
      if (manual) updateMessage.value = "正在检查更新…";
      return;
    }
    updateBusy.value = true;
    updateMessage.value = manual ? "正在检查更新…" : "";
    try {
      const ignored = manual ? "" : config.value.ignored_update_version;
      const info = await checkForUpdate(ignored);
      await save({ last_update_check: todayIso() });
      lastUpdateInfo.value = info;
      if (!info.available) {
        if (manual) {
          updateMessage.value = `已是最新版本（${info.current}）`;
        }
        return;
      }
      updateMessage.value = `发现新版本 ${info.latest}`;
      // 简单确认
      const ok = window.confirm(
        `发现新版本 ${info.latest}（当前 ${info.current}）\n\n${(info.body || "").slice(0, 400)}\n\n是否更新？\n（取消后再选是否忽略此版本）`,
      );
      if (!ok) {
        const ignore = window.confirm(`是否忽略版本 ${info.latest}？`);
        if (ignore) await save({ ignored_update_version: info.latest });
        return;
      }
      if (config.value.ignored_update_version === info.latest) {
        await save({ ignored_update_version: "" });
      }
      await installUpdateOrOpenPage(info);
    } catch (e) {
      if (manual) updateMessage.value = `检查失败：${e}`;
    } finally {
      updateBusy.value = false;
    }
  }

  function openSettings() {
    settingsOpen.value = true;
    updateMessage.value = "";
  }

  function closeSettings() {
    settingsOpen.value = false;
    stopSound();
  }

  async function setMode(m: "full" | "mini") {
    mode.value = m;
    await save({ last_mode: m });
    try {
      if (m === "mini") await invoke("enter_mini_mode");
      else await invoke("enter_full_mode");
    } catch (e) {
      console.error("mode switch failed", e);
    }
  }

  async function hideToTray() {
    try {
      await invoke("hide_main_window");
    } catch (e) {
      console.error(e);
    }
  }

  async function quitApp() {
    stopSound();
    try {
      await invoke("quit_app");
    } catch {
      window.close();
    }
  }

  return {
    config,
    settingsOpen,
    mode,
    loaded,
    colors,
    themes,
    soundPresets,
    updateBusy,
    updateMessage,
    lastUpdateInfo,
    load,
    save,
    setTheme,
    setSoundId,
    toggleTransparent,
    toggleAutostart,
    setAutostart,
    importSound,
    selectHistorySound,
    previewSound,
    stopPreview,
    clearSoundHistory,
    purgeSounds,
    playFinishIfNeeded,
    runUpdateCheck,
    openReleasesPage,
    openSettings,
    closeSettings,
    setMode,
    hideToTray,
    quitApp,
    applyThemeCss,
    isSoundPlaying,
  };
});
