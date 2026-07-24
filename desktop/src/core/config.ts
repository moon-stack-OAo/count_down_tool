/** 配置类型与默认值（兼容 Python config.json） */

import type { SoundId } from "./constants";
import { DEFAULT_THEME_ID } from "./themes";

export interface AppConfig {
  mini_position: [number, number] | null;
  mini_size: [number, number] | null;
  transparent_mode: boolean;
  last_mode: "full" | "mini";
  autostart: boolean;
  theme_id: string;
  theme_custom: Record<string, string>;
  mini_text: Record<string, string>;
  sound_muted: boolean;
  sound_id: SoundId;
  sound_path: string;
  sound_history: { path: string; name: string }[];
  check_update_on_start: boolean;
  last_update_check: string;
  ignored_update_version: string;
  /** 完整窗上次设置的到期时分秒（可选，仅前端记忆） */
  last_hms?: [number, number, number];
}

export function defaultConfig(): AppConfig {
  return {
    mini_position: null,
    mini_size: null,
    transparent_mode: false,
    last_mode: "full",
    autostart: false,
    theme_id: DEFAULT_THEME_ID,
    theme_custom: {},
    mini_text: {},
    sound_muted: false,
    sound_id: "soft",
    sound_path: "",
    sound_history: [],
    check_update_on_start: true,
    last_update_check: "",
    ignored_update_version: "",
    last_hms: [18, 0, 0],
  };
}

export function mergeConfig(raw: unknown): AppConfig {
  const base = defaultConfig();
  if (!raw || typeof raw !== "object") return base;
  const o = raw as Record<string, unknown>;

  if (Array.isArray(o.mini_position) && o.mini_position.length === 2) {
    base.mini_position = [Number(o.mini_position[0]), Number(o.mini_position[1])];
  }
  if (Array.isArray(o.mini_size) && o.mini_size.length === 2) {
    base.mini_size = [Number(o.mini_size[0]), Number(o.mini_size[1])];
  }
  if (typeof o.transparent_mode === "boolean") base.transparent_mode = o.transparent_mode;
  if (o.last_mode === "full" || o.last_mode === "mini") base.last_mode = o.last_mode;
  if (typeof o.autostart === "boolean") base.autostart = o.autostart;
  if (typeof o.theme_id === "string" && o.theme_id) base.theme_id = o.theme_id;
  if (o.theme_custom && typeof o.theme_custom === "object") {
    base.theme_custom = o.theme_custom as Record<string, string>;
  }
  if (o.mini_text && typeof o.mini_text === "object") {
    base.mini_text = o.mini_text as Record<string, string>;
  }
  if (typeof o.sound_muted === "boolean") base.sound_muted = o.sound_muted;
  if (typeof o.sound_id === "string") {
    const sid = o.sound_id as SoundId;
    if (["system", "soft", "chime", "alert", "custom"].includes(sid)) {
      base.sound_id = sid;
    }
  }
  if (typeof o.sound_path === "string") base.sound_path = o.sound_path;
  if (Array.isArray(o.sound_history)) {
    base.sound_history = o.sound_history
      .map((item) => {
        if (item && typeof item === "object" && "path" in item) {
          const e = item as { path?: string; name?: string };
          return { path: String(e.path || ""), name: String(e.name || "") };
        }
        if (typeof item === "string") return { path: item, name: "" };
        return null;
      })
      .filter((x): x is { path: string; name: string } => !!x && !!x.path)
      .slice(0, 12);
  }
  if (typeof o.check_update_on_start === "boolean") {
    base.check_update_on_start = o.check_update_on_start;
  }
  if (typeof o.last_update_check === "string") base.last_update_check = o.last_update_check;
  if (typeof o.ignored_update_version === "string") {
    base.ignored_update_version = o.ignored_update_version;
  }
  if (Array.isArray(o.last_hms) && o.last_hms.length === 3) {
    base.last_hms = [
      Number(o.last_hms[0]) || 0,
      Number(o.last_hms[1]) || 0,
      Number(o.last_hms[2]) || 0,
    ];
  }
  return base;
}
