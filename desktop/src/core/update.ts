/** 更新检查：优先 Tauri updater，失败则 GitHub API + 打开发布页 */

import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";
import { openUrl } from "@tauri-apps/plugin-opener";
import { APP_VERSION } from "./constants";

export const GITHUB_RELEASES_PAGE =
  "https://github.com/moon-stack-OAo/count_down_tool/releases/latest";

export interface UpdateInfo {
  available: boolean;
  current: string;
  latest: string;
  body: string;
  /** tauri updater 可用时尝试安装 */
  canInstall: boolean;
  htmlUrl: string;
}

function parseVer(s: string): number[] {
  const m = s.replace(/^v/i, "").match(/(\d+)\.(\d+)\.(\d+)/);
  if (!m) return [0, 0, 0];
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}

export function isNewerVersion(remote: string, local: string): boolean {
  const a = parseVer(remote);
  const b = parseVer(local);
  for (let i = 0; i < 3; i++) {
    if (a[i] > b[i]) return true;
    if (a[i] < b[i]) return false;
  }
  return false;
}

export async function checkForUpdate(ignoredVersion = ""): Promise<UpdateInfo> {
  const current = APP_VERSION;

  // 1) Tauri updater（需 latest.json + 签名；未配置时会失败）
  try {
    const update = await check();
    if (update) {
      const latest = update.version || "";
      if (ignoredVersion && latest === ignoredVersion) {
        return {
          available: false,
          current,
          latest,
          body: "",
          canInstall: false,
          htmlUrl: GITHUB_RELEASES_PAGE,
        };
      }
      return {
        available: true,
        current,
        latest,
        body: update.body || "",
        canInstall: true,
        htmlUrl: GITHUB_RELEASES_PAGE,
      };
    }
  } catch (e) {
    console.debug("tauri updater check skipped", e);
  }

  // 2) GitHub API 回退
  try {
    const res = await fetch(
      "https://api.github.com/repos/moon-stack-OAo/count_down_tool/releases/latest",
      { headers: { Accept: "application/vnd.github+json" } },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as {
      tag_name?: string;
      body?: string;
      html_url?: string;
    };
    const latest = (data.tag_name || "").replace(/^v/i, "");
    const newer = isNewerVersion(latest, current);
    if (!newer || (ignoredVersion && latest === ignoredVersion)) {
      return {
        available: false,
        current,
        latest: latest || current,
        body: "",
        canInstall: false,
        htmlUrl: data.html_url || GITHUB_RELEASES_PAGE,
      };
    }
    return {
      available: true,
      current,
      latest,
      body: (data.body || "").slice(0, 600),
      canInstall: false,
      htmlUrl: data.html_url || GITHUB_RELEASES_PAGE,
    };
  } catch (e) {
    console.error("github update check failed", e);
    return {
      available: false,
      current,
      latest: current,
      body: "",
      canInstall: false,
      htmlUrl: GITHUB_RELEASES_PAGE,
    };
  }
}

export async function installUpdateOrOpenPage(info: UpdateInfo): Promise<void> {
  if (info.canInstall) {
    try {
      const update = await check();
      if (update) {
        await update.downloadAndInstall();
        await relaunch();
        return;
      }
    } catch (e) {
      console.error("install update failed", e);
    }
  }
  await openUrl(info.htmlUrl || GITHUB_RELEASES_PAGE);
}

export async function openReleasesPage(): Promise<void> {
  await openUrl(GITHUB_RELEASES_PAGE);
}

export function todayIso(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}
