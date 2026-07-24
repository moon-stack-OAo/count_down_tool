<script setup lang="ts">
import { computed } from "vue";
import {
  APP_NAME,
  STATE_FINISHED,
  STATE_IDLE,
  STATE_PAUSED,
  STATE_RUNNING,
} from "../core/constants";
import { PRESETS } from "../core/countdown";
import TitleBar from "../components/TitleBar.vue";
import SettingsPanel from "../components/SettingsPanel.vue";
import TimeStepper from "../components/TimeStepper.vue";
import { useCountdownStore } from "../stores/countdown";
import { useSettingsStore } from "../stores/settings";

const cd = useCountdownStore();
const settings = useSettingsStore();

const primaryBtnClass = computed(() => {
  switch (cd.state) {
    case STATE_RUNNING:
    case STATE_PAUSED:
      return "is-running";
    case STATE_FINISHED:
      return "is-finished";
    case STATE_IDLE:
    default:
      return "is-idle";
  }
});

function setHour(v: number) {
  cd.setHms(v, cd.minute, cd.second);
}
function setMinute(v: number) {
  cd.setHms(cd.hour, v, cd.second);
}
function setSecond(v: number) {
  cd.setHms(cd.hour, cd.minute, v);
}
</script>

<template>
  <div class="full-root opaque-shell">
    <TitleBar
      :title="`⏱  ${APP_NAME}`"
      @settings="settings.openSettings()"
      @mini="settings.setMode('mini')"
      @close="settings.hideToTray()"
    />

    <div class="main-body">
      <div class="card display-card">
        <div
          class="countdown-display"
          :class="{ success: cd.state === STATE_FINISHED }"
        >
          {{ cd.remainingText }}
        </div>
        <div
          class="progress-track"
          :class="{ full: cd.state === STATE_FINISHED }"
        >
          <div class="progress-fill" :style="{ width: `${cd.progress * 100}%` }" />
        </div>
        <div class="meta">
          <div class="target">{{ cd.targetLabel }}</div>
          <div class="clock">现在 {{ cd.clockText }}</div>
        </div>
      </div>

      <div class="card muted time-card" :class="{ locked: cd.inputsLocked }">
        <div class="section-label">到期时间</div>
        <div class="hms-row">
          <TimeStepper
            :model-value="cd.hour"
            :min="0"
            :max="23"
            :disabled="cd.inputsLocked"
            @update:model-value="setHour"
          />
          <span class="sep">:</span>
          <TimeStepper
            :model-value="cd.minute"
            :min="0"
            :max="59"
            :disabled="cd.inputsLocked"
            @update:model-value="setMinute"
          />
          <span class="sep">:</span>
          <TimeStepper
            :model-value="cd.second"
            :min="0"
            :max="59"
            :disabled="cd.inputsLocked"
            @update:model-value="setSecond"
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

      <div v-if="cd.error" class="error-line">{{ cd.error }}</div>

      <div class="actions">
        <button
          type="button"
          class="btn-primary"
          :class="primaryBtnClass"
          @click="cd.toggle()"
        >
          {{ cd.buttonText }}
        </button>
        <button type="button" class="btn-secondary" @click="cd.reset()">重置</button>
      </div>
    </div>

    <SettingsPanel v-if="settings.settingsOpen" />
  </div>
</template>
