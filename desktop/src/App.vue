<script setup lang="ts">
import { onMounted, onUnmounted, watch } from "vue";
import { listen } from "@tauri-apps/api/event";
import FullView from "./views/FullView.vue";
import MiniView from "./views/MiniView.vue";
import { useCountdownStore } from "./stores/countdown";
import { useSettingsStore } from "./stores/settings";

const settings = useSettingsStore();
const cd = useCountdownStore();

let unlisten: (() => void) | undefined;

/** Mini + 透明：html 加 class，避免任何层铺底色 */
function syncClearChrome() {
  const clear =
    settings.mode === "mini" && !!settings.config.transparent_mode;
  document.documentElement.classList.toggle("mini-clear", clear);
}

function onKey(ev: KeyboardEvent) {
  if (ev.key === "Escape") {
    if (settings.settingsOpen) settings.closeSettings();
    else settings.hideToTray();
  } else if (ev.key === "m" || ev.key === "M") {
    settings.setMode(settings.mode === "mini" ? "full" : "mini");
  }
}

onMounted(async () => {
  await settings.load();
  if (settings.config.last_hms) {
    const [h, m, s] = settings.config.last_hms;
    cd.setHms(h, m, s);
  }
  cd.setOnFinished(() => {
    void settings.playFinishIfNeeded();
  });

  try {
    unlisten = await listen<string>("tray://action", (e) => {
      const action = e.payload;
      if (action === "show") void settings.setMode("full");
      else if (action === "mini") void settings.setMode("mini");
      else if (action === "settings") {
        void settings.setMode("full").then(() => settings.openSettings());
      } else if (action === "toggle") cd.toggle();
      else if (action === "quit") void settings.quitApp();
    });
  } catch {
    /* 浏览器预览无 Tauri */
  }

  window.addEventListener("keydown", onKey);
  syncClearChrome();
});

onUnmounted(() => {
  unlisten?.();
  window.removeEventListener("keydown", onKey);
  document.documentElement.classList.remove("mini-clear");
});

watch(
  () => [cd.hour, cd.minute, cd.second] as const,
  ([h, m, s]) => {
    if (!cd.inputsLocked) {
      void settings.save({ last_hms: [h, m, s] });
    }
  },
);

watch(
  () => [settings.mode, settings.config.transparent_mode] as const,
  () => syncClearChrome(),
  { immediate: true },
);
</script>

<template>
  <MiniView v-if="settings.mode === 'mini'" />
  <FullView v-else />
</template>
