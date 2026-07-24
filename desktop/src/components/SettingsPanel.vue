<script setup lang="ts">
import { APP_NAME, APP_VERSION } from "../core/constants";
import { useSettingsStore } from "../stores/settings";

const settings = useSettingsStore();

async function toggleMute() {
  await settings.save({ sound_muted: !settings.config.sound_muted });
}

async function toggleCheckUpdate() {
  await settings.save({
    check_update_on_start: !settings.config.check_update_on_start,
  });
}
</script>

<template>
  <div class="settings-overlay" @click.self="settings.closeSettings()">
    <div class="settings-panel">
      <header class="titlebar" data-tauri-drag-region>
        <div class="titlebar-title">⚙  设置</div>
        <div class="titlebar-actions">
          <button type="button" class="circle-btn close" @click="settings.closeSettings()">
            ×
          </button>
        </div>
      </header>

      <div class="settings-scroll">
        <p style="font-size: 12px; color: var(--c-text-muted); margin-bottom: 12px">
          外观 · 声音 · 系统 · 关于
        </p>
        <div style="height: 2px; background: var(--c-accent); margin-bottom: 16px" />

        <section class="settings-section">
          <h3>外观</h3>
          <div class="settings-card">
            <div
              v-for="[id, name] in settings.themes"
              :key="id"
              class="option-row"
              @click="settings.setTheme(id)"
            >
              <span class="mark">{{ settings.config.theme_id === id ? "✓" : "" }}</span>
              <span>{{ name }}</span>
            </div>
            <div class="option-row" @click="settings.toggleTransparent()">
              <span class="mark">{{ settings.config.transparent_mode ? "✓" : "" }}</span>
              <span>透明 Mini（背景 100% 透明）</span>
            </div>
          </div>
        </section>

        <section class="settings-section">
          <h3>声音</h3>
          <div class="settings-card">
            <div class="option-row" @click="toggleMute()">
              <span class="mark">{{ settings.config.sound_muted ? "✓" : "" }}</span>
              <span>结束静音</span>
            </div>
            <div
              v-for="p in settings.soundPresets"
              :key="p.id"
              class="option-row"
              @click="settings.setSoundId(p.id)"
            >
              <span class="mark">{{ settings.config.sound_id === p.id ? "✓" : "" }}</span>
              <span>{{ p.name }}</span>
            </div>
            <p
              v-if="settings.config.sound_id === 'custom' && settings.config.sound_path"
              style="font-size: 11px; color: var(--c-text-dim); padding: 4px 8px"
            >
              当前自定义：{{ settings.config.sound_path.split(/[/\\]/).pop() }}
            </p>
            <div v-if="settings.config.sound_history.length" style="margin-top: 6px">
              <div
                style="font-size: 11px; color: var(--c-text-muted); padding: 4px 8px"
              >
                最近导入
              </div>
              <div
                v-for="h in settings.config.sound_history.slice(0, 8)"
                :key="h.path"
                class="option-row"
                @click="settings.selectHistorySound(h.path, h.name)"
              >
                <span class="mark">{{
                  settings.config.sound_id === "custom" &&
                  settings.config.sound_path === h.path
                    ? "✓"
                    : ""
                }}</span>
                <span>{{ h.name || h.path.split(/[/\\]/).pop() }}</span>
              </div>
            </div>
            <div class="settings-btns">
              <button type="button" class="btn-secondary" @click="settings.importSound()">
                导入…
              </button>
              <button type="button" class="btn-primary" @click="settings.previewSound()">
                试听
              </button>
              <button type="button" class="btn-secondary" @click="settings.stopPreview()">
                停止
              </button>
            </div>
            <div class="settings-btns">
              <button
                type="button"
                class="btn-secondary"
                @click="settings.clearSoundHistory()"
              >
                清空历史
              </button>
              <button type="button" class="btn-secondary" @click="settings.purgeSounds()">
                清理未使用
              </button>
            </div>
            <p style="font-size: 11px; color: var(--c-text-muted); padding: 4px 8px">
              .ncm 暂不支持，请转换为 mp3/wav 后导入
            </p>
          </div>
        </section>

        <section class="settings-section">
          <h3>系统</h3>
          <div class="settings-card">
            <div class="option-row" @click="settings.toggleAutostart()">
              <span class="mark">{{ settings.config.autostart ? "✓" : "" }}</span>
              <span>开机自启</span>
            </div>
            <div class="option-row" @click="toggleCheckUpdate()">
              <span class="mark">{{
                settings.config.check_update_on_start ? "✓" : ""
              }}</span>
              <span>启动时检查更新</span>
            </div>
          </div>
        </section>

        <section class="settings-section">
          <h3>关于</h3>
          <div class="settings-card">
            <div style="font-weight: 600; padding: 4px 8px">{{ APP_NAME }}</div>
            <div class="about-ver" style="padding: 0 8px">
              版本 {{ APP_VERSION }} · Tauri
            </div>
            <div class="settings-btns">
              <button
                type="button"
                class="btn-primary"
                :disabled="settings.updateBusy"
                @click="settings.runUpdateCheck(true)"
              >
                检查更新…
              </button>
              <button
                type="button"
                class="btn-secondary"
                @click="settings.openReleasesPage()"
              >
                GitHub 发布页
              </button>
            </div>
            <p
              v-if="settings.updateMessage"
              style="font-size: 12px; color: var(--c-accent-glow); padding: 8px"
            >
              {{ settings.updateMessage }}
            </p>
          </div>
        </section>

        <div style="display: flex; justify-content: flex-end">
          <button type="button" class="btn-secondary" @click="settings.closeSettings()">
            关闭
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px;
}
</style>
