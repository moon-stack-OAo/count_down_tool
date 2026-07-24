/**
 * 轻量自检：在 Node 下用 tsx/vitest 均可跑；此处供手工与后续测试接入。
 * 运行（可选）：npx tsx src/core/countdown.spec.ts
 */
import {
  buttonTextForState,
  formatRemaining,
  nextState,
  progressRatio,
  targetFromHms,
  toggleActionForState,
  validateHms,
} from "./countdown";
import {
  ACTION_PAUSE,
  ACTION_START,
  BTN_PAUSE,
  BTN_START,
  STATE_IDLE,
  STATE_RUNNING,
} from "./constants";

function assert(cond: boolean, msg: string) {
  if (!cond) throw new Error(msg);
}

assert(nextState(ACTION_START, STATE_IDLE) === STATE_RUNNING, "idle→start→running");
assert(nextState(ACTION_PAUSE, STATE_RUNNING) === "paused", "running→pause");
assert(buttonTextForState(STATE_IDLE) === BTN_START, "btn idle");
assert(buttonTextForState(STATE_RUNNING) === BTN_PAUSE, "btn running");
assert(toggleActionForState(STATE_IDLE) === ACTION_START, "toggle idle");
assert(validateHms(18, 0, 0).ok === true, "hms ok");
assert(validateHms(25, 0, 0).ok === false, "hms bad hour");
assert(formatRemaining(3661) === "01:01:01", "format");
assert(Math.abs(progressRatio(50, 100) - 0.5) < 1e-9, "progress");

const now = new Date(2026, 0, 1, 10, 0, 0);
const t = targetFromHms(9, 0, 0, now);
assert(t.getDate() === 2, "hms rolls to next day");

console.log("countdown.spec: all passed");
