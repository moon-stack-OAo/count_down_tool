/** 倒计时纯逻辑（无 DOM / Tauri） */

import {
  ACTION_FINISH,
  ACTION_PAUSE,
  ACTION_RESET,
  ACTION_RESTART,
  ACTION_RESUME,
  ACTION_START,
  ACTION_START_FAIL,
  BTN_PAUSE,
  BTN_RESTART,
  BTN_RESUME,
  BTN_START,
  type CountdownAction,
  type CountdownState,
  STATE_FINISHED,
  STATE_IDLE,
  STATE_PAUSED,
  STATE_RUNNING,
} from "./constants";

const BUTTON_TEXT: Record<CountdownState, string> = {
  [STATE_IDLE]: BTN_START,
  [STATE_RUNNING]: BTN_PAUSE,
  [STATE_PAUSED]: BTN_RESUME,
  [STATE_FINISHED]: BTN_RESTART,
};

const TRANSITIONS: Partial<Record<`${CountdownState}:${CountdownAction}`, CountdownState>> = {
  [`${STATE_IDLE}:${ACTION_START}`]: STATE_RUNNING,
  [`${STATE_IDLE}:${ACTION_START_FAIL}`]: STATE_IDLE,
  [`${STATE_IDLE}:${ACTION_RESET}`]: STATE_IDLE,
  [`${STATE_RUNNING}:${ACTION_PAUSE}`]: STATE_PAUSED,
  [`${STATE_RUNNING}:${ACTION_FINISH}`]: STATE_FINISHED,
  [`${STATE_RUNNING}:${ACTION_RESET}`]: STATE_IDLE,
  [`${STATE_RUNNING}:${ACTION_START_FAIL}`]: STATE_IDLE,
  [`${STATE_PAUSED}:${ACTION_RESUME}`]: STATE_RUNNING,
  [`${STATE_PAUSED}:${ACTION_RESET}`]: STATE_IDLE,
  [`${STATE_FINISHED}:${ACTION_RESTART}`]: STATE_RUNNING,
  [`${STATE_FINISHED}:${ACTION_START_FAIL}`]: STATE_FINISHED,
  [`${STATE_FINISHED}:${ACTION_RESET}`]: STATE_IDLE,
};

export function buttonTextForState(state: CountdownState): string {
  return BUTTON_TEXT[state] ?? BTN_START;
}

export function nextState(action: CountdownAction, state: CountdownState): CountdownState {
  const key = `${state}:${action}` as `${CountdownState}:${CountdownAction}`;
  if (TRANSITIONS[key]) return TRANSITIONS[key]!;
  if (action === ACTION_RESET) return STATE_IDLE;
  return state;
}

export function toggleActionForState(state: CountdownState): CountdownAction {
  switch (state) {
    case STATE_IDLE:
      return ACTION_START;
    case STATE_RUNNING:
      return ACTION_PAUSE;
    case STATE_PAUSED:
      return ACTION_RESUME;
    case STATE_FINISHED:
      return ACTION_RESTART;
    default:
      return ACTION_START;
  }
}

export function validateHms(
  hour: number,
  minute: number,
  second: number,
): { ok: true } | { ok: false; error: string } {
  try {
    for (const [val, max] of [
      [hour, 23],
      [minute, 59],
      [second, 59],
    ] as const) {
      const n = Number(val);
      if (!Number.isFinite(n) || n < 0 || n > max) {
        return { ok: false, error: `输入值应在 00-${String(max).padStart(2, "0")} 之间` };
      }
    }
    return { ok: true };
  } catch {
    return { ok: false, error: "请输入有效数字" };
  }
}

/** 今日该时刻；已过则 +1 天 */
export function targetFromHms(
  hour: number,
  minute: number,
  second: number,
  now = new Date(),
): Date {
  const target = new Date(now);
  target.setHours(Math.trunc(hour), Math.trunc(minute), Math.trunc(second), 0);
  if (target.getTime() < now.getTime()) {
    target.setDate(target.getDate() + 1);
  }
  return target;
}

export function targetFromDuration(
  hours: number,
  minutes: number,
  seconds: number,
  now = new Date(),
): { target: Date; durationMs: number } {
  const durationMs =
    (Math.trunc(hours) * 3600 + Math.trunc(minutes) * 60 + Math.trunc(seconds)) * 1000;
  return { target: new Date(now.getTime() + durationMs), durationMs };
}

export function formatRemaining(totalSeconds: number): string {
  let total = Math.trunc(totalSeconds);
  if (total < 0) total = 0;
  const hours = Math.floor(total / 3600);
  const remainder = total % 3600;
  const minutes = Math.floor(remainder / 60);
  const seconds = remainder % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function progressRatio(remainingSeconds: number, totalSeconds: number): number {
  const remaining = Number(remainingSeconds);
  const total = Number(totalSeconds);
  if (!Number.isFinite(remaining) || !Number.isFinite(total)) return 0;
  if (total <= 0) return 1;
  const ratio = 1 - remaining / total;
  return Math.min(1, Math.max(0, ratio));
}

export function remainingSeconds(target: Date, now = new Date()): number {
  return Math.max(0, Math.ceil((target.getTime() - now.getTime()) / 1000));
}

export function formatClock(d = new Date()): string {
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}

export function formatTargetLabel(target: Date): string {
  return `到期 ${formatClock(target)}`;
}

/** 对齐下一整秒，返回 1..1000 ms */
export function nextSecondDelayMs(now = new Date()): number {
  const delay = 1000 - now.getMilliseconds();
  if (delay < 1) return 1;
  if (delay > 1000) return 1000;
  return delay;
}

export const PRESETS: { label: string; h: number; m: number; s: number }[] = [
  { label: "+5分", h: 0, m: 5, s: 0 },
  { label: "+10分", h: 0, m: 10, s: 0 },
  { label: "+15分", h: 0, m: 15, s: 0 },
  { label: "+30分", h: 0, m: 30, s: 0 },
  { label: "+1时", h: 1, m: 0, s: 0 },
];
