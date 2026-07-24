<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    modelValue: number;
    min?: number;
    max?: number;
    disabled?: boolean;
    pad?: number;
  }>(),
  {
    min: 0,
    max: 59,
    disabled: false,
    pad: 2,
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: number];
}>();

function clamp(n: number): number {
  if (Number.isNaN(n)) return props.min;
  return Math.min(props.max, Math.max(props.min, Math.trunc(n)));
}

function step(delta: number) {
  if (props.disabled) return;
  emit("update:modelValue", clamp(props.modelValue + delta));
}

function onInput(e: Event) {
  if (props.disabled) return;
  const raw = (e.target as HTMLInputElement).value;
  if (raw === "") return;
  emit("update:modelValue", clamp(Number(raw)));
}

function onBlur(e: Event) {
  if (props.disabled) return;
  const el = e.target as HTMLInputElement;
  const v = clamp(Number(el.value) || 0);
  el.value = String(v).padStart(props.pad, "0");
  emit("update:modelValue", v);
}

function onWheel(e: WheelEvent) {
  if (props.disabled) return;
  e.preventDefault();
  step(e.deltaY < 0 ? 1 : -1);
}

function displayValue(): string {
  return String(props.modelValue).padStart(props.pad, "0");
}
</script>

<template>
  <div class="time-stepper" :class="{ locked: disabled }">
    <button
      type="button"
      class="step-btn"
      tabindex="-1"
      :disabled="disabled"
      aria-label="减少"
      @click="step(-1)"
    >
      −
    </button>
    <input
      type="text"
      inputmode="numeric"
      class="step-input"
      :value="displayValue()"
      :disabled="disabled"
      :aria-valuemin="min"
      :aria-valuemax="max"
      :aria-valuenow="modelValue"
      @input="onInput"
      @blur="onBlur"
      @wheel="onWheel"
    />
    <button
      type="button"
      class="step-btn"
      tabindex="-1"
      :disabled="disabled"
      aria-label="增加"
      @click="step(1)"
    >
      +
    </button>
  </div>
</template>
