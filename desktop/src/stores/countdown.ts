import { computed, ref } from "vue";
import { defineStore } from "pinia";
import {
  ACTION_FINISH,
  ACTION_PAUSE,
  ACTION_RESET,
  ACTION_RESTART,
  ACTION_RESUME,
  ACTION_START,
  ACTION_START_FAIL,
  type CountdownState,
  STATE_FINISHED,
  STATE_IDLE,
  STATE_PAUSED,
  STATE_RUNNING,
} from "../core/constants";
import {
  buttonTextForState,
  formatClock,
  formatRemaining,
  formatTargetLabel,
  nextSecondDelayMs,
  nextState,
  progressRatio,
  remainingSeconds,
  targetFromDuration,
  targetFromHms,
  toggleActionForState,
  validateHms,
} from "../core/countdown";

export const useCountdownStore = defineStore("countdown", () => {
  const state = ref<CountdownState>(STATE_IDLE);
  const hour = ref(18);
  const minute = ref(0);
  const second = ref(0);
  const target = ref<Date | null>(null);
  const durationTotalSeconds = ref(0);
  const remainingText = ref("--:--:--");
  const progress = ref(0);
  const error = ref("");
  const clockText = ref(formatClock());
  const targetLabel = ref("设置到期时间后开始");
  const pausedRemaining = ref(0);

  let tickTimer: ReturnType<typeof setTimeout> | null = null;
  let clockTimer: ReturnType<typeof setTimeout> | null = null;

  const buttonText = computed(() => buttonTextForState(state.value));
  const inputsLocked = computed(
    () => state.value === STATE_RUNNING || state.value === STATE_PAUSED,
  );

  function clearTick() {
    if (tickTimer != null) {
      clearTimeout(tickTimer);
      tickTimer = null;
    }
  }

  function setError(msg: string) {
    error.value = msg;
    if (msg) {
      setTimeout(() => {
        if (error.value === msg) error.value = "";
      }, 3200);
    }
  }

  function applyState(action: Parameters<typeof nextState>[0]) {
    state.value = nextState(action, state.value);
  }

  function refreshDisplay(now = new Date()) {
    clockText.value = formatClock(now);
    if (state.value === STATE_RUNNING && target.value) {
      const rem = remainingSeconds(target.value, now);
      remainingText.value = formatRemaining(rem);
      progress.value = progressRatio(rem, durationTotalSeconds.value);
      targetLabel.value = formatTargetLabel(target.value);
      if (rem <= 0) {
        finish();
      }
    } else if (state.value === STATE_PAUSED) {
      remainingText.value = formatRemaining(pausedRemaining.value);
      progress.value = progressRatio(pausedRemaining.value, durationTotalSeconds.value);
    } else if (state.value === STATE_FINISHED) {
      remainingText.value = "00:00:00";
      progress.value = 1;
    } else if (state.value === STATE_IDLE) {
      remainingText.value = "--:--:--";
      progress.value = 0;
    }
  }

  function scheduleTick() {
    clearTick();
    if (state.value !== STATE_RUNNING) return;
    tickTimer = setTimeout(() => {
      refreshDisplay();
      scheduleTick();
    }, nextSecondDelayMs());
  }

  function startClockLoop() {
    const loop = () => {
      if (state.value !== STATE_RUNNING) {
        clockText.value = formatClock();
      }
      clockTimer = setTimeout(loop, nextSecondDelayMs());
    };
    if (clockTimer != null) clearTimeout(clockTimer);
    loop();
  }

  function startFromHms() {
    const v = validateHms(hour.value, minute.value, second.value);
    if (!v.ok) {
      setError(v.error);
      applyState(ACTION_START_FAIL);
      return false;
    }
    const t = targetFromHms(hour.value, minute.value, second.value);
    const rem = remainingSeconds(t);
    if (rem <= 0) {
      setError("目标时间无效");
      applyState(ACTION_START_FAIL);
      return false;
    }
    target.value = t;
    durationTotalSeconds.value = rem;
    applyState(ACTION_START);
    refreshDisplay();
    scheduleTick();
    error.value = "";
    return true;
  }

  function startFromPreset(h: number, m: number, s: number) {
    if (inputsLocked.value) return false;
    const { target: t, durationMs } = targetFromDuration(h, m, s);
    target.value = t;
    durationTotalSeconds.value = Math.max(1, Math.round(durationMs / 1000));
    const end = new Date(t);
    hour.value = end.getHours();
    minute.value = end.getMinutes();
    second.value = end.getSeconds();
    applyState(ACTION_START);
    refreshDisplay();
    scheduleTick();
    error.value = "";
    return true;
  }

  function pause() {
    if (state.value !== STATE_RUNNING || !target.value) return;
    pausedRemaining.value = remainingSeconds(target.value);
    applyState(ACTION_PAUSE);
    clearTick();
    refreshDisplay();
  }

  function resume() {
    if (state.value !== STATE_PAUSED) return;
    target.value = new Date(Date.now() + pausedRemaining.value * 1000);
    applyState(ACTION_RESUME);
    refreshDisplay();
    scheduleTick();
  }

  let onFinished: (() => void) | null = null;

  function setOnFinished(cb: (() => void) | null) {
    onFinished = cb;
  }

  function finish() {
    applyState(ACTION_FINISH);
    clearTick();
    remainingText.value = "00:00:00";
    progress.value = 1;
    targetLabel.value = "时间到";
    try {
      onFinished?.();
    } catch (e) {
      console.warn("onFinished", e);
    }
  }

  function restart() {
    if (state.value !== STATE_FINISHED) return;
    // 按上次时长重新开始
    const total = durationTotalSeconds.value || 60;
    target.value = new Date(Date.now() + total * 1000);
    applyState(ACTION_RESTART);
    refreshDisplay();
    scheduleTick();
  }

  function reset() {
    applyState(ACTION_RESET);
    clearTick();
    target.value = null;
    durationTotalSeconds.value = 0;
    pausedRemaining.value = 0;
    remainingText.value = "--:--:--";
    progress.value = 0;
    targetLabel.value = "设置到期时间后开始";
    error.value = "";
  }

  function toggle() {
    const action = toggleActionForState(state.value);
    if (action === ACTION_START) return startFromHms();
    if (action === ACTION_PAUSE) {
      pause();
      return true;
    }
    if (action === ACTION_RESUME) {
      resume();
      return true;
    }
    if (action === ACTION_RESTART) {
      restart();
      return true;
    }
    return false;
  }

  function setHms(h: number, m: number, s: number) {
    if (inputsLocked.value) return;
    hour.value = h;
    minute.value = m;
    second.value = s;
  }

  startClockLoop();

  return {
    state,
    hour,
    minute,
    second,
    remainingText,
    progress,
    error,
    clockText,
    targetLabel,
    buttonText,
    inputsLocked,
    setHms,
    startFromPreset,
    toggle,
    reset,
    refreshDisplay,
    setOnFinished,
  };
});
