<script setup lang="ts">
defineProps<{
  title: string;
  showMini?: boolean;
  showSettings?: boolean;
}>();

const emit = defineEmits<{
  settings: [];
  mini: [];
  close: [];
}>();
</script>

<template>
  <header class="titlebar" data-tauri-drag-region>
    <div class="titlebar-title">{{ title }}</div>
    <div class="titlebar-actions" style="display: flex; gap: 6px">
      <button
        v-if="showSettings !== false"
        type="button"
        class="circle-btn settings"
        title="设置"
        @click="emit('settings')"
      >
        ⚙
      </button>
      <button
        v-if="showMini !== false"
        type="button"
        class="circle-btn mini"
        title="Mini"
        @click="emit('mini')"
      >
        −
      </button>
      <button type="button" class="circle-btn close" title="关闭" @click="emit('close')">
        ×
      </button>
    </div>
  </header>
</template>
