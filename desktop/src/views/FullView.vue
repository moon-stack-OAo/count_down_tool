<script setup lang="ts">
import { APP_NAME } from "../core/constants";
import { PRESETS } from "../core/countdown";
import { STATE_FINISHED } from "../core/constants";
import TitleBar from "../components/TitleBar.vue";
import SettingsPanel from "../components/SettingsPanel.vue";
import { useCountdownStore } from "../stores/countdown";
import { useSettingsStore } from "../stores/settings";

const cd = useCountdownStore();
const settings = useSettingsStore();

function onHour(e: Event) {
  cd.setHms(Number((e.target as HTMLInputElement).value) || 0, cd.minute, cd.second);
}
function onMinute(e: Event) {
  cd.setHms(cd.hour, Number((e.target as HTMLInputElement).value) || 0, cd.second);
}
function onSecond(e: Event) {
  cd.setHms(cd.hour, cd.minute, Number((e.target as HTMLInputElement).value) || 0);
}
</script>

<template>
  <div class="full-root opaque-shell" style="height: 100%; display: flex; flex-direction: column">
    <TitleBar
      :title="`⏱  ${APP_NAME}`"
      @settings="settings.openSettings()"
      @mini="settings.setMode('mini')"
      @close="settings.hideToTray()"
    />

    <div class="main-body">
      <div class="card">
        <div
          class="countdown-display"
          :class="{ success: cd.state === STATE_FINISHED }"
        >
          {{ cd.remainingText }}
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: `${cd.progress * 100}%` }" />
        </div>
        <div class="meta">
          <div>{{ cd.targetLabel }}</div>
          <div class="clock">现在 {{ cd.clockText }}</div>
        </div>
      </div>

      <div class="card muted">
        <div class="section-label">到期时间</div>
        <div class="hms-row">
          <input
            type="number"
            min="0"
            max="23"
            :value="cd.hour"
            :disabled="cd.inputsLocked"
            @change="onHour"
          />
          <span class="sep">:</span>
          <input
            type="number"
            min="0"
            max="59"
            :value="cd.minute"
            :disabled="cd.inputsLocked"
            @change="onMinute"
          />
          <span class="sep">:</span>
          <input
            type="number"
            min="0"
            max="59"
            :value="cd.second"
            :disabled="cd.inputsLocked"
            @change="onSecond"
          />
        </div>
        <div class="presets">
          <button
            v-for="p in PRESETS"
            :key="p.label"
            type="button"
            class="chip"
            :disabled="cd.inputsLocked"
            @click="cd.startFromPreset(p.h, p.m, p.s)"
          >
            {{ p.label }}
          </button>
        </div>
      </div>

      <div class="error-line">{{ cd.error }}</div>

      <div class="actions">
        <button type="button" class="btn-primary" @click="cd.toggle()">
          {{ cd.buttonText }}
        </button>
        <button type="button" class="btn-secondary" @click="cd.reset()">重置</button>
      </div>
    </div>

    <SettingsPanel v-if="settings.settingsOpen" />
  </div>
</template>
