export type Theme = {
  id: string;
  bg: string;
  bg2?: string;
  ink: string;
  muted: string;
  accent: string;
  accentSoft?: string;
  surface: string;
  line: string;
  fontDisplay: string;
  fontBody: string;
  grain?: number;
};

const SERIF =
  '"Noto Serif SC", "Source Han Serif SC", "Songti SC", "STSong", serif';
const SANS =
  '"Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Hiragino Sans GB", sans-serif';

export const THEMES: Record<string, Theme> = {
  desk: {
    id: "desk",
    bg: "#141210",
    bg2: "#1c1917",
    ink: "#f5f0e8",
    muted: "#a89f94",
    accent: "#c4a574",
    accentSoft: "rgba(196,165,116,.14)",
    surface: "rgba(255,248,240,.05)",
    line: "rgba(245,240,232,.12)",
    fontDisplay: SERIF,
    fontBody: SANS,
    grain: 0.04,
  },
  "paper-press": {
    id: "paper-press",
    bg: "#f2ebe0",
    bg2: "#e8efe9",
    ink: "#1a1612",
    muted: "#6a635a",
    accent: "#8b3a2a",
    accentSoft: "rgba(139,58,42,.08)",
    surface: "rgba(255,252,247,.55)",
    line: "rgba(26,22,18,.12)",
    fontDisplay: SERIF,
    fontBody: SANS,
    grain: 0.055,
  },
  "talent-map": {
    id: "talent-map",
    bg: "#f4f7f5",
    bg2: "#eef3f0",
    ink: "#12201c",
    muted: "#5a6862",
    accent: "#0b6e63",
    accentSoft: "rgba(11,110,99,.08)",
    surface: "rgba(255,255,255,.48)",
    line: "rgba(18,32,28,.10)",
    fontDisplay: SERIF,
    fontBody: SANS,
    grain: 0.045,
  },
  "terminal-green": {
    id: "terminal-green",
    bg: "#0c100e",
    bg2: "#121a16",
    ink: "#d8efe4",
    muted: "#7aa892",
    accent: "#3dba8b",
    accentSoft: "rgba(61,186,139,.10)",
    surface: "rgba(61,186,139,.06)",
    line: "rgba(216,239,228,.12)",
    fontDisplay: SERIF,
    fontBody: SANS,
    grain: 0.03,
  },
};

export function resolveTheme(id: string): Theme {
  return THEMES[id] || THEMES["talent-map"] || THEMES["paper-press"];
}
