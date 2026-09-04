export interface AppSettings {
  hotkey?: string;
  modeHotkey?: string;
  macroMode?: "multi" | "normal";
  normalAccountId?: number | null;
  antiAfkEnabled?: boolean;
  antiAfkAction?: "space" | "zoom";
  antiAfkInterval?: number;
  antiAfkStandalone?: boolean;
  ramTrimEnabled?: boolean;
  ramTrimInterval?: number;
  slowReset?: boolean;
  fakePingGuard?: boolean;
  fakePingPrompt?: boolean;
  auraPushNotify?: boolean;
  auraMinimumRarity?: string;
  auraAlwaysSendNames?: string;
  auraPingUserId?: string;
  auraPingMinimumRarity?: string;
  auraAlwaysPingNames?: string;
  clippingEnabled?: boolean;
  clipHotkey?: string;
  clipBiomes?: string[];
  clipBiomeDelay?: string;
  clipAuraMinimumRarity?: string;
  clipAuraNames?: string;
  clipAuraDelay?: string;
  monitorDimEnabled?: boolean;
  monitorDimLevel?: number;
  windowsNotificationsEnabled?: boolean;
  windowsNotifyBiomes?: boolean;
  windowsNotifyDisconnects?: boolean;
  windowsNotifyAuras?: boolean;
  windowsNotifyBiomeHealth?: boolean;
  windowsAuraMinimumRarity?: string;
  biomeHealthMonitorEnabled?: boolean;
  biomeHealthTimeoutMinutes?: number;
  tesseractPromptDismissed?: boolean;
  [key: string]: unknown;
}


export interface FishingAccCfg {
  autoSell?: boolean;
  sellAfter?: number;
  sellCycle?: number;
  route?: string;
  primeRoute?: boolean;
  sellOnStart?: boolean;
}

export interface CalibGroup {
  pixels?: Record<string, unknown>;
  regions?: Record<string, unknown>;
}

export interface Automation {
  mode?: string;
  fishing?: {
    account?: number | null;
    enabled?: boolean;
    schedule?: Array<{ accId: number | null; minutes: number }>;
    webhookEnabled?: boolean;
    accounts?: Record<string, FishingAccCfg>;
    pixels?: Record<string, unknown>;
  };
  cycle?: {
    enabled?: boolean;
    steps?: CycleStep[];
    limbo?: { accounts?: Record<string, LimboAccountEntry> };
  };
  autopop?: {
    accounts?: Record<string, AutopopAccountEntry>;
    presets?: Record<string, unknown>;
    activePreset?: string;
    ocrFailsafe?: boolean;
    amountRegion?: number[] | null;
    notifyUse?: boolean;
    notifyFail?: boolean;
    leaveLimboOnRareBiome?: boolean;
  };
  merchants?: {
    calib?: Record<string, CalibGroup>;
    autobuy?: { accounts?: Record<string, Record<string, unknown>> };
    buyLog?: unknown[];
  };
  eden?: { account?: number | null; edenWatch?: boolean; edenInterval?: number };
  calib?: Record<string, CalibGroup>;
  notifications?: Record<string, boolean>;
  intervals?: Record<string, number>;
  ocrFailsafe?: Record<string, boolean>;
  pixels?: Record<string, unknown>;
  firstItemRegion?: number[] | null;
  biomePings?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface CycleStep {
  type: "fishing" | "switchNormal" | "limboEden";
  accId: number;
  minutes?: number;
  afk?: boolean;
}

export interface LimboAccountEntry {
  path?: string;
  edenWatch?: boolean;
  edenInterval?: number;
}

export interface EdenStats {
  count: number;
  lastFound: string;
  log?: string[];
  accountSeconds?: Record<string, number>;
}

export interface CycleStatus {
  type: "fishing" | "switchNormal" | "limboEden" | null;
  accId: number | null;
  remaining: number;
  index: number;
  total: number;
  enabled?: boolean;
}

export interface Account {
  id: number;
  name: string;
  link?: string;
  avatar?: string;
  enabled?: boolean;
  modules?: {
    strangeController?: boolean;
    biomeRandomizer?: boolean;
    merchantTeleporter?: boolean;
    auraDetection?: boolean;
    fishing?: boolean;
  };
  hasToken?: boolean;
  tokenUser?: string;
  tokenValid?: boolean;
  currentBiome?: string | null;
  biomeSince?: number | null;
  online?: boolean;
  window?: string | null;
  hwndKnown?: boolean;
}

export interface ActivityEntry {
  id: number;
  ts: number;
  text: string;
  kind: string;
  account?: string | null;
  biome?: string | null;
}

export interface Webhook {
  id?: number;
  name?: string;
  url?: string;
  active?: boolean;
  routedAccounts?: number[];
  [key: string]: unknown;
}

export interface AutopopAccountEntry {
  enabled?: boolean;
  biomes?: Record<string, { enabled?: boolean; items?: Array<{ name: string; amount: number; all?: boolean }> }>;
}

export interface TimeTracking {
  totalEngine?: number;
  idle?: number;
  automation?: number;
  modules?: Record<string, number>;
  sessions?: number;
  longestSession?: number;
  firstStart?: string;
  activeMode?: string;
  activeModules?: string[];
  fishCaught?: number;
  [key: string]: unknown;
}

export interface TimelineEntry extends ActivityEntry {
  accountId?: number | null;
  category: "biome" | "aura" | "clip" | "connection" | "fishing" | "merchant" | "action" | "system" | string;
  decision?: DecisionTrace;
}

export interface DecisionTrace {
  status: "acted" | "skipped" | "blocked" | "waiting" | "cancelled" | "failed";
  reasonCode?: string;
  module?: string;
  summary: string;
  checks?: Array<{ label: string; state: "pass" | "fail" | "info"; detail?: string }>;
  facts?: Array<{ label: string; value: string }>;
  nextStep?: { label: string; tab: string; anchor?: string; drawer?: string; accountId?: number };
}

export interface ModuleUseCounts {
  strangeController: number;
  biomeRandomizer: number;
  combined: number;
}

export interface CyberspaceAccountProgress {
  id: number;
  name: string;
  avatar?: string;
  enabled: boolean;
  active: boolean;
  modules: {
    strangeController: boolean;
    biomeRandomizer: boolean;
  };
  lifetime: Omit<ModuleUseCounts, "combined">;
  session: Omit<ModuleUseCounts, "combined">;
  combinedLifetime: number;
  combinedSession: number;
  usesPerHour: number;
}

export interface CyberspaceProgress {
  odds: number;
  cyberspaceCount: number;
  lifetime: ModuleUseCounts;
  unattributed: ModuleUseCounts;
  session: ModuleUseCounts;
  sinceLast: ModuleUseCounts;
  estimatedRemaining: number;
  averageCycleOverdue: number;
  progressPercent: number;
  chanceSinceLastPercent: number;
  etaSeconds: number | null;
  etaMode: "averageCycle" | "fromNow";
  usesPerHour: number;
  activeAccounts: number;
  activeSources: number;
  intervals: {
    strangeController: number;
    biomeRandomizer: number;
  };
  accounts: CyberspaceAccountProgress[];
  lastCyberspace: string;
  lastCyberspaceAccount: number | null;
  trackingSince: string;
  anchorReason: "trackingStart" | "cyberspace" | "statsReset" | "migration";
  sessionCyberspaces: number;
  accurateSinceLastCyberspace: boolean;
}

export interface BackendState {
  running?: boolean;
  uptime?: number;
  version?: string;
  settings?: AppSettings;
  automation?: Automation;
  accounts?: Account[];
  webhooks?: Webhook[];
  biomeCounts?: Record<string, number>;
  moduleCounts?: Record<string, number>;
  cyberspaceProgress?: CyberspaceProgress;
  unknownBiomes?: Record<string, number>;
  merchantCounts?: Record<string, number>;
  edenStats?: EdenStats;
  configRecovery?: {
    status?: "backup" | "unrecoverable";
    preservedFile?: string | null;
  } | null;
  [key: string]: unknown;
}

export interface StatusPayload {
  running?: boolean;
  uptime?: number;
  biomeCounts?: Record<string, number>;
  moduleCounts?: Record<string, number>;
  cyberspaceProgress?: CyberspaceProgress;
  unknownBiomes?: Record<string, number>;
  merchantCounts?: Record<string, number>;
  edenStats?: EdenStats;
  timeTracking?: Record<string, unknown>;
  fishing?: { caught: number; sinceSell: number; sells: number };
  cycle?: CycleStatus;
  accountStates?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}
