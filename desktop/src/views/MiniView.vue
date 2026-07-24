<script setup lang="ts">
import {
  STATE_FINISHED,
  STATE_IDLE,
  STATE_PAUSED,
  STATE_RUNNING,
} from "../core/constants";
import { useCountdownStore } from "../stores/countdown";
import { useSettingsStore } from "../stores/settings";

const cd = useCountdownStore();
const settings = useSettingsStore();

function timeClass() {
  if (cd.state === STATE_FINISHED) return "ok";
  if (cd.state === STATE_PAUSED || cd.state === STATE_IDLE) return "dim";
  return "";
}

function displayText() {
  if (cd.state === STATE_IDLE) return cd.clockText;
  return cd.remainingText;
}
</script>

<template>
  <div
    class="mini-root"
    :class="{ transparent: settings.config.transparent_mode }"
    data-tauri-drag-region
  >
    <div class="mini-time" :class="timeClass()">{{ displayText() }}</div>
    <div class="mini-actions no-drag">
      <button
        v-if="cd.state === STATE_RUNNING || cd.state === STATE_PAUSED || cd.state === STATE_IDLE || cd.state === STATE_FINISHED"
        type="button"
        class="circle-btn"
        title="开始/暂停"
        @click="cd.toggle()"
      >
        ▶
      </button>
      <button
        type="button"
        class="circle-btn settings"
        title="展开"
        @click="settings.setMode('full')"
      >
        ↗
      </button>
      <button
        type="button"
        class="circle-btn close"
        title="关闭"
        @click="settings.hideToTray()"
      >
        ×
      </button>
    </div>
  </div>
</template>
