








import { useEffect, useRef, useState, type ReactNode } from "react";
import { useStore } from "../store";
import { CyberspaceMonitorStrip } from "../components/CyberspaceProgress";
import { callPy } from "../bridge";
import { setMode, toggleMacro } from "../engine";
import { MacroModeToggle } from "../components/MacroModeToggle";
import { biomeMeta, RARE_KEYS, SEMI_RARE_KEYS } from "../data/biomes";
import { getMacroAccounts } from "../data/macroMode";
import { getEnabledMonitorModules } from "../monitorModules";
import type { Account, CyberspaceAccountProgress } from "../types";



const IMG_ROOT = "https://raw.githubusercontent.com/Finnerich/Boterich-Images/main/biome_images/";
const RARE_SET = new Set([...RARE_KEYS, ...SEMI_RARE_KEYS]);

function biomeImage(key: string): string {
  return IMG_ROOT + (key === "sandstorm" ? "SAND_STORM" : key.toUpperCase()) + ".png";
}

function biomeLabel(key: string | null | undefined): string {
  if (!key) return "No biome";
  if (key.startsWith("unknown:")) return key.slice(8);
  return biomeMeta(key)?.name || key.charAt(0).toUpperCase() + key.slice(1);
}

function biomeColor(key: string | null | undefined): string {
  return (key && biomeMeta(key)?.shadow) || "#7e8499";
}

function isRare(key: string | null | undefined): boolean {
  return !!key && RARE_SET.has(key);
}


function fmtClock(totalSeconds: number): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  return `${pad(hours)}:${pad(minutes)}:${pad(totalSeconds % 60)}`;
}


function fmtShort(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}


function fmtTime(unixSeconds: number): string {
  const date = new Date(unixSeconds * 1000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}



export function Monitor() {
  const accounts = useStore((s) => s.accounts);
  const settings = useStore((s) => s.settings);
  const cyberspace = useStore((s) => s.cyberspaceProgress);
  const [biomeDurations, setBiomeDurations] = useState<Record<string, number>>({});

  useEffect(() => {
    void callPy<Record<string, number>>("get_biome_durations")
      .then((durations) => { if (durations) setBiomeDurations(durations); })
      .catch(() => {});
  }, []);

  const trackedAccounts = getMacroAccounts(accounts, settings);
  const anyRare = trackedAccounts.some((account) => isRare(account.currentBiome));

  return (
    <section className={`tab active-tab monitor-tab${anyRare ? " mon-has-rare" : ""}`} id="monitor">
      <div className="mon-side">
        <EnginePanel />
        <SummaryPanel />
        <ActivityPanel />
        <FeedPanel />
      </div>
      <div className="mon-cards">
        {trackedAccounts.map((account, index) => (
          <BiomeCard
            key={account.id}
            account={account}
            usage={cyberspace?.accounts.find((row) => row.id === account.id)}
            durations={biomeDurations}
            index={index}
          />
        ))}
        {!trackedAccounts.length && (
          <div className="mon-empty glass">
            <i className="fa-solid fa-users-slash"></i>
            <span>No enabled accounts. Add one in the Accounts tab.</span>
          </div>
        )}
      </div>
    </section>
  );
}



const MODULE_LABELS: Record<string, string> = {
  biomeLogging: "Biome Logging", antiAfk: "Anti-AFK", strangeController: "Strange Controller",
  biomeRandomizer: "Biome Randomizer", fishing: "Fishing", merchantTeleporter: "Merchants",
  ramTrim: "RAM Trim", eden: "Eden", autopop: "Auto Pop", auraDetection: "Aura Detection",
};

const FISHING_PHASE_LABELS: Record<string, string> = {
  casting: "Casting the line", waiting: "Waiting for a bite",
  reeling: "Reeling it in", selling: "Selling the catch",
};

const MODE_OPTIONS = [
  { key: "idle", label: "Idle", icon: "fa-moon" },
  { key: "automation", label: "Auto", icon: "fa-robot" },
  { key: "eden", label: "Eden", icon: "fa-circle-dot" },
];



function UptimeClock() {
  const running = useStore((s) => s.engineSignal?.running ?? s.running);
  const uptime = useStore((s) => s.uptime);
  const simUptime = useStore((s) => s.engineSignal?.uptime);
  return (
    <div className={`topbar-time${running ? " live" : ""}`} title="Current session uptime">
      {running ? (
        <span className="time-live-dot" aria-hidden="true"></span>
      ) : (
        <i className="fa-solid fa-stopwatch topbar-time-icon"></i>
      )}
      <span className="time-value">{fmtClock(simUptime || uptime)}</span>
    </div>
  );
}


function TickDown({ seconds }: { seconds: number }) {
  const [secondsLeft, setSecondsLeft] = useState(seconds);
  useEffect(() => setSecondsLeft(seconds), [seconds]);
  useEffect(() => {
    const timer = setInterval(() => setSecondsLeft((value) => Math.max(0, value - 1)), 1000);
    return () => clearInterval(timer);
  }, []);
  return <>{fmtShort(secondsLeft)}</>;
}

function EnginePanel() {
  const storeRunning = useStore((s) => s.running);
  const signal = useStore((s) => s.engineSignal);
  const automation = useStore((s) => s.automation);
  const settings = useStore((s) => s.settings);
  const mode = (automation.mode as string) || "idle";
  const hotkey = useStore((s) => (s.settings.hotkey as string) || "F5");
  const cycle = useStore((s) => s.cycleStatus);
  const rotation = useStore((s) => s.fishingStatus.rotation);
  const activeModules = useStore((s) => (s.timeTracking?.activeModules as string[] | undefined));
  const accounts = useStore((s) => s.accounts);
  const macroAccounts = getMacroAccounts(accounts, settings);

  const running = signal?.running ?? storeRunning;
  const currentModule = signal?.module;
  const event = signal?.status?.event;
  const detail = signal?.status?.detail;
  const displayedModules = running
    ? getEnabledMonitorModules({
        activeModules,
        settings,
        automation,
        accounts: macroAccounts,
        currentModuleKey: currentModule?.key,
      })
    : [];

  
  let action = running ? "Nothing scheduled" : "Press Start to run modules";
  if (running && currentModule?.label) {
    action = currentModule.label;
    if (currentModule.key === "fishing" && currentModule.phase && FISHING_PHASE_LABELS[currentModule.phase]) {
      action += `: ${FISHING_PHASE_LABELS[currentModule.phase]}`;
    }
    if (currentModule.account) action += ` on ${currentModule.account}`;
  }
  const actionSub = event?.text || detail?.text || "";

  
  const accountName = (id: number | null) => macroAccounts.find((account) => account.id === id)?.name || "?";
  let nextTask: { label: string; remaining: number } | null = null;
  if (running && cycle?.enabled && cycle.type) {
    nextTask = { label: `Cycle: ${cycle.type} on ${accountName(cycle.accId)}`, remaining: cycle.remaining };
  } else if (running && rotation && rotation.accId != null && rotation.total > 1) {
    nextTask = { label: `Rotation: ${accountName(rotation.accId)}`, remaining: rotation.remaining };
  }

  return (
    <div className={`mon-panel mon-engine glass${running ? " live" : ""}`}>
      {}
      <button
        className={`mon-power ${storeRunning ? "running" : "stopped"}`}
        onClick={() => void toggleMacro()}
        title={storeRunning ? "Stop the engine" : "Start the engine"}
      >
        <i className={`fa-solid ${storeRunning ? "fa-stop" : "fa-play"}`}></i>
        <span>{storeRunning ? "Stop Engine" : "Start Engine"}</span>
        <span className="mon-power-key">{hotkey}</span>
      </button>

      {}
      <div
        className={`mode-seg mode-seg-3 mon-mode-seg ${mode === "automation" ? "auto" : mode}`}
        role="group"
        title="Switch run mode"
      >
        <span className="mode-seg-glider"></span>
        {MODE_OPTIONS.map((option) => (
          <button
            key={option.key}
            className={`mode-seg-opt${mode === option.key ? " active" : ""}`}
            data-mode={option.key}
            onClick={() => void setMode(option.key)}
          >
            <i className={`fa-solid ${option.icon}`}></i>
            <span>{option.label}</span>
          </button>
        ))}
      </div>

      <MacroModeToggle className="mon-mode-seg mon-macro-mode" />

      <div className="mon-eng-status">
        <span className={`dot ${running ? "running" : "stopped"}`}></span>
        <div className="mon-eng-lines">
          <span className="mon-eng-state">{running ? "Running" : "Offline"}</span>
          <span className="mon-eng-action">
            {action}
            {actionSub && <span className={`mon-eng-sub k-${event?.kind || "info"}`}> · {actionSub}</span>}
          </span>
          {nextTask && (
            <span className="mon-eng-next">
              Next: {nextTask.label} · <TickDown seconds={nextTask.remaining} />
            </span>
          )}
        </div>
      </div>

      {!!displayedModules.length && (
        <div className="mon-eng-mods">
          {displayedModules.map((moduleKey) => (
            <span key={moduleKey} className="mon-mod-pill">{MODULE_LABELS[moduleKey] || moduleKey}</span>
          ))}
        </div>
      )}

      <div className="mon-eng-clock">
        <UptimeClock />
      </div>
    </div>
  );
}




function Wall({ biome, phase }: { biome: string | null; phase: "in" | "out" }) {
  const [imageFailed, setImageFailed] = useState(false);
  const meta = biome ? biomeMeta(biome) : null;
  const known = !!biome && !biome.startsWith("unknown:");
  if (!biome || !known || imageFailed) {
    return (
      <div
        className={`mon-wall mon-wall-grad ${phase}`}
        style={{ background: meta?.grad || "linear-gradient(135deg,#2a2c38,#181920)" }}
      />
    );
  }
  return (
    <img
      className={`mon-wall mon-wall-img ${phase}`}
      src={biomeImage(biome)}
      alt=""
      draggable={false}
      onError={() => setImageFailed(true)}
    />
  );
}

function Thumb({ biome }: { biome: string }) {
  const [imageFailed, setImageFailed] = useState(false);
  if (imageFailed) return null;
  return (
    <img
      className="mon-thumb"
      src={biomeImage(biome)}
      alt=""
      draggable={false}
      onError={() => setImageFailed(true)}
    />
  );
}





function BiomeTimer({ since, duration }: { since: number | null | undefined; duration?: number }) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  if (!since) return null;

  const elapsed = Math.max(0, Math.floor(Date.now() / 1000 - since));
  
  
  let remaining = duration != null ? duration - elapsed : null;
  if (remaining != null && remaining < 0) remaining = null;

  const barPercent = duration && remaining != null
    ? Math.max(0, Math.min(100, (remaining / duration) * 100))
    : null;
  const almostOver = remaining != null && remaining <= 10;

  return (
    <>
      <div className="mon-card-clock">
        {remaining != null ? (
          <>
            <span className={`mon-clock-big${almostOver ? " low" : ""}`}>{fmtShort(remaining)}</span>
            <span className="mon-clock-sub">{fmtShort(elapsed)} elapsed</span>
          </>
        ) : (
          <>
            <span className="mon-clock-big">{fmtShort(elapsed)}</span>
            <span className="mon-clock-sub">elapsed</span>
          </>
        )}
      </div>
      {barPercent != null && (
        <div className="mon-card-bar-track">
          <div className={`mon-card-bar${almostOver ? " low" : ""}`} style={{ width: `${barPercent}%` }} />
        </div>
      )}
    </>
  );
}

function BiomeCard({ account, usage, durations, index }: {
  account: Account;
  usage?: CyberspaceAccountProgress;
  durations: Record<string, number>;
  index: number;
}) {
  const biomeKey = account.currentBiome && account.currentBiome !== "normal" ? account.currentBiome : null;
  const rare = isRare(biomeKey);
  const duration = biomeKey ? durations[biomeKey] : undefined;

  
  const lastBiome = useRef<string | null>(biomeKey);
  const [outgoingBiome, setOutgoingBiome] = useState<string | null>(null);
  useEffect(() => {
    if (lastBiome.current !== biomeKey) {
      setOutgoingBiome(lastBiome.current);
      lastBiome.current = biomeKey;
      const timer = setTimeout(() => setOutgoingBiome(null), 700);
      return () => clearTimeout(timer);
    }
  }, [biomeKey]);

  return (
    <div
      className={`mon-card${rare ? " rare" : ""}${account.online ? "" : " offline"}`}
      style={{ animationDelay: `${Math.min(index, 12) * 70}ms` }}
    >
      {outgoingBiome !== null && <Wall key={`out-${outgoingBiome}`} biome={outgoingBiome} phase="out" />}
      <Wall key={`in-${biomeKey}`} biome={biomeKey} phase="in" />
      <div className="mon-card-scrim" />
      <div className="mon-card-content">
        <div className="mon-card-info">
          <div className="mon-card-name" key={biomeKey || "none"}>{biomeLabel(biomeKey)}</div>
          <span className="mon-card-acc">
            <span className={`dot ${account.online ? "running" : "stopped"}`}></span>
            {account.name}
          </span>
          {usage && (
            <span className="mon-card-uses" title="Lifetime uses, with current-session uses in parentheses">
              SC <b>{usage.lifetime.strangeController.toLocaleString("en-US")}</b>
              <i>({usage.session.strangeController} session)</i>
              <em>·</em>
              BR <b>{usage.lifetime.biomeRandomizer.toLocaleString("en-US")}</b>
              <i>({usage.session.biomeRandomizer} session)</i>
            </span>
          )}
        </div>
        <BiomeTimer since={biomeKey ? account.biomeSince : null} duration={duration} />
      </div>
      {rare && <span className="mon-rare-tag">RARE</span>}
      {biomeKey && !biomeKey.startsWith("unknown:") && <Thumb biome={biomeKey} />}
    </div>
  );
}




function MinutesStat() {
  const uptime = useStore((s) => s.uptime);
  const simUptime = useStore((s) => s.engineSignal?.uptime);
  return <span className="mon-sum-v">{Math.floor((simUptime || uptime) / 60)}</span>;
}

function RollRate({ count }: { count: number }) {
  const uptime = useStore((s) => s.uptime);
  const simUptime = useStore((s) => s.engineSignal?.uptime);
  const seconds = simUptime || uptime;
  const rate = seconds >= 60 ? (count / (seconds / 60)).toFixed(2) : "0.00";
  return <span className="mon-sum-v">{rate}</span>;
}

function SummaryPanel() {
  const activity = useStore((s) => s.activity);
  const fishing = useStore((s) => s.fishingStatus);

  const biomeEntries = activity.filter((entry) => entry.kind === "biome");
  const rares = biomeEntries.filter((entry) => isRare(entry.biome)).length;
  const events = biomeEntries.filter((entry) => entry.biome && biomeMeta(entry.biome)?.tier === "event").length;
  
  
  const merchants = activity.filter((entry) => entry.text.startsWith("Merchant found")).length;
  const edens = activity.filter((entry) => entry.text.startsWith("Eden found")).length;

  const rows: Array<{ label: string; node: ReactNode }> = [
    { label: "Biomes", node: <span className="mon-sum-v">{biomeEntries.length}</span> },
    { label: "Rares", node: <span className="mon-sum-v">{rares}</span> },
    { label: "Events", node: <span className="mon-sum-v">{events}</span> },
    { label: "Edens", node: <span className="mon-sum-v">{edens}</span> },
    { label: "Merchants", node: <span className="mon-sum-v">{merchants}</span> },
    { label: "Fish", node: <span className="mon-sum-v">{fishing.caught}</span> },
    { label: "Minutes", node: <MinutesStat /> },
    { label: "Biomes / min", node: <RollRate count={biomeEntries.length} /> },
  ];

  return (
    <div className="mon-panel mon-summary glass">
      <div className="mon-panel-head"><i className="fa-solid fa-chart-simple"></i> Session</div>
      <div className="mon-sum-grid">
        {rows.map((row) => (
          <div className="mon-sum-cell" key={row.label}>
            {row.node}
            <span className="mon-sum-k">{row.label}</span>
          </div>
        ))}
      </div>
      <CyberspaceMonitorStrip />
    </div>
  );
}



const KIND_ICON: Record<string, string> = {
  good: "fa-circle-check", bad: "fa-circle-xmark",
  warn: "fa-triangle-exclamation", info: "fa-circle-info",
};

function ActivityPanel() {
  const activity = useStore((s) => s.activity);
  const entries = activity.filter((entry) => entry.kind !== "biome").slice(-80).reverse();
  return (
    <div className="mon-panel glass">
      <div className="mon-panel-head"><i className="fa-solid fa-list-ul"></i> Activity</div>
      <div className="mon-panel-body">
        {entries.map((entry) => (
          <div className={`mon-log-row k-${entry.kind}`} key={entry.id}>
            <span className="mon-log-time">{fmtTime(entry.ts)}</span>
            <i className={`fa-solid ${KIND_ICON[entry.kind] || KIND_ICON.info}`}></i>
            <span className="mon-log-text">
              {entry.text}
              {entry.account && <span className="mon-log-acc"> · {entry.account}</span>}
            </span>
          </div>
        ))}
        {!entries.length && <div className="mon-panel-empty">Session activity shows up here.</div>}
      </div>
    </div>
  );
}

function FeedPanel() {
  const activity = useStore((s) => s.activity);
  const entries = activity.filter((entry) => entry.kind === "biome").slice(-60).reverse();
  return (
    <div className="mon-panel glass">
      <div className="mon-panel-head"><i className="fa-solid fa-mountain-sun"></i> Biome Feed</div>
      <div className="mon-panel-body">
        {entries.map((entry) => (
          <div className={`mon-feed-row${isRare(entry.biome) ? " rare" : ""}`} key={entry.id}>
            <span className="mon-log-time">{fmtTime(entry.ts)}</span>
            <span className="mon-feed-acc">{entry.account || "?"}</span>
            <span className="mon-feed-arrow">→</span>
            <span className="mon-feed-biome" style={{ color: biomeColor(entry.biome) }}>
              {biomeLabel(entry.biome).toUpperCase()}
            </span>
          </div>
        ))}
        {!entries.length && <div className="mon-panel-empty">Biome changes show up here.</div>}
      </div>
    </div>
  );
}
