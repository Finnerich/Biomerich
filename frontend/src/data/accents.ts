export interface Accent {
  c: string; c2: string; bg0: string; bg1: string;
  bodyGrad: string; loaderGrad: string;
  glass: string; glassSoft: string; glassStrong: string;
  stroke: string; strokeSoft: string; highlight: string;
}


const SURFACES = {
  bg0: "#101116",
  bg1: "#15161c",
  bodyGrad: "#101116",
  loaderGrad: "#101116",
  glass: "#16171e",
  glassSoft: "#191a22",
  glassStrong: "#131419",
  stroke: "rgba(255, 255, 255, 0.08)",
  strokeSoft: "rgba(255, 255, 255, 0.05)",
  highlight: "rgba(255, 255, 255, 0.04)",
};

export const ACCENTS: Accent[] = [
  { c: "#6d84eb", c2: "#5568cf", ...SURFACES },
  { c: "#38c5dd", c2: "#2ba5bb", ...SURFACES },
  { c: "#3ecf8e", c2: "#2fae76", ...SURFACES },
  { c: "#ee6a7c", c2: "#d44d60", ...SURFACES },
  { c: "#e8a33d", c2: "#c9862a", ...SURFACES },
  { c: "#e072b4", c2: "#c25397", ...SURFACES },
  { c: "#a184ef", c2: "#8767d6", ...SURFACES },
  { c: "#d3d7e0", c2: "#9aa1af", ...SURFACES },
  { c: "#4e63ec", c2: "#3a4bd0", ...SURFACES },
];

function hexToRgb(hex: string) {
  const n = parseInt(hex.slice(1), 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}
function hexToGlow(hex: string) {
  const { r, g, b } = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, 0.16)`;
}

export function applyAccentObject(a: Accent): void {
  const root = document.documentElement.style;
  const rgb1 = hexToRgb(a.c), rgb2 = hexToRgb(a.c2);
  const set = (k: string, v: string | number) => root.setProperty(k, String(v));

  set("--accent", a.c);
  set("--accent-2", a.c2);
  set("--accent-glow", hexToGlow(a.c));
  set("--ar", rgb1.r); set("--ag", rgb1.g); set("--ab", rgb1.b);
  set("--a2r", rgb2.r); set("--a2g", rgb2.g); set("--a2b", rgb2.b);
  set("--orb-1-r", rgb1.r); set("--orb-1-g", rgb1.g); set("--orb-1-b", rgb1.b);
  set("--orb-2-r", rgb2.r); set("--orb-2-g", rgb2.g); set("--orb-2-b", rgb2.b);
  set("--bg-0", a.bg0);
  set("--bg-1", a.bg1);
  set("--body-grad", a.bodyGrad);
  set("--loader-grad", a.loaderGrad);
  set("--glass", a.glass);
  set("--glass-soft", a.glassSoft);
  set("--glass-strong", a.glassStrong);
  set("--stroke", a.stroke);
  set("--stroke-soft", a.strokeSoft);
  set("--highlight", a.highlight);
}

export function applyAccent(index: number): void {
  applyAccentObject(ACCENTS[index] || ACCENTS[0]);
}

export function getAccentIndex(settingsIndex?: unknown): number {
  const fromSettings = parseInt(String(settingsIndex ?? -1), 10);
  if (!isNaN(fromSettings) && fromSettings >= 0 && fromSettings < ACCENTS.length) return fromSettings;
  const fromLs = parseInt(localStorage.getItem("accentIndex") || "0", 10);
  return !isNaN(fromLs) && fromLs >= 0 && fromLs < ACCENTS.length ? fromLs : 0;
}
