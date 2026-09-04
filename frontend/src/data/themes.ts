import type { Accent } from "./accents";
import { applyAccent, applyAccentObject, getAccentIndex } from "./accents";
import { applyNavAnim } from "../components/ThemeCanvas";
import { useStore } from "../store";
import { callPy } from "../bridge";

export interface Theme {
  id: string;
  name: string;
  image: string | null;
  anim: string;
  overlay: number;
  blur: number;
  lock?: { anim: string; navAnim?: string; accent: Accent };
}

export const THEMES: Theme[] = [
  { id: "none", name: "None", image: null, anim: "none", overlay: 0, blur: 0 },
  { id: "custom", name: "Custom", image: null, anim: "drift", overlay: 0.52, blur: 1 },
  { id: "nebula", name: "Nebula", image: "assets/themes/nebula.jpg", anim: "kenburns", overlay: 0.58, blur: 2 },
  { id: "aurora", name: "Aurora", image: "assets/themes/aurora.jpg", anim: "drift", overlay: 0.52, blur: 1 },
  {
    id: "slavic", name: "Slavic", image: "assets/themes/slavic.jpg", anim: "drift", overlay: 0.6, blur: 1,
    lock: { anim: "stardust", accent: { c: "#ff4d4d", c2: "#e0102e", bg0: "#0d0405", bg1: "#160708", bodyGrad: "linear-gradient(145deg,#1c080a 0%,#170609 40%,#150508 100%)", loaderGrad: "linear-gradient(155deg,#160708 0%,#100406 100%)", glass: "rgba(26,9,11,0.96)", glassSoft: "rgba(22,7,9,0.92)", glassStrong: "rgba(16,5,7,0.98)", stroke: "rgba(255,77,77,0.14)", strokeSoft: "rgba(255,77,77,0.08)", highlight: "rgba(255,77,77,0.06)" } },
  },
  { id: "fuh", name: "Fuh", image: "assets/themes/fuh.jpg", anim: "drift", overlay: 0.52, blur: 1 },
  { id: "mr_car", name: "Mr. Car", image: "assets/themes/mr_car.jpg", anim: "drift", overlay: 0.52, blur: 1 },
];

let customThemeImage = "";

export function setCustomThemeImage(dataUrl: string): void {
  customThemeImage = String(dataUrl || "");
}

export function getCustomThemeImage(): string {
  return customThemeImage;
}

export async function loadCustomThemeImage(): Promise<string> {
  const result = await callPy<{ ok?: boolean; available?: boolean; dataUrl?: string }>("get_custom_theme_background").catch(() => null);
  customThemeImage = result?.ok && result.available ? String(result.dataUrl || "") : "";
  if (getCurrentThemeId(useStore.getState().settings.themeId) === "custom") {
    applyTheme("custom", false);
  }
  return customThemeImage;
}

function ensureThemeBg(): HTMLElement {
  let el = document.getElementById("themeBg");
  if (!el) {
    el = document.createElement("div");
    el.id = "themeBg";
    document.body.insertBefore(el, document.body.firstChild);
  }
  return el;
}

export function getCurrentThemeId(settingsThemeId?: unknown): string {
  if (settingsThemeId) return String(settingsThemeId);
  return localStorage.getItem("themeId") || "none";
}

export function applyTheme(id: string, persist: boolean): void {
  const theme = THEMES.find((t) => t.id === id) || THEMES[0];
  const image = theme.id === "custom" ? customThemeImage : theme.image;
  const el = ensureThemeBg();
  el.className = "theme-anim-" + (theme.anim || "none");

  if (!image) {
    el.style.opacity = "0";
    el.style.backgroundImage = "";
  } else {
    const ov = theme.overlay == null ? 0.5 : theme.overlay;
    const ov2 = Math.min(0.92, ov + 0.18);
    el.style.backgroundImage = `linear-gradient(rgba(6,6,12,${ov}), rgba(6,6,12,${ov2})), url("${image}")`;
    el.style.filter = theme.blur ? `blur(${theme.blur}px)` : "";
    el.style.opacity = "1";
  }

  THEMES.forEach((t) => {
    if (t.id !== "none") document.body.classList.toggle("theme-" + t.id, t.id === id);
  });

  const st = useStore.getState();
  if (persist) {
    void callPy("set_setting", "themeId", id);
    localStorage.setItem("themeId", id);
    st.patchSettings({ themeId: id });
  }

  if (theme.lock) {
    applyAccentObject(theme.lock.accent);
    const nav = theme.lock.navAnim ?? "none";
    document.body.classList.add("theme-locked");
    applyNavAnim(nav);
    st.setTheme(id, { name: theme.name, anim: theme.lock.anim, nav });
  } else {
    applyAccent(getAccentIndex(st.settings.accentIndex));
    document.body.classList.remove("theme-locked");
    applyNavAnim((st.settings.navAnim as string) || localStorage.getItem("navAnim") || "none");
    st.setTheme(id, null);
  }
}
