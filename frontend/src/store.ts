import { create } from "zustand";
import type { Account, ActivityEntry, AppSettings, Automation, BackendState, CyberspaceProgress, CycleStatus, EdenStats, StatusPayload, TimeTracking, Webhook } from "./types";

export interface EngineSignal {
  module?: { key?: string; label?: string; phase?: string; account?: string };
  status?: {
    detail?: { text?: string; elapsed?: number } | null;
    event?: { id?: number; text?: string; kind?: string; remaining?: number | null } | null;
  };
  uptime?: number;
  running?: boolean;
}
export interface Streak {
  count: number;
  previous: number;
  advanced: boolean;
}
export interface Toast {
  id: number;
  icon: string;
  title: string;
  detail?: string;
}
export interface RarePingWarning {
  id: string;
  account?: string;
  pingTarget?: string;
  test?: boolean;
}
export interface BiomeHealthWarning {
  id: string;
  accountId: number;
  account: string;
  silentMinutes: number;
}
export interface Release {
  tag: string;
  name: string;
  prerelease?: boolean;
  publishedAt?: string;
  body?: string;
  url?: string;
  unstable?: boolean;
  channel?: string;
  exeUrl?: string | null;
  exeName?: string | null;
  exeSize?: number;
  assets?: Array<{ name: string; url: string; size: number }>;
}
export interface Releases {
  available?: boolean;
  current?: string;
  latest?: string;
  releases?: Release[];
  error?: string;
}

interface Store {
  running: boolean;
  uptime: number;
  version: string;
  settings: AppSettings;
  automation: Automation;
  accounts: Account[];
  webhooks: Webhook[];

  biomeCounts: Record<string, number>;
  unknownBiomes: Record<string, number>;
  merchantCounts: Record<string, number>;
  moduleCounts: Record<string, number>;
  cyberspaceProgress: CyberspaceProgress | null;
  edenStats: EdenStats;
  cycleStatus: CycleStatus;
  timeTracking: TimeTracking | null;
  setTimeTracking: (tt: TimeTracking | null) => void;
  tickTimeTracking: () => void;
  fishingStatus: {
    caught: number;
    sinceSell: number;
    sells: number;
    rotation?: { accId: number | null; remaining: number; index: number; total: number };
  };

  bindStates: Record<number, "waiting" | "bound">;
  bindingAccId: number | null;
  setBind: (accId: number, state: "waiting" | "bound" | null) => void;
  setBindingAccId: (id: number | null) => void;
  handleBindResult: (accId: number, success: boolean) => void;


  ocrAvailable: boolean | null;
  setOcrAvailable: (v: boolean | null) => void;

  pluginTabs: Array<{ id: string; name: string; icon: string; tabTitle: string; body: string }>;
  setPluginTabs: (tabs: Store["pluginTabs"]) => void;

  allowedPlugins: string[];
  hwid: string;
  setPluginAccess: (allowed: string[], hwid: string) => void;

  releases: Releases | null;
  setReleases: (r: Releases | null) => void;
  updateModalOpen: boolean;
  setUpdateModalOpen: (v: boolean) => void;

  loading: boolean;
  loaderStatus: string;
  setLoading: (v: boolean) => void;
  setLoaderStatus: (s: string) => void;

  themeId: string;
  themeLock: { name: string; anim: string; nav: string } | null;
  setTheme: (id: string, lock: { name: string; anim: string; nav: string } | null) => void;

  engineSignal: EngineSignal | null;
  setEngineSignal: (s: EngineSignal | null) => void;

  
  activity: ActivityEntry[];
  appendActivity: (entries: ActivityEntry[]) => void;
  clearActivity: () => void;

  streak: Streak | null;
  setStreak: (s: Streak | null) => void;

  toasts: Toast[];
  pushToast: (t: Omit<Toast, "id">) => void;
  dismissToast: (id: number) => void;

  currentTab: string;
  setCurrentTab: (tab: string) => void;
  rarePingWarnings: RarePingWarning[];
  pushRarePingWarning: (warning: RarePingWarning) => void;
  dismissRarePingWarning: (id: string) => void;
  biomeHealthWarnings: BiomeHealthWarning[];
  pushBiomeHealthWarning: (warning: BiomeHealthWarning) => void;
  dismissBiomeHealthWarning: (accountId: number) => void;
  
  
  tutorialDrawer: { kind: string; accId?: number } | null;
  setTutorialDrawer: (d: { kind: string; accId?: number } | null) => void;

  applyState: (s: BackendState | null | undefined) => void;
  patchSettings: (patch: Partial<AppSettings>) => void;

  setRunning: (running: boolean, uptime?: number) => void;
  setUptime: (seconds: number) => void;
  setAutomationMode: (mode: string) => void;
  applyStatus: (s: StatusPayload | null | undefined) => void;
  applyAccountWindows: (states: Array<Record<string, unknown>>) => void;

  patchWebhook: (id: number, patch: Record<string, unknown>) => void;
  patchAutomation: (patch: Partial<Automation>) => void;
}

let toastSeq = 0;

export const useStore = create<Store>((set) => ({
  running: false,
  uptime: 0,
  version: "",
  settings: {},
  automation: {},
  accounts: [],
  webhooks: [],

  biomeCounts: {},
  unknownBiomes: {},
  merchantCounts: {},
  moduleCounts: {},
  cyberspaceProgress: null,
  edenStats: { count: 0, lastFound: "", log: [] },
  cycleStatus: { type: null, accId: null, remaining: 0, index: -1, total: 0, enabled: false },
  timeTracking: null,
  setTimeTracking: (tt) => set({ timeTracking: tt }),
  tickTimeTracking: () =>
    set((st) => {
      const tt = st.timeTracking;
      if (!tt || !st.running) return {};
      const next: TimeTracking = { ...tt };
      next.totalEngine = (Number(next.totalEngine) || 0) + 1;
      const mode = next.activeMode || (st.automation.mode as string) || "idle";
      if (mode === "automation") next.automation = (Number(next.automation) || 0) + 1;
      else next.idle = (Number(next.idle) || 0) + 1;
      const mods = { ...(next.modules || {}) };
      (next.activeModules || []).forEach((k) => { mods[k] = (Number(mods[k]) || 0) + 1; });
      next.modules = mods;
      return { timeTracking: next };
    }),
  fishingStatus: { caught: 0, sinceSell: 0, sells: 0 },

  bindStates: {},
  bindingAccId: null,
  setBind: (accId, state) =>
    set((st) => {
      const next = { ...st.bindStates };
      if (state === null) delete next[accId];
      else next[accId] = state;
      return { bindStates: next };
    }),
  setBindingAccId: (id) => set({ bindingAccId: id }),
  handleBindResult: (accId, success) =>
    set((st) => {
      if (st.bindingAccId !== null && st.bindingAccId !== accId) return {};
      const next = { ...st.bindStates };
      if (success) next[accId] = "bound";
      else if (next[accId] !== "bound") delete next[accId];
      return { bindStates: next, bindingAccId: null };
    }),


  ocrAvailable: null,
  setOcrAvailable: (v) => set({ ocrAvailable: v }),

  pluginTabs: [],
  setPluginTabs: (tabs) => set({ pluginTabs: tabs }),

  allowedPlugins: [],
  hwid: "",
  setPluginAccess: (allowed, hwid) => set({ allowedPlugins: allowed, hwid }),

  releases: null,
  setReleases: (r) => set({ releases: r }),
  updateModalOpen: false,
  setUpdateModalOpen: (v) => set({ updateModalOpen: v }),

  loading: true,
  loaderStatus: "Initializing…",
  setLoading: (v) => set({ loading: v }),
  setLoaderStatus: (s) => set({ loaderStatus: s }),

  themeId: "none",
  themeLock: null,
  setTheme: (id, lock) => set({ themeId: id, themeLock: lock }),

  engineSignal: null,
  setEngineSignal: (s) => set((st) => ({ engineSignal: keepIfEqual(st.engineSignal, s) })),

  activity: [],
  appendActivity: (entries) =>
    set((st) => (entries.length ? { activity: [...st.activity, ...entries].slice(-500) } : {})),
  clearActivity: () => set({ activity: [] }),
  streak: null,
  setStreak: (s) => set({ streak: s }),

  toasts: [],
  pushToast: (t) =>
    set((st) => ({ toasts: [...st.toasts, { ...t, id: ++toastSeq }] })),
  dismissToast: (id) =>
    set((st) => ({ toasts: st.toasts.filter((x) => x.id !== id) })),

  currentTab: "home",
  setCurrentTab: (tab) => set({ currentTab: tab }),
  rarePingWarnings: [],
  pushRarePingWarning: (warning) =>
    set((st) => st.rarePingWarnings.some((item) => item.id === warning.id)
      ? {}
      : { rarePingWarnings: [...st.rarePingWarnings, warning] }),
  dismissRarePingWarning: (id) =>
    set((st) => ({ rarePingWarnings: st.rarePingWarnings.filter((item) => item.id !== id) })),
  biomeHealthWarnings: [],
  pushBiomeHealthWarning: (warning) =>
    set((st) => ({
      biomeHealthWarnings: [
        ...st.biomeHealthWarnings.filter((item) => item.accountId !== warning.accountId),
        warning,
      ],
    })),
  dismissBiomeHealthWarning: (accountId) =>
    set((st) => ({
      biomeHealthWarnings: st.biomeHealthWarnings.filter((item) => item.accountId !== accountId),
    })),
  tutorialDrawer: null,
  setTutorialDrawer: (d) => set({ tutorialDrawer: d }),

  applyState: (s) => {
    if (!s) return;
    set((st) => ({
      running: !!s.running,
      uptime: s.uptime ?? 0,
      version: s.version ?? st.version,
      settings: s.settings ?? st.settings,
      automation: s.automation ?? st.automation,
      accounts: Array.isArray(s.accounts) ? preserveAccountLiveFields(s.accounts, st.accounts) : st.accounts,
      webhooks: Array.isArray(s.webhooks) ? s.webhooks : st.webhooks,
      biomeCounts: s.biomeCounts ?? st.biomeCounts,
      unknownBiomes: s.unknownBiomes ?? st.unknownBiomes,
      merchantCounts: s.merchantCounts ?? st.merchantCounts,
      moduleCounts: s.moduleCounts ?? st.moduleCounts,
      cyberspaceProgress: s.cyberspaceProgress ?? st.cyberspaceProgress,
      edenStats: (s as BackendState).edenStats ?? st.edenStats,
    }));
  },

  patchSettings: (patch) =>
    set((st) => ({ settings: { ...st.settings, ...patch } })),

  setRunning: (running, uptime = 0) => set({ running, uptime: running ? uptime : 0 }),
  setUptime: (seconds) => set({ uptime: seconds }),
  setAutomationMode: (mode) =>
    set((st) => ({ automation: { ...st.automation, mode } })),

  applyStatus: (s) => {
    if (!s) return;
    set((st) => ({
      biomeCounts: keepIfEqual(st.biomeCounts, s.biomeCounts),
      unknownBiomes: keepIfEqual(st.unknownBiomes, s.unknownBiomes),
      merchantCounts: keepIfEqual(st.merchantCounts, s.merchantCounts),
      moduleCounts: keepIfEqual(st.moduleCounts, s.moduleCounts),
      cyberspaceProgress: keepIfEqual(st.cyberspaceProgress, s.cyberspaceProgress),
      timeTracking: s.timeTracking ?? st.timeTracking,
      fishingStatus: keepIfEqual(st.fishingStatus, s.fishing as Store["fishingStatus"] | undefined),
      edenStats: keepIfEqual(st.edenStats, s.edenStats),
      cycleStatus: keepIfEqual(st.cycleStatus, s.cycle),
      accounts: Array.isArray(s.accountStates) ? mergeAccountStates(st.accounts, s.accountStates) : st.accounts,
    }));
  },

  applyAccountWindows: (states) =>
    set((st) => ({
      accounts: Array.isArray(states) ? mergeAccountStates(st.accounts, states) : st.accounts,
    })),

  patchWebhook: (id, patch) =>
    set((st) => ({
      webhooks: st.webhooks.map((w) =>
        (w as Record<string, unknown>).id === id ? { ...(w as object), ...patch } : w,
      ),
    })),
  patchAutomation: (patch) => set((st) => ({ automation: { ...st.automation, ...patch } })),
}));




function keepIfEqual<T>(prev: T, next: T | undefined): T {
  if (next === undefined) return prev;
  if (prev === next) return next;
  try {
    return JSON.stringify(prev) === JSON.stringify(next) ? prev : next;
  } catch {
    return next;
  }
}

function preserveAccountLiveFields(next: Account[], prev: Account[]): Account[] {
  const prevById = new Map(prev.map((a) => [a.id, a]));
  return next.map((a) => {
    const old = prevById.get(a.id);
    if (!old) return a;
    return {
      ...a,
      currentBiome: old.currentBiome ?? null,
      biomeSince: old.biomeSince ?? null,
      online: !!old.online,
      window: old.window ?? null,
      hwndKnown: !!old.hwndKnown,
    };
  });
}

function mergeAccountStates(
  accounts: Account[],
  states: Array<Record<string, unknown>>,
): Account[] {
  const byId = new Map(states.map((s) => [s.id, s]));
  
  
  
  let changed = false;
  const next = accounts.map((acc) => {
    const st = byId.get(acc.id);
    const currentBiome = (st ? (st.currentBiome ?? null) : null) as string | null;
    const biomeSince = (st ? (st.biomeSince ?? null) : null) as number | null;
    const online = !!(st && st.online);
    const windowName = (st ? (st.window ?? null) : null) as string | null;
    const hwndKnown = !!(st && st.hwndKnown);
    if (
      (acc.currentBiome ?? null) === currentBiome &&
      (acc.biomeSince ?? null) === biomeSince &&
      !!acc.online === online &&
      (acc.window ?? null) === windowName &&
      !!acc.hwndKnown === hwndKnown
    ) {
      return acc;
    }
    changed = true;
    return { ...acc, currentBiome, biomeSince, online, window: windowName, hwndKnown };
  });
  return changed ? next : accounts;
}
