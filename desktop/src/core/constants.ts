/** 应用常量（对齐 Python core.countdown_core） */

export const APP_VERSION = "1.3.23";
export const APP_NAME = "倒计时工具";
export const APP_NAME_EN = "Count Down Tool";
export const CONFIG_APP_DIR = "count_down_tool";

export const STATE_IDLE = "idle" as const;
export const STATE_RUNNING = "running" as const;
export const STATE_PAUSED = "paused" as const;
export const STATE_FINISHED = "finished" as const;

export type CountdownState =
  | typeof STATE_IDLE
  | typeof STATE_RUNNING
  | typeof STATE_PAUSED
  | typeof STATE_FINISHED;

export const ACTION_START = "start" as const;
export const ACTION_PAUSE = "pause" as const;
export const ACTION_RESUME = "resume" as const;
export const ACTION_FINISH = "finish" as const;
export const ACTION_RESTART = "restart" as const;
export const ACTION_RESET = "reset" as const;
export const ACTION_START_FAIL = "start_fail" as const;

export type CountdownAction =
  | typeof ACTION_START
  | typeof ACTION_PAUSE
  | typeof ACTION_RESUME
  | typeof ACTION_FINISH
  | typeof ACTION_RESTART
  | typeof ACTION_RESET
  | typeof ACTION_START_FAIL;

export const BTN_START = "开始倒计时";
export const BTN_PAUSE = "暂停";
export const BTN_RESUME = "继续";
export const BTN_RESTART = "重新开始";

export const SOUND_IDS = ["system", "soft", "chime", "alert", "custom"] as const;
export type SoundId = (typeof SOUND_IDS)[number];
