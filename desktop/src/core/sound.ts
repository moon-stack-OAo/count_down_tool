/** 结束音效：预设 / 自定义 / 系统铃（Web Audio） */

import { convertFileSrc, invoke } from "@tauri-apps/api/core";
import type { SoundId } from "./constants";

export const SOUND_PRESETS: { id: SoundId; name: string }[] = [
  { id: "system", name: "系统铃声" },
  { id: "soft", name: "柔和提示" },
  { id: "chime", name: "清脆钟声" },
  { id: "alert", name: "紧急警报" },
];

const PRESET_URL: Partial<Record<SoundId, string>> = {
  soft: "/sounds/soft.wav",
  chime: "/sounds/chime.wav",
  alert: "/sounds/alert.wav",
};

let currentAudio: HTMLAudioElement | null = null;
let stopBell: (() => void) | null = null;

export function stopSound(): void {
  if (currentAudio) {
    try {
      currentAudio.pause();
      currentAudio.src = "";
    } catch {
      /* ignore */
    }
    currentAudio = null;
  }
  if (stopBell) {
    stopBell();
    stopBell = null;
  }
}

function playUrl(url: string): Promise<void> {
  stopSound();
  return new Promise((resolve, reject) => {
    const a = new Audio(url);
    currentAudio = a;
    a.onended = () => {
      if (currentAudio === a) currentAudio = null;
      resolve();
    };
    a.onerror = () => {
      if (currentAudio === a) currentAudio = null;
      reject(new Error("audio play failed"));
    };
    void a.play().catch(reject);
  });
}

/** 系统铃：Web Audio 短促提示 3 次 */
function playSystemBell(times = 3): Promise<void> {
  stopSound();
  const Ctx =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  if (!Ctx) return Promise.resolve();
  const ctx = new Ctx();
  let cancelled = false;
  stopBell = () => {
    cancelled = true;
    void ctx.close();
  };

  return (async () => {
    for (let i = 0; i < times; i++) {
      if (cancelled) break;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = 880;
      gain.gain.value = 0.08;
      osc.connect(gain);
      gain.connect(ctx.destination);
      const t0 = ctx.currentTime;
      osc.start(t0);
      gain.gain.exponentialRampToValueAtTime(0.001, t0 + 0.18);
      osc.stop(t0 + 0.2);
      await new Promise((r) => setTimeout(r, 400));
    }
    if (!cancelled) void ctx.close();
    stopBell = null;
  })();
}

export async function resolvePlayUrl(
  soundId: SoundId,
  customPath: string,
): Promise<"system" | string> {
  if (soundId === "system") return "system";
  if (soundId === "custom" && customPath) {
    try {
      // 自定义文件用 asset 协议
      return convertFileSrc(customPath);
    } catch {
      return PRESET_URL.soft || "system";
    }
  }
  return PRESET_URL[soundId] || PRESET_URL.soft || "system";
}

export async function playFinishSound(opts: {
  muted: boolean;
  soundId: SoundId;
  customPath?: string;
}): Promise<void> {
  if (opts.muted) return;
  try {
    const target = await resolvePlayUrl(opts.soundId, opts.customPath || "");
    if (target === "system") {
      await playSystemBell(3);
      return;
    }
    await playUrl(target);
  } catch (e) {
    console.warn("playFinishSound failed, fallback system", e);
    try {
      await playSystemBell(2);
    } catch {
      /* ignore */
    }
  }
}

export interface ImportSoundResult {
  path: string;
  name: string;
}

export async function importSoundFile(srcPath: string): Promise<ImportSoundResult> {
  return invoke<ImportSoundResult>("import_sound", { path: srcPath });
}

export async function purgeOrphanSounds(
  history: { path: string; name: string }[],
  currentPath: string,
): Promise<number> {
  return invoke<number>("purge_orphan_sounds", {
    history,
    currentPath,
  });
}

export function isSoundPlaying(): boolean {
  if (currentAudio && !currentAudio.paused) return true;
  return stopBell != null;
}
