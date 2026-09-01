import { create } from "zustand";
import { useStore } from "./store";
import { toggleMacro, setMode } from "./engine";

export interface SearchItem {
  label: string;
  sub: string;
  icon: string;
  run: () => void;
}

const go = (tab: string) => () => useStore.getState().setCurrentTab(tab);

export const SEARCH_INDEX: SearchItem[] = [
  { label: "Home & Setup Checklist", sub: "Overview", icon: "fa-house", run: go("home") },
  { label: "Safety & Failsafes", sub: "Macro", icon: "fa-shield-halved", run: go("safety") },
  { label: "Stats & Time Tracking", sub: "Overview", icon: "fa-chart-simple", run: go("stats") },
  { label: "Module Builder", sub: "Macro", icon: "fa-cubes", run: go("modules") },
  { label: "Accounts", sub: "Setup", icon: "fa-users-gear", run: go("accounts") },
  { label: "Webhooks & Notifications", sub: "Setup", icon: "fa-tower-broadcast", run: go("webhooks") },
  { label: "Biome Logging", sub: "Module Builder", icon: "fa-satellite-dish", run: go("modules") },
  { label: "Merchant Detection", sub: "Module Builder", icon: "fa-store", run: go("modules") },
  { label: "Auto Pop", sub: "Module Builder", icon: "fa-wand-magic-sparkles", run: go("modules") },
  { label: "Fishing & Auto Sell", sub: "Module Builder", icon: "fa-fish", run: go("modules") },
  { label: "Anti-AFK", sub: "Module Builder", icon: "fa-person-running", run: go("modules") },
  { label: "Strange Controller", sub: "Module Builder", icon: "fa-gamepad", run: go("modules") },
  { label: "Biome Randomizer", sub: "Module Builder", icon: "fa-shuffle", run: go("modules") },
  { label: "Window Binding", sub: "Module Builder", icon: "fa-link", run: go("modules") },
  { label: "Calibration & OCR", sub: "Macro", icon: "fa-crosshairs", run: go("calibration") },
  { label: "Performance Monitor", sub: "System", icon: "fa-gauge-high", run: go("performance") },
  { label: "Patchlog", sub: "System", icon: "fa-clock-rotate-left", run: go("patchlog") },
  { label: "Settings", sub: "System", icon: "fa-sliders", run: go("settings") },

  { label: "Start Engine", sub: "Action", icon: "fa-power-off", run: () => { if (!useStore.getState().running) void toggleMacro(); } },
  { label: "Stop Engine", sub: "Action", icon: "fa-power-off", run: () => { if (useStore.getState().running) void toggleMacro(); } },
  { label: "Switch to Idle mode", sub: "Action", icon: "fa-moon", run: () => void setMode("idle") },
  { label: "Switch to Automation mode", sub: "Action", icon: "fa-robot", run: () => void setMode("automation") },

  { label: "Accent color", sub: "Settings", icon: "fa-palette", run: go("settings") },
  { label: "Theme / Background", sub: "Settings", icon: "fa-image", run: go("settings") },
  { label: "Start/Stop hotkey", sub: "Settings", icon: "fa-keyboard", run: go("settings") },
  { label: "OCR Failsafe", sub: "Module Builder", icon: "fa-eye", run: go("modules") },
  { label: "Resolution preset", sub: "Calibration", icon: "fa-crosshairs", run: go("calibration") },
];

function score(item: SearchItem, q: string): number {
  const haystack = (item.label + " " + (item.sub || "")).toLowerCase();
  const needle = q.toLowerCase();
  if (haystack.startsWith(needle)) return 3;
  if (item.label.toLowerCase().includes(needle)) return 2;
  if (haystack.includes(needle)) return 1;
  let hi = 0;
  for (const ch of needle) {
    hi = haystack.indexOf(ch, hi);
    if (hi === -1) return 0;
    hi++;
  }
  return 0.5;
}

interface SearchState {
  open: boolean;
  query: string;
  idx: number;
  results: SearchItem[];
  setQuery: (q: string) => void;
  openSearch: () => void;
  closeSearch: () => void;
  setIdx: (i: number) => void;
  move: (d: number) => void;
  pick: (i?: number) => void;
}

export const useSearch = create<SearchState>((set, get) => ({
  open: false,
  query: "",
  idx: -1,
  results: [],
  setQuery: (q) => {
    const t = q.trim();
    if (!t) {
      set({ query: q, results: [], idx: -1 });
      return;
    }
    const accounts = (useStore.getState().accounts as { name: string }[]).map((a) => ({
      label: a.name, sub: "Account", icon: "fa-user", run: go("accounts"),
    }));
    const pool = [...SEARCH_INDEX, ...accounts];
    const results = pool
      .map((item) => ({ item, s: score(item, t) }))
      .filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s)
      .slice(0, 8)
      .map((x) => x.item);
    set({ query: q, results, idx: results.length ? 0 : -1 });
  },
  openSearch: () => set({ open: true }),
  closeSearch: () => set({ open: false, query: "", results: [], idx: -1 }),
  setIdx: (i) => set({ idx: i }),
  move: (d) => set((st) => ({ idx: Math.max(0, Math.min(st.results.length - 1, st.idx + d)) })),
  pick: (i) => {
    const st = get();
    const idx = i ?? st.idx;
    const item = st.results[idx];
    if (item) {
      item.run();
      get().closeSearch();
    }
  },
}));
