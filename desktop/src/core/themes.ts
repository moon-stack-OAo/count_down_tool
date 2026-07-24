/** 预设主题（对齐 Python core.themes） */

export type ThemeColors = Record<string, string>;

export const DEFAULT_THEME_ID = "slate_cyan";

const SLATE_CYAN: ThemeColors = {
  bg: "#0F1419",
  card: "#1A2332",
  card_border: "#2A3A4E",
  glass: "#16202C",
  accent: "#38BDF8",
  accent_hover: "#0EA5E9",
  accent_glow: "#7DD3FC",
  accent_soft: "#0C4A6E",
  success: "#4ADE80",
  error: "#FB7185",
  warning: "#FBBF24",
  text: "#F1F5F9",
  text_dim: "#8B9CB3",
  text_muted: "#64748B",
  input_bg: "#0C1219",
  border: "#2A3A4E",
  title_bar: "#0B1016",
  chip: "#1E2A3A",
  chip_hover: "#2A3F55",
  btn_default: "#334155",
  btn_hover_min: "#FBBF24",
  btn_hover_close: "#F43F5E",
  white: "#FFFFFF",
};

const MIDNIGHT_PURPLE: ThemeColors = {
  bg: "#0D0B14",
  card: "#1A1528",
  card_border: "#2E2640",
  glass: "#15101F",
  accent: "#A78BFA",
  accent_hover: "#8B5CF6",
  accent_glow: "#C4B5FD",
  accent_soft: "#4C1D95",
  success: "#4ADE80",
  error: "#FB7185",
  warning: "#FBBF24",
  text: "#F3F0FF",
  text_dim: "#A89BC4",
  text_muted: "#7C6F9A",
  input_bg: "#0A0812",
  border: "#2E2640",
  title_bar: "#0A0810",
  chip: "#221A33",
  chip_hover: "#342A4A",
  btn_default: "#3D3555",
  btn_hover_min: "#FBBF24",
  btn_hover_close: "#F43F5E",
  white: "#FFFFFF",
};

const WARM_AMBER: ThemeColors = {
  bg: "#14110C",
  card: "#241C12",
  card_border: "#3D2F1F",
  glass: "#1C1610",
  accent: "#F59E0B",
  accent_hover: "#D97706",
  accent_glow: "#FCD34D",
  accent_soft: "#78350F",
  success: "#4ADE80",
  error: "#FB7185",
  warning: "#FBBF24",
  text: "#FFF7ED",
  text_dim: "#C4A882",
  text_muted: "#9A7B52",
  input_bg: "#0F0C08",
  border: "#3D2F1F",
  title_bar: "#0F0C08",
  chip: "#2A2116",
  chip_hover: "#3F3120",
  btn_default: "#4A3B28",
  btn_hover_min: "#FBBF24",
  btn_hover_close: "#F43F5E",
  white: "#FFFFFF",
};

const EMERALD: ThemeColors = {
  bg: "#0A1410",
  card: "#12241C",
  card_border: "#1E3A2F",
  glass: "#0F1C16",
  accent: "#34D399",
  accent_hover: "#10B981",
  accent_glow: "#6EE7B7",
  accent_soft: "#064E3B",
  success: "#4ADE80",
  error: "#FB7185",
  warning: "#FBBF24",
  text: "#ECFDF5",
  text_dim: "#8BB8A4",
  text_muted: "#5C8A76",
  input_bg: "#08120E",
  border: "#1E3A2F",
  title_bar: "#08120E",
  chip: "#163028",
  chip_hover: "#224538",
  btn_default: "#2A4A3C",
  btn_hover_min: "#FBBF24",
  btn_hover_close: "#F43F5E",
  white: "#FFFFFF",
};

const LIGHT: ThemeColors = {
  bg: "#F1F5F9",
  card: "#FFFFFF",
  card_border: "#CBD5E1",
  glass: "#E8EEF5",
  accent: "#0284C7",
  accent_hover: "#0369A1",
  accent_glow: "#0EA5E9",
  accent_soft: "#BAE6FD",
  success: "#16A34A",
  error: "#E11D48",
  warning: "#D97706",
  text: "#0F172A",
  text_dim: "#475569",
  text_muted: "#64748B",
  input_bg: "#FFFFFF",
  border: "#CBD5E1",
  title_bar: "#E2E8F0",
  chip: "#E2E8F0",
  chip_hover: "#CBD5E1",
  btn_default: "#94A3B8",
  btn_hover_min: "#D97706",
  btn_hover_close: "#E11D48",
  white: "#FFFFFF",
};

export const THEMES: Record<string, { name: string; colors: ThemeColors }> = {
  slate_cyan: { name: "石板青蓝", colors: SLATE_CYAN },
  midnight_purple: { name: "暗夜紫", colors: MIDNIGHT_PURPLE },
  warm_amber: { name: "暖琥珀", colors: WARM_AMBER },
  emerald: { name: "翠绿", colors: EMERALD },
  light: { name: "浅色", colors: LIGHT },
};

export function listThemes(): [string, string][] {
  return Object.entries(THEMES).map(([id, meta]) => [id, meta.name]);
}

export function isValidThemeId(id: unknown): id is string {
  return typeof id === "string" && id in THEMES;
}

export function resolveTheme(
  themeId?: string | null,
  custom?: Record<string, string> | null,
): ThemeColors {
  const tid = isValidThemeId(themeId) ? themeId : DEFAULT_THEME_ID;
  const colors = { ...THEMES[tid].colors };
  if (custom && typeof custom === "object") {
    for (const [k, v] of Object.entries(custom)) {
      if (typeof k === "string" && typeof v === "string" && v) {
        colors[k] = v;
      }
    }
  }
  return colors;
}

/** 将主题写入 :root CSS 变量 */
export function applyThemeToDom(colors: ThemeColors): void {
  const root = document.documentElement;
  for (const [k, v] of Object.entries(colors)) {
    root.style.setProperty(`--c-${k.replace(/_/g, "-")}`, v);
  }
}
